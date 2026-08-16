"use strict";

const DEFAULT_API_URL = "http://localhost:8000";

class PackageNotFoundError extends Error {
  constructor(packageName, apiMessage) {
    super(apiMessage || `Package '${packageName}' was not found on the npm registry.`);
    this.name = "PackageNotFoundError";
    this.packageName = packageName;
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

function buildScanUrl(apiUrl, packageName) {
  const encodedPath = packageName
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${apiUrl}/scan/${encodedPath}`;
}

/**
 * Calls the PackageSafe API's GET /scan/{package} endpoint.
 * @returns {Promise<object>} the parsed ScanResult
 */
async function scanPackage(packageName, { apiUrl } = {}) {
  const resolvedApiUrl = resolveApiUrl(apiUrl);
  const url = buildScanUrl(resolvedApiUrl, packageName);

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
    throw new PackageNotFoundError(packageName, detail);
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
  PackageNotFoundError,
  ApiError,
  NetworkError,
  DEFAULT_API_URL,
};
