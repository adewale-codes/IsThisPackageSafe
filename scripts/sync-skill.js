#!/usr/bin/env node
// Regenerates the top-level skills/ copy (for skills.sh discovery) from the
// canonical copy inside plugin/skills/ (required there by Claude Code's
// plugin schema, which can't reference a skill file outside the plugin root).
// Run this after any edit to the canonical SKILL.md.

const fs = require("fs");
const path = require("path");

const SKILL_NAME = "check-package-safety";
const root = path.join(__dirname, "..");
const source = path.join(root, "plugin", "skills", SKILL_NAME, "SKILL.md");
const dest = path.join(root, "skills", SKILL_NAME, "SKILL.md");

const contents = fs.readFileSync(source, "utf8");
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, contents);

console.log(`Synced ${path.relative(root, source)} -> ${path.relative(root, dest)}`);
