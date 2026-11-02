"""The ``dex`` command line (DESIGN.md §8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from dex_trove import __version__, catalog, licenses
from dex_trove import sources as sources_mod
from dex_trove.paths import KIND_DIRS, repo_root, trove_root

app = typer.Typer(
    help="Dex Trove — a trove of dexterities: licence-clean skills, agents and plugins for your agents.",
    no_args_is_help=True,
)
ananke_app = typer.Typer(help="Ananke integration.", no_args_is_help=True)
docs_app = typer.Typer(help="Docs site helpers.", no_args_is_help=True)
app.add_typer(ananke_app, name="ananke")
app.add_typer(docs_app, name="docs")
console = Console()
err = Console(stderr=True)

KindOpt = Annotated[str | None, typer.Option("--kind", "-k", help=f"One of: {', '.join(KIND_DIRS)}")]
SourceOpt = Annotated[str | None, typer.Option("--source", "-s", help="Source id / namespace")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable output")]


def _need_repo() -> Path:
    root = repo_root()
    if root is None:
        err.print("[red]This command needs a Dex-Trove checkout (sources.yaml not found).[/red]")
        raise typer.Exit(2)
    return root


def _version_cb(value: bool) -> None:
    if value:
        console.print(f"dex-trove {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=_version_cb, is_eager=True)] = False,
) -> None:
    """Learn, browse and install agent artifacts."""


@app.command("sources")
def sources_cmd(as_json: JsonOpt = False) -> None:
    """Mapped sources and evaluated candidates."""
    srcs, cands = sources_mod.load()
    if as_json:
        console.print_json(
            json.dumps({"sources": [s.__dict__ for s in srcs], "candidates": [c.__dict__ for c in cands]})
        )
        return
    t = Table("id", "adapter", "repo / local", "enabled", "first-party")
    for s in srcs:
        t.add_row(
            s.id,
            s.adapter,
            s.web_url or s.local or "",
            "yes" if s.enabled else "no",
            "yes" if s.first_party else "",
        )
    console.print(t)
    if cands:
        c = Table("candidate", "licence", "decision")
        for cand in cands:
            c.add_row(cand.repo, cand.license, cand.decision)
        console.print(c)


@app.command()
def learn(
    source_ids: Annotated[
        list[str] | None, typer.Argument(help="Sources to learn (default: all enabled)")
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report only; write nothing")] = False,
    prefer_local: Annotated[
        bool, typer.Option("--prefer-local", help="Use `local:` checkouts when present")
    ] = False,
    no_refresh: Annotated[
        bool, typer.Option("--no-refresh", help="Reuse cached clones without fetching")
    ] = False,
) -> None:
    """Fetch sources, admit licence-clean items and rewrite the trove."""
    from dex_trove import learn as learn_mod
    from dex_trove import notices

    root = _need_repo()
    trove = root / "trove"
    srcs, _ = sources_mod.load(root / "sources.yaml")
    chosen = [s for s in srcs if (s.id in source_ids if source_ids else s.enabled)]
    if source_ids and len(chosen) != len(set(source_ids)):
        err.print(f"[red]unknown source(s): {set(source_ids) - {s.id for s in chosen}}[/red]")
        raise typer.Exit(2)
    learner = learn_mod.Learner(trove, dry_run=dry_run)
    priority = {s.id: s.priority for s in srcs}
    results = []
    for s in chosen:
        try:
            path, commit = sources_mod.fetch(s, prefer_local=prefer_local, refresh=not no_refresh)
        except Exception as exc:  # noqa: BLE001 - keep going; existing items stay untouched
            err.print(f"[yellow]skip {s.id}: {exc}[/yellow]")
            continue
        r = learner.learn(s, path, commit, priority)
        results.append(r)
        reasons: dict[str, int] = {}
        for e in r.excluded:
            reasons[e.reason] = reasons.get(e.reason, 0) + 1
        parts = [f"{len(r.items)} admitted", f"{len(r.excluded)} excluded"]
        if reasons:
            parts[-1] += f" {dict(sorted(reasons.items()))}"
        if r.removed:
            parts.append(f"{len(r.removed)} removed")
        if r.ignored:
            parts.append(f"{r.ignored} ignored (.dexignore)")
        console.print(f"[bold]{s.id}[/bold] @ {(commit or 'local')[:12]}: " + ", ".join(parts))
    if dry_run or not results:
        return
    totals = learn_mod.finalize(trove, results, srcs)
    (root / "THIRD_PARTY_NOTICES.md").write_text(notices.render(trove, srcs), encoding="utf-8")
    console.print(f"trove: {totals['items']} items, {totals['excluded']} excluded → {trove}")


@app.command()
def validate() -> None:
    """CI gate: manifests, licences, hashes, catalog and notices."""
    from dex_trove import notices
    from dex_trove.validate import validate as run

    root = repo_root()
    trove = trove_root()
    notices_text: str | None = None
    notices_file: Path | None = None
    if root is not None:
        srcs, _ = sources_mod.load(root / "sources.yaml")
        notices_text, notices_file = notices.render(trove, srcs), root / "THIRD_PARTY_NOTICES.md"
    problems = run(trove, notices_text=notices_text, notices_file=notices_file)
    for p in problems:
        err.print(f"[red]✗[/red] {p}")
    if problems:
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] {len(catalog.load(trove))} items valid")


def _table(items: list[dict[str, Any]]) -> Table:
    t = Table("kind", "id", "licence", "description", show_lines=False)
    for it in items:
        t.add_row(it["kind"], it["id"], it["license"]["spdx"] or "", (it["description"] or "")[:90])
    return t


@app.command("list")
def list_cmd(kind: KindOpt = None, source: SourceOpt = None, as_json: JsonOpt = False) -> None:
    """List trove items."""
    items = catalog.filter_items(catalog.load(), kind=kind, source=source)
    if as_json:
        console.print_json(json.dumps([{k: i[k] for k in ("kind", "id", "version", "title")} for i in items]))
        return
    console.print(_table(items))
    console.print(f"{len(items)} items")


FacetOpt = Annotated[list[str] | None, typer.Option(show_default=False)]


@app.command()
def search(
    query: Annotated[
        list[str] | None, typer.Argument(help="Words to match (optional with facet filters)")
    ] = None,
    kind: KindOpt = None,
    source: SourceOpt = None,
    task: Annotated[list[str] | None, typer.Option("--task", "-t", help="What job it does")] = None,
    methodology: Annotated[
        list[str] | None, typer.Option("--methodology", "-m", help="sdlc, adlc, tdd…")
    ] = None,
    phase: Annotated[list[str] | None, typer.Option("--phase", "-p", help="Lifecycle phase")] = None,
    role: Annotated[list[str] | None, typer.Option("--role", "-r", help="Who uses it")] = None,
    domain: FacetOpt = None,
    language: FacetOpt = None,
    framework: FacetOpt = None,
    platform: FacetOpt = None,
    maturity: FacetOpt = None,
    exclude: Annotated[
        list[str] | None, typer.Option("--not", help="Exclude facet=value (repeatable)")
    ] = None,
    strict: Annotated[
        bool, typer.Option("--strict", help="Require every listed value within a facet")
    ] = False,
    explain: Annotated[bool, typer.Option("--explain", help="Show why each result matched")] = False,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Continue from a previous page")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 25,
    as_json: JsonOpt = False,
) -> None:
    """Search names, titles, tags and descriptions, and filter by typed facets.

    OR within a facet, AND across facets: `--language python --language go --role qa-engineer`.
    See `dex facets list` for every facet and value.
    """
    text = " ".join(query or [])
    chosen = {
        "task": task,
        "methodology": methodology,
        "phase": phase,
        "role": role,
        "domain": domain,
        "language": language,
        "framework": framework,
        "platform": platform,
        "maturity": maturity,
    }
    faceted = any(chosen.values()) or exclude or strict or explain or cursor
    if not faceted:
        if not text:
            err.print(
                "give search words, a facet filter (e.g. --methodology adlc), or both — see `dex facets list`"
            )
            raise typer.Exit(2)
        hits = catalog.search(catalog.filter_items(catalog.load(), kind=kind, source=source), text)[:limit]
        if as_json:
            console.print_json(
                json.dumps([{k: i[k] for k in ("kind", "id", "title", "description")} for i in hits])
            )
            return
        console.print(_table(hits))
        return

    from dex_trove import query as q
    from dex_trove import taxonomy

    filters = {d: list(v) for d, v in chosen.items() if v}
    if kind:
        filters["kind"] = [kind]
    try:
        fq = q.FacetQuery(
            text=text,
            all=filters,
            exclude=q.parse_exclusions(exclude or []),
            strict=strict,
            limit=limit,
            cursor=cursor,
        )
        items = catalog.filter_items(catalog.load(), source=source)
        result = q.run(fq, taxonomy.load(), items=items)
    except q.QueryError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if as_json:
        console.print_json(json.dumps(q.to_json(result, explain=explain), ensure_ascii=False))
        return
    if not result.hits:
        console.print("[yellow]No items match every filter.[/yellow]")
        for dim, n in result.relaxations.items():
            console.print(f"  without the {dim} filter: {n} item(s)")
        return
    table = Table(box=None, show_header=True, header_style="bold")
    table.add_column("score", justify="right")
    table.add_column("kind")
    table.add_column("id")
    table.add_column("why" if explain else "title")
    for h in result.hits:
        why = "; ".join(f"{d}={','.join(v)}" for d, v in h.matched.items()) + f" [{h.review_status}]"
        table.add_row(f"{h.score:.2f}", h.item["kind"], h.item["id"], why if explain else h.item["title"])
    console.print(table)
    tail = f" — next page: --cursor {result.next_cursor}" if result.next_cursor else ""
    console.print(f"{result.total} match(es){tail}")


@app.command()
def show(ref: str, as_json: JsonOpt = False) -> None:
    """Show one item: provenance, licence, files."""
    try:
        it = catalog.resolve(catalog.load(), ref)
    except catalog.RefError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if as_json:
        console.print_json(json.dumps(it))
        return
    src, lic = it["source"], it["license"]
    console.print(f"[bold]{it['title']}[/bold]  ({it['kind']}:{it['id']}@{it['version']})")
    console.print(it["description"])
    console.print(f"source:   {src['title']} — {src.get('url') or src.get('repo') or 'local'}")
    console.print(f"licence:  {lic['spdx']} ({lic['evidence']})")
    for insp in it.get("inspired_by", []):
        console.print(f"inspired: {insp.get('title')} {insp.get('url', '')}")
    if it.get("members"):
        console.print("members:  " + ", ".join(it["members"]))
    console.print(f"files:    {', '.join(it['files'][:12])}{' …' if len(it['files']) > 12 else ''}")
    console.print(f"path:     {catalog.item_path(it)}")


@app.command()
def install(
    refs: Annotated[list[str], typer.Argument(help="kind:ns/name, ns/name or bare name")],
    target: Annotated[str, typer.Option("--target", "-t", help="claude | copilot | dir")] = "claude",
    scope: Annotated[str, typer.Option(help="user (~/.claude) or project (./.claude) for claude")] = "user",
    path: Annotated[Path | None, typer.Option(help="Base directory (required for --target dir)")] = None,
    allow_exec: Annotated[bool, typer.Option("--allow-exec", help="Allow hooks that run code")] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace files Dex didn't install (or that you edited since)")
    ] = False,
) -> None:
    """Install items into Claude Code, GitHub Copilot or a directory.

    Agents installed for Claude Code get Claude tool names and model values (Copilot ids can't launch there).
    Existing files are replaced only when Dex wrote them and they're unedited, unless you pass --force.
    """
    from dex_trove.install import InstallError
    from dex_trove.install import install as run

    try:
        done = run(refs, target=target, scope=scope, path=path, allow_exec=allow_exec, force=force)
    except (InstallError, catalog.RefError) as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    for d in done:
        if d.dest:
            console.print(f"[green]✓[/green] {d.kind}:{d.id} → {d.dest}")
            for note in d.notes:
                console.print(f"    [dim]adapted: {note}[/dim]")
        else:
            console.print(f"[yellow]–[/yellow] {d.kind}:{d.id}: {d.skipped}")
    if not any(d.dest for d in done):
        # Everything requested was refused or skipped: scripts must not mistake that for success.
        err.print("[red]✗ nothing was installed[/red]")
        raise typer.Exit(1)


@app.command("license")
def license_cmd(path: Path) -> None:
    """Classify a licence file (or the licence files in a directory)."""
    files = licenses.license_files(path) if path.is_dir() else [path]
    if not files:
        err.print("no licence files found")
        raise typer.Exit(1)
    for f in files:
        c = licenses.classify_file(f)
        console.print(f"{f}: [bold]{c.spdx or 'unknown'}[/bold] → {c.verdict} ({c.evidence})")


@app.command("notices")
def notices_cmd() -> None:
    """Regenerate THIRD_PARTY_NOTICES.md."""
    from dex_trove import notices

    root = _need_repo()
    srcs, _ = sources_mod.load(root / "sources.yaml")
    (root / "THIRD_PARTY_NOTICES.md").write_text(notices.render(root / "trove", srcs), encoding="utf-8")
    console.print("THIRD_PARTY_NOTICES.md updated")


@app.command("catalog")
def catalog_cmd() -> None:
    """Rebuild catalog.json from the dex.json files on disk."""
    from dex_trove.learn import finalize

    root = _need_repo()
    srcs, _ = sources_mod.load(root / "sources.yaml")
    totals = finalize(root / "trove", [], srcs)
    console.print(f"catalog: {totals['items']} items")


@ananke_app.command("sync")
def ananke_sync(
    project: Annotated[Path, typer.Option(help="Ananke project directory")] = Path("."),
    kind: Annotated[
        list[str] | None, typer.Option("--kind", "-k", help="Only these kinds (repeatable)")
    ] = None,
    source: Annotated[
        list[str] | None, typer.Option("--source", "-s", help="Only these source namespaces (repeatable)")
    ] = None,
    name: Annotated[
        list[str] | None, typer.Option("--name", "-n", help="Only these items: name or ns/name (repeatable)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Pass --dry-run to ananke: report, register nothing")
    ] = False,
    include_flagged: Annotated[
        bool, typer.Option("--include-flagged", help="Also offer items Ananke's secret scanner would flag")
    ] = False,
    ananke_bin: Annotated[str | None, typer.Option(help="Path to the ananke executable")] = None,
) -> None:
    """Register trove items into an Ananke registry (`ananke registry learn`)."""
    from dex_trove.ananke_bridge import AnankeError, sync

    try:
        selected, proc = sync(
            project=project.resolve(),
            kinds=kind,
            sources=source,
            names=name,
            dry_run=dry_run,
            include_flagged=include_flagged,
            ananke_bin=ananke_bin,
        )
    except AnankeError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    console.print(proc.stdout.rstrip())
    if proc.returncode:
        err.print(proc.stderr.rstrip())
        raise typer.Exit(proc.returncode)
    console.print(f"[green]✓[/green] {len(selected)} trove items offered to Ananke")


@docs_app.command("export")
def docs_export_cmd(
    out: Annotated[Path, typer.Option(help="Astro src directory")] = Path("website/src"),
) -> None:
    """Write Astro content and JSON indexes for the docs site."""
    from dex_trove.docs_export import export

    root = _need_repo()
    srcs, cands = sources_mod.load(root / "sources.yaml")
    n = export(root / "trove", out, srcs, cands)
    console.print(f"exported {n} item pages → {out}")


facets_app = typer.Typer(
    help="Typed facets: the taxonomy, value counts and the facets.json sidecar.", no_args_is_help=True
)
app.add_typer(facets_app, name="facets")


@facets_app.command("list")
def facets_list(
    dimension: Annotated[str | None, typer.Argument(help="One facet, e.g. methodology")] = None,
    as_json: JsonOpt = False,
) -> None:
    """Every facet and value, with definitions and how many items carry it."""
    from dex_trove import facets as fx
    from dex_trove import taxonomy

    tax = taxonomy.load()
    if dimension and dimension not in tax.dimensions:
        err.print(f"[red]unknown facet {dimension!r}; facets: {', '.join(tax.dimensions)}[/red]")
        raise typer.Exit(2)
    records = fx.load() or fx.build(catalog.load(), tax)["items"]
    counts: dict[str, dict[str, int]] = {}
    for rec in records.values():
        for dim, value in rec["facets"].items():
            for v in [value] if isinstance(value, str) else value:
                counts.setdefault(dim, {}).setdefault(v, 0)
                counts[dim][v] += 1
    dims = [tax.dimensions[dimension]] if dimension else list(tax.dimensions.values())
    if as_json:
        out = {
            "taxonomy_version": tax.version,
            "facets": {
                d.id: {
                    "label": d.label,
                    "question": d.question,
                    "cardinality": d.cardinality,
                    "terms": {
                        t.id: {
                            "label": t.label,
                            "definition": t.definition,
                            "aliases": list(t.aliases),
                            "items": counts.get(d.id, {}).get(t.id, 0),
                        }
                        for t in d.terms.values()
                    },
                }
                for d in dims
            },
        }
        console.print_json(json.dumps(out, ensure_ascii=False))
        return
    for d in dims:
        console.print(f"\n[bold]{d.id}[/bold] — {d.question}  [dim]({d.cardinality})[/dim]")
        t = Table("value", "items", "definition", box=None, show_header=False)
        for term in d.terms.values():
            alias = f" [dim](also: {', '.join(term.aliases)})[/dim]" if term.aliases else ""
            t.add_row(term.id, str(counts.get(d.id, {}).get(term.id, 0)), term.definition + alias)
        console.print(t)
    console.print(f"\n[dim]taxonomy {tax.version} · filter with `dex search --<facet> <value>`[/dim]")


@facets_app.command("show")
def facets_show(ref: str, as_json: JsonOpt = False) -> None:
    """One item's facets, where each value came from, and its review status."""
    from dex_trove import facets as fx
    from dex_trove import taxonomy

    try:
        it = catalog.resolve(catalog.load(), ref)
    except catalog.RefError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    rec = fx.load().get(fx.item_key(it)) or fx.classify(it, taxonomy.load(), taxonomy.load_curation())
    if as_json:
        console.print_json(json.dumps(rec, ensure_ascii=False))
        return
    cls = rec["classification"]
    console.print(f"[bold]{it['kind']}:{it['id']}[/bold]  {cls['review_status']} ({cls['source']})")
    for dim, value in rec["facets"].items():
        prov = rec["provenance"].get(dim, {})
        seen: list[str] = []  # curated evidence is one line for all values: print it once
        for v, e in prov.get("evidence", {}).items():
            line = e[0] if e and e[0].startswith("curated:") else f"{v}: {e[0] if e else ''}"
            if line not in seen:
                seen.append(line)
        ev = "; ".join(seen[:3])
        shown = value if isinstance(value, str) else ", ".join(value)
        console.print(f"  {dim:<12} {shown}  [dim]← {prov.get('source', '?')}: {ev}[/dim]")
    if rec.get("unmapped"):
        console.print(f"  [dim]unmapped upstream tags: {', '.join(rec['unmapped']['tags'])}[/dim]")


@facets_app.command("build")
def facets_build() -> None:
    """Rebuild trove/facets.json from catalog.json, the taxonomy and curation (no network; needs a checkout)."""
    from dex_trove import facets as fx
    from dex_trove.taxonomy import TaxonomyError

    trove = _need_repo() / "trove"  # the trove inside an installed wheel is release data, never rewritten
    try:
        data = fx.write(trove, catalog.load(trove))
    except TaxonomyError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    approved = sum(1 for r in data["items"].values() if r["classification"]["review_status"] == "approved")
    console.print(f"facets: {data['count']} items ({approved} curated) → {trove / fx.FACETS_FILE}")


@facets_app.command("doc")
def facets_doc() -> None:
    """Regenerate docs/reference/taxonomy.md from the taxonomy and the current trove."""
    from dex_trove import facets as fx

    root = _need_repo()
    target = root / "docs" / "reference" / "taxonomy.md"
    target.write_text(fx.taxonomy_markdown(records=fx.load(root / "trove")), encoding="utf-8")
    console.print(f"wrote {target}")
