import type { Metadata } from "next";
import Link from "next/link";
import { fetchStats } from "@/lib/stats";
import { resolveApiUrl } from "@/lib/scan";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Transparency - PackageSafe",
  description:
    "Real, aggregate usage numbers for PackageSafe - total scans, unique packages, vulnerabilities found - and an honest account of what is and isn't tracked.",
};

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <dt className="text-xs uppercase tracking-widest text-muted">{label}</dt>
      <dd className="mt-2 font-mono text-3xl font-bold tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
      </dd>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "not yet recorded";
  try {
    return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  } catch {
    return iso;
  }
}

export default async function TransparencyPage() {
  const stats = await fetchStats();

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold sm:text-4xl">Transparency</h1>
      <p className="mt-4 max-w-xl text-muted">
        Real, aggregate numbers about what PackageSafe has actually done - not vanity metrics, and
        nothing fabricated. If a number below is zero, it&apos;s because nothing has happened yet, not
        because it was hidden.
      </p>

      {!stats && (
        <div className="mt-8 rounded-xl border border-warning/40 bg-warning/10 p-5 text-sm text-warning">
          Couldn&apos;t reach the stats endpoint right now. This page shows nothing else because there
          is nothing else to show - no cached or placeholder numbers are substituted.
        </div>
      )}

      {stats && !stats.recording_enabled && (
        <div className="mt-8 rounded-xl border border-border bg-surface p-5 text-sm text-muted">
          This deployment doesn&apos;t have stats recording configured (no database attached), so
          every number below is genuinely zero rather than uncollected.
        </div>
      )}

      {stats && (
        <>
          <p className="mt-6 text-xs text-muted">
            Tracking since {formatDate(stats.tracking_since)} · last updated{" "}
            {formatDate(stats.generated_at)}
          </p>

          <section className="mt-6">
            <h2 className="text-lg font-semibold">Scans performed</h2>
            <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Total scans" value={stats.scans.total} />
              <Stat label="Single package" value={stats.scans.single} />
              <Stat label="Dependency tree" value={stats.scans.tree} />
              <Stat label="Repo scans" value={stats.scans.repo} />
            </dl>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-semibold">Packages seen</h2>
            <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Unique packages scanned" value={stats.unique_packages_scanned} />
              <Stat label="npm" value={stats.ecosystems.npm} />
              <Stat label="PyPI" value={stats.ecosystems.pypi} />
              <Stat label="Maven" value={stats.ecosystems.maven} />
            </dl>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-semibold">Known vulnerabilities found</h2>
            <p className="mt-1 text-xs text-muted">Via OSV.dev, across every package scanned.</p>
            <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Stat label="Total" value={stats.vulnerabilities_found.total} />
              <Stat label="Critical" value={stats.vulnerabilities_found.critical} />
              <Stat label="High" value={stats.vulnerabilities_found.high} />
              <Stat label="Medium" value={stats.vulnerabilities_found.medium} />
              <Stat label="Low" value={stats.vulnerabilities_found.low} />
            </dl>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-semibold">Supply-chain findings</h2>
            <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Heuristic findings triggered" value={stats.heuristic_findings_triggered} />
            </dl>
          </section>
        </>
      )}

      <section className="mt-12 rounded-2xl border border-border bg-surface p-6 text-sm text-muted">
        <h2 className="text-base font-semibold text-foreground">What&apos;s tracked, and why</h2>
        <p className="mt-2">
          Same spirit as{" "}
          <Link href="/how-it-works" className="text-accent hover:underline">
            how the scoring pipeline works
          </Link>
          : nothing here should be a black box. This page is generated from a running total kept in
          a small database, updated once per completed scan.
        </p>

        <p className="mt-4 font-medium text-foreground">Tracked, in aggregate only:</p>
        <ul className="mt-2 ml-4 list-disc space-y-1">
          <li>How many scans have run, by type (single package, dependency tree, repo scan).</li>
          <li>How many distinct packages have been scanned, as a count.</li>
          <li>How many known vulnerabilities and supply-chain findings have been surfaced, by severity.</li>
          <li>A breakdown by ecosystem (npm/PyPI/Maven).</li>
          <li>All of it bucketed by day - no finer-grained timestamps are kept or shown.</li>
        </ul>

        <p className="mt-4 font-medium text-foreground">Deliberately not tracked or exposed:</p>
        <ul className="mt-2 ml-4 list-disc space-y-1">
          <li>
            No IP addresses, request origins, or any other user-identifying information - scanning
            doesn&apos;t require an account, and nothing here changes that.
          </li>
          <li>
            No list of which packages were searched, and no per-package timing or frequency. We do
            keep an internal set of distinct package identifiers (just the name - no timestamp, no
            per-package count) solely so &quot;unique packages scanned&quot; can be a real number
            instead of a guess. That set is never exposed by this page or the API, and on its own
            it can&apos;t answer &quot;what was searched, when, or how often&quot; - which is the
            thing we&apos;re specifically avoiding building.
          </li>
        </ul>

        <p className="mt-4">
          The public numbers are read from{" "}
          <a
            href={`${resolveApiUrl()}/stats`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            GET /stats
          </a>
          , cached for up to 5 minutes - the same endpoint this page renders.
        </p>
      </section>
    </main>
  );
}
