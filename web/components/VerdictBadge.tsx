import type { Verdict } from "@/lib/scan";

const VERDICT_CONFIG: Record<
  Verdict,
  { label: string; icon: string; color: string; bg: string; border: string }
> = {
  safe: {
    label: "Safe",
    icon: "\u{1F7E2}",
    color: "#22c55e",
    bg: "rgba(34,197,94,0.10)",
    border: "rgba(34,197,94,0.25)",
  },
  suspicious: {
    label: "Suspicious",
    icon: "\u{1F7E1}",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.10)",
    border: "rgba(245,158,11,0.25)",
  },
  investigate: {
    label: "Investigate",
    icon: "\u{1F534}",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.10)",
    border: "rgba(239,68,68,0.25)",
  },
};

export default function VerdictBadge({
  verdict,
  size = "md",
}: {
  verdict: Verdict;
  size?: "sm" | "md" | "lg";
}) {
  const cfg = VERDICT_CONFIG[verdict] ?? VERDICT_CONFIG.investigate;
  const sizeClasses =
    size === "lg"
      ? "text-lg px-4 py-2 gap-2"
      : size === "sm"
        ? "text-xs px-2 py-0.5 gap-1"
        : "text-sm px-3 py-1 gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ${sizeClasses}`}
      style={{ color: cfg.color, backgroundColor: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}

export { VERDICT_CONFIG };
