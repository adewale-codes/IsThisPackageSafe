# safecheck (Claude Code plugin)

The easiest way to give Claude Code the ability to check whether a package is
safe before you install it - no config file to edit by hand. This plugin
bundles [`safecheck-mcp`](../mcp) (an MCP server) plus a skill that tells
Claude when to reach for it, so it activates naturally when you ask things
like *"is this safe to add?"* or *"audit my dependencies."*

No scanning logic lives here - installing this plugin just configures Claude
Code to run the same `safecheck-mcp` package the [manual MCP setup](../mcp)
uses.

## Install

```
/plugin marketplace add adewale-codes/IsThisPackageSafe
/plugin install safecheck@IsThisPackageSafe
/reload-plugins
```

If you'd rather use a config file directly, see [`../mcp`](../mcp) instead -
this plugin is the same thing, packaged for a one-command install.

## Try it

> Is `left-pad` safe to add to my project?

Claude should reach for the `scan_package` tool automatically and answer with
a real, current verdict - not from training data.

## What's included

```
plugin/
├── .claude-plugin/
│   └── plugin.json              # plugin metadata
├── .mcp.json                    # declares the safecheck-mcp stdio server
└── skills/
    └── check-package-safety/
        └── SKILL.md             # tells Claude when to use the tools
```

See [`../mcp/README.md`](../mcp/README.md) for what the four available tools
(`scan_package`, `check_dependency_tree`, `scan_repo`, `list_versions`)
actually do.

## This is the canonical copy of the skill

`skills/check-package-safety/SKILL.md` above is the source of truth - it has
to live here because Claude Code's plugin schema only auto-discovers skills
from `./skills/` relative to the plugin root (no field exists to point it
elsewhere). A generated, byte-identical copy also lives at the repo's
top-level [`skills/`](../skills) directory, purely so [skills.sh](https://skills.sh)'s
own discovery (which looks for a root-level `skills/`, not `plugin/skills/`)
can find it too. If you edit this file, run `node ../scripts/sync-skill.js`
(from `plugin/`) or `node scripts/sync-skill.js` (from the repo root)
afterward to keep the copy in sync - it will silently drift otherwise.
