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
def validate(
    since: Annotated[
        str | None,
        typer.Option("--since", help="Git ref whose releases.json must still hold (releases are immutable)"),
    ] = None,
) -> None:
    """CI gate: manifests, licences, hashes, catalog, notices and the release ledger."""
    import subprocess

    from dex_trove import notices
    from dex_trove.validate import validate as run

    root = repo_root()
    trove = trove_root()
    notices_text: str | None = None
    notices_file: Path | None = None
    if root is not None:
        srcs, _ = sources_mod.load(root / "sources.yaml")
        notices_text, notices_file = notices.render(trove, srcs), root / "THIRD_PARTY_NOTICES.md"
    previous = None
    if since:
        if root is None:
            err.print("[red]--since needs a Dex-Trove checkout[/red]")
            raise typer.Exit(2)
        rel = (trove / "releases.json").resolve().relative_to(root.resolve()).as_posix()
        shown = subprocess.run(["git", "show", f"{since}:{rel}"], cwd=root, capture_output=True, text=True)
        previous = (
            json.loads(shown.stdout) if shown.returncode == 0 else None
        )  # no ledger then: nothing to keep
    problems = run(trove, notices_text=notices_text, notices_file=notices_file, previous_ledger=previous)
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
    needs: Annotated[
        list[str] | None, typer.Option("--needs", help="What it needs installed: text-only, python, node…")
    ] = None,
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
    rank: Annotated[
        str,
        typer.Option(
            "--rank",
            help="words: every word must match (default); semantic: BM25 + taxonomy expansion, for questions",
        ),
    ] = "words",
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
        "needs": needs,
        "maturity": maturity,
    }
    faceted = any(chosen.values()) or exclude or strict or explain or cursor
    if not faceted:
        if not text:
            err.print(
                "give search words, a facet filter (e.g. --methodology adlc), or both — see `dex facets list`"
            )
            raise typer.Exit(2)
        pool = catalog.filter_items(catalog.load(), kind=kind, source=source)
        if rank not in ("words", "semantic"):
            err.print("--rank is words or semantic")
            raise typer.Exit(2)
        if rank == "semantic":
            from dex_trove import semantic

            hits = semantic.rank(pool, text)[:limit]
        else:
            hits = catalog.search(pool, text)[:limit]
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
    refs: Annotated[list[str] | None, typer.Argument(help="kind:ns/name, ns/name or bare name")] = None,
    target: Annotated[str, typer.Option("--target", "-t", help="claude | copilot | dir")] = "claude",
    scope: Annotated[str, typer.Option(help="user (~/.claude) or project (./.claude) for claude")] = "user",
    path: Annotated[Path | None, typer.Option(help="Base directory (required for --target dir)")] = None,
    allow_exec: Annotated[bool, typer.Option("--allow-exec", help="Allow hooks that run code")] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace files Dex didn't install (or that you edited since)")
    ] = False,
    locked: Annotated[
        bool, typer.Option("--locked", help="Install exactly the versions pinned in the lock file")
    ] = False,
    lock_file: Annotated[Path, typer.Option("--lock-file", help="Lock to read with --locked")] = Path(
        "dex.lock.json"
    ),
) -> None:
    """Install items into Claude Code, GitHub Copilot or a directory.

    Agents installed for Claude Code get Claude tool names and model values (Copilot ids can't launch there).
    Existing files are replaced only when Dex wrote them and they're unedited, unless you pass --force.
    """
    from dex_trove import releases
    from dex_trove.install import InstallError, install_locked
    from dex_trove.install import install as run

    try:
        if locked:
            if refs:
                raise InstallError("--locked installs the whole lock; don't name items too")
            entries = releases.read_lock(lock_file)
            errors, warnings = releases.check_lock(releases.load(trove_root()), entries)
            for w in warnings:
                err.print(f"[yellow]![/yellow] {w}")
            if errors:
                raise InstallError("; ".join(errors))
            done = install_locked(
                entries, target=target, scope=scope, path=path, allow_exec=allow_exec, force=force
            )
        else:
            if not refs:
                raise InstallError("name at least one item, or pass --locked")
            done = run(refs, target=target, scope=scope, path=path, allow_exec=allow_exec, force=force)
    except (InstallError, catalog.RefError, releases.ReleaseError) as exc:
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


# --------------------------------------------------------------------------- releases and locks
release_app = typer.Typer(
    help="Release history: every version an item ever shipped, with yank, deprecation and fork lineage.",
    no_args_is_help=True,
)
app.add_typer(release_app, name="release")


def _key(ref: str) -> tuple[str, str | None]:
    """``ref[@version]`` → (``kind:ns/name``, version). The item must be in the trove or in its release history."""
    from dex_trove import releases

    base, _, version = ref.partition("@")
    ledger = releases.load(trove_root())
    if ":" in base and base in ledger["items"]:
        return base, version or None
    try:
        it = catalog.resolve(catalog.load(), base)
    except catalog.RefError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    return releases.key_of(it), version or None


def _now() -> str:
    from dex_trove.learn import now_iso

    return now_iso()


@release_app.command("list")
def release_list(ref: str, as_json: JsonOpt = False) -> None:
    """Every release of an item, oldest first."""
    from dex_trove import releases

    key, _ = _key(ref)
    rels = releases.history(releases.load(trove_root()), key)
    if as_json:
        console.print_json(json.dumps({"key": key, "releases": rels}))
        return
    t = Table("version", "digest", "released", "upstream commit", "status", title=key)
    for r in rels:
        status = []
        if r.get("yanked"):
            status.append(f"yanked: {r['yanked']['reason']}")
        if r.get("deprecated"):
            status.append(
                "deprecated"
                + (f" → {r['deprecated']['replaced_by']}" if r["deprecated"].get("replaced_by") else "")
            )
        if r.get("parent"):
            status.append(f"fork of {r['parent']['key']}@{r['parent']['version']}")
        t.add_row(
            r["version"],
            r["content_hash"][:12],
            r["released_at"][:10],
            str(r["source"].get("commit") or "first-party")[:12],
            "; ".join(status) or r.get("channel", "stable"),
        )
    console.print(t)


def _need_checkout_here() -> Path:
    """The Dex-Trove checkout containing the current directory: the only place the ledger may be changed.

    Unlike ``_need_repo`` there is no fallback to the development checkout dex was installed from, so running a
    maintainer command from some other project can never edit that checkout's trove.
    """
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "sources.yaml").is_file() and (candidate / "src" / "dex_trove").is_dir():
            return candidate
    err.print("[red]Run this inside a Dex-Trove checkout: it changes trove/releases.json.[/red]")
    raise typer.Exit(2)


def _edit_ledger(action: Any) -> None:
    from dex_trove import releases

    trove = _need_checkout_here() / "trove"
    ledger = releases.load(trove)
    try:
        action(ledger)
    except releases.ReleaseError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    releases.save(trove, ledger)


@release_app.command("yank")
def release_yank(
    ref: Annotated[str, typer.Argument(help="kind:ns/name@version")],
    reason: Annotated[str, typer.Option("--reason", help="Why (shown to everyone who has it locked)")],
) -> None:
    """Mark a release as not to be chosen again. Locks that pin it keep working, with a warning."""
    from dex_trove import releases

    key, version = _key(ref)
    if not version:
        err.print("[red]name the version: kind:ns/name@version[/red]")
        raise typer.Exit(2)
    _edit_ledger(lambda ledger: releases.yank(ledger, key, version, reason, at=_now()))
    console.print(f"[yellow]yanked[/yellow] {key}@{version}")


@release_app.command("unyank")
def release_unyank(ref: Annotated[str, typer.Argument(help="kind:ns/name@version")]) -> None:
    """Reverse a yank."""
    from dex_trove import releases

    key, version = _key(ref)
    if not version:
        err.print("[red]name the version: kind:ns/name@version[/red]")
        raise typer.Exit(2)
    _edit_ledger(lambda ledger: releases.unyank(ledger, key, version))
    console.print(f"unyanked {key}@{version}")


@release_app.command("deprecate")
def release_deprecate(
    ref: Annotated[str, typer.Argument(help="kind:ns/name, or kind:ns/name@version for one release")],
    reason: Annotated[str, typer.Option("--reason")],
    replaced_by: Annotated[
        str | None, typer.Option("--replaced-by", help="kind:ns/name to use instead")
    ] = None,
) -> None:
    """Deprecate an item (every release) or one release, optionally naming its replacement."""
    from dex_trove import releases

    key, version = _key(ref)
    rep = _key(replaced_by)[0] if replaced_by else None
    _edit_ledger(
        lambda ledger: releases.deprecate(ledger, key, reason, at=_now(), replaced_by=rep, version=version)
    )
    console.print(f"deprecated {key}{'@' + version if version else ''}" + (f" → {rep}" if rep else ""))


@release_app.command("lineage")
def release_lineage(ref: str, as_json: JsonOpt = False) -> None:
    """Fork ancestry: the parents an item was forked from, and the items forked from it."""
    from dex_trove import releases

    key, _ = _key(ref)
    info = releases.lineage(releases.load(trove_root()), key)
    if as_json:
        console.print_json(json.dumps(info))
        return
    console.print(f"[bold]{key}[/bold]")
    for p in info["parents"]:
        console.print(f"  forked from {p['key']}@{p['version']} ({p['content_hash'][:12]})")
    for c in info["children"]:
        console.print(f"  forked as   {c}")
    if not info["parents"] and not info["children"]:
        console.print("  no forks recorded")


@release_app.command("record")
def release_record() -> None:
    """Append releases for items whose current digest isn't released yet (``dex learn`` does this itself)."""
    from dex_trove import releases

    trove = _need_checkout_here() / "trove"
    ledger = releases.load(trove)
    items = catalog.load(trove)
    changed = releases.record(ledger, items)
    releases.save(trove, ledger)
    from dex_trove import docs_export, relations

    relations.write(trove, relations.build(items, ledger, docs_export.relations(items)[0]))
    console.print(f"{len(changed)} change(s) recorded" + (": " + ", ".join(changed[:10]) if changed else ""))


@app.command("lock")
def lock_cmd(
    refs: Annotated[
        list[str], typer.Argument(help="Items to pin: kind:ns/name[@version] (a plugin pins its members)")
    ],
    lock_file: Annotated[Path, typer.Option("--lock-file", help="Lock to write or update")] = Path(
        "dex.lock.json"
    ),
) -> None:
    """Pin items to an exact version and digest in a project lock (dex.lock.json)."""
    from dex_trove import releases

    ledger = releases.load(trove_root())
    items = catalog.load()
    entries = {e.key: e for e in (releases.read_lock(lock_file) if lock_file.is_file() else [])}
    try:
        for ref in refs:
            key, version = _key(ref)
            kind = key.split(":", 1)[0]
            if kind == "plugin":
                plugin = catalog.resolve(items, key)
                for member in plugin.get("members", []):
                    mk = releases.key_of(catalog.resolve(items, member))
                    entries[mk] = releases.lock_entry(mk, releases.resolve(ledger, mk))
                continue
            entries[key] = releases.lock_entry(key, releases.resolve(ledger, key, version))
    except (releases.ReleaseError, catalog.RefError) as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    releases.write_lock(lock_file, list(entries.values()), generator=f"dex-trove {__version__}")
    for e in sorted(entries.values(), key=lambda e: e.key):
        console.print(f"[green]✓[/green] {e.key}@{e.version} {e.content_hash[:12]}")
    console.print(f"{len(entries)} pinned in {lock_file}")


@app.command("verify-lock")
def verify_lock(
    lock_file: Annotated[Path, typer.Option("--lock-file")] = Path("dex.lock.json"),
    fetch: Annotated[
        bool, typer.Option("--fetch", help="Also fetch non-current pins from Git and check their bytes")
    ] = False,
) -> None:
    """Check a lock against the release ledger: every pin exists with its digest; yanked or deprecated pins warn."""
    import tempfile

    from dex_trove import releases

    try:
        entries = releases.read_lock(lock_file)
    except releases.ReleaseError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    errors, warnings = releases.check_lock(releases.load(trove_root()), entries)
    current = {releases.key_of(it): it["content_hash"] for it in catalog.load()}
    if fetch and not errors:
        with tempfile.TemporaryDirectory() as tmp:
            for e in entries:
                if current.get(e.key) == e.content_hash:
                    continue
                try:
                    releases.fetch(e, Path(tmp) / e.key.replace(":", "-").replace("/", "."))
                except releases.ReleaseError as exc:
                    errors.append(str(exc))
    for w in warnings:
        err.print(f"[yellow]![/yellow] {w}")
    for problem in errors:
        err.print(f"[red]✗[/red] {problem}")
    if errors:
        raise typer.Exit(1)
    stale = sum(1 for e in entries if current.get(e.key) != e.content_hash)
    console.print(
        f"[green]✓[/green] {len(entries)} pin(s) valid"
        + (f"; {stale} not the current release" if stale else "")
    )


# --------------------------------------------------------------------------- reviewed learning candidates
candidate_app = typer.Typer(
    help="Reviewed learning candidates: evaluate, review, then publish into a source. Nothing publishes on its own.",
    no_args_is_help=True,
)
app.add_typer(candidate_app, name="candidate")
VisibilityOpt = Annotated[
    str, typer.Option("--visibility", help="public, or internal (never to a public source)")
]


def _print_report(rep: Any, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(rep.as_dict()))
        return
    for p in rep.passed:
        console.print(f"[green]✓[/green] {p}")
    for f in rep.failed:
        err.print(f"[red]✗[/red] {f}")


@candidate_app.command("check")
def candidate_check(path: Path, visibility: VisibilityOpt = "public", as_json: JsonOpt = False) -> None:
    """Run the skill, licence, secret and evaluation gates on a candidate folder."""
    from dex_trove import candidates

    try:
        rep = candidates.check(path, visibility=visibility)
    except candidates.CandidateError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    _print_report(rep, as_json)
    if not rep.ok:
        raise typer.Exit(1)


@candidate_app.command("review")
def candidate_review(
    path: Path,
    reviewer: Annotated[str, typer.Option("--reviewer", help="Who reviewed it")],
    reason: Annotated[str, typer.Option("--reason", help="Why approved or rejected")],
    approve: Annotated[bool, typer.Option("--approve/--reject", help="The decision")] = False,
) -> None:
    """Record a review decision beside the candidate (review.json). Publishing needs an approval."""
    from dex_trove import candidates

    try:
        d = candidates.review(path, approve=approve, reviewer=reviewer, reason=reason)
    except candidates.CandidateError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    console.print(f"{d['decision']} by {d['reviewer']}")


@candidate_app.command("publish")
def candidate_publish(
    path: Path,
    to: Annotated[str, typer.Option("--to", help="Source id from sources.yaml (a local folder source)")],
    visibility: VisibilityOpt = "public",
) -> None:
    """Copy an approved, passing candidate into a source. Run `dex learn` afterwards to release it."""
    from dex_trove import candidates

    srcs, _ = sources_mod.load(_need_checkout_here() / "sources.yaml")
    source = next((s for s in srcs if s.id == to), None)
    if source is None:
        err.print(f"[red]no source {to!r} in sources.yaml[/red]")
        raise typer.Exit(2)
    try:
        dest = candidates.publish(path, source, visibility=visibility)
    except candidates.CandidateError as exc:
        for reason in str(exc).split("; "):
            err.print(f"[red]✗[/red] {reason}")
        raise typer.Exit(1) from exc
    console.print(f"[green]✓[/green] published to {dest}; run `dex learn --source {to}` to release it")


@app.command("related")
def related_cmd(
    ref: str,
    rel_type: Annotated[
        str | None, typer.Option("--type", help="Only this relation type, e.g. requires")
    ] = None,
    as_json: JsonOpt = False,
) -> None:
    """Typed relations of an item: requires, complements, alternatives, plugin membership, forks, replacements.

    Curated and derived relations are facts with evidence; `similar` is an inferred hint. None of them says two
    items are compatible.
    """
    from dex_trove import relations

    key, _ = _key(ref)
    rels = [
        r for r in relations.load(trove_root())["items"].get(key, []) if not rel_type or r["type"] == rel_type
    ]
    if as_json:
        console.print_json(json.dumps({"key": key, "relations": rels}))
        return
    if not rels:
        console.print(f"{key}: no relations" + (f" of type {rel_type}" if rel_type else ""))
        return
    t = Table("type", "item", "origin", "evidence", title=key)
    for r in rels:
        t.add_row(r["type"], r["target"], r["origin"], r["evidence"][:80])
    console.print(t)


@ananke_app.command("handoff")
def ananke_handoff(
    lock_file: Annotated[Path, typer.Option("--lock-file", help="The Dex lock to hand to Ananke")] = Path(
        "dex.lock.json"
    ),
) -> None:
    """Print the [tool.ananke] requirements that pin a Dex lock's skills and agents exactly.

    Resolve-only: nothing is installed, activated or run. Paste the block into pyproject.toml, then
    `ananke sync` resolves the same versions under your policy and writes ananke.lock.
    """
    from dex_trove import releases
    from dex_trove.ananke_bridge import handoff_toml

    try:
        entries = releases.read_lock(lock_file)
    except releases.ReleaseError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    errors, warnings = releases.check_lock(releases.load(trove_root()), entries)
    for w in warnings:
        err.print(f"[yellow]![/yellow] {w}")
    if errors:
        for e in errors:
            err.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    text, notes = handoff_toml(entries)
    print(text, end="")
    for n in notes:
        err.print(f"[dim]note: {n}[/dim]")


@app.command("check-installs")
def check_installs(as_json: JsonOpt = False) -> None:
    """Install every item into each tool layout in a scratch folder and check the tool can load it.

    Writes trove/install-checks.json: what Dex verified itself, shown apart from what items claim about themselves.
    """
    from dex_trove import checks

    trove = _need_checkout_here() / "trove"
    data = checks.run(trove, generator=f"dex-trove {__version__}")
    checks.write(trove, data)
    if as_json:
        console.print_json(json.dumps(data["summary"]))
        return
    for target, s in data["summary"].items():
        console.print(f"{target}: {s['pass']} pass, {s['fail']} fail")
    fails = [(k, t, v) for k, row in data["items"].items() for t, v in row.items() if v != "pass"]
    for k, t, v in fails[:15]:
        console.print(f"  [yellow]–[/yellow] {t} {k}: {v}")


@app.command("overlap")
def overlap_cmd(
    threshold: Annotated[float, typer.Option("--threshold", help="Word overlap needed, 0–1")] = 0.45,
    kind: KindOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    as_json: JsonOpt = False,
) -> None:
    """Groups of items that seem to do the same job, each member scored on evidence Dex can verify.

    A candidate list for curation: confirm a real overlap as `alternative-to` in taxonomy/relations.yaml.
    """
    from dex_trove import overlap

    found = overlap.groups(catalog.filter_items(catalog.load(), kind=kind), threshold=threshold)
    if as_json:
        console.print_json(json.dumps({"threshold": threshold, "groups": found}))
        return
    for g in found[:limit]:
        console.print(f"[bold]similarity {g['similarity']}[/bold]")
        for m in g["members"]:
            mark = "★" if m.get("best") else " "
            console.print(f"  {mark} {m['score']:.2f}  {m['key']}  [dim]{', '.join(m['why'])}[/dim]")
    console.print(f"{len(found)} group(s) at threshold {threshold}")
