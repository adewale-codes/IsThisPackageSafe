# safecheck-mcp

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server exposing
[PackageSafe](https://packagesafe.dev)'s supply-chain risk scanning as tools an AI
agent - Claude Code, Claude Desktop, or any other MCP-compatible client - can call
directly, mid-task, instead of a human running the [CLI](../cli) or visiting the
website separately.

No scanning logic lives here. Every tool is a thin wrapper around the same
[`cli/lib/scan.js`](../cli/lib/scan.js) and [`cli/lib/repo.js`](../cli/lib/repo.js)
that the `safecheck` CLI itself uses, reused directly rather than duplicated - see
["Why a separate package"](#why-a-separate-package-from-safecheck) below. By
default it talks to the live deployed API, so results reflect the real registry,
GitHub, and OSV.dev state as of right now - never a static or cached snapshot.

## Tools

| Tool | Use it when... |
| --- | --- |
| `scan_package` | asked whether one specific package (optionally a specific version) is safe to install/add/upgrade to |
| `check_dependency_tree` | asked whether a package is safe *including everything it depends on* - the "X is fine but depends on Y which has a CVE" case |
| `scan_repo` | asked to audit an entire project's dependencies at once (given the actual manifest file contents) |
| `list_versions` | need to see what versions of a package actually exist, e.g. before recommending an older one |

## Don't want to edit a config file?

If you use Claude Code and this feels like more setup than you want, install
the [Claude Code plugin](../plugin) instead - it's the exact same thing
(this MCP server), just a couple of copy-pasteable commands instead of hand-
editing JSON:

```
/plugin marketplace add adewale-codes/IsThisPackageSafe
/plugin install safecheck@IsThisPackageSafe
```

Everything below is for setting this MCP server up directly - useful for
Claude Desktop, other MCP clients, or if you'd rather manage the config
yourself.

## Install & configure

### Claude Code

```bash
claude mcp add safecheck -- npx -y safecheck-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "safecheck": {
      "command": "npx",
      "args": ["-y", "safecheck-mcp"]
    }
  }
}
```

Restart Claude Desktop/Code and the four tools above should appear.

### Pointing at a different backend

By default this talks to `https://isthispackagesafe-production.up.railway.app`. To
point it at a local backend during development instead, add an `env` block:

```json
{
  "mcpServers": {
    "safecheck": {
      "command": "npx",
      "args": ["-y", "safecheck-mcp"],
      "env": { "PACKAGESAFE_API_URL": "http://localhost:8000" }
    }
  }
}
```

### Running from a local checkout (before this is published)

```json
{
  "mcpServers": {
    "safecheck": {
      "command": "node",
      "args": ["/absolute/path/to/IsThisPackageSafe/mcp/bin/server.js"]
    }
  }
}
```

## Example

> **You:** Claude, is `left-pad` safe to add to my project?
>
> **Claude** calls `scan_package({ ecosystem: "npm", name: "left-pad" })`, reads the
> returned verdict/risk score/findings, and answers in its own words - something
> like: *"left-pad scores 0/100 (safe) - no supply-chain findings and no known
> vulnerabilities as of this scan. It's a very small, long-stable package, so this
> is about as low-risk as a dependency gets."*

A request like *"does axios pull in anything risky?"* should make an agent reach
for `check_dependency_tree` instead - the tool descriptions are written so the verb
in the question ("is X safe" vs. "does X depend on/pull in") maps to the right
tool without needing to name it explicitly.

## Why a separate package from `safecheck`

`cli/`'s own `package.json` deliberately has zero runtime dependencies - anyone
running `npm install -g safecheck` just to scan a package from their terminal
shouldn't also pull in the MCP SDK and its transitive dependencies. Since
`cli/lib/scan.js` and `cli/lib/repo.js` are already cleanly separated,
importable modules (not tangled into `cli/bin/cli.js`'s argument parsing), reusing
them from a sibling package via a relative `require()` - safe within this
monorepo, where both packages are versioned and released together - costs nothing
in duplicated logic while keeping the MCP SDK dependency isolated to only the
people who actually want it.

## Development

```bash
cd mcp
npm install
node bin/server.js   # runs on stdio - it's not meant to be run directly like this,
                      # but it'll start and log its target API URL to stderr
```

`test-client.js` (not published - see `package.json`'s `files` field) spins up the
server as a real subprocess and drives it over the actual MCP protocol, the same
way Claude Desktop/Code would - useful for verifying a change without needing a
full MCP client attached:

```bash
node test-client.js
```
