"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { discoverManifests, hasManifests } = require("../lib/repo");

function makeTmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "safecheck-test-"));
}

test("discoverManifests finds a package.json at the root", () => {
  const dir = makeTmpDir();
  fs.writeFileSync(path.join(dir, "package.json"), '{"dependencies":{"axios":"^1.0.0"}}');

  const found = discoverManifests(dir);
  assert.equal(found.length, 1);
  assert.equal(found[0].path, "package.json");
  assert.match(found[0].content, /axios/);

  fs.rmSync(dir, { recursive: true, force: true });
});

test("discoverManifests finds manifests in nested directories (monorepo case)", () => {
  const dir = makeTmpDir();
  fs.mkdirSync(path.join(dir, "web"));
  fs.mkdirSync(path.join(dir, "backend"));
  fs.writeFileSync(path.join(dir, "web", "package.json"), "{}");
  fs.writeFileSync(path.join(dir, "backend", "requirements.txt"), "fastapi>=0.111\n");

  const found = discoverManifests(dir);
  const paths = found.map((f) => f.path).sort();
  assert.deepEqual(paths, ["backend/requirements.txt", "web/package.json"]);

  fs.rmSync(dir, { recursive: true, force: true });
});

test("discoverManifests skips node_modules and other vendor directories", () => {
  const dir = makeTmpDir();
  fs.mkdirSync(path.join(dir, "node_modules", "some-pkg"), { recursive: true });
  fs.writeFileSync(path.join(dir, "node_modules", "some-pkg", "package.json"), "{}");
  fs.writeFileSync(path.join(dir, "package.json"), "{}");

  const found = discoverManifests(dir);
  assert.equal(found.length, 1);
  assert.equal(found[0].path, "package.json");

  fs.rmSync(dir, { recursive: true, force: true });
});

test("discoverManifests finds multiple manifest types side by side", () => {
  const dir = makeTmpDir();
  fs.writeFileSync(path.join(dir, "package.json"), "{}");
  fs.writeFileSync(path.join(dir, "requirements.txt"), "requests==2.6.0\n");
  fs.writeFileSync(path.join(dir, "pom.xml"), "<project></project>");

  const found = discoverManifests(dir);
  const paths = found.map((f) => f.path).sort();
  assert.deepEqual(paths, ["package.json", "pom.xml", "requirements.txt"]);

  fs.rmSync(dir, { recursive: true, force: true });
});

test("hasManifests is true when a manifest is present", () => {
  const dir = makeTmpDir();
  fs.writeFileSync(path.join(dir, "package.json"), "{}");
  assert.equal(hasManifests(dir), true);
  fs.rmSync(dir, { recursive: true, force: true });
});

test("hasManifests is false for an empty directory", () => {
  const dir = makeTmpDir();
  assert.equal(hasManifests(dir), false);
  fs.rmSync(dir, { recursive: true, force: true });
});
