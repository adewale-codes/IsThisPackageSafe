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

function buildScanUrl(apiUrl, ecosystem, packageIdentifier) {
  const encodedPath = packageIdentifier
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${apiUrl}/scan/${ecosystem}/${encodedPath}`;
}

/**
 * Calls the PackageSafe API's GET /scan/{ecosystem}/{package} endpoint.
 * @returns {Promise<object>} the parsed ScanResult
 */
async function scanPackage(packageName, { apiUrl, ecosystem = DEFAULT_ECOSYSTEM } = {}) {
  const resolvedApiUrl = resolveApiUrl(apiUrl);
  const url = buildScanUrl(resolvedApiUrl, ecosystem, packageName);

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
  PackageNotFoundError,
  ApiError,
  NetworkError,
  DEFAULT_API_URL,
  VALID_ECOSYSTEMS,
  DEFAULT_ECOSYSTEM,
};
