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

function formatReport(result) {
  const lines = [];
  const verdictMeta = VERDICT_META[result.verdict] || VERDICT_META.investigate;

  lines.push(`${verdictMeta.icon} ${paint(verdictMeta.label.toUpperCase(), "bold", verdictMeta.color)}`);
  lines.push(paint(`Risk score: ${result.risk_score}/100`, "bold"));
  lines.push(`${result.package}@${result.resolved_version}`);
  lines.push("");

  const findings = (result.findings || []).filter((f) => f.points > 0);

  if (findings.length === 0) {
    lines.push(paint("No findings.", "dim"));
  } else {
    lines.push(paint("Findings:", "bold"));
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

  return lines.join("\n");
}

module.exports = { formatReport, colorEnabled };
