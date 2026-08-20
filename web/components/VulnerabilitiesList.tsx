import type { VulnerabilityCheckStatus, VulnerabilityFinding, VulnSeverity } from "@/lib/scan";

// Deliberately not reusing VerdictBadge's green/amber/red - a "low severity
// vulnerability" is a different kind of fact than a "safe" supply-chain
// verdict, and reusing green here would blur that distinction. Five levels
// (not three) because CVE severity has real gradations OSV reports.
const SEVERITY_CONFIG: Record<VulnSeverity, { label: string; color: string; bg: string; border: string }> = {
  critical: {
    label: "Critical",
    color: "#dc2626",
    bg: "rgba(220,38,38,0.08)",
    border: "rgba(220,38,38,0.3)",
  },
  high: {
    label: "High",
    color: "#ea580c",
    bg: "rgba(234,88,12,0.08)",
    border: "rgba(234,88,12,0.3)",
  },
  medium: {
    label: "Medium",
    color: "#d97706",
    bg: "rgba(217,119,6,0.08)",
    border: "rgba(217,119,6,0.3)",
  },
  low: {
    label: "Low",
    color: "#2563eb",
    bg: "rgba(37,99,235,0.08)",
    border: "rgba(37,99,235,0.3)",
  },
  unknown: {
    label: "Unknown",
    color: "#64748b",
    bg: "rgba(100,116,139,0.06)",
    border: "rgba(100,116,139,0.25)",
  },
};

function SeverityBadge({ severity }: { severity: VulnSeverity }) {
  const cfg = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.unknown;
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{ color: cfg.color, backgroundColor: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      {cfg.label}
    </span>
  );
}

export default function VulnerabilitiesList({
  vulnerabilities,
  check,
}: {
  vulnerabilities: VulnerabilityFinding[];
  check: VulnerabilityCheckStatus;
}) {
  if (check.status === "failed") {
    return (
      <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">
        <p className="font-semibold text-warning">⚠️ Vulnerability check did not complete</p>
        <p className="mt-1 text-muted">
          {check.note ??
            "OSV.dev could not be reached. This does not mean the package is clean - it means this check was skipped."}
        </p>
      </div>
    );
  }

  if (vulnerabilities.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5 text-sm text-muted">
        No known vulnerabilities found (checked against OSV.dev).
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {vulnerabilities.map((vuln) => {
        const cfg = SEVERITY_CONFIG[vuln.severity] ?? SEVERITY_CONFIG.unknown;
        return (
          <li
            key={vuln.id}
            className="rounded-xl border p-4"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <a
                  href={vuln.references[0] ?? `https://osv.dev/vulnerability/${vuln.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-sm font-semibold hover:underline"
                  style={{ color: cfg.color }}
                >
                  {vuln.id}
                </a>
                <SeverityBadge severity={vuln.severity} />
              </div>
              <span className="rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-xs text-muted">
                +{vuln.points}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-muted">{vuln.summary}</p>
            {vuln.fixed_version && (
              <p className="mt-1 text-xs text-muted">
                Fixed in <span className="font-mono">{vuln.fixed_version}</span>
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
