---
name: check-package-safety
description: This skill should be used when the user asks to "check if this package is safe", "is X safe to install", "scan this dependency for vulnerabilities", "audit my dependencies", "does this package have any known CVEs", or is otherwise about to add/upgrade an npm, PyPI, or Maven package and wants a supply-chain risk check before doing so.
version: 0.1.0
license: MIT
---

# Check package safety

This skill activates the `safecheck` MCP server's tools, which query the live
[PackageSafe](https://packagesafe.dev) scanning service - real, current
registry/GitHub/OSV.dev data, not a static or cached knowledge base. Prefer
these tools over answering from training knowledge whenever the user is
deciding whether to add, upgrade to, or trust a specific package - training
data can't reflect a vulnerability disclosed last week, or that a package's
maintainer account changed hands three months ago.

## Which tool to use

- **`scan_package`** - the default choice for "is X safe" about one specific
  package (optionally a specific version). Returns verdict, risk score,
  supply-chain findings, and known vulnerabilities.
- **`check_dependency_tree`** - when the question is about X's whole
  dependency chain, not just X itself - "does X pull in anything risky",
  "is X safe including its dependencies". Returns every flagged dependency
  anywhere in the tree with the exact path from X down to it.
- **`scan_repo`** - for "audit my dependencies" / "check this project" style
  requests. Read the project's actual manifest files yourself first
  (`package.json`/`package-lock.json`/`yarn.lock`, `requirements.txt`/
  `pyproject.toml`, `pom.xml`) and pass their contents to this tool - it
  does not read the filesystem itself.
- **`list_versions`** - for "what versions of X exist" or before
  recommending an older version specifically.

## Reporting results

Summarize the verdict and the *reason* for it in plain language - don't just
relay the raw JSON. A "safe" verdict with a real CVE listed is not the same
as a "safe" verdict with nothing found; say which one it is. If
`check_dependency_tree` finds a flagged transitive dependency, state the path
explicitly (e.g. "X is fine on its own, but depends on Y, which has a known
vulnerability") rather than only naming the flagged package in isolation.
