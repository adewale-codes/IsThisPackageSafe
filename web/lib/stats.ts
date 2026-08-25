import { resolveApiUrl } from "./scan";

export interface ScanCounts {
  single: number;
  tree: number;
  repo: number;
  total: number;
}

export interface EcosystemCounts {
  npm: number;
  pypi: number;
  maven: number;
}

export interface VulnerabilitySeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  unknown: number;
  total: number;
}

export interface StatsResponse {
  generated_at: string;
  tracking_since: string | null;
  recording_enabled: boolean;
  scans: ScanCounts;
  unique_packages_scanned: number;
  ecosystems: EcosystemCounts;
  vulnerabilities_found: VulnerabilitySeverityCounts;
  heuristic_findings_triggered: number;
}

/**
 * Phase 12: fetches the public, aggregate-only /stats endpoint. No auth,
 * no per-user anything - see the backend's stats.py for exactly what is
 * and isn't tracked. Server-side fetch, not cached client-side beyond
 * whatever the backend's own 5-minute TTL already provides.
 */
export async function fetchStats(): Promise<StatsResponse | null> {
  const url = `${resolveApiUrl()}/stats`;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as StatsResponse;
  } catch {
    return null;
  }
}
