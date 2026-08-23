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
const { discoverManifests, hasManifests, scanRepo } = require("../lib/repo");
const { formatReport, formatTreeReport, formatRepoReport } = require("../lib/format");

const { version: VERSION } = require("../package.json");

const USAGE = `Usage: safecheck <package-name>[@version] [options]
       safecheck scan [path]

With no arguments, run inside a directory containing a manifest (package.json,
requirements.txt, pyproject.toml, pom.xml), safecheck auto-detects it and
scans the whole repo - direct and transitive dependencies, across every
manifest found. "safecheck scan [path]" does the same for a path other
than the current directory.

A package name may be prefixed with an ecosystem and a colon to scan a
non-npm registry, e.g. "pypi:requests" or "maven:com.google.guava:guava".
Unprefixed names default to npm. A trailing "@version" pins the scan to
that exact version instead of latest, e.g. "axios@1.2.0" or
"maven:com.google.guava:guava@30.0-jre".

Options:
  --ecosystem <name>  Ecosystem to scan: npm, pypi, or maven (default: npm)
  --tree              Also scan transitive dependencies and report any
                       that are flagged (findings and/or known vulnerabilities)
  --max-depth <n>     Max dependency tree depth to explore (default: 3)
  --node-cap <n>      Max total packages to scan (default: 200)
  --json              Print raw JSON instead of a formatted report
  --api-url <url>     PackageSafe API base URL (default: $PACKAGESAFE_API_URL or http://localhost:8000)
  -h, --help          Show this help message
  -v, --version       Show the installed safecheck version

Exit codes:
  0  verdict is "safe" (worst verdict across the repo, for a repo scan)
  1  verdict is "suspicious"/"investigate", package/manifest not found, or a scan error occurred`;

function parseArgs(argv) {
  const args = {
    positional: [],
    json: false,
    apiUrl: null,
    ecosystem: null,
    tree: false,
    maxDepth: null,
    nodeCap: null,
    help: false,
    version: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--json") {
      args.json = true;
    } else if (arg === "--tree") {
      args.tree = true;
    } else if (arg === "-v" || arg === "--version") {
      args.version = true;
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
    } else {
      args.positional.push(arg);
    }
  }

  return args;
}

function verdictExitCode(verdict) {
  return verdict === "safe" ? 0 : 1;
}

/** Worst verdict across every scanned package, for the repo-scan exit code -
 * report.packages is already sorted worst-first by the backend. */
function repoVerdictExitCode(report) {
  if (report.packages.length === 0) return 0;
  return verdictExitCode(report.packages[0].scan.verdict);
}

async function runRepoScan(dirPath, args) {
  const manifests = discoverManifests(dirPath);
  if (manifests.length === 0) {
    console.error(`✖ No manifest files found in ${dirPath} (looked for package.json, `
      + `requirements.txt, pyproject.toml, pom.xml).`);
    process.exit(1);
  }

  const report = await scanRepo(manifests, {
    apiUrl: args.apiUrl,
    maxDepth: args.maxDepth,
    nodeCap: args.nodeCap,
  });

  if (args.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(formatRepoReport(report));
  }

  process.exit(repoVerdictExitCode(report));
}

async function runPackageScan(packageArg, args) {
  const { ecosystem: sniffedEcosystem, packageIdentifier: rawIdentifier } = parsePackageArg(packageArg);
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

  if (args.version) {
    console.log(VERSION);
    process.exit(0);
  }

  if (args.help) {
    console.log(USAGE);
    process.exit(0);
  }

  const [first, second, ...rest] = args.positional;

  try {
    if (first === "scan") {
      if (rest.length > 0) {
        throw new Error(`Unexpected argument: ${rest[0]}`);
      }
      await runRepoScan(second || ".", args);
      return;
    }

    if (args.positional.length > 1) {
      throw new Error(`Unexpected argument: ${args.positional[1]}`);
    }

    if (!first) {
      // No package name given - the "npm audit"-like ergonomic: if the
      // current directory has a manifest, just scan the repo instead of
      // requiring an explicit "scan" subcommand.
      if (hasManifests(".")) {
        await runRepoScan(".", args);
        return;
      }
      console.log(USAGE);
      process.exit(1);
    }

    await runPackageScan(first, args);
  } catch (err) {
    if (err instanceof PackageNotFoundError) {
      console.error(`✖ ${err.message}`);
    } else if (err instanceof NetworkError) {
      console.error(`✖ ${err.message}`);
    } else if (err instanceof ApiError) {
      console.error(`✖ PackageSafe API error: ${err.message}`);
    } else {
      console.error(`✖ ${err.message}`);
    }
    process.exit(1);
  }
}

main();
