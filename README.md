# IsThisPackageSafe

Supply-chain risk scanning for npm, PyPI, and Maven packages - typosquats,
maintainer takeovers, install-script surprises, known CVEs, and repo-wide
dependency scanning. Live at [packagesafe.dev](https://packagesafe.dev).

## Project structure

| Directory | What it is |
| --- | --- |
| [`backend/`](backend) | FastAPI service - all scanning/scoring logic |
| [`web/`](web) | Next.js website (packagesafe.dev) |
| [`cli/`](cli) | `safecheck` - the open-source CLI |
| [`mcp/`](mcp) | `safecheck-mcp` - an MCP server so AI agents can call scanning directly |
| [`action/`](action) | GitHub Action wrapping the CLI for CI use |
| [`weekly-report/`](weekly-report) | scheduled job publishing a "riskiest packages this week" report |
