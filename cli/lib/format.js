"use strict";

const CODES = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  gray: "\x1b[90m",
  cyan: "\x1b[36m",
};

const colorEnabled = !process.env.NO_COLOR && process.stdout.isTTY;

function paint(text, ...codes) {
  if (!colorEnabled) return text;
  return `${codes.map((c) => CODES[c]).join("")}${text}${CODES.reset}`;
}

const VERDICT_META = {
  safe: { icon: "\u{1F7E2}", label: "safe", color: "green" },
  suspicious: { icon: "\u{1F7E1}", label: "suspicious", color: "yellow" },
  investigate: { icon: "\u{1F534}", label: "investigate", color: "red" },
};

const SEVERITY_META = {
  danger: { icon: "\u{1F534}", color: "red" },
  warning: { icon: "\u{1F7E1}", color: "yellow" },
  info: { icon: "\u{26AA}", color: "gray" },
};

const VULN_SEVERITY_META = {
  critical: { icon: "\u{1F534}", color: "red" },
  high: { icon: "\u{1F7E0}", color: "red" },
  medium: { icon: "\u{1F7E1}", color: "yellow" },
  low: { icon: "\u{1F7E2}", color: "green" },
  unknown: { icon: "\u{26AA}", color: "gray" },
};

function formatReport(result) {
  const lines = [];
  const verdictMeta = VERDICT_META[result.verdict] || VERDICT_META.investigate;

  lines.push(`${verdictMeta.icon} ${paint(verdictMeta.label.toUpperCase(), "bold", verdictMeta.color)}`);
  lines.push(paint(`Risk score: ${result.risk_score}/100`, "bold"));
  lines.push(`${result.package}@${result.resolved_version}`);
  lines.push("");

  const findings = (result.findings || []).filter((f) => f.points > 0);

  // Supply-chain / malicious-intent signal (typosquatting, maintainer
  // takeovers, install scripts, ...) - kept in its own section, deliberately
  // never merged with the known-vulnerabilities section below. A package can
  // be "not malicious" (no findings here) and still carry a real CVE.
  lines.push(paint("Supply-chain findings:", "bold"));
  if (findings.length === 0) {
    lines.push(paint("  No findings.", "dim"));
  } else {
    for (const finding of findings) {
      const sevMeta = SEVERITY_META[finding.severity] || SEVERITY_META.info;
      lines.push(
        `  ${sevMeta.icon} ${paint(`[${finding.label}]`, "bold", sevMeta.color)} ${paint(
          `(+${finding.points})`,
          "dim"
        )}`
      );
      lines.push(`     ${finding.detail}`);
    }
  }

  lines.push("");
  lines.push(formatVulnerabilities(result));

  return lines.join("\n");
}

// Known-vulnerability (CVE/GHSA) signal, from OSV.dev - independent of the
// supply-chain findings above. Rendered as its own clearly-labeled section
// so a "safe" verdict on supply-chain grounds never reads as "no known CVEs".
function formatVulnerabilities(result) {
  const lines = [];
  const vulns = result.vulnerabilities || [];
  const check = result.vulnerability_check || { status: "completed" };

  const scoreNote =
    typeof result.vulnerability_score === "number"
      ? paint(` (+${result.vulnerability_score} to risk score)`, "dim")
      : "";
  lines.push(paint("Known vulnerabilities:", "bold") + scoreNote);

  if (check.status === "failed") {
    lines.push(
      paint(`  ⚠️  Vulnerability check did not complete${check.note ? `: ${check.note}` : "."}`, "yellow")
    );
    return lines.join("\n");
  }

  if (vulns.length === 0) {
    lines.push(paint("  No known vulnerabilities found (via OSV.dev).", "dim"));
    return lines.join("\n");
  }

  for (const vuln of vulns) {
    const sevMeta = VULN_SEVERITY_META[vuln.severity] || VULN_SEVERITY_META.unknown;
    lines.push(
      `  ${sevMeta.icon} ${paint(vuln.id, "bold", sevMeta.color)} ${paint(
        `[${vuln.severity}]`,
        sevMeta.color
      )} ${paint(`(+${vuln.points})`, "dim")}`
    );
    lines.push(`     ${vuln.summary}`);
    if (vuln.fixed_version) {
      lines.push(paint(`     Fixed in ${vuln.fixed_version}`, "dim"));
    }
    if (vuln.references && vuln.references[0]) {
      lines.push(paint(`     ${vuln.references[0]}`, "dim"));
    }
  }

  return lines.join("\n");
}

// Phase 8: dependency tree - the root package's own report, followed by a
// flat list of transitive dependencies that came back flagged (clean ones
// are never included - see dependency_tree.py). Deliberately plain/compact;
// Phase 11 handles visual polish.
function formatTreeReport(tree) {
  const lines = [formatReport(tree.root), ""];

  const caveats = [];
  if (tree.max_depth_reached) caveats.push("depth limit reached - graph may go deeper");
  if (tree.node_cap_reached) caveats.push("node limit reached - graph may be larger");
  const caveatNote = caveats.length ? paint(` (${caveats.join("; ")})`, "dim") : "";

  lines.push(paint(`Dependency tree: ${tree.total_scanned} package(s) scanned`, "bold") + caveatNote);
  lines.push("");

  const flagged = tree.flagged_dependencies || [];
  if (flagged.length === 0) {
    lines.push(paint("No flagged transitive dependencies found.", "dim"));
    return lines.join("\n");
  }

  lines.push(paint(`Flagged transitive dependencies (${flagged.length}):`, "bold"));
  for (const dep of flagged) {
    const verdictMeta = VERDICT_META[dep.verdict] || VERDICT_META.investigate;
    lines.push(
      `  ${verdictMeta.icon} ${paint(`${dep.package}@${dep.version}`, "bold")} ` +
        paint(`(risk ${dep.risk_score}/100)`, "dim")
    );
    lines.push(paint(`     path: ${dep.path.join(" -> ")}`, "dim"));
    for (const finding of dep.findings || []) {
      lines.push(`     - ${finding.label}`);
    }
    for (const vuln of dep.vulnerabilities || []) {
      const sevMeta = VULN_SEVERITY_META[vuln.severity] || VULN_SEVERITY_META.unknown;
      lines.push(`     - ${paint(vuln.id, sevMeta.color)} [${vuln.severity}]`);
    }
  }

  return lines.join("\n");
}

module.exports = { formatReport, formatTreeReport, colorEnabled };
