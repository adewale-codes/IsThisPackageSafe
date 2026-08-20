#!/usr/bin/env node
"use strict";

const fs = require("fs");

function getInput(name, defaultValue = "") {
  const envName = `INPUT_${name.replace(/ /g, "_").toUpperCase()}`;
  const value = process.env[envName];
  return value === undefined || value === "" ? defaultValue : value;
}

function setOutput(name, value) {
  const outputFile = process.env.GITHUB_OUTPUT;
  if (!outputFile) return;
  fs.appendFileSync(outputFile, `${name}<<PACKAGESAFE_EOF\n${value}\nPACKAGESAFE_EOF\n`);
}

function appendSummary(markdown) {
  const summaryFile = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryFile) return;
  fs.appendFileSync(summaryFile, markdown + "\n");
}

function resolveApiUrl(explicit) {
  const url = explicit || process.env.PACKAGESAFE_API_URL || "https://api.packagesafe.dev";
  return url.replace(/\/+$/, "");
}

function buildScanUrl(apiUrl, packageName) {
  const encodedPath = packageName.split("/").map(encodeURIComponent).join("/");
  return `${apiUrl}/scan/${encodedPath}`;
}

async function scanPackage(apiUrl, packageName) {
  const url = buildScanUrl(apiUrl, packageName);
  let response;
  try {
    response = await fetch(url);
  } catch (err) {
    throw new Error(`could not reach PackageSafe API at ${apiUrl} (${err.message})`);
  }

  if (response.status === 404) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      // ignore, fall through to default message
    }
    throw new Error(detail || `package '${packageName}' was not found on the npm registry`);
  }

  if (!response.ok) {
    throw new Error(`PackageSafe API returned status ${response.status} for '${packageName}'`);
  }

  return response.json();
}

function readDependencyNames(packageJsonPath) {
  const raw = fs.readFileSync(packageJsonPath, "utf8");
  const data = JSON.parse(raw);
  const deps = { ...(data.dependencies || {}), ...(data.devDependencies || {}) };
  return Object.keys(deps);
}

const VERDICT_ICON = { safe: "\u{1F7E2}", suspicious: "\u{1F7E1}", investigate: "\u{1F534}" };
const VERDICT_RANK = { safe: 0, suspicious: 1, investigate: 2 };

async function main() {
  const singlePackage = getInput("package");
  const packageJsonPath = getInput("package-json", "package.json");
  const apiUrl = resolveApiUrl(getInput("api-url"));
  const failOn = new Set(
    getInput("fail-on", "suspicious,investigate")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );

  let packageNames;
  if (singlePackage) {
    packageNames = [singlePackage];
  } else if (fs.existsSync(packageJsonPath)) {
    packageNames = readDependencyNames(packageJsonPath);
  } else {
    console.log(
      `::warning::No 'package' input given and '${packageJsonPath}' does not exist - nothing to scan.`
    );
    packageNames = [];
  }

  if (packageNames.length === 0) {
    console.log("PackageSafe: no packages to scan.");
    setOutput("verdict", "safe");
    setOutput("flagged", "[]");
    return;
  }

  console.log(`PackageSafe: scanning ${packageNames.length} package(s) against ${apiUrl}...`);

  const results = [];
  const errors = [];
  for (const name of packageNames) {
    try {
      results.push(await scanPackage(apiUrl, name));
    } catch (err) {
      errors.push({ name, message: err.message });
    }
  }

  const flagged = results.filter((r) => failOn.has(r.verdict));
  const worstVerdict = results.reduce(
    (worst, r) => (VERDICT_RANK[r.verdict] > VERDICT_RANK[worst] ? r.verdict : worst),
    "safe"
  );

  const summaryLines = [
    "",
    "## PackageSafe scan results",
    "",
    "| Package | Version | Verdict | Score |",
    "| --- | --- | --- | --- |",
  ];

  console.log("");
  for (const r of results) {
    const icon = VERDICT_ICON[r.verdict] || "⚪";
    console.log(`${icon} ${r.package}@${r.resolved_version} - ${r.verdict} (${r.risk_score}/100)`);
    summaryLines.push(`| ${r.package} | ${r.resolved_version} | ${icon} ${r.verdict} | ${r.risk_score}/100 |`);
  }
  for (const e of errors) {
    console.log(`::warning::Could not scan '${e.name}': ${e.message}`);
    summaryLines.push(`| ${e.name} | - | ⚠️ error | - |`);
  }
  appendSummary(summaryLines.join("\n"));

  setOutput("verdict", worstVerdict);
  setOutput(
    "flagged",
    JSON.stringify(
      flagged.map((r) => ({
        package: r.package,
        version: r.resolved_version,
        verdict: r.verdict,
        risk_score: r.risk_score,
      }))
    )
  );

  if (flagged.length > 0) {
    console.log("");
    console.log(
      `::error::PackageSafe flagged ${flagged.length} package(s): ` +
        flagged.map((r) => `${r.package} (${r.verdict}, ${r.risk_score}/100)`).join(", ")
    );
    for (const r of flagged) {
      const nonZero = (r.findings || []).filter((f) => f.points > 0);
      const detail = nonZero.length
        ? nonZero.map((f) => `${f.label} (+${f.points})`).join("; ")
        : "see full report";
      console.log(
        `::error title=PackageSafe%3A ${r.package}::${r.package}@${r.resolved_version} is ${r.verdict} ` +
          `(${r.risk_score}/100) - ${detail}`
      );
    }
    process.exitCode = 1;
    return;
  }

  console.log("");
  console.log("PackageSafe: all scanned packages passed.");
}

main().catch((err) => {
  console.error(`::error::PackageSafe action failed unexpectedly: ${err.message}`);
  process.exitCode = 1;
});
