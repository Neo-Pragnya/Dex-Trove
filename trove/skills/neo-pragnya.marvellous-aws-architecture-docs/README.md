# Marvellous AWS Architectures Docs

AWS-reference-style architecture diagrams **as code**: official AWS icons inside account, VPC and cluster boundaries,
numbered step badges with a numbered legend, an animation that walks the flow, "map so far" views that build the
system up stage by stage, editable draw.io output, and a shareable interactive HTML docs page.

![complete diagram](assets/previews/rag-chatbot.png)
![stage view: release 2](assets/previews/rag-chatbot-stage-2.png)
![concept diagram with cards](assets/previews/concept-cards.png)

## Quick start

```bash
python scripts/build_arch.py assets/examples/serverless_rag_chatbot.py --out /tmp/rag-docs --title "Serverless RAG chatbot"
open /tmp/rag-docs/index.html        # ▶ play the flow · step · build it up release by release
```

Write your own `arch_specs.py` (nodes on a grid, groups, numbered flows, optional stages) and run the same command.
See `SKILL.md` for the workflow and `references/` for the field reference, the layout playbook and integration notes.

* Python 3.10+, standard library only (Pillow only for `scripts/fetch_icons.py`).
* 126 icons included (`assets/icons/CATALOG.md`); add more with `scripts/fetch_icons.py --add key=aws/<category>/<icon>.png`.
* Icons: official AWS Architecture Icons (via the MIT-licensed `diagrams` package), Kubernetes community icons, and
  technology logos used only to identify the technology. See `assets/icons/SOURCE.md`.
