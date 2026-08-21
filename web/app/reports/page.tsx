import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import VerdictBadge from "@/components/VerdictBadge";
import type { Verdict } from "@/lib/scan";

export const revalidate = 3600; // ISR: refresh at most once an hour

export const metadata: Metadata = {
  title: "Riskiest npm packages this week",
  description:
    "PackageSafe's weekly ranking of popular npm packages by supply-chain risk score.",
};

interface ReportFinding {
  id: string;
  label: string;
  severity: string;
  points: number;
  detail: string;
}

interface ReportEntry {
  rank: number;
  package: string;
  version: string;
  risk_score: number;
  verdict: Verdict;
  description: string | null;
  top_finding: ReportFinding | null;
}

interface Report {
  generated_at: string;
  period_label: string;
  packages_scanned: number;
  packages_failed: number;
  failed: { package: string; error: string }[];
  packages: ReportEntry[];
}

function readLatestReport(): Report | null {
  const filePath = path.join(process.cwd(), "content", "reports", "latest.json");
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as Report;
  } catch {
    return null;
  }
}

function formatGeneratedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }) + " UTC";
  } catch {
    return iso;
  }
}

export default function ReportsPage() {
  const report = readLatestReport();

  if (!report) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-24 text-center">
        <h1 className="text-xl font-bold">No report yet</h1>
        <p className="mt-2 text-sm text-muted">
          The weekly riskiest-packages job hasn&apos;t run yet. Check back soon, or run{" "}
          <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-xs">
            weekly-report/generate.py
          </code>{" "}
          to produce one.
        </p>
        <Link href="/" className="mt-6 inline-block text-sm text-accent hover:underline">
          ← Back to PackageSafe
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">Riskiest npm packages this week</h1>
        <p className="mt-3 text-muted">
          {report.period_label} · {report.packages_scanned} packages scanned · generated{" "}
          {formatGeneratedAt(report.generated_at)}
        </p>
      </header>

      <div className="mt-10 overflow-x-auto rounded-2xl border border-border bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-border text-xs uppercase tracking-widest text-muted">
            <tr>
              <th className="px-4 py-3">#</th>
              <th className="px-4 py-3">Package</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Verdict</th>
              <th className="px-4 py-3">Top finding</th>
            </tr>
          </thead>
          <tbody>
            {report.packages.map((entry) => (
              <tr key={entry.package} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-mono text-muted">{entry.rank}</td>
                <td className="px-4 py-3">
                  <Link
                    href={`/p/npm/${encodeURIComponent(entry.package)}`}
                    className="font-mono font-semibold text-accent hover:underline"
                  >
                    {entry.package}
                  </Link>
                  <span className="ml-1 text-xs text-muted">@{entry.version}</span>
                  {entry.description && (
                    <p className="mt-0.5 max-w-xs truncate text-xs text-muted">
                      {entry.description}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3 font-mono font-bold tabular-nums">
                  {entry.risk_score}/100
                </td>
                <td className="px-4 py-3">
                  <VerdictBadge verdict={entry.verdict} size="sm" />
                </td>
                <td className="px-4 py-3 text-xs text-muted">
                  {entry.top_finding ? entry.top_finding.label : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {report.packages_failed > 0 && (
        <p className="mt-4 text-xs text-muted">
          {report.packages_failed} package(s) couldn&apos;t be scanned this run and were excluded.
        </p>
      )}

      <p className="mt-8 text-center text-sm text-muted">
        Want your package on this list?{" "}
        <Link href="/" className="text-accent hover:underline">
          Scan it with PackageSafe
        </Link>
        .
      </p>
    </main>
  );
}
