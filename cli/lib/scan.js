"use strict";

const DEFAULT_API_URL = "http://localhost:8000";
const VALID_ECOSYSTEMS = ["npm", "pypi", "maven"];
const DEFAULT_ECOSYSTEM = "npm";

class PackageNotFoundError extends Error {
  constructor(packageName, ecosystem, apiMessage) {
    super(apiMessage || `Package '${packageName}' was not found in the ${ecosystem} registry.`);
    this.name = "PackageNotFoundError";
    this.packageName = packageName;
    this.ecosystem = ecosystem;
  }
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

class NetworkError extends Error {
  constructor(message, cause) {
    super(message);
    this.name = "NetworkError";
    this.cause = cause;
  }
}

function resolveApiUrl(explicitUrl) {
  const url = explicitUrl || process.env.PACKAGESAFE_API_URL || DEFAULT_API_URL;
  return url.replace(/\/+$/, "");
}

/**
 * A bare "package" argument may be prefixed with a recognized ecosystem name
 * and a colon (e.g. "pypi:requests", "maven:com.google.guava:guava" - only
 * the first colon is a delimiter, so Maven's own groupId:artifactId syntax
 * survives intact). Anything else - including a plain npm name/scoped
 * package - defaults to npm, so existing usage keeps working unchanged.
 */
function parsePackageArg(rawArg) {
  const colonIndex = rawArg.indexOf(":");
  if (colonIndex > 0) {
    const prefix = rawArg.slice(0, colonIndex);
    if (VALID_ECOSYSTEMS.includes(prefix)) {
      return { ecosystem: prefix, packageIdentifier: rawArg.slice(colonIndex + 1) };
    }
  }
  return { ecosystem: DEFAULT_ECOSYSTEM, packageIdentifier: rawArg };
}

/**
 * Splits a trailing "@version" off a package identifier (Phase 8), e.g.
 * "axios@1.2.0" -> {packageIdentifier: "axios", version: "1.2.0"} or
 * "@babel/core@7.20.0" -> {packageIdentifier: "@babel/core", version: "7.20.0"}.
 * A scoped npm package's leading '@' is part of the name, not a version
 * separator - only a LATER '@' marks a pinned version. No '@' at all means
 * unversioned (defaults to latest, unchanged Phase 1-7 behavior).
 */
function parsePackageVersion(raw) {
  const searchFrom = raw.startsWith("@") ? 1 : 0;
  const at = raw.indexOf("@", searchFrom);
  if (at === -1) return { packageIdentifier: raw, version: null };
  const version = raw.slice(at + 1);
  return { packageIdentifier: raw.slice(0, at), version: version || null };
}

function buildScanUrl(apiUrl, ecosystem, packageIdentifier, options = {}) {
  const { version, includeTree, maxDepth, nodeCap } = options;
  const encodedPath = packageIdentifier
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const params = [];
  if (version) params.push(`version=${encodeURIComponent(version)}`);
  if (includeTree) params.push("include_tree=true");
  if (maxDepth != null) params.push(`max_depth=${encodeURIComponent(maxDepth)}`);
  if (nodeCap != null) params.push(`node_cap=${encodeURIComponent(nodeCap)}`);
  const query = params.length ? `?${params.join("&")}` : "";
  return `${apiUrl}/scan/${ecosystem}/${encodedPath}${query}`;
}

/**
 * Calls the PackageSafe API's GET /scan/{ecosystem}/{package} endpoint
 * (optionally version-pinned and/or with a dependency tree - Phase 8).
 * @returns {Promise<object>} the parsed ScanResult, or DependencyTree when includeTree is set
 */
async function scanPackage(
  packageName,
  { apiUrl, ecosystem = DEFAULT_ECOSYSTEM, version, includeTree, maxDepth, nodeCap } = {}
) {
  const resolvedApiUrl = resolveApiUrl(apiUrl);
  const url = buildScanUrl(resolvedApiUrl, ecosystem, packageName, {
    version,
    includeTree,
    maxDepth,
    nodeCap,
  });

  let response;
  try {
    response = await fetch(url);
  } catch (err) {
    throw new NetworkError(
      `Could not reach PackageSafe API at ${resolvedApiUrl} (${err.message}). Is the backend running?`,
      err
    );
  }

  if (response.status === 404) {
    let detail;
    try {
      const body = await response.json();
      detail = body.detail;
    } catch {
      // fall through to default message
    }
    throw new PackageNotFoundError(packageName, ecosystem, detail);
  }

  if (!response.ok) {
    let detail;
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

module.exports = {
  scanPackage,
  resolveApiUrl,
  buildScanUrl,
  parsePackageArg,
  parsePackageVersion,
  PackageNotFoundError,
  ApiError,
  NetworkError,
  DEFAULT_API_URL,
  VALID_ECOSYSTEMS,
  DEFAULT_ECOSYSTEM,
};
