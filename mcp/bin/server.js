#!/usr/bin/env node
"use strict";

/**
 * safecheck-mcp: an MCP (Model Context Protocol) server exposing
 * PackageSafe's scanning as tools an AI agent can call directly, instead
 * of a human running the CLI or visiting the site.
 *
 * No new scanning logic lives here - every tool is a thin wrapper around
 * cli/lib/scan.js and cli/lib/repo.js (required via a relative path, since
 * this is a sibling package in the same monorepo, not a published
 * dependency) which already implement the HTTP calls, error handling, and
 * ecosystem/version parsing this needs. Duplicating that logic here would
 * mean two places that could drift out of sync with the actual API - see
 * MCP.md for why this is a separate package from `safecheck` itself
 * rather than a new bin entry on it.
 *
 * Defaults to the live deployed API (not localhost, unlike the CLI's own
 * default) - an agent connecting this server has no local backend running,
 * so pointing it at production out of the box is what makes "copy the
 * config, it just works" true. Set PACKAGESAFE_API_URL yourself (in the
 * MCP client's env config) to point at a local backend during development.
 */

const DEPLOYED_API_URL = "https://isthispackagesafe-production.up.railway.app";
if (!process.env.PACKAGESAFE_API_URL) {
  process.env.PACKAGESAFE_API_URL = DEPLOYED_API_URL;
}

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod");

const { scanPackage, fetchVersions } = require("../../cli/lib/scan");
const { scanRepo } = require("../../cli/lib/repo");

const { version: MCP_VERSION } = require("../package.json");

const ECOSYSTEM_SCHEMA = z
  .enum(["npm", "pypi", "maven"])
  .default("npm")
  .describe(
    "Package ecosystem/registry. Maven package names use the 'groupId:artifactId' coordinate " +
      "format (e.g. 'com.google.guava:guava'), not a bare name."
  );

function textResult(value) {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

function errorResult(err) {
  return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
}

const server = new McpServer({ name: "safecheck-mcp", version: MCP_VERSION });

server.registerTool(
  "scan_package",
  {
    title: "Scan a package for supply-chain risk",
    description:
      "Runs a LIVE PackageSafe security scan of a single npm, PyPI, or Maven package (optionally " +
      "a specific pinned version) against the real, currently-deployed scanning service - not a " +
      "static or cached knowledge base, so the result reflects the registry/GitHub/OSV.dev data as " +
      "of right now. Returns the full result: verdict (safe/suspicious/investigate), a 0-100 risk " +
      "score, supply-chain findings (typosquatting, maintainer takeovers, suspicious install " +
      "scripts, etc.), and known CVE/GHSA vulnerabilities. Use this when asked whether a specific " +
      "package is safe to install, add as a dependency, or upgrade to.",
    inputSchema: {
      ecosystem: ECOSYSTEM_SCHEMA,
      name: z
        .string()
        .describe("Package name, e.g. 'axios', 'requests', or 'com.google.guava:guava' for Maven."),
      version: z
        .string()
        .optional()
        .describe("A specific version to scan. Omit to scan the latest published version."),
    },
  },
  async ({ ecosystem, name, version }) => {
    try {
      return textResult(await scanPackage(name, { ecosystem, version }));
    } catch (err) {
      return errorResult(err);
    }
  }
);

server.registerTool(
  "check_dependency_tree",
  {
    title: "Check a package's full dependency tree for flagged issues",
    description:
      "Runs a LIVE PackageSafe scan of a package AND recursively walks its dependency tree (direct " +
      "and transitive), returning every dependency anywhere in that tree with a supply-chain " +
      "finding or a known vulnerability, each with the exact path from the root package down to it " +
      "(e.g. ['react', 'some-dep', 'flagged-package']). Use this - not scan_package - when the " +
      "question is about the package's whole dependency chain, e.g. 'is X safe INCLUDING everything " +
      "it pulls in' or 'does X depend on anything with a CVE', not just X itself.",
    inputSchema: {
      ecosystem: ECOSYSTEM_SCHEMA,
      name: z.string().describe("Package name, e.g. 'axios' or 'com.google.guava:guava' for Maven."),
      version: z.string().optional().describe("A specific version to scan. Omit for latest."),
      max_depth: z
        .number()
        .int()
        .min(0)
        .max(6)
        .optional()
        .describe("How many levels of transitive dependencies to explore (default 3)."),
    },
  },
  async ({ ecosystem, name, version, max_depth }) => {
    try {
      return textResult(
        await scanPackage(name, { ecosystem, version, includeTree: true, maxDepth: max_depth })
      );
    } catch (err) {
      return errorResult(err);
    }
  }
);

server.registerTool(
  "scan_repo",
  {
    title: "Scan an entire project's dependency manifests at once",
    description:
      "Runs a LIVE PackageSafe scan across every dependency manifest in a project at once (npm's " +
      "package.json/package-lock.json/yarn.lock, Python's requirements.txt/pyproject.toml, Maven's " +
      "pom.xml) - direct and transitive dependencies, ranked worst-first. Use this to audit an " +
      "entire project/repo rather than one package at a time, e.g. 'audit my dependencies' or " +
      "'check this project for supply-chain risk'. You (the calling agent) need to read the actual " +
      "manifest file contents from the project yourself and pass them in - this tool does not read " +
      "the filesystem.",
    inputSchema: {
      manifests: z
        .array(
          z.object({
            path: z
              .string()
              .describe(
                "File path relative to the project root, e.g. 'package.json' or " +
                  "'backend/requirements.txt' - used to detect the manifest type and pair a " +
                  "lockfile with its sibling package.json."
              ),
            content: z.string().describe("The raw, unmodified file content."),
          })
        )
        .min(1)
        .describe("Every manifest file found in the project (package.json, requirements.txt, etc.)."),
      max_depth: z.number().int().min(0).max(6).optional(),
      node_cap: z.number().int().min(1).max(1000).optional(),
    },
  },
  async ({ manifests, max_depth, node_cap }) => {
    try {
      return textResult(await scanRepo(manifests, { maxDepth: max_depth, nodeCap: node_cap }));
    } catch (err) {
      return errorResult(err);
    }
  }
);

server.registerTool(
  "list_versions",
  {
    title: "List a package's published version history",
    description:
      "Fetches the real, current published version history (newest-first, with publish dates where " +
      "available) for an npm, PyPI, or Maven package directly from the registry - a LIVE lookup, " +
      "not from training data. Use this to check what versions actually exist, find an older " +
      "version before deciding whether to scan/recommend it with scan_package, or see how recently " +
      "a package was last updated.",
    inputSchema: {
      ecosystem: ECOSYSTEM_SCHEMA,
      name: z.string().describe("Package name, e.g. 'axios' or 'com.google.guava:guava' for Maven."),
    },
  },
  async ({ ecosystem, name }) => {
    try {
      return textResult(await fetchVersions(name, { ecosystem }));
    } catch (err) {
      return errorResult(err);
    }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`safecheck-mcp v${MCP_VERSION} running on stdio, API: ${process.env.PACKAGESAFE_API_URL}`);
}

main().catch((err) => {
  console.error("safecheck-mcp failed to start:", err);
  process.exit(1);
});
