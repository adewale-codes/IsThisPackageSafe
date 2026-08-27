import VerdictBadge from "@/components/VerdictBadge";
import FindingsList from "@/components/FindingsList";
import VulnerabilitiesList from "@/components/VulnerabilitiesList";
import ShareButtons from "@/components/ShareButtons";
import VersionSelector from "@/components/VersionSelector";
import DependencyTreeSection from "@/components/DependencyTreeSection";
import RegistryLink from "@/components/RegistryLink";
import SearchBox from "@/components/SearchBox";
import type { ScanResult, VersionEntry } from "@/lib/scan";

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

/**
 * The full result body, shared between the latest-version page
 * (/p/[ecosystem]/[package]) and the version-pinned page
 * (/p/[ecosystem]/[package]/[version]) - Phase 8 asked for the pinned page
 * to reuse the existing result-page components rather than duplicate them.
 */
export default function ScanResultView({
  result,
  versions,
  pinnedVersion,
}: {
  result: ScanResult;
  versions: VersionEntry[] | null;
  pinnedVersion?: string;
}) {
  const publishedAt = formatDate(result.metadata.first_published_at);
  const deepScanFinding = result.deep_scan.finding;
  const isPinned = Boolean(pinnedVersion);

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
            <div className="mt-2">
              <RegistryLink
                ecosystem={result.ecosystem}
                packageName={result.package}
                version={result.resolved_version}
              />
            </div>
          </div>
          <VerdictBadge verdict={result.verdict} size="lg" />
        </div>

        {isPinned && result.metadata.latest_version !== result.resolved_version && (
          <p className="rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-muted">
            Viewing a pinned scan of <span className="font-mono">{result.resolved_version}</span>.
            The current latest release is{" "}
            <span className="font-mono">{result.metadata.latest_version}</span>.
          </p>
        )}

        {versions && versions.length > 0 && (
          <VersionSelector
            ecosystem={result.ecosystem}
            packageName={result.package}
            versions={versions}
            currentVersion={isPinned ? result.resolved_version : null}
          />
        )}

        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-4xl font-bold tabular-nums">{result.safety_score}</span>
            <span className="text-muted">/ 100 safe</span>
          </div>
          <p className="mt-1 text-xs text-muted">
            risk score <span className="font-mono">{result.risk_score}</span>/100 -{" "}
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
          safetyScore={result.safety_score}
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

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Dependency Tree</h2>
        <p className="mt-1 text-xs text-muted">
          Recursively checks this package&apos;s dependencies (and their dependencies) for known
          issues - e.g. &quot;this package is fine, but depends on X which has a CVE.&quot;
        </p>
        <div className="mt-4">
          <DependencyTreeSection
            ecosystem={result.ecosystem}
            packageName={result.package}
            version={isPinned ? result.resolved_version : undefined}
          />
        </div>
      </section>

      <section className="mt-10 flex justify-center">
        <SearchBox placeholder="Scan another package…" />
      </section>
    </main>
  );
}
