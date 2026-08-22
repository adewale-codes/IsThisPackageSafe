#!/usr/bin/env node
"use strict";

const {
  scanPackage,
  parsePackageArg,
  parsePackageVersion,
  PackageNotFoundError,
  ApiError,
  NetworkError,
  VALID_ECOSYSTEMS,
} = require("../lib/scan");
const { formatReport, formatTreeReport } = require("../lib/format");

const USAGE = `Usage: packagesafe <package-name>[@version] [options]

A package name may be prefixed with an ecosystem and a colon to scan a
non-npm registry, e.g. "pypi:requests" or "maven:com.google.guava:guava".
Unprefixed names default to npm. A trailing "@version" pins the scan to
that exact version instead of latest, e.g. "axios@1.2.0" or
"maven:com.google.guava:guava@30.0-jre".

Options:
  --ecosystem <name>  Ecosystem to scan: npm, pypi, or maven (default: npm)
  --tree              Also scan transitive dependencies and report any
                       that are flagged (findings and/or known vulnerabilities)
  --max-depth <n>     Max dependency tree depth to explore with --tree (default: 3)
  --node-cap <n>      Max total packages to scan with --tree (default: 200)
  --json              Print raw JSON instead of a formatted report
  --api-url <url>     PackageSafe API base URL (default: $PACKAGESAFE_API_URL or http://localhost:8000)
  -h, --help          Show this help message

Exit codes:
  0  verdict is "safe"
  1  verdict is "suspicious"/"investigate", package not found, or a scan error occurred`;

function parseArgs(argv) {
  const args = {
    packageName: null,
    json: false,
    apiUrl: null,
    ecosystem: null,
    tree: false,
    maxDepth: null,
    nodeCap: null,
    help: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--json") {
      args.json = true;
    } else if (arg === "--tree") {
      args.tree = true;
    } else if (arg === "--api-url") {
      args.apiUrl = argv[++i];
      if (!args.apiUrl) {
        throw new Error("--api-url requires a value");
      }
    } else if (arg === "--max-depth") {
      const value = argv[++i];
      if (!value || Number.isNaN(Number(value))) {
        throw new Error("--max-depth requires a numeric value");
      }
      args.maxDepth = Number(value);
    } else if (arg === "--node-cap") {
      const value = argv[++i];
      if (!value || Number.isNaN(Number(value))) {
        throw new Error("--node-cap requires a numeric value");
      }
      args.nodeCap = Number(value);
    } else if (arg === "--ecosystem") {
      args.ecosystem = argv[++i];
      if (!args.ecosystem) {
        throw new Error("--ecosystem requires a value");
      }
      if (!VALID_ECOSYSTEMS.includes(args.ecosystem)) {
        throw new Error(
          `Unknown ecosystem '${args.ecosystem}'. Supported: ${VALID_ECOSYSTEMS.join(", ")}`
        );
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
    const { ecosystem: sniffedEcosystem, packageIdentifier: rawIdentifier } = parsePackageArg(
      args.packageName
    );
    const ecosystem = args.ecosystem || sniffedEcosystem;
    const { packageIdentifier, version } = parsePackageVersion(rawIdentifier);

    const result = await scanPackage(packageIdentifier, {
      apiUrl: args.apiUrl,
      ecosystem,
      version,
      includeTree: args.tree,
      maxDepth: args.maxDepth,
      nodeCap: args.nodeCap,
    });

    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else if (args.tree) {
      console.log(formatTreeReport(result));
    } else {
      console.log(formatReport(result));
    }

    const verdict = args.tree ? result.root.verdict : result.verdict;
    process.exit(verdictExitCode(verdict));
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
