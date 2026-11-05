---
name: repo-context
description: "Understand a code repository using far fewer tokens: start from a small map, then use Ananke's outline, symbol and callers, which stay current with every edit, or repomix, Graphify, grep or a plain read, whichever measured cheapest for the question. Use before exploring or reading an unfamiliar or large repo, or when asked to save tokens or map a codebase."
license: MIT
---

# Repo context

Most of a repository is irrelevant to any one question. Spend tokens on the part that matters.

## Start with a map

```bash
ananke context map --project .     # usually under 2,000 tokens
ananke context status --project .  # which tools are ready, and how to get the others
```

If Ananke isn't installed (`pip install ananke-plexus`), list files with `git ls-files`, read the README and the manifest, and use `grep`.

## Then pick by question

Measured on a repository of about 790,000 tokens of source. Costs are tokens.

| Question | Use | Cost | Instead of |
| --- | --- | ---: | ---: |
| Where do I start? | `ananke context map` | 1,162 | 790,000 |
| What's in this big file? | `ananke context outline FILE` | 462 | 8,480 |
| The same, with signatures | `ananke context outline FILE --signatures` | 1,150 | 8,480 |
| One function | `ananke context symbol NAME` | 115 to 1,625 | 8,480 |
| Who calls this? | `ananke context callers NAME` | 130 to 191 | 167 with `grep`, 1,730 with Serena |
| What's in a small file (under about 1,000 tokens)? | Read it, or outline it first | 980, or 61 | |
| Many files at once | `ananke context pack --include 'src/**/*.py'` | 92,766 | 288,740 |
| How does it fit together? | Graphify's `GRAPH_REPORT.md` | 5,000 to 21,000 | not available otherwise |
| One concept across the graph | `graphify query "..."` or `graphify explain X` | 700 to 1,700 | many reads |
| How do several repositories connect? | `graphify merge-graphs` | varies | not available otherwise |

`callers` lists what it resolved first, then other mentions it found as text. Check those by hand when it matters, such as before a rename: names are inferred, not followed through types.

The lookups read Python, JavaScript and TypeScript. For anything else they say so: use `grep` and read.

## Rules that save the most

1. **Don't read a file to find something.** Outline it or search, then read the lines that matter.
2. **Read part of a big file,** by symbol or by line range.
3. **Never read `graphify-out/graph.json`:** it's hundreds of thousands of tokens. Read the report, or query it.
4. **Always scope a pack.** On a whole repository, docs dominate, and compression may save only 5%. Check what it says it left out.
5. **Limit command output:** `tail`, `cut`, `grep`, and quiet flags. A long log costs as much as a file.
6. **Start a new chat for a new task.** Everything said so far is sent with each turn, which is usually the biggest cost.
7. **Prefer one agent.** Each agent starts cold and re-reads what you already know.

## Stale answers

| Tool | Current? |
| --- | --- |
| `ananke context` map, outline, symbol, callers | Yes. Each checks for edits, new files and deletions, and rebuilds only if something changed. Nothing to run |
| repomix | Yes, packed when you ask. It doesn't update by itself |
| Serena | Yes, it reads the code each time |
| Graphify | **No.** Run `graphify update .` first; it needs no LLM. `ananke context status` says if the graph is stale |

## Using it by default in a project

```bash
ananke context enable --dry-run   # see what would change
ananke context enable             # detects the assistants this project uses
ananke context enable --client kiro --client copilot
ananke context disable            # removes exactly what was added
```

| Assistant | `--client` | Instructions go in |
| --- | --- | --- |
| Claude Code | `claude-code` | `CLAUDE.md`, plus a hook that loads the map each session |
| OpenAI Codex | `codex` | `AGENTS.md` |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` |
| Kiro | `kiro` | `.kiro/steering/ananke-context.md` |
| Cursor | `cursor` | `.cursor/rules/ananke-context.mdc` |
| Amazon Q | `amazon-q` | `.amazonq/rules/ananke-context.md` |

Ask before enabling a project: it changes files other people share.

## Optional tools

Everything above works without these.

**Serena** (GPL-3.0-or-later) is worth adding for languages Ananke doesn't read, references that follow types, or rename and symbol-level editing. It runs as its own MCP server and is never a dependency. Its default mode costs about 1,100 tokens per chat to connect; avoid `--agent-interface tools` (about 8,000) unless your client loads tools lazily. This keeps its usage ping and dashboard off:

```bash
claude mcp add --scope user serena --env SERENA_USAGE_REPORTING=false -- \
  uvx --python 3.12 --from serena-agent==2.1.0 serena start-mcp-server \
  --context claude-code --project-from-cwd --enable-web-dashboard false --open-web-dashboard false
uvx --python 3.12 --from serena-agent==2.1.0 serena project create . --language python
```

Without the project file, lookups quietly find nothing: symptoms are empty results, or "Active language servers: []".

**repomix**: `pip install "ananke-plexus[context]"`.

**Graphify** (Apache-2.0): `pip install graphifyy`, then `graphify update .`. List generated files such as `**/*.min.js` in `.graphifyignore`, or they take over its communities.
