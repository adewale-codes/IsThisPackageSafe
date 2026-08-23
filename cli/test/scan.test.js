"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  parsePackageArg,
  parsePackageVersion,
  buildScanUrl,
  resolveApiUrl,
  DEFAULT_ECOSYSTEM,
} = require("../lib/scan");

test("parsePackageArg defaults to npm for a bare name", () => {
  assert.deepEqual(parsePackageArg("axios"), {
    ecosystem: "npm",
    packageIdentifier: "axios",
  });
});

test("parsePackageArg defaults to npm for a scoped package (no ecosystem prefix)", () => {
  assert.deepEqual(parsePackageArg("@babel/core"), {
    ecosystem: "npm",
    packageIdentifier: "@babel/core",
  });
});

test("parsePackageArg recognizes a pypi: prefix", () => {
  assert.deepEqual(parsePackageArg("pypi:requests"), {
    ecosystem: "pypi",
    packageIdentifier: "requests",
  });
});

test("parsePackageArg keeps Maven's own colon syntax intact after the ecosystem prefix", () => {
  assert.deepEqual(parsePackageArg("maven:com.google.guava:guava"), {
    ecosystem: "maven",
    packageIdentifier: "com.google.guava:guava",
  });
});

test("parsePackageArg treats an unrecognized prefix as part of the (npm) name", () => {
  assert.deepEqual(parsePackageArg("notaneco:something"), {
    ecosystem: "npm",
    packageIdentifier: "notaneco:something",
  });
});

test("parsePackageVersion splits a trailing @version", () => {
  assert.deepEqual(parsePackageVersion("axios@1.2.0"), {
    packageIdentifier: "axios",
    version: "1.2.0",
  });
});

test("parsePackageVersion leaves an unversioned name alone", () => {
  assert.deepEqual(parsePackageVersion("axios"), {
    packageIdentifier: "axios",
    version: null,
  });
});

test("parsePackageVersion doesn't mistake a scoped package's leading @ for a version separator", () => {
  assert.deepEqual(parsePackageVersion("@babel/core"), {
    packageIdentifier: "@babel/core",
    version: null,
  });
});

test("parsePackageVersion handles a scoped package that IS version-pinned", () => {
  assert.deepEqual(parsePackageVersion("@babel/core@7.20.0"), {
    packageIdentifier: "@babel/core",
    version: "7.20.0",
  });
});

test("parsePackageVersion handles a Maven coordinate with a pinned version", () => {
  assert.deepEqual(parsePackageVersion("com.google.guava:guava@30.0-jre"), {
    packageIdentifier: "com.google.guava:guava",
    version: "30.0-jre",
  });
});

test("resolveApiUrl strips a trailing slash", () => {
  assert.equal(resolveApiUrl("http://localhost:8000/"), "http://localhost:8000");
});

test("resolveApiUrl falls back to the documented default", () => {
  const original = process.env.PACKAGESAFE_API_URL;
  delete process.env.PACKAGESAFE_API_URL;
  try {
    assert.equal(resolveApiUrl(), "http://localhost:8000");
  } finally {
    if (original !== undefined) process.env.PACKAGESAFE_API_URL = original;
  }
});

test("buildScanUrl encodes a scoped package name segment-by-segment", () => {
  const url = buildScanUrl("http://localhost:8000", "npm", "@babel/core");
  assert.equal(url, "http://localhost:8000/scan/npm/%40babel/core");
});

test("buildScanUrl adds a version query param when given one", () => {
  const url = buildScanUrl("http://localhost:8000", "npm", "axios", { version: "1.2.0" });
  assert.equal(url, "http://localhost:8000/scan/npm/axios?version=1.2.0");
});

test("buildScanUrl adds tree query params when requested", () => {
  const url = buildScanUrl("http://localhost:8000", "npm", "axios", {
    includeTree: true,
    maxDepth: 2,
    nodeCap: 50,
  });
  assert.equal(
    url,
    "http://localhost:8000/scan/npm/axios?include_tree=true&max_depth=2&node_cap=50"
  );
});

test("DEFAULT_ECOSYSTEM is npm", () => {
  assert.equal(DEFAULT_ECOSYSTEM, "npm");
});
