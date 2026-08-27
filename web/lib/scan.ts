import { cache } from "react";

export type Severity = "info" | "warning" | "danger";
export type Verdict = "safe" | "suspicious" | "investigate";
export type Ecosystem = "npm" | "pypi" | "maven";

export const ECOSYSTEMS: Ecosystem[] = ["npm", "pypi", "maven"];
export const DEFAULT_ECOSYSTEM: Ecosystem = "npm";

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
  ecosystem: Ecosystem;
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

export type DeepScanStatus = "completed" | "failed" | "skipped";

export interface DeepScanFinding {
  status: DeepScanStatus;
  obfuscation_detected: boolean;
  suspicious_network_calls: boolean;
  summary: string;
  points: number;
  cached: boolean;
}

export interface DeepScanInfo {
  would_trigger: boolean;
  reason?: string | null;
  implemented: boolean;
  finding?: DeepScanFinding | null;
}

// Known-vulnerability (CVE/GHSA) signal from OSV.dev (Phase 6) - kept
// structurally separate from Finding/heuristics throughout: a package can
// be "not malicious" (no Findings) and still carry a real, serious CVE.
export type VulnSeverity = "critical" | "high" | "medium" | "low" | "unknown";

export interface VulnerabilityFinding {
  id: string;
  summary: string;
  severity: VulnSeverity;
  fixed_version?: string | null;
  references: string[];
  points: number;
}

export type VulnCheckStatusValue = "completed" | "failed";

export interface VulnerabilityCheckStatus {
  status: VulnCheckStatusValue;
  note?: string | null;
}

export interface ScanResult {
  ecosystem: Ecosystem;
  package: string;
  resolved_version: string;
  risk_score: number;
  /** 100 - risk_score - the same number, framed positively. Always derived
   * server-side (never compute this independently), see the backend's
   * ScanResult.safety_score docstring. */
  safety_score: number;
  heuristics_score: number;
  vulnerability_score: number;
  verdict: Verdict;
  metadata: PackageMetadata;
  downloads: DownloadStats;
  github: GithubSignals;
  findings: Finding[];
  deep_scan: DeepScanInfo;
  vulnerabilities: VulnerabilityFinding[];
  vulnerability_check: VulnerabilityCheckStatus;
}

// Phase 8: version browsing + transitive dependency analysis.

export interface VersionEntry {
  version: string;
  published_at?: string | null;
}

export interface FlaggedDependency {
  ecosystem: Ecosystem;
  package: string;
  version: string;
  path: string[];
  risk_score: number;
  safety_score: number;
  verdict: Verdict;
  findings: Finding[];
  vulnerabilities: VulnerabilityFinding[];
}

export interface DependencyTree {
  root: ScanResult;
  flagged_dependencies: FlaggedDependency[];
  total_scanned: number;
  max_depth_reached: boolean;
  node_cap_reached: boolean;
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

export interface ScanOptions {
  version?: string | null;
  includeTree?: boolean;
  maxDepth?: number;
  nodeCap?: number;
}

function encodedPackagePath(packageName: string): string {
  return packageName
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

export function buildScanUrl(
  packageName: string,
  ecosystem: Ecosystem = DEFAULT_ECOSYSTEM,
  options: ScanOptions = {}
): string {
  const params = new URLSearchParams();
  if (options.version) params.set("version", options.version);
  if (options.includeTree) params.set("include_tree", "true");
  if (options.maxDepth != null) params.set("max_depth", String(options.maxDepth));
  if (options.nodeCap != null) params.set("node_cap", String(options.nodeCap));
  const query = params.toString();
  return `${resolveApiUrl()}/scan/${ecosystem}/${encodedPackagePath(packageName)}${query ? `?${query}` : ""}`;
}

export function buildVersionsUrl(packageName: string, ecosystem: Ecosystem = DEFAULT_ECOSYSTEM): string {
  return `${resolveApiUrl()}/versions/${ecosystem}/${encodedPackagePath(packageName)}`;
}

async function fetchJson(url: string, packageName: string, ecosystem: Ecosystem, version?: string | null) {
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
    const displayName = version ? `${packageName}@${version}` : packageName;
    throw new PackageNotFoundError(
      detail || `Package '${displayName}' was not found in the ${ecosystem} registry.`
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
}

/**
 * Fetches a live scan from the API - optionally version-pinned and/or with
 * a dependency tree (Phase 8). Wrapped in React's cache() so a single
 * request (page + generateMetadata + any other callers) only hits the API
 * once per distinct argument set - there is no server-side result caching
 * beyond that, matching Phase 1/2's "every load is a live scan" behavior.
 */
export const scanPackage = cache(async (
  packageName: string,
  ecosystem: Ecosystem = DEFAULT_ECOSYSTEM,
  options: ScanOptions = {}
): Promise<ScanResult> => {
  const url = buildScanUrl(packageName, ecosystem, options);
  return fetchJson(url, packageName, ecosystem, options.version) as Promise<ScanResult>;
});

/**
 * Fetches a scan with its full dependency tree (Phase 8). A separate
 * function (rather than overloading scanPackage's return type) so callers -
 * and TypeScript - always know statically which shape they're getting.
 */
export const scanPackageWithTree = cache(async (
  packageName: string,
  ecosystem: Ecosystem = DEFAULT_ECOSYSTEM,
  options: Omit<ScanOptions, "includeTree"> = {}
): Promise<DependencyTree> => {
  const url = buildScanUrl(packageName, ecosystem, { ...options, includeTree: true });
  return fetchJson(url, packageName, ecosystem, options.version) as Promise<DependencyTree>;
});

/**
 * Full version history for a package, newest-first (Phase 8). Not wrapped
 * in cache() like scanPackage - it's cheap, and each page that wants it
 * calls it at most once, so per-request de-dup isn't needed.
 */
export async function fetchVersions(
  packageName: string,
  ecosystem: Ecosystem = DEFAULT_ECOSYSTEM
): Promise<VersionEntry[]> {
  const url = buildVersionsUrl(packageName, ecosystem);
  return fetchJson(url, packageName, ecosystem) as Promise<VersionEntry[]>;
}
