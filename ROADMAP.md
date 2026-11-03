# Roadmap

What's planned for [Dex Trove](https://pypi.org/project/dex-trove/). Release notes for each version are in
[CHANGELOG.md](CHANGELOG.md). Plans change; this says what's intended, and nothing here is promised until it's released.

## Now: what Dev Guru needs

- A skill for mapping a repository with Dev Guru, released once the Ananke operation it wraps is out.
- The capability matrix naming the new Ananke operations: repository analysis, data model and API pathways.

## Next

- Wrapper skills for capabilities, each released with its Ananke operation.
- Evaluating the matrix's candidate items against golden tasks, starting with the highest-priority capabilities.
- A comparison of the ingested frameworks: Superpowers, BMAD, Spec Kit and Impeccable.
- A generator that turns a project template into a skill.

## Known gaps

- `skill:bmad-method/bmad` has a version regex that a crafted version string can hang. The fix belongs upstream.
- Six capabilities have no item covering them: multi-repository topology, SAS modernisation, Jenkins triage, Jenkins trigger, Kibana
  dashboards and BPMN design.
- GST and Acuta, named in the plan, have no known upstream repository.
