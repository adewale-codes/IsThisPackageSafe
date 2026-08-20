# weekly-report

The recurring content mechanism: scans a curated list of popular npm
packages, ranks them by PackageSafe risk score, and writes a report the
website's `/reports` page reads - plus ready-to-post X/LinkedIn copy.

## Run it

```
pip install -r requirements.txt
export PACKAGESAFE_API_URL=http://localhost:8000   # or the deployed API
python generate.py
```

Writes into `../web/content/reports/`:

- `<YYYY-MM-DD>.json` - dated snapshot (ranked packages, scores, verdicts, top finding per package)
- `latest.json` - same shape, always the most recent run; this is what `/reports` renders
- `<YYYY-MM-DD>-share.txt` - a short top-3 summary formatted for X/LinkedIn

## Scheduling

`.github/workflows/weekly-report.yml` runs this on a cron schedule (Mondays)
and via `workflow_dispatch` for manual runs, then commits the generated
JSON/text back to the repo - the same pattern as any static-site content
pipeline (a push to `main` triggers the site's normal rebuild/redeploy).

If the backend isn't deployed with a public API yet, point
`PACKAGESAFE_API_URL` at wherever it's reachable, or run this as a cron job
colocated with the backend instead of via GitHub Actions.

## Package list

`SEED_PACKAGES` in `generate.py` is a fixed, curated list of well-established
npm packages - not a live "trending" feed (none was specified in scope for
this phase). It's broad enough that real heuristic variance (archived repos,
deprecated packages, high dependency counts) shows up on its own without
needing to seed anything artificially risky.
