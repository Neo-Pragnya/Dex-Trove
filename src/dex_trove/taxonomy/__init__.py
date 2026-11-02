"""The capability taxonomy: typed facet dimensions with controlled, versioned terms (ontology.yaml).

Validation is strict because everything downstream (search, the site's filters, Ananke hand-off) depends on term
ids being stable and unambiguous. :func:`normalize` turns user or upstream spellings into canonical ids and
returns ``None`` for unknown values, which callers keep as ``unmapped`` instead of discarding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

ONTOLOGY = "ontology.yaml"
CURATION = "curation.yaml"
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Methodologies that overlap but must never collapse into one another through aliases.
DISTINCT = {"methodology": [("sdlc", "adlc"), ("tdd", "bdd"), ("devops", "sre")]}


class TaxonomyError(ValueError):
    pass


@dataclass(frozen=True)
class Term:
    id: str
    label: str
    definition: str
    aliases: tuple[str, ...] = ()
    match: tuple[re.Pattern[str], ...] = ()
    globs: tuple[str, ...] = ()
    deprecated: bool = False
    replaced_by: str | None = None


@dataclass(frozen=True)
class Dimension:
    id: str
    label: str
    question: str
    cardinality: str
    derived: str | None
    terms: dict[str, Term] = field(default_factory=dict)
    lookup: dict[str, str] = field(default_factory=dict)  # every id/alias spelling → canonical id


@dataclass(frozen=True)
class Taxonomy:
    version: str
    dimensions: dict[str, Dimension]

    def normalize(self, dimension: str, value: str) -> str | None:
        dim = self.dimensions.get(dimension)
        if dim is None:
            raise TaxonomyError(f"unknown dimension {dimension!r}; known: {', '.join(self.dimensions)}")
        term_id = dim.lookup.get(_key(value))
        if term_id is None:
            return None
        term = dim.terms[term_id]
        return term.replaced_by if term.deprecated and term.replaced_by else term_id

    def term(self, dimension: str, term_id: str) -> Term:
        return self.dimensions[dimension].terms[term_id]


def _key(value: str) -> str:
    return re.sub(r"[\s_]+", "-", str(value).strip().lower())


def parse(data: dict[str, Any]) -> Taxonomy:
    """Build and validate a taxonomy from parsed YAML; raises :class:`TaxonomyError` on any problem."""
    version = str(data.get("taxonomy_version") or "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise TaxonomyError(f"taxonomy_version must be MAJOR.MINOR.PATCH, got {version!r}")
    dims: dict[str, Dimension] = {}
    for dim_id, raw in (data.get("dimensions") or {}).items():
        if not _ID.match(dim_id):
            raise TaxonomyError(f"dimension id {dim_id!r} is not lower-kebab")
        if raw.get("cardinality") not in ("one", "many"):
            raise TaxonomyError(f"{dim_id}: cardinality must be 'one' or 'many'")
        terms: dict[str, Term] = {}
        lookup: dict[str, str] = {}
        for t in raw.get("terms") or []:
            tid = str(t.get("id", ""))
            if not _ID.match(tid):
                raise TaxonomyError(f"{dim_id}: term id {tid!r} is not lower-kebab")
            if tid in terms:
                raise TaxonomyError(f"{dim_id}: duplicate term id {tid!r}")
            if not t.get("definition"):
                raise TaxonomyError(f"{dim_id}/{tid}: every term needs a definition")
            try:
                patterns = tuple(re.compile(p, re.IGNORECASE) for p in t.get("match") or [])
            except re.error as exc:
                raise TaxonomyError(f"{dim_id}/{tid}: bad match pattern: {exc}") from exc
            terms[tid] = Term(
                id=tid,
                label=str(t.get("label") or tid),
                definition=str(t["definition"]),
                aliases=tuple(_key(a) for a in t.get("aliases") or []),
                match=patterns,
                globs=tuple(t.get("globs") or []),
                deprecated=bool(t.get("deprecated", False)),
                replaced_by=t.get("replaced_by"),
            )
        for tid, term in terms.items():
            for spelling in (tid, *term.aliases):
                owner = lookup.get(spelling)
                if owner is not None and owner != tid:
                    raise TaxonomyError(f"{dim_id}: {spelling!r} names both {owner!r} and {tid!r}")
                lookup[spelling] = tid
            if term.deprecated and term.replaced_by is not None and term.replaced_by not in terms:
                raise TaxonomyError(f"{dim_id}/{tid}: replaced_by {term.replaced_by!r} is not a term")
        for a, b in DISTINCT.get(dim_id, []):
            if a in terms and b in terms and (lookup.get(a) == b or lookup.get(b) == a):
                raise TaxonomyError(f"{dim_id}: {a!r} and {b!r} overlap but are not aliases of each other")
        dims[dim_id] = Dimension(
            id=dim_id,
            label=str(raw.get("label") or dim_id),
            question=str(raw.get("question") or ""),
            cardinality=raw["cardinality"],
            derived=raw.get("derived"),
            terms=terms,
            lookup=lookup,
        )
    for required in ("kind", "task"):
        if required not in dims:
            raise TaxonomyError(f"the taxonomy must define the {required!r} dimension")
    return Taxonomy(version=version, dimensions=dims)


def _read(name: str, path: Path | None) -> dict[str, Any]:
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        text = resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise TaxonomyError(f"{name} must be a mapping")
    return data


@lru_cache(maxsize=4)
def load(path: Path | None = None) -> Taxonomy:
    return parse(_read(ONTOLOGY, path))


def load_curation(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Curated facet overrides keyed by item id (``ns/name`` or ``kind:ns/name``)."""
    data = _read(CURATION, path)
    items = data.get("items") or {}
    if not isinstance(items, dict):
        raise TaxonomyError("curation.yaml: `items` must map item ids to facet overrides")
    return {str(k): dict(v or {}) for k, v in items.items()}


__all__ = ["Dimension", "Taxonomy", "TaxonomyError", "Term", "load", "load_curation", "parse"]
