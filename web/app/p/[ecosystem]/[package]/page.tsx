import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import VerdictBadge from "@/components/VerdictBadge";
import FindingsList from "@/components/FindingsList";
import VulnerabilitiesList from "@/components/VulnerabilitiesList";
import ShareButtons from "@/components/ShareButtons";
import {
  scanPackage,
  PackageNotFoundError,
  NetworkError,
  ApiError,
  ECOSYSTEMS,
  type Ecosystem,
  type ScanResult,
} from "@/lib/scan";

export const dynamic = "force-dynamic";

type PageParams = { ecosystem: string; package: string };

function isEcosystem(value: string): value is Ecosystem {
  return (ECOSYSTEMS as string[]).includes(value);
}

/**
 * This Next.js version (14.2.35) does not reliably percent-decode dynamic
 * segment values for nested Page components - a segment like
 * "com.google.guava%3Aguava" arrives with the %3A intact rather than
 * decoded to ":" (confirmed via a minimal repro; Route Handlers at an
 * identical path decode correctly, so this is scoped to Page param
 * resolution specifically). Decoding here is a safe no-op for the common
 * case (plain names never contain "%") and fixes Maven coordinates, which
 * do.
 */
function decodeParam(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export async function generateMetadata({
  params,
}: {
  params: PageParams;
}): Promise<Metadata> {
  const ecosystem = decodeParam(params.ecosystem);
  const packageName = decodeParam(params.package);
  if (!isEcosystem(ecosystem)) {
    return { title: "Unknown ecosystem" };
  }

  try {
    const result = await scanPackage(packageName, ecosystem);
    const verdictLabel = result.verdict[0].toUpperCase() + result.verdict.slice(1);
    return {
      title: `${result.package} - ${verdictLabel} (${result.risk_score}/100)`,
      description: `${result.package}@${result.resolved_version} scored ${result.risk_score}/100 on PackageSafe (${result.verdict}). See the full risk breakdown.`,
    };
  } catch {
    return {
      title: `${packageName} - not found`,
      description: `PackageSafe could not find '${packageName}' in the ${ecosystem} registry.`,
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

export default async function PackageResultPage({ params }: { params: PageParams }) {
  const ecosystem = decodeParam(params.ecosystem);
  const packageName = decodeParam(params.package);
  if (!isEcosystem(ecosystem)) {
    notFound();
  }

  let result: ScanResult;
  try {
    result = await scanPackage(packageName, ecosystem);
  } catch (err) {
    if (err instanceof PackageNotFoundError) {
      return <NotFoundState packageName={packageName} ecosystem={ecosystem} />;
    }
    if (err instanceof NetworkError || err instanceof ApiError) {
      return <ErrorState packageName={packageName} message={err.message} />;
    }
    return <ErrorState packageName={packageName} message="Something went wrong while scanning this package." />;
  }

  const publishedAt = formatDate(result.metadata.first_published_at);
  const deepScanFinding = result.deep_scan.finding;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-muted">{result.ecosystem}</p>
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

        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-4xl font-bold tabular-nums">{result.risk_score}</span>
            <span className="text-muted">/ 100 risk score</span>
          </div>
          <p className="mt-1 text-xs text-muted">
            <span className="font-mono">{result.heuristics_score}</span> from supply-chain
            heuristics &middot; <span className="font-mono">{result.vulnerability_score}</span>{" "}
            from known vulnerabilities
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-4 border-t border-border pt-5 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">Downloads</dt>
            <dd className="mt-1 font-mono">
              {result.downloads.available ? result.downloads.downloads.toLocaleString() : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">First published</dt>
            <dd className="mt-1">{publishedAt ?? "-"}</dd>
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

        {deepScanFinding && deepScanFinding.status === "completed" && (
          <div className="rounded-xl border border-accent/40 bg-accent/10 p-4 text-sm">
            <p className="font-semibold text-accent">🔍 Flagged for deeper inspection</p>
            <p className="mt-1 text-muted">{deepScanFinding.summary}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {deepScanFinding.obfuscation_detected && (
                <span className="rounded-full border border-error/30 bg-error/10 px-2 py-0.5 text-error">
                  Obfuscation detected
                </span>
              )}
              {deepScanFinding.suspicious_network_calls && (
                <span className="rounded-full border border-error/30 bg-error/10 px-2 py-0.5 text-error">
                  Suspicious network calls
                </span>
              )}
              <span className="rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-muted">
                +{deepScanFinding.points}
              </span>
            </div>
          </div>
        )}

        {deepScanFinding && deepScanFinding.status === "failed" && (
          <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">
            <p className="font-semibold text-warning">⚠️ Deep scan did not complete</p>
            <p className="mt-1 text-muted">{deepScanFinding.summary}</p>
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
        <p className="mt-1 text-xs text-muted">
          Supply-chain / malicious-intent signals - typosquatting, maintainer takeovers,
          install scripts, and similar.
        </p>
        <div className="mt-4">
          <FindingsList findings={result.findings} />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Known Vulnerabilities</h2>
        <p className="mt-1 text-xs text-muted">
          Published CVE/GHSA advisories for this exact version, via OSV.dev - independent of the
          findings above. A package can have no supply-chain findings and still carry a known
          vulnerability.
        </p>
        <div className="mt-4">
          <VulnerabilitiesList
            vulnerabilities={result.vulnerabilities}
            check={result.vulnerability_check}
          />
        </div>
      </section>

      <section className="mt-10 flex justify-center">
        <SearchBox placeholder="Scan another package…" />
      </section>
    </main>
  );
}

function NotFoundState({ packageName, ecosystem }: { packageName: string; ecosystem: Ecosystem }) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <span className="text-5xl">🔎</span>
      <h1 className="mt-4 text-xl font-bold">Package not found</h1>
      <p className="mt-2 text-sm text-muted">
        <span className="font-mono text-foreground">{packageName}</span> was not found in the{" "}
        {ecosystem} registry. Double-check the spelling, or try another package below.
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
