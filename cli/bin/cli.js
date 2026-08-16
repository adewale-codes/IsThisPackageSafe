#!/usr/bin/env node
"use strict";

const { scanPackage, PackageNotFoundError, ApiError, NetworkError } = require("../lib/scan");
const { formatReport } = require("../lib/format");

const USAGE = `Usage: packagesafe <package-name> [options]

Options:
  --json              Print raw JSON instead of a formatted report
  --api-url <url>     PackageSafe API base URL (default: $PACKAGESAFE_API_URL or http://localhost:8000)
  -h, --help          Show this help message

Exit codes:
  0  verdict is "safe"
  1  verdict is "suspicious"/"investigate", package not found, or a scan error occurred`;

function parseArgs(argv) {
  const args = { packageName: null, json: false, apiUrl: null, help: false };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--json") {
      args.json = true;
    } else if (arg === "--api-url") {
      args.apiUrl = argv[++i];
      if (!args.apiUrl) {
        throw new Error("--api-url requires a value");
      }
    } else if (arg === "-h" || arg === "--help") {
      args.help = true;
    } else if (arg.startsWith("-")) {
      throw new Error(`Unknown option: ${arg}`);
    } else if (!args.packageName) {
      args.packageName = arg;
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
  }

  return args;
}

function verdictExitCode(verdict) {
  return verdict === "safe" ? 0 : 1;
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(`Error: ${err.message}\n`);
    console.error(USAGE);
    process.exit(1);
  }

  if (args.help || !args.packageName) {
    console.log(USAGE);
    process.exit(args.help ? 0 : 1);
  }

  try {
    const result = await scanPackage(args.packageName, { apiUrl: args.apiUrl });

    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(formatReport(result));
    }

    process.exit(verdictExitCode(result.verdict));
  } catch (err) {
    if (err instanceof PackageNotFoundError) {
      console.error(`✖ ${err.message}`);
    } else if (err instanceof NetworkError) {
      console.error(`✖ ${err.message}`);
    } else if (err instanceof ApiError) {
      console.error(`✖ PackageSafe API error: ${err.message}`);
    } else {
      console.error(`✖ Unexpected error: ${err.message}`);
    }
    process.exit(1);
  }
}

main();
