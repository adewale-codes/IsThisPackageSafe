import { cache } from "react";

export type Severity = "info" | "warning" | "danger";
export type Verdict = "safe" | "suspicious" | "investigate";

export interface Finding {
  id: string;
  label: string;
  severity: Severity;
  points: number;
  detail: string;
}

export interface Maintainer {
  name: string;
  email?: string | null;
}

export interface RepositoryInfo {
  raw_url?: string | null;
  owner?: string | null;
  repo?: string | null;
}

export interface PackageMetadata {
  name: string;
  description?: string | null;
  latest_version: string;
  version_count: number;
  first_published_at?: string | null;
  latest_published_at?: string | null;
  license?: string | null;
  homepage?: string | null;
  keywords: string[];
  repository: RepositoryInfo;
  maintainers: Maintainer[];
  dependencies: Record<string, string>;
  dependency_count: number;
  install_scripts: Record<string, string>;
  tarball_url?: string | null;
  unpacked_size_bytes?: number | null;
}

export interface DownloadStats {
  period: string;
  downloads: number;
  start?: string | null;
  end?: string | null;
  available: boolean;
}

export interface GithubSignals {
  linked: boolean;
  owner?: string | null;
  repo?: string | null;
  exists?: boolean | null;
  archived?: boolean | null;
  stars?: number | null;
  forks?: number | null;
  open_issues?: number | null;
  contributors_count?: number | null;
  last_pushed_at?: string | null;
  error?: string | null;
}

export interface DeepScanInfo {
  would_trigger: boolean;
  reason?: string | null;
  implemented: boolean;
}

export interface ScanResult {
  package: string;
  resolved_version: string;
  risk_score: number;
  verdict: Verdict;
  metadata: PackageMetadata;
  downloads: DownloadStats;
  github: GithubSignals;
  findings: Finding[];
  deep_scan: DeepScanInfo;
}

const DEFAULT_API_URL = "http://localhost:8000";

export class PackageNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PackageNotFoundError";
  }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export function resolveApiUrl(): string {
  const url = process.env.PACKAGESAFE_API_URL || DEFAULT_API_URL;
  return url.replace(/\/+$/, "");
}

export function buildScanUrl(packageName: string): string {
  const encodedPath = packageName
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${resolveApiUrl()}/scan/${encodedPath}`;
}

/**
 * Fetches a live scan from the Phase 1 API. Wrapped in React's cache() so a
 * single request (page + generateMetadata + any other callers) only hits the
 * API once — there is no server-side result caching beyond that, matching
 * Phase 1/2's "every load is a live scan" behavior.
 */
export const scanPackage = cache(async (packageName: string): Promise<ScanResult> => {
  const url = buildScanUrl(packageName);

  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store" });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new NetworkError(
      `Could not reach the PackageSafe API at ${resolveApiUrl()} (${message}). Is the backend running?`
    );
  }

  if (response.status === 404) {
    let detail: string | undefined;
    try {
      const body = await response.json();
      detail = body.detail;
    } catch {
      // fall through to default message
    }
    throw new PackageNotFoundError(
      detail || `Package '${packageName}' was not found on the npm registry.`
    );
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = await response.json();
      detail = body.detail;
    } catch {
      // fall through to default message
    }
    throw new ApiError(
      detail || `PackageSafe API returned status ${response.status}`,
      response.status
    );
  }

  return response.json();
});
