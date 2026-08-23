"use strict";

const fs = require("fs");
const path = require("path");
const { resolveApiUrl } = require("./scan");

const MANIFEST_BASENAMES = new Set([
  "package.json",
  "package-lock.json",
  "yarn.lock",
  "requirements.txt",
  "pyproject.toml",
  "pom.xml",
]);

const SKIP_DIR_NAMES = new Set([
  "node_modules",
  ".git",
  ".venv",
  "venv",
  "__pycache__",
  "dist",
  "build",
  "target",
  ".next",
  ".turbo",
]);

const MAX_WALK_DEPTH = 4;

/**
 * Walks a directory tree (bounded depth, skipping common vendor/build
 * dirs) looking for recognized manifest filenames, and reads their content
 * as UTF-8 text. Returns [{path, content}] with paths relative to `root`
 * and using forward slashes regardless of platform, so the backend's
 * manifest classification (by basename) and directory-grouping (for
 * pairing a lockfile with its package.json) behave consistently.
 */
function discoverManifests(root, { maxDepth = MAX_WALK_DEPTH } = {}) {
  const found = [];

  function walk(dir, depth) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (SKIP_DIR_NAMES.has(entry.name) || entry.name.startsWith(".")) continue;
        if (depth < maxDepth) walk(path.join(dir, entry.name), depth + 1);
        continue;
      }
      if (!entry.isFile() || !MANIFEST_BASENAMES.has(entry.name)) continue;

      const fullPath = path.join(dir, entry.name);
      let content;
      try {
        content = fs.readFileSync(fullPath, "utf-8");
      } catch {
        continue;
      }
      const relPath = path.relative(root, fullPath).split(path.sep).join("/");
      found.push({ path: relPath, content });
    }
  }

  walk(root, 0);
  return found;
}

/** True if `dir` (or anything up to maxDepth below it) contains a manifest -
 * used for the CLI's "no arguments -> auto-detect a repo scan" ergonomic. */
function hasManifests(dir) {
  return discoverManifests(dir, { maxDepth: 1 }).length > 0;
}

/**
 * POSTs discovered manifest contents to the backend's repo-scan endpoint
 * and returns the parsed RepoScanReport.
 */
async function scanRepo(manifests, { apiUrl, maxDepth, nodeCap } = {}) {
  const resolvedApiUrl = resolveApiUrl(apiUrl);
  const body = { manifests };
  if (maxDepth != null) body.max_depth = maxDepth;
  if (nodeCap != null) body.node_cap = nodeCap;

  let response;
  try {
    response = await fetch(`${resolvedApiUrl}/scan/repo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    const error = new Error(
      `Could not reach PackageSafe API at ${resolvedApiUrl} (${err.message}). Is the backend running?`
    );
    error.name = "NetworkError";
    throw error;
  }

  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      // fall through to default message
    }
    const error = new Error(detail || `PackageSafe API returned status ${response.status}`);
    error.name = "ApiError";
    error.status = response.status;
    throw error;
  }

  return response.json();
}

module.exports = { discoverManifests, hasManifests, scanRepo, MANIFEST_BASENAMES };
