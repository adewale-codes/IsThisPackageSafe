"use client";

import { useState } from "react";
import DependencyChainViz from "@/components/DependencyChainViz";
import type { DependencyTree, Ecosystem } from "@/lib/scan";

const VERDICT_DOT: Record<string, string> = {
  safe: "bg-green-500",
  suspicious: "bg-yellow-500",
  investigate: "bg-red-500",
};

/**
 * Phase 8: fetch-on-demand rather than on every page load - a full tree
 * scan can recursively check dozens of transitive dependencies and take
 * real time (bounded but potentially tens of seconds), so it's an explicit
 * user action, not something that slows down every normal package lookup.
 * Deliberately plain - Phase 11 handles visual polish.
 */
export default function DependencyTreeSection({
  ecosystem,
  packageName,
  version,
}: {
  ecosystem: Ecosystem;
  packageName: string;
  version?: string;
}) {
  const [state, setState] = useState<"idle" | "loading" | "error" | "done">("idle");
  const [tree, setTree] = useState<DependencyTree | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleScan() {
    setState("loading");
    setError(null);
    try {
      const params = new URLSearchParams({ ecosystem, package: packageName });
      if (version) params.set("version", version);
      const resp = await fetch(`/api/tree?${params.toString()}`, { cache: "no-store" });
      const body = await resp.json();
      if (!resp.ok) {
        throw new Error(body.detail || `Request failed with status ${resp.status}`);
      }
      setTree(body as DependencyTree);
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setState("error");
    }
  }

  if (state === "idle") {
    return (
      <button
        type="button"
        onClick={handleScan}
        className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground hover:border-accent"
      >
        Scan dependency tree
      </button>
    );
  }

  if (state === "loading") {
    return <p className="text-sm text-muted">Scanning dependency tree - this can take a while for large graphs…</p>;
  }

  if (state === "error") {
    return (
      <div className="text-sm">
        <p className="text-error">Dependency tree scan failed: {error}</p>
        <button
          type="button"
          onClick={handleScan}
          className="mt-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground hover:border-accent"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!tree) return null;

  const caveats: string[] = [];
  if (tree.max_depth_reached) caveats.push("depth limit reached - graph may go deeper");
  if (tree.node_cap_reached) caveats.push("node limit reached - graph may be larger");

  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-muted">
        {tree.total_scanned} package(s) scanned.
        {caveats.length > 0 && ` (${caveats.join("; ")})`}
      </p>

      {tree.flagged_dependencies.length === 0 ? (
        <p className="text-muted">No flagged transitive dependencies found.</p>
      ) : (
        <>
          <DependencyChainViz
            ecosystem={ecosystem}
            rootPackage={tree.root.package}
            rootVerdict={tree.root.verdict}
            flaggedDependencies={tree.flagged_dependencies}
          />
          <p className="text-xs text-muted">
            Each highlighted node is a flagged dependency - click one to see its own result page.
            The path traces exactly how it entered {tree.root.package}&apos;s dependency graph.
          </p>
        </>
      )}

      {tree.flagged_dependencies.length > 0 && (
        <ul className="flex flex-col gap-3" aria-label="Flagged dependency details">
          {tree.flagged_dependencies.map((dep) => (
            <li key={`${dep.package}@${dep.version}`} className="rounded-lg border border-border p-3">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 shrink-0 rounded-full ${VERDICT_DOT[dep.verdict] ?? "bg-gray-400"}`} />
                <span className="font-mono font-semibold">
                  {dep.package}@{dep.version}
                </span>
                <span className="text-xs text-muted">risk {dep.risk_score}/100</span>
              </div>
              <p className="mt-1 font-mono text-xs text-muted">{dep.path.join(" → ")}</p>
              <ul className="mt-2 flex flex-col gap-1 text-xs text-muted">
                {dep.findings.map((f) => (
                  <li key={f.id}>- {f.label}</li>
                ))}
                {dep.vulnerabilities.map((v) => (
                  <li key={v.id}>
                    - {v.id} [{v.severity}]
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
