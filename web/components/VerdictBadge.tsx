import type { Verdict } from "@/lib/scan";

const VERDICT_CONFIG: Record<
  Verdict,
  { label: string; icon: string; color: string; bg: string; border: string }
> = {
  safe: {
    label: "Safe",
    icon: "\u{1F7E2}",
    color: "#16a34a",
    bg: "rgba(22,163,74,0.10)",
    border: "rgba(22,163,74,0.35)",
  },
  suspicious: {
    label: "Suspicious",
    icon: "\u{1F7E1}",
    color: "#d97706",
    bg: "rgba(217,119,6,0.10)",
    border: "rgba(217,119,6,0.35)",
  },
  investigate: {
    label: "Investigate",
    icon: "\u{1F534}",
    color: "#dc2626",
    bg: "rgba(220,38,38,0.10)",
    border: "rgba(220,38,38,0.35)",
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
