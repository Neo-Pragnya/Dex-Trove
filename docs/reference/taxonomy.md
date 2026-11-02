---
title: Taxonomy reference
description: Every facet and value Dex Trove uses to classify items, with definitions and aliases.
---

# Taxonomy reference

Taxonomy version **1.0.0**. Generated from `src/dex_trove/taxonomy/ontology.yaml` by
`dex facets doc`; don't edit by hand. How the facets are filled and queried:
[Finding capabilities](../guides/finding-capabilities.md).

Aliases are other spellings that mean the same value: `dex search --role test-engineer` is
`--role qa-engineer`. Item counts are for the trove this page was generated with.

## Kind (`kind`)

What is it? One value per item. Set from the catalog.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `skill` | 468 | A reusable procedure or body of know-how an agent loads on demand for one kind of task. | — |
| `agent` | 220 | A persona with its own objective and tool scope that a host can delegate work to. | — |
| `instruction` | 189 | Persistent guidance (style, rules, conventions) applied broadly, often scoped to file globs. | — |
| `prompt` | 0 | A reusable invocation: a slash command or prompt file run on request. | — |
| `workflow` | 8 | An ordered, multi-step process with gates, inputs and outputs. | — |
| `hook` | 7 | A handler that runs on a host lifecycle event (before a tool call, at session end). | — |
| `plugin` | 72 | A distributable bundle of other artifacts that installs as a set. | — |

## Task (`task`)

What job does it do? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `ideate` | 4 | Generate, compare and shape ideas before committing to requirements. | `brainstorm`, `ideation` |
| `elicit-requirements` | 28 | Interview stakeholders and capture needs, constraints and acceptance criteria. | `requirements`, `prd`, `user-stories` |
| `write-spec` | 41 | Produce a spec or plan that later steps implement and verify against. | `spec`, `specification`, `write-plan`, `planning` |
| `design-architecture` | 76 | Decide structure, boundaries, components and their trade-offs. | `architecture`, `system-design`, `adr` |
| `design-api` | 18 | Define endpoints, schemas and contracts for an API. | `api-design`, `openapi` |
| `implement` | 101 | Write production code for a feature or change. | `implementation`, `coding`, `code-generation` |
| `refactor` | 95 | Restructure existing code without changing behaviour, or upgrade it to newer platforms. | `refactoring`, `modernize`, `modernise`, `migration`, `upgrade` |
| `review-code` | 33 | Assess a change for correctness, quality and risk, and give actionable feedback. | `code-review`, `pr-review`, `reviewing` |
| `write-tests` | 113 | Author unit, integration or end-to-end tests. | `testing`, `tests`, `unit-tests` |
| `plan-tests` | 12 | Decide what to test, at which level, and how coverage relates to risk. | `test-plan`, `test-strategy` |
| `generate-api-tests` | 0 | Create tests that exercise an API's contract and failure modes. | `api-tests`, `api-testing`, `contract-tests` |
| `debug` | 64 | Find and fix the root cause of a failure. | `debugging`, `troubleshoot`, `root-cause` |
| `debug-ci` | 12 | Diagnose failing builds, pipelines and deployments. | `ci-triage`, `pipeline-failure-analysis`, `jenkins-triage` |
| `security-review` | 55 | Find vulnerabilities, threats and unsafe patterns, and propose mitigations. | `security-audit`, `threat-model`, `appsec` |
| `optimise-performance` | 80 | Measure and improve speed, memory or cost. | `performance`, `optimization`, `optimisation` |
| `write-docs` | 32 | Produce READMEs, guides, API references or other written documentation. | `documentation`, `docs`, `technical-writing` |
| `visualize` | 28 | Draw diagrams, graphs or visual explanations of a system. | `diagram`, `diagrams`, `visualise`, `visualize-graph` |
| `design-ui` | 38 | Design layouts, visual style, interaction and front-end look and feel. | `ui-design`, `ux`, `frontend-design` |
| `audit-accessibility` | 19 | Check and improve accessibility against WCAG and assistive technology. | `accessibility`, `a11y`, `wcag` |
| `deploy` | 69 | Ship software: build, package, release and deploy. | `release`, `deployment`, `publish`, `ci-cd` |
| `provision-infrastructure` | 49 | Define and manage cloud or on-prem infrastructure, usually as code. | `iac`, `infrastructure-as-code`, `cloud` |
| `operate` | 50 | Monitor, trace and respond to incidents in running systems. | `observability`, `monitoring`, `incident-response` |
| `analyse-data` | 16 | Explore, query and explain data sets. | `data-analysis`, `analytics`, `sql-queries` |
| `build-ml` | 31 | Train, evaluate or integrate machine-learning models, LLMs and RAG. | `machine-learning`, `ml`, `llm`, `rag` |
| `build-agents` | 48 | Create agents, skills, MCP servers or other capabilities for AI agents. | `agent-development`, `mcp`, `skill-authoring` |
| `manage-work` | 6 | Plan, track and coordinate work items, tickets and projects. | `project-management`, `tickets`, `planning-work` |
| `use-git` | 35 | Branch, commit, merge and manage repositories and pull requests. | `git`, `version-control` |
| `verify` | 30 | Prove that work is complete and correct with evidence before claiming success. | `verification`, `quality-gate` |
| `reflect` | 21 | Retrospectives, lessons learned, knowledge capture and coaching. | `retrospective`, `learning`, `mentoring`, `onboarding` |

## Methodology (`methodology`)

Which way of working does it support? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `sdlc` | 10 | Software Development Life Cycle: the human-driven requirements, design, build, test, release and operate loop. | `software-development-lifecycle` |
| `adlc` | 18 | Agent Development Life Cycle (as in Ananke Plexus): software built by agents and humans together, driven by specs, policies, explicit context assembly, gates and execution evidence. Overlaps SDLC; not an alias of it. | `agent-development-lifecycle`, `agentic-development` |
| `sdd` | 5 | Specifications are the source of truth; plans, code and tests trace back to them. | `spec-driven-development`, `spec-driven` |
| `tdd` | 10 | Write a failing test first, make it pass, then refactor. | `test-driven-development`, `red-green-refactor` |
| `bdd` | 1 | Behaviour described as Given/When/Then scenarios shared by business and engineering. | `behavior-driven-development`, `behaviour-driven-development`, `gherkin` |
| `atdd` | 1 | Acceptance tests agreed up front define done. | `acceptance-test-driven-development` |
| `ddd` | 1 | Model software around the business domain: bounded contexts, aggregates, ubiquitous language. | `domain-driven-design` |
| `devops` | 29 | Development and operations as one loop: automation, CI/CD, shared ownership. | `ci-cd` |
| `sre` | 2 | Site reliability engineering: SLOs, error budgets, incident response, toil reduction. | `site-reliability-engineering` |
| `mlops` | 0 | Operating machine-learning and LLM systems: tracking, evaluation, deployment, monitoring. | `llmops` |
| `dataops` | 0 | Automated, tested, observable data pipelines. | — |

## Lifecycle phase (`phase`)

Where in the lifecycle is it useful? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `discovery` | 40 | Understanding the problem, users and options. | `ideation`, `research` |
| `requirements` | 54 | Capturing what must be built and how success is judged. | `specification` |
| `design` | 136 | Architecture, API and UI design decisions. | `architecture` |
| `implementation` | 253 | Writing and changing code. | `build`, `coding`, `development` |
| `testing` | 115 | Authoring and running tests. | `qa`, `test` |
| `verification` | 161 | Reviewing and proving correctness before release. | `review`, `quality` |
| `deployment` | 74 | Releasing and shipping. | `release`, `delivery` |
| `operations` | 62 | Running, monitoring and supporting software in production. | `ops`, `production` |
| `retrospective` | 4 | Looking back: lessons, knowledge capture, improvement. | `retro`, `reflection` |

## Role (`role`)

Who typically uses it? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `product-manager` | 12 | Owns the problem, requirements and priorities. | `pm`, `product-owner` |
| `architect` | 79 | Owns structure, boundaries and technical direction. | `solution-architect`, `software-architect` |
| `developer` | 301 | Writes and changes code. | `engineer`, `software-engineer`, `programmer` |
| `qa-engineer` | 117 | Plans and performs testing and quality assurance. | `test-engineer`, `quality-engineer`, `tester` |
| `security-engineer` | 58 | Finds and fixes security risk. | `appsec`, `security` |
| `devops-engineer` | 99 | Runs pipelines, infrastructure and production systems. | `sre`, `platform-engineer`, `ops` |
| `data-scientist` | 26 | Builds analyses, models and ML or LLM systems. | `ml-engineer`, `data-analyst` |
| `data-engineer` | 1 | Builds data pipelines and stores. | — |
| `designer` | 41 | Shapes user experience and visual design. | `ux-designer`, `ui-designer` |
| `technical-writer` | 28 | Writes documentation and guides. | `writer`, `docs-author` |
| `reviewer` | 90 | Reviews others' changes. | `code-reviewer` |
| `release-manager` | 6 | Coordinates releases and their gates. | — |
| `learner` | 19 | Someone learning a technology or practice. | `student`, `educator`, `mentor` |

## Domain (`domain`)

Which area of a system does it concern? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `api` | 81 | Web and service APIs and their contracts. | `rest`, `graphql` |
| `frontend` | 84 | Browser and UI code. | `web-ui`, `ui` |
| `backend` | 22 | Server-side services and business logic. | `server` |
| `mobile` | 19 | iOS, Android and cross-platform apps. | `ios`, `android` |
| `infrastructure` | 118 | Cloud resources, networks, containers and IaC. | `cloud`, `iac` |
| `data` | 61 | Databases, data pipelines and analytics. | `database`, `data-engineering` |
| `ml-ai` | 114 | Machine learning, LLMs, agents and AI systems. | `ai`, `ml`, `llm` |
| `security` | 68 | Application, supply-chain and infrastructure security. | `appsec` |
| `observability` | 26 | Logs, metrics, traces and monitoring. | `monitoring` |
| `documentation` | 31 | Docs sites, READMEs and written knowledge. | `docs` |
| `developer-tooling` | 66 | Editors, CLIs, build tools, Git and the agent harness itself. | `devtools`, `tooling` |

## Language (`language`)

Which programming language does it apply to? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `python` | 58 | Python. | `py` |
| `typescript` | 39 | TypeScript. | `ts` |
| `javascript` | 47 | JavaScript and Node.js. | `js`, `nodejs`, `node` |
| `java` | 36 | Java. | — |
| `kotlin` | 12 | Kotlin. | — |
| `csharp` | 75 | C# and .NET. | `c-sharp`, `dotnet`, `cs` |
| `go` | 6 | Go. | `golang` |
| `rust` | 6 | Rust. | — |
| `cpp` | 5 | C and C++. | `c`, `c++` |
| `php` | 9 | PHP. | — |
| `ruby` | 5 | Ruby. | — |
| `swift` | 5 | Swift. | — |
| `sql` | 28 | SQL. | — |
| `shell` | 9 | Bash, zsh and PowerShell scripts. | `bash`, `powershell`, `zsh` |

## Framework or tool (`framework`)

Which technology does it target? Any number of values.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `fastapi` | 1 | FastAPI. | — |
| `django` | 0 | Django. | — |
| `pytest` | 3 | pytest. | — |
| `playwright` | 13 | Playwright browser testing. | `playwright-python`, `playwright-js` |
| `react` | 42 | React. | `reactjs` |
| `angular` | 7 | Angular. | — |
| `vue` | 7 | Vue. | `vuejs` |
| `nextjs` | 6 | Next.js. | `next` |
| `astro` | 3 | Astro. | — |
| `spring` | 14 | Spring and Spring Boot. | `spring-boot` |
| `dotnet` | 51 | .NET and ASP.NET. | `aspnet` |
| `terraform` | 20 | Terraform. | — |
| `bicep` | 13 | Azure Bicep. | — |
| `kubernetes` | 6 | Kubernetes and Helm. | `k8s`, `helm` |
| `docker` | 17 | Docker and containers. | `containers` |
| `github-actions` | 15 | GitHub Actions workflows. | — |
| `azure` | 67 | Microsoft Azure services. | — |
| `aws` | 16 | Amazon Web Services. | `amazon-web-services` |
| `mcp` | 99 | Model Context Protocol servers and clients. | `model-context-protocol` |
| `dbt` | 0 | dbt. | — |
| `pyspark` | 4 | Apache Spark and PySpark. | `spark` |

## Platform (`platform`)

Where can Dex install it natively? Any number of values. Set from where `dex install` can place it.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `claude-code` | 760 | Installs into .claude/ (skills, agents, commands). | — |
| `github-copilot` | 964 | Installs into .github/ (skills, agents, instructions, prompts, hooks, workflows). | — |
| `ananke` | 964 | Registers in an Ananke registry (dex ananke sync, or [troves] in Ananke). | — |

## Maturity (`maturity`)

How established is it? One value per item.

| Value | Items | Definition | Aliases |
| --- | --- | --- | --- |
| `stable` | 7 | Used and maintained; changes are versioned. | — |
| `beta` | 0 | Usable; may still change. | — |
| `experimental` | 0 | Early; expect gaps. | — |
| `deprecated` | 0 | Kept for existing users; prefer its replacement. | — |
| `unknown` | 957 | The source doesn't say. Most upstream items. | — |
