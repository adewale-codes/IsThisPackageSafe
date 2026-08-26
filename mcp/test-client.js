"use strict";

// Throwaway verification script (not shipped - see mcp/package.json's
// "files" field) - spawns the real MCP server as a subprocess and drives
// it over actual stdio, the same way Claude Desktop/Code would, rather
// than calling the tool implementations in-process.

const path = require("path");
const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StdioClientTransport } = require("@modelcontextprotocol/sdk/client/stdio.js");

async function main() {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.join(__dirname, "bin", "server.js")],
  });

  const client = new Client({ name: "verification-client", version: "0.0.1" });
  await client.connect(transport);

  console.log("=== Connected. Listing tools ===");
  const { tools } = await client.listTools();
  for (const t of tools) {
    console.log(`- ${t.name}: ${t.description.slice(0, 80)}...`);
  }

  console.log("\n=== Calling scan_package(npm, axios) ===");
  const scanResult = await client.callTool({
    name: "scan_package",
    arguments: { ecosystem: "npm", name: "axios" },
  });
  const scanData = JSON.parse(scanResult.content[0].text);
  console.log(
    `verdict=${scanData.verdict} risk_score=${scanData.risk_score} resolved_version=${scanData.resolved_version}`
  );

  console.log("\n=== Calling check_dependency_tree(npm, express, max_depth=2) ===");
  const treeResult = await client.callTool({
    name: "check_dependency_tree",
    arguments: { ecosystem: "npm", name: "express", max_depth: 2, node_cap: 40 },
  });
  const treeData = JSON.parse(treeResult.content[0].text);
  console.log(`root=${treeData.root.package} total_scanned=${treeData.total_scanned}`);
  console.log(`flagged_dependencies: ${treeData.flagged_dependencies.length}`);
  for (const dep of treeData.flagged_dependencies.slice(0, 5)) {
    console.log(`  - ${dep.package}@${dep.version} path=[${dep.path.join(" -> ")}] verdict=${dep.verdict}`);
  }

  console.log("\n=== Calling list_versions(npm, axios) ===");
  const versionsResult = await client.callTool({
    name: "list_versions",
    arguments: { ecosystem: "npm", name: "axios" },
  });
  const versionsData = JSON.parse(versionsResult.content[0].text);
  console.log(`total versions: ${versionsData.length}, newest: ${versionsData[0].version}`);

  console.log("\n=== Calling scan_repo with a synthetic manifest ===");
  const repoResult = await client.callTool({
    name: "scan_repo",
    arguments: {
      manifests: [
        { path: "package.json", content: JSON.stringify({ dependencies: { axios: "^1.0.0" } }) },
      ],
      max_depth: 0,
    },
  });
  const repoData = JSON.parse(repoResult.content[0].text);
  console.log(`total_scanned=${repoData.total_scanned} direct=${repoData.direct_count}`);

  console.log("\n=== Calling scan_package with an invalid ecosystem (should be a clean validation error) ===");
  const badResult = await client.callTool({
    name: "scan_package",
    arguments: { ecosystem: "rust", name: "foo" },
  });
  console.log(
    badResult.isError
      ? `correctly rejected: ${badResult.content[0].text.slice(0, 120)}`
      : "UNEXPECTED: did not reject invalid ecosystem"
  );

  console.log("\n=== Calling scan_package for a nonexistent package (should be a clean not-found error) ===");
  const notFoundResult = await client.callTool({
    name: "scan_package",
    arguments: { ecosystem: "npm", name: "this-package-definitely-does-not-exist-xyz-999" },
  });
  console.log(
    notFoundResult.isError
      ? `correctly reported: ${notFoundResult.content[0].text.slice(0, 120)}`
      : "UNEXPECTED: did not report not-found"
  );

  await client.close();
  console.log("\nAll checks completed.");
}

main().catch((err) => {
  console.error("Test client failed:", err);
  process.exit(1);
});
