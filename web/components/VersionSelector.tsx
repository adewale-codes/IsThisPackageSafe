"use client";

import { useRouter } from "next/navigation";
import type { Ecosystem, VersionEntry } from "@/lib/scan";

const LATEST_VALUE = "__latest__";

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return null;
  }
}

/**
 * Phase 8: a version dropdown on the result page - picking one navigates to
 * the version-pinned page (/p/[ecosystem]/[package]/[version]), or back to
 * the always-latest page for the synthetic "Latest" option.
 */
export default function VersionSelector({
  ecosystem,
  packageName,
  versions,
  currentVersion,
}: {
  ecosystem: Ecosystem;
  packageName: string;
  versions: VersionEntry[];
  currentVersion: string | null;
}) {
  const router = useRouter();
  const encodedPackage = packageName.split("/").map(encodeURIComponent).join("/");

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    if (value === LATEST_VALUE) {
      router.push(`/p/${ecosystem}/${encodedPackage}`);
    } else {
      router.push(`/p/${ecosystem}/${encodedPackage}/${encodeURIComponent(value)}`);
    }
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="version-select" className="text-xs uppercase tracking-widest text-muted">
        Version
      </label>
      <select
        id="version-select"
        value={currentVersion ?? LATEST_VALUE}
        onChange={handleChange}
        className="min-h-[36px] rounded-lg border border-border bg-surface px-3 py-1.5 font-mono text-sm text-foreground focus:border-accent focus:outline-none"
      >
        <option value={LATEST_VALUE}>latest</option>
        {versions.map((v) => {
          const date = formatDate(v.published_at);
          return (
            <option key={v.version} value={v.version}>
              {v.version}
              {date ? ` (${date})` : ""}
            </option>
          );
        })}
      </select>
      <span className="text-xs text-muted">{versions.length} version(s)</span>
    </div>
  );
}
