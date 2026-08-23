# safecheck

Supply-chain risk scanner for npm, PyPI, and Maven packages, and a CLI for
[PackageSafe](https://packagesafe.dev). Catches typosquats, maintainer
takeovers, sketchy install scripts, and known CVEs (via [OSV.dev](https://osv.dev)) -
for a single package, a package's full dependency tree, or an entire repo's
manifests at once.

This CLI is a thin client: all scoring logic lives in the PackageSafe API. For
the full experience - dependency-tree visualization, shareable result pages,
search - see [packagesafe.dev](https://packagesafe.dev).

## Install

```bash
# Use it once, no install:
npx safecheck axios

# Install globally, use it anywhere:
npm install -g safecheck
safecheck axios

# Add it to a project, so `npm run security-check` works for anyone who clones it:
npm install --save-dev safecheck
```

```json
{
  "scripts": {
    "security-check": "safecheck"
  }
}
```

With the last option, `npm run security-check` auto-detects your project's
manifests and runs a full repo scan (see below) - no arguments needed.

## Usage

**A single package, latest version, npm assumed:**

```bash
safecheck axios
```

**A specific version:**

```bash
safecheck axios@1.2.0
```

**A non-npm package - prefix with the ecosystem:**

```bash
safecheck pypi:requests
safecheck maven:com.google.guava:guava
safecheck maven:com.google.guava:guava@30.0-jre
```

**Its full dependency tree, not just the package itself:**

```bash
safecheck axios --tree
```

**An entire repo - run with no arguments inside a directory containing a
manifest** (`package.json`, `requirements.txt`, `pyproject.toml`, `pom.xml`) **and
it auto-detects and scans everything, direct and transitive:**

```bash
cd my-project
safecheck
```

**Or scan a specific path explicitly, from anywhere:**

```bash
safecheck scan ./some-other-repo
```

**Machine-readable output, for scripting:**

```bash
safecheck axios --json
safecheck --tree --json
safecheck scan . --json
```

### All options

```
Usage: safecheck <package-name>[@version] [options]
       safecheck scan [path]

Options:
  --ecosystem <name>  Ecosystem to scan: npm, pypi, or maven (default: npm)
  --tree              Also scan transitive dependencies and report any
                       that are flagged (findings and/or known vulnerabilities)
  --max-depth <n>     Max dependency tree depth to explore (default: 3)
  --node-cap <n>      Max total packages to scan (default: 200)
  --json              Print raw JSON instead of a formatted report
  --api-url <url>     PackageSafe API base URL (default: $PACKAGESAFE_API_URL or http://localhost:8000)
  -h, --help          Show this help message
  -v, --version       Show the installed safecheck version
```

### Configuration

By default the CLI calls `http://localhost:8000`. Point it at a deployed
backend with either:

```bash
export PACKAGESAFE_API_URL=https://api.packagesafe.dev
safecheck axios
```

or the `--api-url` flag, which takes precedence over the env var.

## Exit codes

- `0` - the worst verdict found (across a single package, its tree, or a
  whole repo scan) is `safe`
- `1` - the worst verdict is `suspicious`/`investigate`, a package/manifest
  wasn't found, or the API couldn't be reached

This makes it usable as a CI gate:

```bash
safecheck some-dependency || exit 1
# or, for a whole repo:
safecheck || exit 1
```

## Example output

```
🟢 SAFE
Risk score: 0/100
axios@1.19.0

Supply-chain findings:
  No findings.

Known vulnerabilities: (+0 to risk score)
  No known vulnerabilities found (via OSV.dev).
```

```
🟡 SUSPICIOUS
Risk score: 35/100
reactt@1.0.1

Supply-chain findings:
  🔴 [Possible typosquat of a popular package] (+30)
     Name 'reactt' is within edit distance 1 of popular package 'react' but does not match it exactly.
  ⚪ [No linked source repository] (+5)
     Package metadata does not link to a GitHub repository.
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) - covers local development and how
to add support for a new package ecosystem.

## License

MIT
