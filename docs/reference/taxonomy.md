---
title: Taxonomy reference
description: Every facet and value Dex Trove uses to classify items, with definitions and aliases.
---

# Taxonomy reference

Taxonomy version **1.1.0**. Generated from `src/dex_trove/taxonomy/ontology.yaml` by
`dex facets doc`; don't edit by hand. How the facets are filled and queried:
[Finding capabilities](../guides/finding-capabilities.md).

Aliases are other spellings that mean the same value: `dex search --role test-engineer` is
`--role qa-engineer`. Item counts are for the trove this page was generated with.

## Kind (`kind`)

What is it? One value per item. Set from the catalog.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `skill` | 900 | A reusable procedure or body of know-how an agent loads on demand for one kind of task. | — |
| `agent` | 522 | A persona with its own objective and tool scope that a host can delegate work to. | — |
| `instruction` | 189 | Persistent guidance (style, rules, conventions) applied broadly, often scoped to file globs. | — |
| `prompt` | 9 | A reusable invocation: a slash command or prompt file run on request. | — |
| `workflow` | 8 | An ordered, multi-step process with gates, inputs and outputs. | — |
| `hook` | 7 | A handler that runs on a host lifecycle event (before a tool call, at session end). | — |
| `plugin` | 72 | A distributable bundle of other artifacts that installs as a set. | — |

## Task (`task`)

What job does it do? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `ideate` | 8 | Generate, compare and shape ideas before committing to requirements. | `brainstorm`, `ideation` |
| `elicit-requirements` | 47 | Interview stakeholders and capture needs, constraints and acceptance criteria. | `requirements`, `prd`, `user-stories` |
| `write-spec` | 59 | Produce a spec or plan that later steps implement and verify against. | `spec`, `specification`, `write-plan`, `planning` |
| `design-architecture` | 151 | Decide structure, boundaries, components and their trade-offs. | `architecture`, `system-design`, `adr` |
| `design-api` | 32 | Define endpoints, schemas and contracts for an API. | `api-design`, `openapi` |
| `implement` | 209 | Write production code for a feature or change. | `implementation`, `coding`, `code-generation` |
| `refactor` | 138 | Restructure existing code without changing behaviour, or upgrade it to newer platforms. | `refactoring`, `modernize`, `modernise`, `migration`, `upgrade` |
| `review-code` | 51 | Assess a change for correctness, quality and risk, and give actionable feedback. | `code-review`, `pr-review`, `reviewing` |
| `write-tests` | 177 | Author unit, integration or end-to-end tests. | `testing`, `tests`, `unit-tests` |
| `plan-tests` | 23 | Decide what to test, at which level, and how coverage relates to risk. | `test-plan`, `test-strategy` |
| `generate-api-tests` | 1 | Create tests that exercise an API's contract and failure modes. | `api-tests`, `api-testing`, `contract-tests` |
| `debug` | 108 | Find and fix the root cause of a failure. | `debugging`, `troubleshoot`, `root-cause` |
| `debug-ci` | 15 | Diagnose failing builds, pipelines and deployments. | `ci-triage`, `pipeline-failure-analysis`, `jenkins-triage` |
| `security-review` | 101 | Find vulnerabilities, threats and unsafe patterns, and propose mitigations. | `security-audit`, `threat-model`, `appsec` |
| `optimise-performance` | 218 | Measure and improve speed, memory or cost. | `performance`, `optimization`, `optimisation` |
| `write-docs` | 49 | Produce READMEs, guides, API references or other written documentation. | `documentation`, `docs`, `technical-writing` |
| `visualize` | 52 | Draw diagrams, graphs or visual explanations of a system. | `diagram`, `diagrams`, `visualise`, `visualize-graph` |
| `design-ui` | 64 | Design layouts, visual style, interaction and front-end look and feel. | `ui-design`, `ux`, `frontend-design` |
| `audit-accessibility` | 33 | Check and improve accessibility against WCAG and assistive technology. | `accessibility`, `a11y`, `wcag` |
| `deploy` | 151 | Ship software: build, package, release and deploy. | `release`, `deployment`, `publish`, `ci-cd` |
| `provision-infrastructure` | 98 | Define and manage cloud or on-prem infrastructure, usually as code. | `iac`, `infrastructure-as-code`, `cloud` |
| `operate` | 112 | Monitor, trace and respond to incidents in running systems. | `observability`, `monitoring`, `incident-response` |
| `analyse-data` | 65 | Explore, query and explain data sets. | `data-analysis`, `analytics`, `sql-queries` |
| `build-ml` | 88 | Train, evaluate or integrate machine-learning models, LLMs and RAG. | `machine-learning`, `ml`, `llm`, `rag` |
| `build-agents` | 56 | Create agents, skills, MCP servers or other capabilities for AI agents. | `agent-development`, `mcp`, `skill-authoring` |
| `manage-work` | 15 | Plan, track and coordinate work items, tickets and projects. | `project-management`, `tickets`, `planning-work` |
| `use-git` | 50 | Branch, commit, merge and manage repositories and pull requests. | `git`, `version-control` |
| `verify` | 51 | Prove that work is complete and correct with evidence before claiming success. | `verification`, `quality-gate` |
| `reflect` | 35 | Retrospectives, lessons learned, knowledge capture and coaching. | `retrospective`, `learning`, `mentoring`, `onboarding` |

## Methodology (`methodology`)

Which way of working does it support? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `sdlc` | 14 | Software Development Life Cycle: the human-driven requirements, design, build, test, release and operate loop. | `software-development-lifecycle` |
| `adlc` | 20 | Agent Development Life Cycle (as in Ananke Plexus): software built by agents and humans together, driven by specs, policies, explicit context assembly, gates and execution evidence. Overlaps SDLC; not an alias of it. | `agent-development-lifecycle`, `agentic-development` |
| `sdd` | 6 | Specifications are the source of truth; plans, code and tests trace back to them. | `spec-driven-development`, `spec-driven` |
| `tdd` | 12 | Write a failing test first, make it pass, then refactor. | `test-driven-development`, `red-green-refactor` |
| `bdd` | 2 | Behaviour described as Given/When/Then scenarios shared by business and engineering. | `behavior-driven-development`, `behaviour-driven-development`, `gherkin` |
| `atdd` | 1 | Acceptance tests agreed up front define done. | `acceptance-test-driven-development` |
| `ddd` | 2 | Model software around the business domain: bounded contexts, aggregates, ubiquitous language. | `domain-driven-design` |
| `devops` | 44 | Development and operations as one loop: automation, CI/CD, shared ownership. | `ci-cd` |
| `sre` | 5 | Site reliability engineering: SLOs, error budgets, incident response, toil reduction. | `site-reliability-engineering` |
| `mlops` | 8 | Operating machine-learning and LLM systems: tracking, evaluation, deployment, monitoring. | `llmops` |
| `dataops` | 5 | Automated, tested, observable data pipelines. | — |

## Lifecycle phase (`phase`)

Where in the lifecycle is it useful? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `discovery` | 97 | Understanding the problem, users and options. | `ideation`, `research` |
| `requirements` | 82 | Capturing what must be built and how success is judged. | `specification` |
| `design` | 271 | Architecture, API and UI design decisions. | `architecture` |
| `implementation` | 395 | Writing and changing code. | `build`, `coding`, `development` |
| `testing` | 173 | Authoring and running tests. | `qa`, `test` |
| `verification` | 267 | Reviewing and proving correctness before release. | `review`, `quality` |
| `deployment` | 165 | Releasing and shipping. | `release`, `delivery` |
| `operations` | 146 | Running, monitoring and supporting software in production. | `ops`, `production` |
| `retrospective` | 8 | Looking back: lessons, knowledge capture, improvement. | `retro`, `reflection` |

## Role (`role`)

Who typically uses it? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `product-manager` | 22 | Owns the problem, requirements and priorities. | `pm`, `product-owner` |
| `architect` | 165 | Owns structure, boundaries and technical direction. | `solution-architect`, `software-architect` |
| `developer` | 499 | Writes and changes code. | `engineer`, `software-engineer`, `programmer` |
| `qa-engineer` | 177 | Plans and performs testing and quality assurance. | `test-engineer`, `quality-engineer`, `tester` |
| `security-engineer` | 102 | Finds and fixes security risk. | `appsec`, `security` |
| `devops-engineer` | 218 | Runs pipelines, infrastructure and production systems. | `sre`, `platform-engineer`, `ops` |
| `data-scientist` | 71 | Builds analyses, models and ML or LLM systems. | `ml-engineer`, `data-analyst` |
| `data-engineer` | 9 | Builds data pipelines and stores. | — |
| `designer` | 66 | Shapes user experience and visual design. | `ux-designer`, `ui-designer` |
| `technical-writer` | 44 | Writes documentation and guides. | `writer`, `docs-author` |
| `reviewer` | 135 | Reviews others' changes. | `code-reviewer` |
| `release-manager` | 9 | Coordinates releases and their gates. | — |
| `learner` | 44 | Someone learning a technology or practice. | `student`, `educator`, `mentor` |

## Domain (`domain`)

Which area of a system does it concern? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `api` | 176 | Web and service APIs and their contracts. | `rest`, `graphql` |
| `frontend` | 119 | Browser and UI code. | `web-ui`, `ui` |
| `backend` | 105 | Server-side services and business logic. | `server` |
| `mobile` | 31 | iOS, Android and cross-platform apps. | `ios`, `android` |
| `infrastructure` | 339 | Cloud resources, networks, containers and IaC. | `cloud`, `iac` |
| `data` | 96 | Databases, data pipelines and analytics. | `database`, `data-engineering` |
| `ml-ai` | 184 | Machine learning, LLMs, agents and AI systems. | `ai`, `ml`, `llm` |
| `security` | 136 | Application, supply-chain and infrastructure security. | `appsec` |
| `observability` | 65 | Logs, metrics, traces and monitoring. | `monitoring` |
| `documentation` | 49 | Docs sites, READMEs and written knowledge. | `docs` |
| `developer-tooling` | 111 | Editors, CLIs, build tools, Git and the agent harness itself. | `devtools`, `tooling` |

## Language (`language`)

Which programming language does it apply to? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `python` | 144 | Python. | `py` |
| `typescript` | 67 | TypeScript. | `ts` |
| `javascript` | 82 | JavaScript and Node.js. | `js`, `nodejs`, `node` |
| `java` | 68 | Java. | — |
| `kotlin` | 13 | Kotlin. | — |
| `csharp` | 111 | C# and .NET. | `c-sharp`, `dotnet`, `cs` |
| `go` | 8 | Go. | `golang` |
| `rust` | 18 | Rust. | — |
| `cpp` | 10 | C and C++. | `c`, `c++` |
| `php` | 12 | PHP. | — |
| `ruby` | 7 | Ruby. | — |
| `swift` | 7 | Swift. | — |
| `sql` | 38 | SQL. | — |
| `shell` | 20 | Bash, zsh and PowerShell scripts. | `bash`, `powershell`, `zsh` |

## Framework or tool (`framework`)

Which technology does it target? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `fastapi` | 6 | FastAPI. | — |
| `django` | 3 | Django. | — |
| `pytest` | 3 | pytest. | — |
| `playwright` | 16 | Playwright browser testing. | `playwright-python`, `playwright-js` |
| `react` | 53 | React. | `reactjs` |
| `angular` | 10 | Angular. | — |
| `vue` | 9 | Vue. | `vuejs` |
| `nextjs` | 8 | Next.js. | `next` |
| `astro` | 3 | Astro. | — |
| `spring` | 18 | Spring and Spring Boot. | `spring-boot` |
| `dotnet` | 86 | .NET and ASP.NET. | `aspnet` |
| `terraform` | 28 | Terraform. | — |
| `bicep` | 19 | Azure Bicep. | — |
| `kubernetes` | 14 | Kubernetes and Helm. | `k8s`, `helm` |
| `docker` | 47 | Docker and containers. | `containers` |
| `github-actions` | 16 | GitHub Actions workflows. | — |
| `azure` | 230 | Microsoft Azure services. | — |
| `aws` | 25 | Amazon Web Services. | `amazon-web-services` |
| `mcp` | 119 | Model Context Protocol servers and clients. | `model-context-protocol` |
| `dbt` | 1 | dbt. | — |
| `pyspark` | 7 | Apache Spark and PySpark. | `spark` |

## Platform (`platform`)

Where can Dex install it natively? Any number of values. Set from where `dex install` can place it.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `claude-code` | 1503 | Installs into .claude/ (skills, agents, commands). | — |
| `github-copilot` | 1707 | Installs into .github/ (skills, agents, instructions, prompts, hooks, workflows). | — |
| `ananke` | 1707 | Registers in an Ananke registry (dex ananke sync, or [troves] in Ananke). | — |

## Needs (`needs`)

What must be installed for it to run? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `text-only` | 1469 | Only Markdown and data: the agent reads it; nothing runs. | — |
| `python` | 188 | Bundles Python scripts or a Python project file. | — |
| `node` | 28 | Bundles JavaScript or TypeScript, or a package.json. | — |
| `shell` | 29 | Bundles sh, bash or zsh scripts. | — |
| `powershell` | 19 | Bundles PowerShell scripts. | — |
| `windows-cmd` | 1 | Bundles .bat or .cmd scripts. | — |
| `docker` | 0 | Bundles a Dockerfile or a Compose file. | — |

## Maturity (`maturity`)

How established is it? One value per item.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `stable` | 7 | Used and maintained; changes are versioned. | — |
| `beta` | 4 | Usable; may still change. | — |
| `experimental` | 0 | Early; expect gaps. | — |
| `deprecated` | 0 | Kept for existing users; prefer its replacement. | — |
| `unknown` | 1696 | The source doesn't say. Most upstream items. | — |
