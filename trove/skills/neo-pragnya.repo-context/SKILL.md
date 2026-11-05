---
name: repo-context
description: "Understand a code repository using far fewer tokens: start from a small map, then use Serena, repomix, Graphify, grep or a plain read, whichever measured cheapest for the question. Use before exploring or reading an unfamiliar or large repo, or when asked to save tokens or map a codebase."
license: MIT
---

# Repo context

Most of a repository is irrelevant to any one question. Spend tokens on the part that matters.

## Start with a map

```bash
ananke context map --project .     # usually under 2,000 tokens; rebuilds when the code changes
ananke context status --project .  # which tools are ready, and how to get the others
```

If Ananke isn't installed (`pip install ananke-plexus`), list files with `git ls-files`, and read the README and the manifest.

## Then pick by question

Measured on a repository of about 790,000 tokens of source. Costs are tokens.

| Question | Use | Cost | Instead of |
| --- | --- | ---: | ---: |
| Where do I start? | `ananke context map` | 900 | 790,000 |
| What's in this big file? | Serena `get_symbols_overview` | 277 | 8,138 |
| One function from a big file | Serena `find_symbol` with the body | 4,427 | 8,138 |
| Who calls this? | `grep -n`, then read what matters | 167 | 1,730 with Serena references |
| What's in this small file (under about 1,000 tokens)? | Read it | 980 | 1,191 with Serena |
| Many files at once | `ananke context pack --include 'src/**/*.py'` | 92,766 | 288,740 |
| How does it fit together? | Graphify's `GRAPH_REPORT.md` | 5,000 to 21,000 | not available otherwise |
| One concept across the graph | `graphify query "..."` or `graphify explain X` | 700 to 1,700 | many reads |
| How do several repositories connect? | `graphify merge-graphs` | varies | not available otherwise |

## Rules that save the most

1. **Don't read a file to find something.** Search, then read the lines that matter.
2. **Read part of a big file,** by symbol or by line range.
3. **Never read `graphify-out/graph.json`:** it's hundreds of thousands of tokens. Read the report, or query it.
4. **Always scope a pack.** On a whole repository, docs dominate, and compression may save only 5%.
5. **Limit command output:** `tail`, `cut`, `grep`, and quiet flags. A long log costs as much as a file.
6. **Start a new chat for a new task.** Everything said so far is sent with each turn, which is usually the biggest cost.
7. **Prefer one agent.** Each agent starts cold and re-reads what you already know.

## Stale answers

| Tool | Current? |
| --- | --- |
| `ananke context map` | Yes, it rebuilds when the sources change |
| Serena | Yes, it reads the code each time |
| repomix | Yes, packed when you ask |
| Graphify | **No.** Run `graphify update .` first; it needs no LLM. `ananke context status` says if the graph is stale |

## Setting up

**Serena** (GPL-3.0-or-later) runs as its own MCP server. Its default mode costs about 1,100 tokens to connect. Avoid
`--agent-interface tools` (about 8,000) unless your client loads tools lazily.

```bash
claude mcp add --scope user serena -- uvx --python 3.12 --from serena-agent==2.1.0 serena start-mcp-server \
  --context claude-code --project-from-cwd --enable-web-dashboard false --open-web-dashboard false
uvx --python 3.12 --from serena-agent==2.1.0 serena project create . --language python
```

Without the project file, lookups quietly find nothing: symptoms are empty results, or "Active language servers: []".

**repomix** (MIT): `pip install "ananke-plexus[context]"`.

**Graphify** (Apache-2.0): `pip install graphifyy`, then `graphify update .`. List generated files such as `**/*.min.js` in
`.graphifyignore`, or they take over its communities.
