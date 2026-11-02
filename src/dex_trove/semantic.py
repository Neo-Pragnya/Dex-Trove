"""Optional "semantic-lite" ranking: BM25 with stemming, plus query expansion through the taxonomy (``--rank semantic``).

The default search requires every word to match, which is predictable but misses natural questions such as
"find the root cause of a bug". This ranker scores partial matches with BM25 over an item's name, title, tags and
description, and expands the query through the taxonomy: when the query matches a facet term's own rule ("root
cause" → task ``debug``), items carrying that facet score higher.

It uses no model, no network and no new dependency, and it only reorders and widens results. It never changes what
an item may do. ``tests/test_search_eval.py`` checks that it beats the lexical baseline on a labelled query set.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from dex_trove import facets, taxonomy

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    [
        "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "my", "me", "i", "it", "is", "be",
        "how", "do", "does", "can", "into", "from", "by", "at", "as", "that", "this", "before", "without", "going",
        "use", "using", "your", "you", "its", "are", "will", "when", "what", "which", "two", "once",
    ]
)  # fmt: skip
FIELDS = (("name", 3.0), ("title", 2.0), ("tags", 1.0), ("description", 1.0))
FACET_WEIGHT = 2.0
K1, B = 1.2, 0.75


def stem(word: str) -> str:
    """A light suffix stripper; enough to join test/tests/testing, plan/planning, review/reviews."""
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "es", "ed", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    return word[:-1] if len(word) > 4 and word[-1] == word[-2] else word


def tokens(text: str) -> list[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def _doc(item: dict[str, Any]) -> Counter[str]:
    c: Counter[str] = Counter()
    for field, weight in FIELDS:
        value = item.get(field, "")
        text = " ".join(value) if isinstance(value, list) else str(value).replace("-", " ")
        for t in tokens(text):
            c[t] += weight  # type: ignore[assignment]
    return c


def expand(query: str, tax: taxonomy.Taxonomy) -> set[tuple[str, str]]:
    """Facet terms whose own match rules fire on the query text."""
    hits: set[tuple[str, str]] = set()
    for dim_id, dim in tax.dimensions.items():
        for term in dim.terms.values():
            if any(p.search(query) for p in term.match):
                hits.add((dim_id, term.id))
    return hits


def rank(
    items: list[dict[str, Any]], query: str, tax: taxonomy.Taxonomy | None = None
) -> list[dict[str, Any]]:
    tax = tax or taxonomy.load()
    q = [t for t in dict.fromkeys(tokens(query))]
    docs = [_doc(it) for it in items]
    n = len(docs) or 1
    avg = sum(sum(d.values()) for d in docs) / n
    df = Counter(t for d in docs for t in set(d) if t in q)
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q}
    wanted = expand(query.lower(), tax)
    records = facets.load()
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for it, d in zip(items, docs, strict=True):
        length = sum(d.values())
        s = 0.0
        for t in q:
            f = d.get(t, 0)
            if f:
                s += idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / avg))
        if wanted:
            have = records.get(f"{it['kind']}:{it['id']}", {}).get("facets", {})
            matched = sum(
                1
                for dim, term in wanted
                if term in (have.get(dim) if isinstance(have.get(dim), list) else [have.get(dim)])
            )
            s += (
                FACET_WEIGHT * matched / len(wanted) if s > 0 else 0.0
            )  # facets refine word matches; alone they're too broad
        if s > 0:
            scored.append((s, f"{it['kind']}:{it['id']}", it))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [it for _, _, it in scored]


__all__ = ["expand", "rank", "stem", "tokens"]
