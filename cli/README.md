# packagesafe (CLI)

Thin terminal client for the PackageSafe risk-scanning API. Contains no scoring
logic of its own - it calls `GET /scan/{package}` on the PackageSafe backend
(Phase 1) and renders the result.

## Usage

```
npx packagesafe <package-name> [options]
```

Local development (without publishing to npm):

```
node bin/cli.js axios
# or
npm link
packagesafe axios
```

### Options

- `--json` - print the raw `ScanResult` JSON instead of a formatted report (for scripting)
- `--api-url <url>` - override the API base URL for this run
- `-h, --help` - show usage

### Configuration

By default the CLI calls `http://localhost:8000`. Point it at a deployed
backend with either:

```
export PACKAGESAFE_API_URL=https://api.packagesafe.example.com
packagesafe axios
```

or the `--api-url` flag (which takes precedence over the env var).

## Exit codes

- `0` - verdict is `safe`
- `1` - verdict is `suspicious` or `investigate`, the package wasn't found, or
  the API could not be reached

This makes the CLI usable as a CI gate:

```
packagesafe some-dependency || exit 1
```

## Output

```
🟢 SAFE
Risk score: 0/100
axios@1.19.0

No findings.
```

```
🟡 SUSPICIOUS
Risk score: 35/100
reactt@1.0.1

Findings:
  🔴 [Possible typosquat of a popular package] (+30)
     Name 'reactt' is within edit distance 1 of popular package 'react' but does not match it exactly.
  ⚪ [No linked source repository] (+5)
     Package metadata does not link to a GitHub repository.
```
