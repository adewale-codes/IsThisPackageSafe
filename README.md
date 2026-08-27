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
| [`plugin/`](plugin) | Claude Code plugin - one-command install of the MCP server above |
| [`skills/`](skills) | Generated copy of the plugin's skill, for [skills.sh](https://skills.sh) discovery - see note below |
| [`action/`](action) | GitHub Action wrapping the CLI for CI use |
| [`weekly-report/`](weekly-report) | scheduled job publishing a "riskiest packages this week" report |

`skills/check-package-safety/SKILL.md` is not hand-edited. It's a generated,
byte-identical copy of `plugin/skills/check-package-safety/SKILL.md` (the
canonical version - required to live inside `plugin/` by Claude Code's own
plugin schema, which has no way to reference a skill file outside the plugin
root). The top-level copy exists only because skills.sh's bare-repo discovery
(`npx skills add adewale-codes/IsThisPackageSafe`) scans for a root-level
`skills/<name>/SKILL.md`, not `plugin/skills/`. After editing the canonical
file, regenerate the copy with:

```bash
node scripts/sync-skill.js
```
