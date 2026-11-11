"""SAS to Python, without silently changing what the numbers mean.

* ``sas_inventory`` reads SAS programs: DATA steps, PROCs, PROC SQL, macros (defined and called), ``%let``,
  ``libname`` and ``%include``, with the datasets each step reads and writes and the line it starts on.
* ``sas_lineage`` connects them (dataset to step to dataset) and gives every step a verdict: **supported**,
  **partial** (translated, with the semantic difference named) or **unsupported** (not translated). Macro bodies and
  macro calls are always quarantined: they're listed, never expanded or guessed.
* ``sas_draft`` writes a pandas draft for the supported and partial steps. SAS rules that differ from pandas are
  kept on purpose by small helpers in the draft: a missing value is smaller than any number in comparisons, ``.``
  equals ``.``, SUM/MEAN/MIN/MAX skip missing values, trailing blanks don't count in text comparisons, PROC SORT is
  stable. Every translated statement cites its SAS line, and an unsupported step stops the run (``NotTranslated``)
  naming the line and the reason, so nothing runs that wasn't translated.
* ``sas_parity`` compares an output SAS produced with the draft's output (CSV) within a declared tolerance, by key
  or by position, and reports which outputs came from steps that weren't translated.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dex_trove.mcp.common import (
    Context,
    ToolError,
    artifact,
    finding,
    result,
    write_json,
    write_sarif,
)
from dex_trove.mcp.server import Tool

NAME = "sas"
TITLE = "SAS: inventory, lineage, a pandas draft and parity checks"
CAPABILITIES = (
    "CAP-sas-modernization-01",
    "CAP-sas-modernization-02",
    "CAP-sas-modernization-03",
    "CAP-sas-modernization-04",
)
INSTRUCTIONS = (
    "Moves SAS programs to Python step by step with evidence. Order: sas_inventory (steps, datasets, macros), "
    "sas_lineage (what feeds what, and which steps are supported, partial or unsupported), sas_draft (a pandas draft "
    "that keeps SAS missing-value rules and refuses to run untranslated steps), then sas_parity to compare outputs "
    "from SAS and from the draft within a tolerance. Never present a partial or unsupported step as equivalent."
)
MAX_BYTES = 5_000_000
MACRO_KEYWORDS = frozenset(
    {
        "let",
        "put",
        "if",
        "then",
        "else",
        "do",
        "end",
        "to",
        "by",
        "while",
        "until",
        "include",
        "global",
        "local",
        "macro",
        "mend",
        "sysfunc",
        "eval",
        "sysevalf",
        "str",
        "nrstr",
        "quote",
        "bquote",
        "superq",
        "upcase",
        "scan",
        "substr",
        "length",
        "index",
        "symexist",
        "abort",
        "return",
        "goto",
        "syscall",
        "sysexec",
        "window",
        "display",
        "input",
    }
)
UNSUPPORTED_STATEMENTS = {
    "retain": "RETAIN carries values across rows",
    "array": "arrays",
    "do": "DO loops",
    "end": "DO loops",
    "output": "explicit OUTPUT",
    "infile": "reading raw files (INFILE/INPUT)",
    "input": "reading raw files (INFILE/INPUT)",
    "datalines": "inline data",
    "cards": "inline data",
    "call": "CALL routines",
    "put": "PUT statements",
    "select": "SELECT/WHEN",
    "update": "UPDATE",
    "modify": "MODIFY",
    "link": "LINK/RETURN",
    "goto": "GOTO",
    "return": "LINK/RETURN",
    "stop": "STOP",
    "abort": "ABORT",
}
UNSUPPORTED_PATTERNS = {
    r"\blag\d*\s*\(": "LAG reads earlier rows",
    r"\bdif\d*\s*\(": "DIF reads earlier rows",
    r"\b(first|last)\.\w": "BY-group FIRST./LAST.",
    r"\b_n_\b": "_N_ row numbers",
    r"\bthen\s+do\b": "DO blocks",
    r"\belse\s+do\b": "DO blocks",
}
IGNORED_DATA = frozenset({"length", "format", "informat", "label", "attrib"})
FUNCTIONS = {
    "sum": "sas_sum",
    "mean": "sas_mean",
    "min": "sas_min",
    "max": "sas_max",
    "missing": "sas_missing",
    "round": "sas_round",
    "abs": "sas_abs",
    "int": "sas_int",
    "sqrt": "sas_sqrt",
    "log": "sas_log",
    "exp": "sas_exp",
    "upcase": "sas_upcase",
    "lowcase": "sas_lowcase",
    "strip": "sas_strip",
    "trim": "sas_trim",
    "substr": "sas_substr",
    "coalesce": "sas_coalesce",
    "coalescec": "sas_coalesce",
    "cats": "sas_cats",
    "n": "sas_n",
    "nmiss": "sas_nmiss",
}
SUPPORTED_PROCS = {"sort", "means", "summary", "freq", "sql"}
NO_OUTPUT_PROCS = {"print", "contents", "datasets", "options", "format", "printto", "template", "report"}
STATS = {
    "n": "count",
    "mean": "mean",
    "sum": "sum",
    "min": "min",
    "max": "max",
    "std": "std",
    "median": "median",
    "nmiss": "nmiss",
}


@dataclass
class Statement:
    text: str
    line: int
    file: str


@dataclass
class Step:
    kind: str  # data | proc | macro-def | macro-call
    name: str
    file: str
    line: int
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)
    verdict: str = "supported"
    reasons: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.file}:{self.line}"

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "verdict": self.verdict,
            "reasons": self.reasons,
        }


# ── Lexing ──────────────────────────────────────────────────────────────────


def _blank_comments(text: str) -> str:
    """Removes /* */ comments, keeping newlines so line numbers stay right."""
    out, i, n, quote = [], 0, len(text), ""
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            i += 1
        elif ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append("".join(c if c == "\n" else " " for c in text[i:end]))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def statements(text: str, file: str) -> list[Statement]:
    text = _blank_comments(text)
    found: list[Statement] = []
    buf: list[str] = []
    quote, line, start = "", 1, 1
    for ch in text:
        if not buf and ch.isspace():
            line += ch == "\n"
            start = line
            continue
        if not buf:
            start = line
        buf.append(ch)
        if ch == "\n":
            line += 1
        comment = buf[0] == "*" or (buf[0] == "%" and len(buf) > 1 and buf[1] == "*")
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"" and not comment:  # quotes in a * comment don't open strings
            quote = ch
        elif ch == ";":
            stmt = "".join(buf[:-1]).strip()
            buf = []
            if stmt and not stmt.startswith("*") and not stmt.lower().startswith("%*"):
                found.append(Statement(re.sub(r"\s+", " ", stmt), start, file))
    rest = "".join(buf).strip()
    if rest:
        found.append(Statement(re.sub(r"\s+", " ", rest), start, file))
    return found


def _word(stmt: Statement) -> str:
    match = re.match(r"%?[A-Za-z_][\w.]*", stmt.text)
    return match.group(0).lower() if match else ""


def _datasets(text: str) -> list[str]:
    """Dataset names in a list like ``a b(keep=x) lib.c``, without their options."""
    text = re.sub(r"\([^()]*\)", " ", text)
    return [w.lower() for w in re.findall(r"[A-Za-z_&][\w.&]*", text) if not w.startswith("&")]


def _option(text: str, name: str) -> str | None:
    match = re.search(rf"\b{name}\s*=\s*([A-Za-z_][\w.]*)", text, re.I)
    return match.group(1).lower() if match else None


# ── Parsing ─────────────────────────────────────────────────────────────────


def parse(ctx: Context, files: list[Path]) -> dict[str, Any]:
    steps: list[Step] = []
    macros: dict[str, dict[str, Any]] = {}
    lets: dict[str, str] = {}
    libnames: dict[str, str] = {}
    includes: list[dict[str, Any]] = []
    for path in files:
        if path.stat().st_size > MAX_BYTES:
            raise ToolError(f"{path.name}: larger than {MAX_BYTES} bytes")
        rel = path.relative_to(ctx.root).as_posix()
        stmts = statements(path.read_text(encoding="utf-8", errors="replace"), rel)
        current: Step | None = None
        macro: Step | None = None
        for stmt in stmts:
            word = _word(stmt)
            if macro is not None:
                macro.statements.append(stmt)
                if word == "%mend":
                    macro = None
                continue
            if word == "%macro":
                named = re.match(r"%macro\s+(\w+)", stmt.text, re.I)
                name = named.group(1).lower() if named else "?"
                macro = Step(
                    "macro-def",
                    name,
                    rel,
                    stmt.line,
                    verdict="unsupported",
                    reasons=["macro definitions are quarantined"],
                )
                macros[name] = {"file": rel, "line": stmt.line}
                steps.append(macro)
                current = None
                continue
            if word == "%let":
                match = re.match(r"%let\s+(\w+)\s*=\s*(.*)", stmt.text, re.I)
                if match:
                    lets[match.group(1).lower()] = match.group(2).strip()
                continue
            if word == "%include":
                includes.append({"file": rel, "line": stmt.line, "target": stmt.text[8:].strip()})
                continue
            if word.startswith("%") and word[1:] not in MACRO_KEYWORDS:
                steps.append(
                    Step(
                        "macro-call",
                        word[1:],
                        rel,
                        stmt.line,
                        statements=[stmt],
                        verdict="unsupported",
                        reasons=[
                            f"macro call %{word[1:]} is quarantined: expand it by hand or translate the macro"
                        ],
                    )
                )
                current = None
                continue
            if word == "libname":
                match = re.match(r"libname\s+(\w+)\s+['\"]([^'\"]*)['\"]", stmt.text, re.I)
                if match:
                    libnames[match.group(1).lower()] = match.group(2)
                continue
            if word == "data":
                current = Step("data", "data", rel, stmt.line, statements=[stmt])
                current.outputs = [d for d in _datasets(stmt.text[4:]) if d != "_null_"]
                steps.append(current)
                continue
            if word == "proc":
                match = re.match(r"proc\s+(\w+)", stmt.text, re.I)
                name = match.group(1).lower() if match else "?"
                current = Step("proc", name, rel, stmt.line, statements=[stmt])
                if src := _option(stmt.text, "data"):
                    current.inputs.append(src)
                if out := _option(stmt.text, "out"):
                    current.outputs.append(out)
                steps.append(current)
                continue
            if word in {"run", "quit"}:
                current = None
                continue
            if current is None:
                steps.append(
                    Step(
                        "global",
                        word or "?",
                        rel,
                        stmt.line,
                        statements=[stmt],
                        verdict="unsupported",
                        reasons=[f"statement outside a step: {stmt.text[:60]}"],
                    )
                )
                continue
            current.statements.append(stmt)
            if current.kind == "data" and word in {"set", "merge"}:
                current.inputs += _datasets(stmt.text[len(word) :])
            if current.kind == "proc":
                if current.name == "sql":
                    _sql_io(current, stmt)
                elif out := _option(stmt.text, "out"):
                    current.outputs.append(out)
    for step in steps:
        _judge(step, lets)
        step.inputs = list(dict.fromkeys(step.inputs))
        step.outputs = list(dict.fromkeys(step.outputs))
        if step.kind == "proc" and step.name in {"sort"} and step.inputs and not step.outputs:
            step.outputs = list(step.inputs)  # sorts in place
    return {"steps": steps, "macros": macros, "lets": lets, "libnames": libnames, "includes": includes}


def _sql_io(step: Step, stmt: Statement) -> None:
    match = re.match(r"create\s+table\s+([\w.]+)\s+as\s+(.*)", stmt.text, re.I)
    if match:
        step.outputs.append(match.group(1).lower())
        step.inputs += [
            m.lower() for m in re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", match.group(2), re.I)
        ]


def _judge(step: Step, lets: dict[str, str]) -> None:
    if step.kind in {"macro-def", "macro-call", "global"}:
        return
    body = " ".join(s.text for s in step.statements).lower()
    if "&" in body and re.search(r"&(\w+)", body):
        unknown = sorted({m for m in re.findall(r"&(\w+)", body) if m not in lets})
        if unknown:
            step.verdict = "unsupported"
            step.reasons.append(
                f"macro variables without a %let value: {', '.join('&' + u for u in unknown)}"
            )
            return
    if step.kind == "data":
        reasons = []
        for stmt in step.statements:
            word = _word(stmt)
            lowered = stmt.text.lower()
            if word in UNSUPPORTED_STATEMENTS:
                reasons.append(f"line {stmt.line}: {UNSUPPORTED_STATEMENTS[word]}")
            for pattern, why in UNSUPPORTED_PATTERNS.items():
                if re.search(pattern, lowered):
                    reasons.append(f"line {stmt.line}: {why}")
            if word in {"data", "set", "merge"} and "(" in stmt.text:
                reasons.append(
                    f"line {stmt.line}: dataset options in parentheses (keep=, where=, rename=...)"
                )
            if word == "merge":
                step.verdict = "partial"
                step.reasons.append(
                    f"line {stmt.line}: MERGE translated as a join; SAS match-merge differs for many-to-many keys"
                )
        if len(step.outputs) > 1:
            reasons.append("more than one output dataset")
        if not any(_word(s) in {"set", "merge"} for s in step.statements[1:]):
            reasons.append("no SET or MERGE (the step makes data from nothing)")
        if reasons:
            step.verdict = "unsupported"
            step.reasons = sorted(set(reasons))
        return
    if step.name in NO_OUTPUT_PROCS:
        step.verdict = "skipped"
        step.reasons.append(f"PROC {step.name.upper()} writes no dataset")
        return
    if step.name not in SUPPORTED_PROCS:
        step.verdict = "unsupported"
        step.reasons.append(
            f"PROC {step.name.upper()} isn't translated (statistical and reporting procedures need a person)"
        )
        return
    opts = step.statements[0].text.lower()
    if step.name in {"means", "summary"}:
        if "nway" not in opts:
            step.verdict = "partial"
            step.reasons.append(
                "without NWAY, SAS also writes every class combination (_TYPE_); the draft writes the full crossing only"
            )
        if not any(_word(s) == "output" for s in step.statements[1:]):
            step.verdict = "skipped"
            step.reasons.append("no OUTPUT OUT= dataset")
    if step.name == "freq":
        tables = [s for s in step.statements[1:] if _word(s) == "tables"]
        if any("*" in s.text for s in tables):
            step.verdict = "unsupported"
            step.reasons.append("crosstabs (a*b) aren't translated")
        elif not step.outputs:
            step.verdict = "skipped"
            step.reasons.append("no OUT= dataset")
        else:
            step.verdict = "partial"
            step.reasons.append(
                "missing levels: SAS leaves them out of PERCENT unless MISSING; check with parity"
            )
    if step.name == "sql":
        step.verdict = "partial"
        step.reasons.append(
            "PROC SQL runs through SQLite in the draft: check functions and CALCULATED columns"
        )


# ── Expressions ─────────────────────────────────────────────────────────────

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+\.?\d*(?:e[+-]?\d+)?|\.\d+)|(?P<miss>\.(?![\w]))|(?P<str>'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")"
    r"|(?P<op>\*\*|\|\||<=|>=|\^=|~=|¬=|=|<|>|\+|-|\*|/|\(|\)|,)|(?P<name>[A-Za-z_][\w.]*))",
    re.I,
)
_WORD_OPS = {"eq": "=", "ne": "^=", "lt": "<", "gt": ">", "le": "<=", "ge": ">="}
_CMP = {
    "=": "sas_eq",
    "^=": "sas_ne",
    "~=": "sas_ne",
    "¬=": "sas_ne",
    "<": "sas_lt",
    ">": "sas_gt",
    "<=": "sas_le",
    ">=": "sas_ge",
}


class Untranslatable(Exception):
    pass


def _tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            if text[pos:].strip():
                raise Untranslatable(f"can't read {text[pos : pos + 20]!r}")
            break
        kind = match.lastgroup or ""
        value = match.group(kind)
        if kind == "name" and value.lower() in _WORD_OPS:
            kind, value = "op", _WORD_OPS[value.lower()]
        elif kind == "name" and value.lower() in {"and", "or", "not", "in"}:
            kind, value = "kw", value.lower()
        out.append((kind, value))
        pos = match.end()
    return out


class _Expr:
    """Recursive descent over SAS expressions, producing Python that calls the draft's SAS helpers."""

    def __init__(self, text: str, df: str) -> None:
        self.toks = _tokens(text)
        self.i = 0
        self.df = df

    def peek(self) -> tuple[str, str]:
        return self.toks[self.i] if self.i < len(self.toks) else ("", "")

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self) -> str:
        out = self.or_()
        if self.i != len(self.toks):
            raise Untranslatable(f"unexpected {self.peek()[1]!r}")
        return out

    def or_(self) -> str:
        left = self.and_()
        while self.peek() == ("kw", "or"):
            self.take()
            left = f"sas_or({left}, {self.and_()})"
        return left

    def and_(self) -> str:
        left = self.not_()
        while self.peek() == ("kw", "and"):
            self.take()
            left = f"sas_and({left}, {self.not_()})"
        return left

    def not_(self) -> str:
        if self.peek() == ("kw", "not"):
            self.take()
            return f"sas_not({self.not_()})"
        return self.cmp()

    def cmp(self) -> str:
        left = self.concat()
        kind, value = self.peek()
        if kind == "op" and value in _CMP:
            self.take()
            return f"{_CMP[value]}({left}, {self.concat()})"
        if (kind, value) == ("kw", "in"):
            self.take()
            if self.take() != ("op", "("):
                raise Untranslatable("IN needs a list in parentheses")
            items = [self.concat()]
            while self.peek() == ("op", ","):
                self.take()
                items.append(self.concat())
            if self.take() != ("op", ")"):
                raise Untranslatable("unclosed IN list")
            return f"sas_in({left}, [{', '.join(items)}])"
        return left

    def concat(self) -> str:
        left = self.add()
        while self.peek() == ("op", "||"):
            self.take()
            left = f"sas_concat({left}, {self.add()})"
        return left

    def add(self) -> str:
        left = self.mul()
        while self.peek()[1] in {"+", "-"} and self.peek()[0] == "op":
            op = self.take()[1]
            left = f"({left} {op} {self.mul()})"
        return left

    def mul(self) -> str:
        left = self.power()
        while self.peek()[1] in {"*", "/"} and self.peek()[0] == "op":
            op = self.take()[1]
            left = f"sas_div({left}, {self.power()})" if op == "/" else f"({left} * {self.power()})"
        return left

    def power(self) -> str:
        base = self.unary()
        if self.peek() == ("op", "**"):
            self.take()
            return f"({base} ** {self.unary()})"
        return base

    def unary(self) -> str:
        if self.peek() in {("op", "-"), ("op", "+")}:
            op = self.take()[1]
            return f"({op}{self.unary()})"
        return self.atom()

    def atom(self) -> str:
        kind, value = self.take()
        if kind == "num":
            return value
        if kind == "miss":
            return "MISSING"
        if kind == "str":
            inner = value[1:-1].replace(value[0] * 2, value[0])
            return repr(inner)
        if (kind, value) == ("op", "("):
            inner = self.or_()
            if self.take() != ("op", ")"):
                raise Untranslatable("unclosed parenthesis")
            return f"({inner})"
        if kind == "name":
            low = value.lower()
            if self.peek() == ("op", "("):
                if low not in FUNCTIONS:
                    raise Untranslatable(f"function {value.upper()} isn't translated")
                self.take()
                args = []
                if self.peek() != ("op", ")"):
                    args.append(self.or_())
                    while self.peek() == ("op", ","):
                        self.take()
                        args.append(self.or_())
                if self.take() != ("op", ")"):
                    raise Untranslatable("unclosed function call")
                return f"{FUNCTIONS[low]}({', '.join(args)})"
            if "." in low:
                raise Untranslatable(f"{value} (FIRST./LAST. or a dotted name)")
            return f'{self.df}["{low}"]'
        raise Untranslatable(f"unexpected {value!r}")


def expr(text: str, df: str = "df") -> str:
    return _Expr(text, df).parse()


# ── Draft ───────────────────────────────────────────────────────────────────

HELPERS = '''
# ---- SAS semantics kept on purpose (do not "simplify" these away) -----------------------------------------
import math
import sqlite3
import sys
import numpy as np
import pandas as pd

MISSING = np.nan


def _num(x):
    return pd.to_numeric(x, errors="coerce") if isinstance(x, pd.Series) else x


def _is_text(x):
    """Text in pandas 2 (object) and pandas 3 (the str dtype) alike."""
    if isinstance(x, pd.Series):
        return x.dtype == object or pd.api.types.is_string_dtype(x.dtype)
    return isinstance(x, str)


def _key(x):
    """Missing sorts below every number in SAS comparisons; text ignores trailing blanks."""
    if _is_text(x):
        return x.fillna("").astype(str).str.rstrip() if isinstance(x, pd.Series) else x.rstrip()
    x = _num(x)
    return x.fillna(-math.inf) if isinstance(x, pd.Series) else (-math.inf if x is None or (isinstance(x, float) and math.isnan(x)) else x)


def sas_eq(a, b): return _key(a) == _key(b)
def sas_ne(a, b): return _key(a) != _key(b)
def sas_lt(a, b): return _key(a) < _key(b)
def sas_le(a, b): return _key(a) <= _key(b)
def sas_gt(a, b): return _key(a) > _key(b)
def sas_ge(a, b): return _key(a) >= _key(b)
def sas_in(a, items): return _key(a).isin([_key(i) for i in items]) if isinstance(a, pd.Series) else _key(a) in [_key(i) for i in items]


def _truth(x):
    """A condition is true when it's non-zero and not missing."""
    if isinstance(x, pd.Series) and x.dtype != bool:
        x = _num(x)
        return x.notna() & (x != 0)
    return x


def sas_and(a, b): return _truth(a) & _truth(b)
def sas_or(a, b): return _truth(a) | _truth(b)
def sas_not(a): return ~_truth(a)
def sas_div(a, b):
    """Division by zero gives missing, as in SAS (with a note in the log there)."""
    a, b = _num(a), _num(b)
    return a / (b.replace(0, np.nan) if isinstance(b, pd.Series) else (np.nan if b == 0 else b))


def _frame(args): return pd.concat([pd.Series(_num(a)) if not isinstance(a, pd.Series) else _num(a) for a in args], axis=1)
def sas_sum(*a): f = _frame(a); return f.sum(axis=1, min_count=1)
def sas_mean(*a): return _frame(a).mean(axis=1)
def sas_min(*a): return _frame(a).min(axis=1)
def sas_max(*a): return _frame(a).max(axis=1)
def sas_n(*a): return _frame(a).notna().sum(axis=1)
def sas_nmiss(*a): return _frame(a).isna().sum(axis=1)
def sas_missing(a): return a.isna() | (a.astype(str).str.strip() == "") if _is_text(a) else _num(a).isna()
def sas_round(a, unit=1):
    """SAS rounds half away from zero; Python's round() rounds half to even."""
    v = _num(a) / unit
    return np.where(v >= 0, np.floor(v + 0.5), -np.floor(-v + 0.5)) * unit
def sas_abs(a): return _num(a).abs()
def sas_int(a): return np.trunc(_num(a))
def sas_sqrt(a): return np.sqrt(_num(a))
def sas_log(a): return np.log(_num(a).where(_num(a) > 0))
def sas_exp(a): return np.exp(_num(a))
def sas_upcase(a): return a.str.upper()
def sas_lowcase(a): return a.str.lower()
def sas_strip(a): return a.str.strip()
def sas_trim(a): return a.str.rstrip()
def sas_substr(a, start, length=None): return a.str[int(start) - 1:None if length is None else int(start) - 1 + int(length)]
def sas_coalesce(*a):
    out = a[0]
    for x in a[1:]:
        out = out.combine_first(x) if isinstance(x, pd.Series) else out.fillna(x)
    return out
def sas_cats(*a): return pd.concat([pd.Series(x).astype(str).str.strip() for x in a], axis=1).fillna("").agg("".join, axis=1)
def sas_concat(a, b): return a.astype(str) + (b.astype(str) if isinstance(b, pd.Series) else str(b))


def assign(df, name, value, where=None):
    """Assignment, optionally only where a condition holds (other rows keep their value, or missing if new)."""
    if where is None:
        df[name] = value
        return df
    if name not in df:
        df[name] = pd.Series([""] * len(df), index=df.index, dtype=object) if _is_text(value) else MISSING
    mask = _truth(where).fillna(False) if isinstance(where, pd.Series) else where
    df.loc[mask, name] = value[mask] if isinstance(value, pd.Series) else value
    return df


def sort(df, by, descending=(), nodupkey=False):
    """PROC SORT: stable, missing first in ascending order (as in SAS)."""
    order = pd.DataFrame({i: _key(df[c]) for i, c in enumerate(by)})
    idx = order.sort_values(list(range(len(by))), ascending=[c not in descending for c in by], kind="mergesort").index
    out = df.loc[idx]
    if nodupkey:
        out = out.loc[~order.loc[idx].duplicated()]
    return out.reset_index(drop=True)


class NotTranslated(NotImplementedError):
    pass


SKIPPED = []


def not_translated(where, strict):
    """An untranslated step stops the run, unless --skip-unsupported: then its outputs are simply missing."""
    if strict:
        raise NotTranslated(where)
    SKIPPED.append(where)


def sql(query, tables):
    with sqlite3.connect(":memory:") as db:
        for name, frame in tables.items():
            frame.to_sql(name.replace(".", "__"), db, index=False)
        return pd.read_sql_query(query, db)
# ------------------------------------------------------------------------------------------------------------
'''


def _ident(dataset: str) -> str:
    return dataset.lower()


def _apply_lets(text: str, lets: dict[str, str]) -> str:
    return re.sub(r"&(\w+)\.?", lambda m: lets.get(m.group(1).lower(), m.group(0)), text)


def _data_step(step: Step, lets: dict[str, str]) -> list[str]:
    code: list[str] = []
    src_stmt = next(s for s in step.statements[1:] if _word(s) in {"set", "merge"})
    sources = _datasets(_apply_lets(src_stmt.text[len(_word(src_stmt)) :], lets))
    by = next((_datasets(s.text[2:]) for s in step.statements[1:] if _word(s) == "by"), [])
    if _word(src_stmt) == "merge":
        code.append(
            f"    # line {src_stmt.line}: {src_stmt.text}  (PARTIAL: match-merge as an outer join on {by})"
        )
        code.append(f"    df = data[{sources[0]!r}].copy()")
        for other in sources[1:]:
            code.append(
                f"    df = df.merge(data[{other!r}], on={by!r}, how='outer', suffixes=('', '__right'))"
            )
            code.append("    df = df[[c for c in df.columns if not c.endswith('__right')]]")
    else:
        code.append(f"    # line {src_stmt.line}: {src_stmt.text}")
        code.append(f"    df = pd.concat([data[d] for d in {sources!r}], ignore_index=True)")
    for stmt in step.statements[1:]:
        if _word(stmt) == "where":
            code.append(f"    # line {stmt.line}: {stmt.text}")
            code.append(
                f"    df = df[_truth({expr(_apply_lets(stmt.text[5:], lets))}).fillna(False)].reset_index(drop=True)"
            )
    keep: list[str] = []
    drop: list[str] = []
    renames: dict[str, str] = {}
    for stmt in step.statements[1:]:
        word = _word(stmt)
        text = _apply_lets(stmt.text, lets)
        if word in {"set", "merge", "by", "where"} or word in IGNORED_DATA:
            if word in IGNORED_DATA:
                code.append(f"    # line {stmt.line}: {stmt.text}  (metadata only, no effect on values)")
            continue
        code.append(f"    # line {stmt.line}: {stmt.text}")
        if word == "keep":
            keep += _datasets(text[4:])
        elif word == "drop":
            drop += _datasets(text[4:])
        elif word == "rename":
            renames.update({a.lower(): b.lower() for a, b in re.findall(r"(\w+)\s*=\s*(\w+)", text[6:])})
        elif word in {"if", "else"}:
            code += _conditional(text, stmt.line)
        elif match := re.match(r"(\w+)\s*=\s*(.+)$", text):
            code.append(f"    df = assign(df, {match.group(1).lower()!r}, {expr(match.group(2))})")
        else:
            raise Untranslatable(f"line {stmt.line}: {stmt.text[:40]}")
    if keep:
        code.append(
            f"    df = df[[c for c in df.columns if c in {keep!r}]]  # SAS keeps the PDV column order"
        )
    if drop:
        code.append(f"    df = df.drop(columns=[c for c in {drop!r} if c in df.columns])")
    if renames:
        code.append(f"    df = df.rename(columns={renames!r})")
    code.append(f"    data[{step.outputs[0]!r}] = df")
    return code


def _conditional(text: str, line: int) -> list[str]:
    """IF/THEN, ELSE IF/THEN and ELSE with an assignment or DELETE, or a subsetting IF. ``covered`` tracks the chain."""
    low = text.lower()
    if low.startswith("else"):
        rest = text[4:].strip()
        if rest.lower().startswith("if "):
            match = re.match(r"if\s+(.*?)\s+then\s+(.*)$", rest, re.I)
            if not match:
                raise Untranslatable(f"line {line}: ELSE IF without THEN")
            cond = expr(match.group(1))
            head = [f"    cond = sas_and(sas_not(covered), {cond})", f"    covered = sas_or(covered, {cond})"]
            action = match.group(2)
        else:
            head, action = ["    cond = sas_not(covered)"], rest
    elif match := re.match(r"if\s+(.*?)\s+then\s+(.*)$", text, re.I):
        cond = expr(match.group(1))
        head, action = [f"    cond = {cond}", "    covered = _truth(cond)"], match.group(2)
    else:
        return [f"    df = df[_truth({expr(text[2:])}).fillna(False)].reset_index(drop=True)"]
    if action.strip().lower() == "delete":
        return [
            *head,
            "    keep_rows = ~_truth(cond).fillna(False)",
            "    df, covered = df[keep_rows].reset_index(drop=True), covered[keep_rows].reset_index(drop=True)",
        ]
    assigned = re.match(r"(\w+)\s*=\s*(.+)$", action.strip())
    if not assigned:
        raise Untranslatable(f"line {line}: only an assignment or DELETE after THEN/ELSE is translated")
    return [
        *head,
        f"    df = assign(df, {assigned.group(1).lower()!r}, {expr(assigned.group(2))}, where=cond)",
    ]


def _proc_step(step: Step, lets: dict[str, str]) -> list[str]:
    first = _apply_lets(step.statements[0].text, lets)
    code = [f"    # line {step.line}: {step.statements[0].text}"]
    src = step.inputs[0] if step.inputs else None
    if step.name == "sort":
        by_stmt = next((s for s in step.statements[1:] if _word(s) == "by"), None)
        if by_stmt is None or src is None:
            raise Untranslatable("PROC SORT needs DATA= and BY")
        words = by_stmt.text.split()[1:]
        by, desc = [], []
        for i, w in enumerate(words):
            if w.lower() == "descending":
                continue
            by.append(w.lower())
            if i and words[i - 1].lower() == "descending":
                desc.append(w.lower())
        code.append(f"    # line {by_stmt.line}: {by_stmt.text}")
        nodup = "nodupkey" in first.lower()
        code.append(
            f"    data[{step.outputs[0]!r}] = sort(data[{src!r}], {by!r}, descending={tuple(desc)!r}, nodupkey={nodup})"
        )
        return code
    if step.name in {"means", "summary"}:
        cls = next((_datasets(s.text[5:]) for s in step.statements[1:] if _word(s) == "class"), [])
        var = next((_datasets(s.text[3:]) for s in step.statements[1:] if _word(s) == "var"), [])
        out_stmt = next(s for s in step.statements[1:] if _word(s) == "output")
        if not var:
            raise Untranslatable("PROC MEANS without VAR")
        code.append(f"    # line {out_stmt.line}: {out_stmt.text}")
        target = _option(out_stmt.text, "out") or "out"
        cols: list[tuple[str, str, str]] = []
        if "/" in out_stmt.text:
            raise Untranslatable("OUTPUT options after / (AUTONAME...)")
        text = out_stmt.text[6:]
        heads = list(re.finditer(r"\b(\w+)\s*(\([^)]*\))?\s*=", text))
        for n, found in enumerate(heads):
            stat, which = found.group(1).lower(), found.group(2) or ""
            names = text[found.end() : heads[n + 1].start() if n + 1 < len(heads) else len(text)].strip()
            if stat == "out":
                continue
            if stat not in STATS:
                raise Untranslatable(f"statistic {stat.upper()} isn't translated")
            vars_ = _datasets(which[1:-1]) if which else var
            labels = names.split() or vars_
            cols += [(v, stat, label.lower()) for v, label in zip(vars_, labels, strict=False)]
        code.append(f"    src = data[{src!r}]")
        code.append("    num = src.copy()")
        code.append(f"    for c in {var!r}: num[c] = _num(num[c])")
        if cls:
            code.append(f"    g = num.groupby({cls!r}, dropna=True, sort=True)")
            code.append("    out = g.size().rename('_freq_').reset_index()")
        else:
            code.append("    g = None")
            code.append("    out = pd.DataFrame({'_freq_': [len(num)]})")
        code.append(f"    out.insert(0, '_type_', {2 ** len(cls) - 1})")
        for v, stat, label in cols:
            func = STATS[stat]
            if func == "sum":
                calc = f"g[{v!r}].sum(min_count=1).values" if cls else f"[num[{v!r}].sum(min_count=1)]"
            elif func == "nmiss":
                calc = (
                    f"g[{v!r}].apply(lambda s: s.isna().sum()).values"
                    if cls
                    else f"[num[{v!r}].isna().sum()]"
                )
            else:
                calc = f"g[{v!r}].{func}().values" if cls else f"[num[{v!r}].{func}()]"
            code.append(f"    out[{label!r}] = {calc}")
        code.append(f"    data[{target!r}] = out")
        return code
    if step.name == "freq":
        tables = next(s for s in step.statements[1:] if _word(s) == "tables")
        var = _datasets(tables.text[6:].split("/")[0])
        if len(var) != 1:
            raise Untranslatable("only one-way TABLES with OUT= is translated")
        code.append(f"    # line {tables.line}: {tables.text}")
        code.append(f"    s = data[{src!r}][{var[0]!r}]")
        code.append(
            f"    counts = s.dropna().value_counts(sort=False).sort_index().rename_axis({var[0]!r}).reset_index(name='count')"
        )
        code.append("    counts['percent'] = counts['count'] / counts['count'].sum() * 100")
        code.append(f"    data[{step.outputs[0]!r}] = counts")
        return code
    if step.name == "sql":
        for stmt in step.statements[1:]:
            match = re.match(r"create\s+table\s+([\w.]+)\s+as\s+(.*)", _apply_lets(stmt.text, lets), re.I)
            if not match:
                raise Untranslatable(f"line {stmt.line}: only CREATE TABLE ... AS SELECT is translated")
            if re.search(r"\bcalculated\b", match.group(2), re.I):
                raise Untranslatable(f"line {stmt.line}: CALCULATED columns")
            query = re.sub(
                r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b",
                lambda m: (
                    f"{m.group(1)}__{m.group(2)}"
                    if m.group(1).lower() in {d.split(".")[0] for d in step.inputs if "." in d}
                    else m.group(0)
                ),
                match.group(2),
            )
            sources = list(step.inputs)
            code.append(f"    # line {stmt.line}: {stmt.text}  (PARTIAL: SQLite dialect)")
            code.append(
                f"    data[{match.group(1).lower()!r}] = sql({query!r}, {{d: data[d] for d in {sources!r}}})"
            )
        return code
    raise Untranslatable(f"PROC {step.name.upper()}")


def draft(parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    steps: list[Step] = parsed["steps"]
    lets = parsed["lets"]
    body: list[str] = []
    notes: list[dict[str, Any]] = []
    for step in steps:
        if step.verdict == "skipped" or step.kind == "global" and not step.outputs:
            continue
        body.append("")
        header = f"    # ---- {step.kind} {step.name} at {step.id}: {step.verdict.upper()}"
        if step.reasons:
            header += " (" + "; ".join(step.reasons) + ")"
        body.append(header)
        if step.verdict == "unsupported":
            body.append(
                f"    not_translated({f'{step.id}: not translated: ' + '; '.join(step.reasons)!r}, strict)"
            )
            notes.append({"step": step.id, "verdict": "unsupported", "reasons": step.reasons})
            continue
        try:
            body += _data_step(step, lets) if step.kind == "data" else _proc_step(step, lets)
        except (Untranslatable, StopIteration) as exc:
            step.verdict = "unsupported"
            step.reasons.append(f"not translated: {exc}")
            body[-1] = header.replace(": PARTIAL", ": UNSUPPORTED").replace(": SUPPORTED", ": UNSUPPORTED")
            body.append(f"    not_translated({f'{step.id}: not translated: {exc}'!r}, strict)")
        notes.append({"step": step.id, "verdict": step.verdict, "reasons": step.reasons})
    inputs = sorted({d for s in steps for d in s.inputs} - {d for s in steps for d in s.outputs})
    outputs = sorted({d for s in steps for d in s.outputs})
    source = (
        '"""Draft generated by dex-trove sas_draft. Review every PARTIAL step; UNSUPPORTED steps raise.\n\n'
        "Column names are lower-cased on load (SAS names are case-insensitive). Inputs: "
        + ", ".join(inputs)
        + ". Outputs: "
        + ", ".join(outputs)
        + '.\n"""\n'
        + HELPERS
        + '\n\ndef run(data, strict=True):\n    """data maps dataset names (lower case, lib.name) to DataFrames; returns it with the outputs added."""\n'
        + "    data = {k.lower(): v.rename(columns=str.lower) for k, v in data.items()}\n"
        + "\n".join(body)
        + "\n    return data\n\n\n"
        + "def main(argv=None):\n    import argparse, pathlib\n    p = argparse.ArgumentParser()\n"
        + "    p.add_argument('--data', required=True, help='folder with <dataset>.csv files (lib.name -> lib.name.csv)')\n"
        + "    p.add_argument('--out', required=True)\n"
        + "    p.add_argument('--skip-unsupported', action='store_true', help='run the translated steps, skip the rest')\n"
        + "    a = p.parse_args(argv)\n"
        + "    src = pathlib.Path(a.data)\n"
        + f"    data = {{d: pd.read_csv(src / (d + '.csv'), na_values=['.'], keep_default_na=True) for d in {inputs!r} if (src / (d + '.csv')).exists()}}\n"
        + "    data = run(data, strict=not a.skip_unsupported)\n    out = pathlib.Path(a.out)\n    out.mkdir(parents=True, exist_ok=True)\n"
        + f"    for d in {outputs!r}:\n        if d in data:\n            data[d].to_csv(out / (d + '.csv'), index=False)\n"
        + "    for where in SKIPPED:\n        print('skipped: ' + where, file=sys.stderr)\n\n\n"
        + "if __name__ == '__main__':\n    main()\n"
    )
    return source, notes


# ── Tools ───────────────────────────────────────────────────────────────────


def _sources(ctx: Context, paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for value in paths or ["."]:
        path = ctx.path(value)
        files += [path] if path.is_file() else sorted(p for p in path.rglob("*.sas") if ".dex" not in p.parts)
    if not files:
        raise ToolError("no .sas files found; pass paths to SAS programs or folders that contain them")
    bad = [p.name for p in files if p.suffix.lower() != ".sas"]
    if bad:
        raise ToolError(f"not SAS programs (.sas): {', '.join(bad)}")
    return files


def inventory(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    parsed = parse(ctx, _sources(ctx, args.get("paths") or []))
    steps = [s.summary() for s in parsed["steps"]]
    path = write_json(
        ctx.evidence / "inventory.json",
        {
            "schema": "dex-trove/sas-inventory@1",
            "steps": steps,
            "macros": parsed["macros"],
            "lets": parsed["lets"],
            "libnames": parsed["libnames"],
            "includes": parsed["includes"],
        },
    )
    warnings = [
        f"%include {i['target']} at {i['file']}:{i['line']} wasn't followed; add that file to paths"
        for i in parsed["includes"]
    ]
    return result(
        ctx,
        "ok",
        steps=steps,
        macros=parsed["macros"],
        lets=parsed["lets"],
        libnames=parsed["libnames"],
        datasets=sorted({d for s in steps for d in s["inputs"] + s["outputs"]}),
        warnings=warnings,
        artifacts=[artifact(ctx, path, "application/json", schema="dex-trove/sas-inventory@1")],
        inputs=args,
    )


def lineage(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    parsed = parse(ctx, _sources(ctx, args.get("paths") or []))
    steps: list[Step] = parsed["steps"]
    edges = [{"from": d, "to": s.id} for s in steps for d in s.inputs] + [
        {"from": s.id, "to": d} for s in steps for d in s.outputs
    ]
    counts = {
        v: sum(1 for s in steps if s.verdict == v) for v in ("supported", "partial", "unsupported", "skipped")
    }
    findings = [
        finding(
            "warning" if s.verdict == "partial" else "error",
            f"{s.kind} {s.name}: {s.verdict}: {'; '.join(s.reasons)}",
            rule=f"sas.{s.verdict}",
            uri=s.file,
            line=s.line,
            status="observed",
            remediation="translate by hand and prove it with sas_parity"
            if s.verdict == "unsupported"
            else "check this difference with sas_parity on representative data",
        )
        for s in steps
        if s.verdict in {"partial", "unsupported"}
    ]
    ids = {s.id: f"s{i}" for i, s in enumerate(steps)}
    lines = ["flowchart LR", *(f'  {ids[s.id]}["{s.kind} {s.name} ({s.verdict})"]' for s in steps)]
    for e in edges:
        a = ids.get(e["from"], "d_" + re.sub(r"\W", "_", e["from"]))
        b = ids.get(e["to"], "d_" + re.sub(r"\W", "_", e["to"]))
        lines.append(f"  {a} --> {b}")
    path = write_json(
        ctx.evidence / "lineage.json",
        {"schema": "dex-trove/sas-lineage@1", "steps": [s.summary() for s in steps], "edges": edges},
    )
    artifacts = [artifact(ctx, path, "application/json", schema="dex-trove/sas-lineage@1")]
    if findings:
        artifacts.append(
            artifact(ctx, write_sarif(ctx, "sas-lineage", findings, tool="dex-sas"), "application/sarif+json")
        )
    return result(
        ctx,
        "ok",
        counts=counts,
        steps=[s.summary() for s in steps],
        edges=edges,
        mermaid="\n".join(lines),
        findings=findings,
        artifacts=artifacts,
        inputs=args,
    )


def draft_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    parsed = parse(ctx, _sources(ctx, args.get("paths") or []))
    source, notes = draft(parsed)
    compile(source, "draft.py", "exec")  # the draft must at least be valid Python
    out = ctx.path(args.get("output") or "sas_draft.py", must_exist=False)
    if out.exists() and not args.get("overwrite"):
        raise ToolError(
            f"{out.relative_to(ctx.root)} exists; pass overwrite to replace it (or another output path)"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(source, encoding="utf-8")
    plan = write_json(
        ctx.evidence / "draft-plan.json",
        {"schema": "dex-trove/sas-draft@1", "draft": out.relative_to(ctx.root).as_posix(), "steps": notes},
    )
    counts = {v: sum(1 for n in notes if n["verdict"] == v) for v in ("supported", "partial", "unsupported")}
    warnings = []
    if counts["unsupported"]:
        warnings.append(
            f"{counts['unsupported']} step(s) stop the run until translated by hand (or run with --skip-unsupported)"
        )
    if counts["partial"]:
        warnings.append(
            f"{counts['partial']} step(s) are partial: prove them with sas_parity before relying on them"
        )
    return result(
        ctx,
        "drafted",
        counts=counts,
        steps=notes,
        warnings=warnings,
        artifacts=[
            artifact(ctx, out, "text/x-python", schema="dex-trove/sas-draft@1"),
            artifact(ctx, plan, "application/json", schema="dex-trove/sas-draft@1"),
        ],
        inputs=args,
    )


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ToolError(f"{path.name}: no header row")
    names = [n.strip().lower() for n in reader.fieldnames]
    rows = [
        {n: (v or "").strip() if v is not None else "" for n, v in zip(names, r.values(), strict=False)}
        for r in reader
    ]
    return names, rows


def _number(value: str) -> float | None:
    if value in {"", "."}:
        return None
    try:
        return float(value)
    except ValueError:
        return math.nan


def parity(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    exp_cols, expected = _read_csv(ctx.path(args["expected"]))
    act_cols, actual = _read_csv(ctx.path(args["actual"]))
    abs_tol = float(args.get("abs_tol", 1e-9))
    rel_tol = float(args.get("rel_tol", 1e-9))
    if abs_tol < 0 or rel_tol < 0:
        raise ToolError("tolerances can't be negative")
    keys = [k.lower() for k in args.get("keys") or []]
    missing_cols = sorted(set(exp_cols) - set(act_cols))
    extra_cols = sorted(set(act_cols) - set(exp_cols))
    cols = [c for c in exp_cols if c in act_cols and c not in set(args.get("ignore") or [])]
    if any(k not in cols for k in keys):
        raise ToolError(f"key column(s) {', '.join(k for k in keys if k not in cols)} aren't in both files")
    mismatches: list[dict[str, Any]] = []
    unmatched: list[str] = []
    if keys:
        index = {tuple(r[k] for k in keys): r for r in actual}
        pairs = []
        for row in expected:
            key = tuple(row[k] for k in keys)
            if key in index:
                pairs.append((row, index.pop(key)))
            else:
                unmatched.append(f"expected row {dict(zip(keys, key, strict=False))} isn't in actual")
        unmatched += [f"actual row {dict(zip(keys, k, strict=False))} isn't in expected" for k in index]
    else:
        pairs = list(zip(expected, actual, strict=False))
    worst: dict[str, float] = {}
    for i, (exp, act) in enumerate(pairs):
        for col in cols:
            a, b = exp.get(col, ""), act.get(col, "")
            na, nb = _number(a), _number(b)
            if na is not None and nb is not None and not math.isnan(na) and not math.isnan(nb):
                diff = abs(na - nb)
                worst[col] = max(worst.get(col, 0.0), diff)
                if diff > max(abs_tol, rel_tol * max(abs(na), abs(nb))):
                    mismatches.append({"row": i + 1, "column": col, "expected": a, "actual": b, "diff": diff})
            elif (na is None) != (nb is None):
                mismatches.append(
                    {"row": i + 1, "column": col, "expected": a or ".", "actual": b or ".", "diff": None}
                )
            elif a.rstrip() != b.rstrip() and not (na is None and nb is None):
                mismatches.append({"row": i + 1, "column": col, "expected": a, "actual": b, "diff": None})
    problems = []
    if len(expected) != len(actual):
        problems.append(f"row counts differ: expected {len(expected)}, actual {len(actual)}")
    if missing_cols:
        problems.append(f"columns missing from actual: {', '.join(missing_cols)}")
    problems += unmatched[:20]
    plan_notes: list[dict[str, Any]] = []
    if args.get("plan"):
        plan = json.loads(ctx.path(args["plan"]).read_text(encoding="utf-8"))
        plan_notes = [n for n in plan.get("steps", []) if n.get("verdict") in {"partial", "unsupported"}]
    status = "match" if not problems and not mismatches else "mismatch"
    if status == "match" and any(n["verdict"] == "unsupported" for n in plan_notes):
        status = "incomplete"
    findings = [finding("error", p, rule="sas.parity", uri=args["actual"]) for p in problems]
    findings += [
        finding(
            "error",
            f"row {m['row']} {m['column']}: expected {m['expected']}, got {m['actual']}",
            rule="sas.parity",
            uri=args["actual"],
        )
        for m in mismatches[:50]
    ]
    report = write_json(
        ctx.evidence / f"parity-{Path(args['actual']).stem}.json",
        {
            "schema": "dex-trove/sas-parity@1",
            "expected": args["expected"],
            "actual": args["actual"],
            "keys": keys,
            "tolerance": {"abs": abs_tol, "rel": rel_tol},
            "rows": {"expected": len(expected), "actual": len(actual)},
            "columns_compared": cols,
            "extra_columns": extra_cols,
            "max_abs_diff": worst,
            "status": status,
            "mismatches": mismatches[:200],
            "problems": problems,
            "untranslated_or_partial_steps": plan_notes,
        },
    )
    artifacts = [artifact(ctx, report, "application/json", schema="dex-trove/sas-parity@1")]
    if findings:
        artifacts.append(
            artifact(
                ctx,
                write_sarif(ctx, f"parity-{Path(args['actual']).stem}", findings, tool="dex-sas"),
                "application/sarif+json",
            )
        )
    return result(
        ctx,
        status,
        rows={"expected": len(expected), "actual": len(actual)},
        compared=cols,
        extra_columns=extra_cols,
        max_abs_diff=worst,
        mismatches=mismatches[:20],
        problems=problems,
        steps_to_review=plan_notes,
        findings=findings,
        artifacts=artifacts,
        inputs=args,
    )


_PATHS = {
    "type": "array",
    "items": {"type": "string"},
    "description": ".sas files or folders (default: the whole project)",
}

TOOLS = [
    Tool(
        "sas_inventory",
        "SAS steps, datasets read and written, macros, %let values, libnames and %includes, with lines.",
        {"paths": _PATHS},
        inventory,
        writes=True,
    ),
    Tool(
        "sas_lineage",
        "Dataset-to-step lineage and a supported/partial/unsupported verdict for every step, with reasons.",
        {"paths": _PATHS},
        lineage,
        writes=True,
    ),
    Tool(
        "sas_draft",
        "Writes a pandas draft that keeps SAS missing-value rules; untranslated steps stop the run.",
        {
            "paths": _PATHS,
            "output": {"type": "string", "description": "Default sas_draft.py"},
            "overwrite": {"type": "boolean"},
        },
        draft_tool,
        writes=True,
    ),
    Tool(
        "sas_parity",
        "Compares a SAS output CSV with the draft's output within a tolerance, by key or by position.",
        {
            "expected": {"type": "string"},
            "actual": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}},
            "abs_tol": {"type": "number"},
            "rel_tol": {"type": "number"},
            "ignore": {"type": "array", "items": {"type": "string"}},
            "plan": {
                "type": "string",
                "description": "draft-plan.json, to mark outputs of untranslated steps",
            },
        },
        parity,
        required=("expected", "actual"),
        writes=True,
    ),
]
