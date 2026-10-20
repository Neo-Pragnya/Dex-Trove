---
title: Installing items
description: Where each kind of item goes for Claude Code, GitHub Copilot and plain directories.
---

# Installing items

```bash
dex install REF... --target claude|copilot|dir [--scope user|project] [--path DIR] [--allow-exec]
```

`dex install` copies items out of the installed package into a tool's native layout. It never runs anything.
You can pass several refs at once, and plugins expand to their members.

## Targets

### `--target claude` (default)

| Kind | Destination | Notes |
| --- | --- | --- |
| skill | `<base>/skills/<name>/` | whole folder, minus Dex's `ananke.yaml`/`dex.json`; licence files included |
| agent | `<base>/agents/<name>.md` | entry file + `<name>.md.LICENSE` |
| prompt | `<base>/commands/<name>.md` | becomes a slash command |
| plugin | members, as above | |
| instruction, hook, workflow | — | reported as "no native claude layout"; use `--target dir` |

`<base>` is `~/.claude` with `--scope user` (default) or `./.claude` with `--scope project`. `--path` overrides it.

### `--target copilot`

| Kind | Destination |
| --- | --- |
| skill | `.github/skills/<name>/` |
| agent | `.github/agents/<name>.agent.md` |
| instruction | `.github/instructions/<name>.instructions.md` |
| prompt | `.github/prompts/<name>.prompt.md` |
| hook | `.github/hooks/<name>/` (needs `--allow-exec`) |
| workflow | `.github/workflows/<name>.md` |
| plugin | members, as above |

The base is `./.github` in the current directory; `--path` overrides it.

### `--target dir --path DIR`

Copies the complete normalised item to `DIR/<kind-plural>/<namespace>.<name>/`, including `ananke.yaml` and
`dex.json`. Use it to vendor items into a repo, feed another harness, or review an item before installing it.

## Names on disk

Native targets use the plain item **name**. Skills require the folder name to match `name:` in `SKILL.md`.
If you install two items with the same name from different sources, the second overwrites the first. Check with
`dex search <name>` first.

## Licences travel with the item

- Folder items keep their own licence files and any `LICENSE.upstream` / `NOTICE.upstream`.
- Single-file items (agents, instructions, prompts, workflows) get a sibling `<file>.LICENSE` when the governing
  text came from outside the file.

Keep these files if you redistribute the installed items.

## Executable items

- Items with scripts are tagged `executes-code`. They install normally, but read the scripts before an agent
  runs them.
- **Hooks** run automatically on session events, so they are refused unless you pass `--allow-exec`:

```bash
dex install awesome-copilot/secrets-scanner --target copilot
# – hook:awesome-copilot/secrets-scanner: hook runs code — pass --allow-exec after reviewing it
dex install awesome-copilot/secrets-scanner --target copilot --allow-exec
```

## Updating and removing

Upgrade the package (`pip install -U dex-trove`) and run the same `dex install` again; destinations are replaced.
To remove an item, delete its folder or file. Dex keeps no install state of its own.

## Adapting across tools

Upstream items are written for a particular tool. When moving between tools:

- **Agent `tools:` lists** use the source tool's names (Copilot's `codebase`, `editFiles`, …). Claude Code
  ignores tool names it doesn't know. Adjust the frontmatter if the agent relies on specific tools.
- **Skills** follow the cross-tool Agent Skills spec and are the most portable kind.
- **Instructions** have no Claude Code equivalent. Reference the file from `CLAUDE.md` or wrap it in a skill.
