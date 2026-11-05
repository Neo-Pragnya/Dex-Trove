---
name: map-a-repository
description: "Understand and explain a whole code repository or a folder of notebooks with Dev Guru: an offline file or local web interface with a code map, end-to-end flows, an ERD, API routes, a CALM architecture, quality, coverage, CVEs and an explanation of each notebook, including code in %%writefile cells. Use when asked to map, explain, onboard to or review a repository or a course or research folder, to show how it connects, or to find its database, routes or vulnerabilities."
license: MIT
---

# Map a repository

Dev Guru reads a repository and shows how it works. Nothing in the repository is run, and nothing leaves your machine unless you ask for a CVE check.

```bash
pip install dev-guru
dev explore . -o map.html      # one offline file with every view
dev serve .                    # the same pages, live, with analysis and CVE checks a click away
```

## Which to use

| You want | Use |
| --- | --- |
| Something to read or hand to a colleague | `dev explore . -o map.html` |
| Real CVEs and fixes in that file | `dev explore . -o map.html --check-vulnerabilities`. It sends package names and versions to osv.dev |
| To publish it outside your team | `dev explore . -o public.html --profile public`, which keeps structure and counts |
| To keep looking as the code changes | `dev serve .` |
| A small map for an AI assistant | `dev context .`, usually under 2,000 tokens |

## Reading a new repository

Do these in order, and check each against what you know.

1. **Overview and Code map.** Do the components and folders look right? A folder under **Not connected** that should connect is the first thing to look into.
2. **One flow you can check by hand.** Open End-to-end flows and step through a route you know. If it's right, trust the others more. If a step's missing, the page's limits usually say why.
3. **API pathways.** Calls to routes that don't exist here are bugs, or a service in another repository.
4. **Data.** Compare the tables with your schema. Tables **Known only from use** have no model or SQL file here.
5. **Architecture.** It's inferred, so check it. To compare it from now on, save your own model at `.ananke/architecture/system.calm.json`, and the page lists what differs.
6. **Quality, Coverage, CVEs.** Coverage needs a report your tests produced. CVEs need you to ask. Until then they say unknown, which isn't zero and isn't clean.

## A folder of notebooks

Point it at the folder. Code in `%%writefile` cells counts as a file at that path, even if nobody has run the notebook, so its routes, tables and requirements appear on every page. The **Notebooks** page explains each one from its own headings: what it's for, what it covers, what it writes, what it builds on and what uses it. Executed copies aren't counted twice.

The explanation comes from the notebook's text, and nothing is generated, so a notebook with no headings has little to say. A path built at run time can't be followed, and the page says how many it skipped.

## When you report what you found

- Quote the file and line. Every table, route and step shows where it came from.
- Say what's inferred: links come from names and imports, not from running the code, so a call through a variable or a framework's magic can be missing.
- Say what's unknown. "Not checked" isn't "clean".
