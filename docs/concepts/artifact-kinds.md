---
title: Artifact kinds
description: Skills, agents, instructions, prompts, hooks, workflows and plugins, and how each tool uses them.
---

# Artifact kinds

Dex Trove has seven kinds. Each keeps its upstream format, maps to an Ananke kind, and installs into the native
layout of each tool that supports it.

| Kind | Upstream shape | Ananke kind | Claude Code | GitHub Copilot | Trove count |
| --- | --- | --- | --- | --- | --- |
| [skill](#skill) | folder with `SKILL.md` | `skill` | `skills/<name>/` | `.github/skills/<name>/` | 468 |
| [agent](#agent) | `*.agent.md` or frontmatter `.md` | `agent` | `agents/<name>.md` | `.github/agents/<name>.agent.md` | 222 |
| [instruction](#instruction) | `*.instructions.md` with `applyTo` | `prompt` | — | `.github/instructions/` | 192 |
| [prompt](#prompt) | `*.prompt.md` | `prompt` | `commands/<name>.md` | `.github/prompts/` | 0 |
| [hook](#hook) | folder with `README.md` + `hooks.json` | `tool` | — | `.github/hooks/<name>/` | 8 |
| [workflow](#workflow) | agentic workflow `.md` | `workflow` | — | `.github/workflows/<name>.md` | 8 |
| [plugin](#plugin) | `plugin.json` listing members | `bundle` | members | members | 72 |

"—" means the tool has no native equivalent; use `--target dir`. Counts are for the 0.1.0 trove.

## Skill

A **skill** is a folder of instructions plus bundled resources (scripts, references, templates, assets) that an
agent loads *on demand* when the task matches its description. It follows the
[Agent Skills specification](https://agentskills.io/specification):

```text
my-skill/
├── SKILL.md          frontmatter: name, description (+ license, allowed-tools, compatibility, metadata…)
├── references/       docs the agent reads only when needed
├── scripts/          deterministic helpers the agent runs
└── assets/           templates, examples, images
```

The `description` is what makes a skill trigger: the harness shows the agent only names and descriptions, and the
agent opens `SKILL.md` when one matches. Good descriptions say *what* the skill does and *when* to use it.

- **Claude Code**: `dex install <ref> --target claude` → `~/.claude/skills/<name>/` (user) or
  `./.claude/skills/<name>/` (`--scope project`). Claude Code discovers skills there automatically.
- **Copilot**: `--target copilot` → `.github/skills/<name>/`.
- **Ananke**: kind `skill`; activate with `ananke apm install <ns>/<name>` after learning.

Skills that contain scripts are tagged `executes-code` and show **runs code** on their page. Read the scripts
before you let an agent run them.

## Agent

An **agent** (custom agent, subagent or "chat mode") is a persona with its own system instructions and,
optionally, a tool allow-list, a preferred model and MCP servers. Upstream frontmatter commonly includes:

| Key | Meaning |
| --- | --- |
| `name`, `description` | identity and when to use it |
| `tools` | tools the agent may use (e.g. `codebase`, `editFiles`, `runCommands`) |
| `model` | preferred model |
| `mcp-servers` | MCP servers the agent expects |
| `argument-hint`, `user-invocable`, `handoffs` | invocation details |

The item page shows all of these under **Upstream metadata**.

- **Claude Code**: `agents/<name>.md` (a subagent). `dex install` translates Copilot `tools` and `model` values into
  ones Claude Code can launch; see [Agents in Claude Code](../guides/installing-items.md#agents-in-claude-code).
- **Copilot**: `.github/agents/<name>.agent.md`.
- **Ananke**: kind `agent`; the manifest's `instructions.ref` points at the entry file.

## Instruction

An **instruction** file holds coding standards that the harness applies automatically to files matching its
`applyTo` glob (e.g. `'**/*.py'`). Item pages show the glob.

- **Copilot**: `.github/instructions/<name>.instructions.md`.
- **Claude Code**: no native equivalent. Install with `--target dir` and reference the file from `CLAUDE.md`, or
  turn it into a skill.
- **Ananke**: kind `prompt`, tag `instruction`.

## Prompt

A reusable prompt file (`*.prompt.md`), invoked explicitly by the user. The current sources ship none, but the
`awesome-copilot` adapter supports them.

- **Claude Code**: `commands/<name>.md` (a slash command).
- **Copilot**: `.github/prompts/<name>.prompt.md`.

## Hook

A **hook** runs a command automatically when an agent session event fires (`sessionStart`, `sessionEnd`,
`preToolUse`, …). It is a folder with a `README.md` (frontmatter `name`, `description`, `tags`), a `hooks.json`
and usually a script:

```json
{
  "version": 1,
  "hooks": {
    "sessionEnd": [
      { "type": "command", "bash": ".github/hooks/secrets-scanner/scan-secrets.sh", "timeoutSec": 30 }
    ]
  }
}
```

Item pages list each event with its command and timeout.

Hooks **run code without asking**, so Dex never installs one unless you pass `--allow-exec`. Read the script first.

- **Copilot**: `.github/hooks/<name>/` (with `--allow-exec`).
- **Ananke**: kind `tool`, tags `hook` and `executes-code`.

## Workflow

An **agentic workflow** ([GitHub Agentic Workflows](https://github.github.com/gh-aw)) is a Markdown file whose
frontmatter declares triggers (`on`), `permissions`, `safe-outputs`, `tools` and `engine`, and whose body
is natural-language instructions. Item pages show the triggers and permissions.

- **Copilot / GitHub**: `.github/workflows/<name>.md`, then compile with the `gh aw` CLI.
- **Ananke**: kind `workflow`.

## Plugin

A **plugin** groups related skills and agents around a theme (e.g. `arize-ax` bundles 9 Arize skills). Upstream
it is a `plugin.json` ([Agent Plugins](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)) whose
`extensions.com.github.awesome-copilot` lists `skills` and `agents`.

In Dex a plugin keeps its `plugin.json` and `README.md`, and its members are resolved to trove items:

- `dex install <plugin>` installs every member into the target.
- In Ananke the plugin becomes a **bundle** whose `members` are `ananke://<kind>/<ns>/<name>` references.
  `ananke registry resolve <ns>/<plugin> --explain` shows the member graph.
- Members excluded for licence or other reasons are dropped. A plugin with no admissible members, such as
  awesome-copilot's canvas-only plugins, is excluded as `out-of-scope`.
