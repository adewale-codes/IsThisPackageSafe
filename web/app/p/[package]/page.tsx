import type { Metadata } from "next";
import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import VerdictBadge from "@/components/VerdictBadge";
import FindingsList from "@/components/FindingsList";
import ShareButtons from "@/components/ShareButtons";
import {
  scanPackage,
  PackageNotFoundError,
  NetworkError,
  ApiError,
  type ScanResult,
} from "@/lib/scan";

export const dynamic = "force-dynamic";

function packageNameFromParams(params: { package: string }): string {
  return params.package;
}

export async function generateMetadata({
  params,
}: {
  params: { package: string };
}): Promise<Metadata> {
  const packageName = packageNameFromParams(params);

  try {
    const result = await scanPackage(packageName);
    const verdictLabel = result.verdict[0].toUpperCase() + result.verdict.slice(1);
    return {
      title: `${result.package} — ${verdictLabel} (${result.risk_score}/100)`,
      description: `${result.package}@${result.resolved_version} scored ${result.risk_score}/100 on PackageSafe (${result.verdict}). See the full risk breakdown.`,
    };
  } catch {
    return {
      title: `${packageName} — not found`,
      description: `PackageSafe could not find '${packageName}' on the npm registry.`,
    };
  }
}

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return null;
  }
}

export default async function PackageResultPage({
  params,
}: {
  params: { package: string };
}) {
  const packageName = packageNameFromParams(params);

  let result: ScanResult;
  try {
    result = await scanPackage(packageName);
  } catch (err) {
    if (err instanceof PackageNotFoundError) {
      return <NotFoundState packageName={packageName} />;
    }
    if (err instanceof NetworkError || err instanceof ApiError) {
      return <ErrorState packageName={packageName} message={err.message} />;
    }
    return <ErrorState packageName={packageName} message="Something went wrong while scanning this package." />;
  }

  const publishedAt = formatDate(result.metadata.first_published_at);
  const showDeepScanFlag = result.deep_scan.would_trigger && !result.deep_scan.implemented;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-mono text-2xl font-bold sm:text-3xl">
              {result.package}
              <span className="text-muted">@{result.resolved_version}</span>
            </h1>
            {result.metadata.description && (
              <p className="mt-1 text-sm text-muted">{result.metadata.description}</p>
            )}
          </div>
          <VerdictBadge verdict={result.verdict} size="lg" />
        </div>

        <div className="flex items-baseline gap-2">
          <span className="font-mono text-4xl font-bold tabular-nums">{result.risk_score}</span>
          <span className="text-muted">/ 100 risk score</span>
        </div>

        <dl className="grid grid-cols-2 gap-4 border-t border-border pt-5 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">Downloads</dt>
            <dd className="mt-1 font-mono">
              {result.downloads.available ? result.downloads.downloads.toLocaleString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">First published</dt>
            <dd className="mt-1">{publishedAt ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">Dependencies</dt>
            <dd className="mt-1 font-mono">{result.metadata.dependency_count}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">GitHub stars</dt>
            <dd className="mt-1 font-mono">
              {result.github.linked && result.github.exists
                ? (result.github.stars ?? 0).toLocaleString()
                : "not linked"}
            </dd>
          </div>
        </dl>

        {showDeepScanFlag && (
          <div className="rounded-xl border border-accent/40 bg-accent/10 p-4 text-sm">
            <p className="font-semibold text-accent">🔍 Flagged for deeper inspection</p>
            <p className="mt-1 text-muted">
              This package&apos;s deterministic score already warrants a closer look, but
              the LLM-driven deep-scan layer isn&apos;t implemented yet. Treat the findings
              below as the current picture — a fuller source-level analysis is planned.
            </p>
          </div>
        )}

        <ShareButtons
          packageName={result.package}
          verdict={result.verdict}
          riskScore={result.risk_score}
        />
      </div>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Findings</h2>
        <div className="mt-4">
          <FindingsList findings={result.findings} />
        </div>
      </section>

      <section className="mt-10 flex justify-center">
        <SearchBox placeholder="Scan another package…" />
      </section>
    </main>
  );
}

function NotFoundState({ packageName }: { packageName: string }) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <span className="text-5xl">🔎</span>
      <h1 className="mt-4 text-xl font-bold">Package not found</h1>
      <p className="mt-2 text-sm text-muted">
        <span className="font-mono text-foreground">{packageName}</span> was not found on the
        npm registry. Double-check the spelling, or try another package below.
      </p>
      <div className="mt-8 w-full">
        <SearchBox />
      </div>
      <Link href="/" className="mt-6 text-sm text-accent hover:underline">
        ← Back to PackageSafe
      </Link>
    </main>
  );
}

function ErrorState({ packageName, message }: { packageName: string; message: string }) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <span className="text-5xl">⚠️</span>
      <h1 className="mt-4 text-xl font-bold">Couldn&apos;t scan {packageName}</h1>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <Link href="/" className="mt-6 text-sm text-accent hover:underline">
        ← Back to PackageSafe
      </Link>
    </main>
  );
}
