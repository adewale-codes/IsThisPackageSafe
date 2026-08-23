# Contributing to safecheck

Thanks for considering it. This CLI is a thin client over the PackageSafe
API - almost no scanning logic lives here. If you're looking to fix a
scoring heuristic, add an ecosystem, or change how vulnerabilities are
detected, that work happens in the `backend/` service in the same repo, not
in `cli/`.

## Repo layout

```
backend/   FastAPI service - all scanning/scoring logic lives here
cli/       this package - a thin terminal client over the backend API
web/       Next.js website (packagesafe.dev)
```

## Running the CLI locally

```bash
cd cli
npm install    # no dependencies today, but this validates package.json
node bin/cli.js axios
```

Or symlink it as a global command while you work on it:

```bash
npm link
safecheck axios
```

The CLI needs a running backend to talk to. From the repo root:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt    # .venv\Scripts\pip on Windows
.venv/bin/uvicorn app.main:app --reload
```

Then either export `PACKAGESAFE_API_URL=http://localhost:8000` (the
default, so this is usually a no-op) or pass `--api-url` per invocation.

## Running the tests

The CLI itself has no automated test suite yet (see `.github/workflows/`
for what CI actually runs - currently `node -c` syntax checks and a couple
of smoke invocations against a live backend). If you're adding CLI
behavior, a `node --test` suite under `cli/test/` is the natural next step
and PRs adding one are welcome.

## Adding a new package ecosystem (e.g. crates.io, RubyGems, Go modules)

This is a **backend** change. The extension point is
[`EcosystemClient`](../backend/app/services/ecosystems/base.py) - an
abstract class every ecosystem (npm, PyPI, Maven today) implements:

```python
class EcosystemClient(ABC):
    async def fetch_metadata(self, client, package_identifier, version=None) -> PackageMetadata: ...
    async def fetch_versions(self, client, package_identifier) -> list[str]: ...
    async def fetch_version_history(self, client, package_identifier) -> list[VersionEntry]: ...
    async def fetch_downloads(self, client, package_identifier) -> DownloadStats: ...
```

To add one:

1. Create `backend/app/services/ecosystems/<name>.py` implementing the
   interface - look at `pypi.py` for the simplest reference (single JSON
   API, closest to most modern registries) or `maven.py` for a harder case
   (XML, a non-name+version coordinate format).
2. Register it in `backend/app/services/ecosystems/__init__.py`'s `CLIENTS`
   dict.
3. Add the ecosystem string to the `Ecosystem` literal in
   `backend/app/models/schemas.py`.
4. Map its OSV.dev ecosystem string in `scanner.py`'s `_OSV_ECOSYSTEM` dict
   - **verify the exact casing against a real OSV query first** (it's
   case-sensitive and inconsistent between ecosystems - `npm` is lowercase,
   `PyPI` and `Maven` are not).
5. On the CLI side, add the name to `VALID_ECOSYSTEMS` in `cli/lib/scan.js`
   and to the manifest-detection logic in `cli/lib/repo.js` if the
   ecosystem has its own manifest format worth auto-detecting.

Every existing client follows a "never fake data" rule: if a registry
doesn't expose some signal (e.g. Maven has no download-count API), return
an explicit "not available" shape rather than a zero or a guess - the
scoring layer treats "not available" and "clean" differently.

## Submitting a PR

- Keep changes focused - a PR that fixes one heuristic or adds one
  ecosystem is easy to review; a PR that does five things isn't.
- If you're changing scoring behavior, explain the reasoning in the PR
  description - false positives (flagging safe packages) are just as
  costly as false negatives here.
- CI runs lint + a syntax/smoke check on every PR (see
  `.github/workflows/cli-ci.yml`). It needs to pass before merge.
