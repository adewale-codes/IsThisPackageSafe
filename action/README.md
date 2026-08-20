# packagesafe/check

A GitHub Action that scans npm packages with [PackageSafe](https://packagesafe.dev)
and fails the build if a dependency is flagged as `suspicious` or `investigate`.

Publish-ready as `packagesafe/check@v1` - this directory is a self-contained
`node20` action with zero runtime dependencies (it uses Node's built-in
`fetch`, same as the [CLI](../cli) and [web app](../web)). It intentionally
re-implements the small amount of scan-calling logic from the CLI directly
(same API contract, same env var name) rather than depending on the CLI as a
package, since a published action has to be self-contained and the CLI isn't
published to npm yet. Once it is, a future version could swap this for
`npx packagesafe` under the hood without changing the action's inputs/outputs.

## Usage

Scan every dependency in `package.json`:

```yaml
- uses: packagesafe/check@v1
```

Scan a single package (e.g. before adding a new dependency in a PR):

```yaml
- uses: packagesafe/check@v1
  with:
    package: left-pad
```

Point at a self-hosted PackageSafe API and only fail on `investigate`:

```yaml
- uses: packagesafe/check@v1
  with:
    api-url: https://packagesafe.internal.example.com
    fail-on: investigate
```

## Inputs

| Name | Default | Description |
| --- | --- | --- |
| `package` | (none) | Scan just this one package instead of `package-json`'s dependencies. |
| `package-json` | `package.json` | Path to the `package.json` to read `dependencies`/`devDependencies` from. |
| `api-url` | `https://api.packagesafe.dev` | Base URL of the PackageSafe API (can also be set via the `PACKAGESAFE_API_URL` env var). |
| `fail-on` | `suspicious,investigate` | Comma-separated verdicts that should fail the build. |

## Outputs

| Name | Description |
| --- | --- |
| `verdict` | The worst verdict found across all scanned packages. |
| `flagged` | JSON array of `{package, version, verdict, risk_score}` for every package matching `fail-on`. |

## Behavior

- Prints a `🟢/🟡/🔴 <package>@<version> - <verdict> (<score>/100)` line per
  package to the Action log, plus a markdown table to the job summary.
- A package that fails to scan (not found on npm, API unreachable) logs a
  `::warning::` and is skipped from the pass/fail decision rather than
  failing the whole build - a scan-infrastructure hiccup shouldn't block
  unrelated PRs.
- Any package matching `fail-on` logs an `::error::` annotation (so it shows
  up inline on the PR's Files/Checks view) and the action exits `1`.

See [`examples/`](./examples) for two runnable workflows - one against a
package that's expected to fail (`reactt`, a typosquat), one against a known
safe package (`axios`).
