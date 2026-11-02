"""Find items that do the same job, and benchmark them on evidence Dex holds (``dex overlap``).

Upstream libraries often ship several items for one job. Dex keeps them all; picking a best reference is a curation
decision. This module finds candidate groups and scores each member on verifiable signals only:

- install checks pass for every target it supports (``install-checks.json``);
- facets reviewed by a person (``facets.json``);
- runs no code, or its code is visible (``executes_code``);
- a description long enough to trigger reliably;
- a licence with evidence.

Similarity is word overlap (Jaccard) between titles and descriptions of items of the same kind that share a task.
It finds candidates; a person confirms them as ``alternative-to`` relations with evidence.
"""

from __future__ import annotations

import re
from typing import Any

from dex_trove import checks, facets, releases
from dex_trove.paths import trove_root

_WORD = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "your",
        "you",
        "are",
        "use",
        "using",
        "into",
        "when",
        "what",
        "which",
        "will",
        "can",
        "its",
        "not",
        "any",
        "all",
        "how",
        "about",
        "also",
        "more",
        "then",
        "than",
        "them",
        "they",
        "their",
        "there",
        "these",
        "those",
        "such",
        "via",
        "each",
        "other",
        "only",
        "should",
        "would",
        "could",
        "skill",
        "agent",
        "instruction",
        "prompt",
        "hook",
        "workflow",
        "plugin",
        "guide",
        "expert",
        "assistant",
        "helps",
        "help",
        "files",
        "file",
        "code",
    ]
)
# Items for different languages, frameworks or clouds do the same *kind* of job for different people: not overlap.
CONTEXT = ("language", "framework")


def words(item: dict[str, Any]) -> frozenset[str]:
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return frozenset(w.strip(".-") for w in _WORD.findall(text) if w.strip(".-") not in _STOP)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def score(item: dict[str, Any], record: dict[str, Any], checked: dict[str, str]) -> tuple[float, list[str]]:
    """0–1 and the reasons, from signals Dex can verify."""
    parts: list[tuple[float, str]] = []
    if checked:
        ok = all(v == "pass" for v in checked.values())
        parts.append((1.0 if ok else 0.0, "install checks pass" if ok else "an install check fails"))
    reviewed = record.get("classification", {}).get("review_status") == "approved"
    parts.append((1.0 if reviewed else 0.4, "facets reviewed" if reviewed else "facets suggested"))
    runs = bool(item.get("executes_code"))
    parts.append((0.6 if runs else 1.0, "bundles code to review" if runs else "runs no code"))
    length = len(item.get("description") or "")
    good = 80 <= length <= 1024
    parts.append((1.0 if good else 0.5, "clear description" if good else "description too short or too long"))
    lic = bool((item.get("license") or {}).get("evidence"))
    parts.append((1.0 if lic else 0.0, "licence evidence" if lic else "no licence evidence"))
    return round(sum(p for p, _ in parts) / len(parts), 2), [r for _, r in parts]


def groups(items: list[dict[str, Any]], *, threshold: float = 0.45) -> list[dict[str, Any]]:
    """Connected groups of same-kind items sharing a task whose word overlap reaches ``threshold``."""
    recs = facets.load()
    checked = checks.load(trove_root())["items"]
    keyed = {releases.key_of(it): it for it in items}
    fac = {k: recs.get(k, {}).get("facets", {}) for k in keyed}
    tasks = {k: set(fac[k].get("task", [])) for k in keyed}

    def same_context(a: str, b: str) -> bool:
        for dim in CONTEXT:
            x, y = set(fac[a].get(dim, [])), set(fac[b].get(dim, []))
            if x and y and not x & y:
                return False
        return True

    vocab = {k: words(it) for k, it in keyed.items()}
    parent = {k: k for k in keyed}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    pairs: dict[tuple[str, str], float] = {}
    by_kind: dict[str, list[str]] = {}
    for k, it in keyed.items():
        by_kind.setdefault(it["kind"], []).append(k)
    for ks in by_kind.values():
        ks.sort()
        for i, a in enumerate(ks):
            for b in ks[i + 1 :]:
                if not tasks[a] & tasks[b] or not same_context(a, b):
                    continue
                sim = jaccard(vocab[a], vocab[b])
                if sim >= threshold:
                    pairs[(a, b)] = sim
                    parent[find(a)] = find(b)
    clusters: dict[str, list[str]] = {}
    for a, b in pairs:
        for k in (a, b):
            clusters.setdefault(find(k), [])
            if k not in clusters[find(k)]:
                clusters[find(k)].append(k)
    out: list[dict[str, Any]] = []
    for members in clusters.values():
        rows: list[dict[str, Any]] = []
        for k in sorted(members):
            s, why = score(keyed[k], recs.get(k, {}), checked.get(k, {}))
            rows.append({"key": k, "title": keyed[k].get("title", ""), "score": s, "why": why})
        rows.sort(key=lambda r: (-r["score"], r["key"]))
        rows[0]["best"] = len(rows) > 1 and rows[0]["score"] > rows[1]["score"]
        sims = [v for (a, b), v in pairs.items() if a in members and b in members]
        out.append({"similarity": round(max(sims), 2), "members": rows})
    out.sort(key=lambda g: (-g["similarity"], g["members"][0]["key"]))
    return out


__all__ = ["groups", "jaccard", "score", "words"]
