import type { Finding, Severity } from "@/lib/scan";

const SEVERITY_CONFIG: Record<Severity, { icon: string; color: string; bg: string; border: string }> = {
  danger: {
    icon: "\u{1F534}",
    color: "#dc2626",
    bg: "rgba(220,38,38,0.08)",
    border: "rgba(220,38,38,0.3)",
  },
  warning: {
    icon: "\u{1F7E1}",
    color: "#d97706",
    bg: "rgba(217,119,6,0.08)",
    border: "rgba(217,119,6,0.3)",
  },
  info: {
    icon: "\u{26AA}",
    color: "#64748b",
    bg: "rgba(100,116,139,0.06)",
    border: "rgba(100,116,139,0.25)",
  },
};

export default function FindingsList({ findings }: { findings: Finding[] }) {
  const relevant = findings.filter((f) => f.points > 0);

  if (relevant.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5 text-sm text-muted">
        No heuristics were triggered for this package.
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {relevant.map((finding) => {
        const cfg = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.info;
        return (
          <li
            key={finding.id}
            className="rounded-xl border p-4"
            style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span aria-hidden="true">{cfg.icon}</span>
                <span className="font-semibold" style={{ color: cfg.color }}>
                  {finding.label}
                </span>
              </div>
              <span className="rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-xs text-muted">
                +{finding.points}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-muted">{finding.detail}</p>
          </li>
        );
      })}
    </ul>
  );
}
