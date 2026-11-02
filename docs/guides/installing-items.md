---
title: Installing items
description: Where each kind of item goes for Claude Code, GitHub Copilot and plain directories.
---

# Installing items

```bash
dex install REF... --target claude|copilot|dir [--scope user|project] [--path DIR] [--allow-exec] [--force]
```

`dex install` copies items out of the installed package into a tool's native layout. It never runs anything, and it
never replaces a file or folder it didn't write: see [Existing files are safe](#existing-files-are-safe). You can pass
several refs at once, and plugins expand to their members. To find what to install, see
[Finding capabilities](finding-capabilities.md).

## Targets

### `--target claude` (default)

| Kind | Destination | Notes |
| --- | --- | --- |
| skill | `<base>/skills/<name>/` | whole folder, minus Dex's `ananke.yaml`/`dex.json`; licence files included |
| agent | `<base>/agents/<name>.md` | entry file, adapted for Claude Code ([below](#agents-in-claude-code)), + `<name>.md.LICENSE` |
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

## Agents in Claude Code

Most agents in the trove were written for GitHub Copilot. Two of their frontmatter fields stop them from launching in
Claude Code as they are ([Claude Code's subagent reference](https://code.claude.com/docs/en/sub-agents)):

- **`tools`** lists Copilot or VS Code tool ids (`codebase`, `edit/editFiles`, `runCommands`). Claude Code expects
  its own tool names, and "if no entry in the list resolves to a tool, the subagent usually fails to launch".
- **`model`** names models like `GPT-4.1`. Claude Code accepts `sonnet`, `opus`, `haiku`, `fable`, a full Claude
  model ID, or `inherit`.

So for `--target claude`, `dex install` rewrites those two fields **in the installed copy**. The trove keeps the
upstream file byte-for-byte, and the agent's body (its instructions) is never changed.

| Copilot / VS Code tool ids | Claude Code tools |
| --- | --- |
| `read`, `codebase`, `search/codebase`, `readFile` | `Read`, `Grep`, `Glob` |
| `search`, `searchResults`, `usages`, `findTestFiles`, `search/*` | `Grep`, `Glob` |
| `edit`, `editFiles`, `edit/editFiles`, `new`, `edit/createFile` | `Edit`, `Write` |
| `runCommands`, `execute`, `runInTerminal`, `terminalLastCommand`, `runTests`, `testFailure`, `runTasks` | `Bash` |
| `fetch`, `web/fetch` | `WebFetch` |
| `web` | `WebFetch`, `WebSearch` |

- Ids with no Claude Code equivalent are **dropped and reported**: IDE panels (`problems`, `changes`), VS Code APIs,
  extensions, and MCP servers named the Copilot way. Nothing is guessed.
- If an agent listed tools and **none** of them maps, it gets read-only `Read, Grep, Glob`. Removing `tools`
  instead would give the agent every tool, which is more than its author asked for.
- Claude model names are kept (`sonnet`, `claude-opus-5-5`) or normalised (`Claude Sonnet 4.5` → `sonnet`).
  Anything else is removed, so Claude Code uses its default.
- The adapted file starts with a `# dex-trove: adapted for Claude Code…` comment, and `dex install` prints each
  change:

```console
$ dex install awesome-copilot/accessibility --scope project
✓ agent:awesome-copilot/accessibility → .claude/agents/accessibility.md
    adapted: dropped 6 tool id(s) with no Claude equivalent: changes, extensions, githubRepo, openSimpleBrowser, problems, vscodeAPI
    adapted: dropped model 'GPT-4.1' (not a Claude model; Claude Code picks the default)
```

Skills need no adaptation: Claude Code reads `SKILL.md` as is. Agents for `--target copilot` are copied unchanged.

## Existing files are safe

Native targets use the plain item **name**, so a trove item can share a name with something you already have.
`dex install` replaces a destination only when:

- it doesn't exist yet;
- Dex installed it and it hasn't been edited since (recorded in `<base>/.dex-trove-installed.json`, with a SHA-256
  for each destination); or
- it's byte-identical to what Dex would write (a copy made by an older Dex, before the record existed).

Anything else is left alone. The command reports why and exits 1 if nothing was installed:

```console
$ dex install neo-pragnya/living-diagrams --scope project
– skill:neo-pragnya/living-diagrams: .claude/skills/living-diagrams already exists and wasn't installed by Dex (or was edited since) — pass --force to replace it
✗ nothing was installed
```

Pass `--force` to replace it. A **symlinked** destination (for example a skill you link in from your own
repository) is never followed: `--force` replaces the link itself and leaves its target untouched.

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
dex install awesome-copilot/tool-guardian --target copilot
# – hook:awesome-copilot/tool-guardian: hook runs code — pass --allow-exec after reviewing it
dex install awesome-copilot/tool-guardian --target copilot --allow-exec
```

## Updating and removing

Upgrade the package (`pip install -U dex-trove`) and run the same `dex install` again. Copies Dex installed, and
that you haven't edited, are replaced; edited ones are kept unless you pass `--force`. To remove an item, delete its
folder or file. Dex's only install state is `.dex-trove-installed.json` in the target base, and it's safe to delete
(Dex then just won't recognise its earlier copies as its own).

## Adapting across tools

Upstream items are written for a particular tool. When moving between tools:

- **Agent `tools:` and `model:`** use the source tool's names. For Claude Code, `dex install` translates them
  ([Agents in Claude Code](#agents-in-claude-code)); for other harnesses, use `--target dir` and adjust them yourself.
- **Skills** follow the cross-tool Agent Skills spec and are the most portable kind.
- **Instructions** have no Claude Code equivalent. Reference the file from `CLAUDE.md` or wrap it in a skill.
