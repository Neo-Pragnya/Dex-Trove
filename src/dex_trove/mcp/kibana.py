"""Kibana dashboards from the fields an application really logs, exported as saved objects, imported only on approval.

1. ``kibana_fields`` finds field definitions in the source: Elasticsearch/OpenSearch mappings and index templates
   (declared types), JSON Schemas (declared), Python ``logger.info(..., extra={...})`` and structlog keyword
   arguments, and JavaScript ``logger.info({...})`` objects (types inferred from literal values, or unknown).
2. ``kibana_spec`` checks a dashboard spec against those fields: every field exists, numeric aggregations use
   numeric fields, splits use keyword-like fields, and the time field is a date.
3. ``kibana_export`` writes saved-object NDJSON (a data view, one aggregation-based visualization per panel and a
   dashboard) in the 7.10 format that Kibana 7.10+, 8.x and OpenSearch Dashboards migrate forward on import, and
   checks the contract of what it wrote: valid lines, unique ids, every reference resolved.
4. ``kibana_import_preview`` and ``kibana_import`` send it to a target listed in ``.dex/kibana.json``. Production
   targets are refused outright; others need ``--allow-actions`` and the preview's approval digest. Objects are
   never overwritten.
"""

from __future__ import annotations

import ast
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from dex_trove.mcp.common import (
    Context,
    ToolError,
    approval_for,
    artifact,
    basic_auth,
    finding,
    http,
    now_iso,
    require_approval,
    result,
    sha256_file,
    stable_digest,
    write_json,
    write_sarif,
    write_text,
)
from dex_trove.mcp.server import Tool

NAME = "kibana"
TITLE = "Kibana: dashboards from logged fields, gated import"
CAPABILITIES = (
    "CAP-kibana-dashboard-01",
    "CAP-kibana-dashboard-02",
    "CAP-kibana-dashboard-03",
    "CAP-kibana-dashboard-04",
)
INSTRUCTIONS = (
    "Builds Kibana dashboards from fields the code really logs. Order: kibana_fields (what's logged, with types and "
    "where), write a dashboard spec JSON in the project, kibana_spec (missing fields and type mismatches), "
    "kibana_export (saved-object NDJSON for the target version), then optionally kibana_import_preview and "
    "kibana_import with the approval digest after the user agrees. Production targets are never written."
)
AUTH_HINT = "Set KIBANA_API_KEY, or KIBANA_USER and KIBANA_PASSWORD, in the server's environment."
SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tox", ".dex", "dex-evidence"}
)
MAX_FILES = 20_000
MAX_BYTES = 2_000_000
LOG_NAMES = frozenset({"log", "logger", "LOG", "LOGGER", "_log", "_logger", "structlog", "logging"})
LEVELS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "msg", "log"}
)
RESERVED_KW = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})
NUMERIC = frozenset(
    {"long", "integer", "short", "byte", "double", "float", "half_float", "scaled_float", "unsigned_long"}
)
SPLITTABLE = NUMERIC | {"keyword", "ip", "boolean", "date", "constant_keyword", "wildcard"}
ECS_BASE = {"@timestamp": "date", "message": "text", "log.level": "keyword", "service.name": "keyword"}
PANEL_TYPES = {
    "metric": "metric",
    "line": "line",
    "bar": "histogram",
    "area": "area",
    "table": "table",
    "pie": "pie",
}
AGGS = frozenset({"count", "sum", "avg", "min", "max", "cardinality", "median"})
MIGRATION = {"index-pattern": "7.6.0", "visualization": "7.10.0", "dashboard": "7.9.3"}
SPEC_SCHEMA = "dex-trove/kibana-dashboard-spec@1"


def _schema_type(spec: dict[str, Any]) -> str:
    kind = spec.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "")
    if kind == "string":
        return (
            "date"
            if spec.get("format") in {"date-time", "date"}
            else "ip"
            if spec.get("format") in {"ipv4", "ipv6"}
            else "keyword"
        )
    return {"integer": "long", "number": "double", "boolean": "boolean", "object": "object"}.get(
        str(kind), "unknown"
    )


def _walk_mapping(props: dict[str, Any], prefix: str, out: list[tuple[str, str]]) -> None:
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        name = f"{prefix}{key}"
        if isinstance(spec.get("properties"), dict):
            _walk_mapping(spec["properties"], name + ".", out)
        else:
            out.append((name, str(spec.get("type", "object"))))


def _walk_schema(props: dict[str, Any], prefix: str, out: list[tuple[str, str]]) -> None:
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        name = f"{prefix}{key}"
        if isinstance(spec.get("properties"), dict):
            _walk_schema(spec["properties"], name + ".", out)
        else:
            out.append((name, _schema_type(spec)))


def _find_mappings(data: Any) -> list[dict[str, Any]]:
    """Every ``mappings.properties`` object inside a JSON document (index templates nest it)."""
    found: list[dict[str, Any]] = []
    if isinstance(data, dict):
        mappings = data.get("mappings")
        if isinstance(mappings, dict) and isinstance(mappings.get("properties"), dict):
            found.append(mappings["properties"])
        for value in data.values():
            found += _find_mappings(value)
    elif isinstance(data, list):
        for value in data:
            found += _find_mappings(value)
    return found


def _literal_type(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "long"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "keyword"
    if isinstance(node, ast.JoinedStr):
        return "keyword"
    return "unknown"


def _python_fields(text: str) -> list[tuple[str, str, int]]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LEVELS
        ):
            continue
        owner = node.func.value
        base = owner.func if isinstance(owner, ast.Call) else owner
        name = base.attr if isinstance(base, ast.Attribute) else base.id if isinstance(base, ast.Name) else ""
        if name not in LOG_NAMES and not name.endswith(("log", "logger")):
            continue
        for kw in node.keywords:
            if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                for key, value in zip(kw.value.keys, kw.value.values, strict=False):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        found.append((key.value, _literal_type(value), node.lineno))
            elif kw.arg and kw.arg not in RESERVED_KW:
                found.append((kw.arg, _literal_type(kw.value), node.lineno))
    return found


_JS_LOG = re.compile(
    r"\b(?:log|logger|this\.logger|this\.log)\s*\.\s*(?:trace|debug|info|warn|error|fatal)\s*\(\s*\{([^{}]{0,2000})\}"
)
_JS_KEY = re.compile(r"(?:^|,)\s*(?:['\"]([\w.@-]+)['\"]|([A-Za-z_$][\w$]*))\s*:\s*([^,]+)")


def _js_type(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"-?\d+", value):
        return "long"
    if re.fullmatch(r"-?\d*\.\d+", value):
        return "double"
    if value in {"true", "false"}:
        return "boolean"
    if value[:1] in {"'", '"', "`"}:
        return "keyword"
    return "unknown"


def _js_fields(text: str) -> list[tuple[str, str, int]]:
    found = []
    for match in _JS_LOG.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        for key in _JS_KEY.finditer(match.group(1)):
            found.append((key.group(1) or key.group(2), _js_type(key.group(3)), line))
    return found


def _files(ctx: Context, paths: list[str]) -> list[Path]:
    roots = [ctx.path(p) for p in paths] if paths else [ctx.root]
    out: list[Path] = []
    for start in roots:
        if start.is_file():
            out.append(start)
            continue
        for folder, dirs, names in os.walk(start):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(names):
                if name.endswith((".py", ".json", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")):
                    out.append(Path(folder) / name)
                    if len(out) >= MAX_FILES:
                        return out
    return out


def discover(
    ctx: Context, paths: list[str], *, ecs: bool = True
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    fields: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    def add(name: str, kind: str, origin: str, uri: str, line: int | None = None) -> None:
        entry = fields.setdefault(name, {"name": name, "types": {}, "sources": []})
        entry["types"].setdefault(kind, origin)
        if len(entry["sources"]) < 10:
            entry["sources"].append({"uri": uri, **({"line": line} if line else {}), "origin": origin})

    for path in _files(ctx, paths):
        if path.stat().st_size > MAX_BYTES:
            warnings.append(f"skipped {path.relative_to(ctx.root)}: larger than {MAX_BYTES} bytes")
            continue
        rel = path.relative_to(ctx.root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".json":
            try:
                data = json.loads(text)
            except ValueError:
                continue
            for props in _find_mappings(data):
                pairs: list[tuple[str, str]] = []
                _walk_mapping(props, "", pairs)
                for name, kind in pairs:
                    add(name, kind, "declared", rel)
            if (
                isinstance(data, dict)
                and isinstance(data.get("properties"), dict)
                and ("$schema" in data or path.name.endswith(".schema.json"))
            ):
                pairs = []
                _walk_schema(data["properties"], "", pairs)
                for name, kind in pairs:
                    add(name, kind, "declared", rel)
        elif path.suffix == ".py":
            for name, kind, line in _python_fields(text):
                add(name, kind, "inferred", rel, line)
        else:
            for name, kind, line in _js_fields(text):
                add(name, kind, "inferred", rel, line)
    if ecs:
        for name, kind in ECS_BASE.items():
            if name not in fields:
                fields[name] = {
                    "name": name,
                    "types": {kind: "ecs"},
                    "sources": [{"uri": "ECS", "origin": "ecs"}],
                }
    for entry in fields.values():
        declared = [k for k, o in entry["types"].items() if o == "declared"]
        known = [k for k in entry["types"] if k != "unknown"]
        entry["type"] = (
            declared[0]
            if len(set(declared)) == 1
            else (known[0] if len(set(known)) == 1 else "unknown" if not known else "conflict")
        )
        entry["type_source"] = entry["types"].get(entry["type"], "declared" if declared else "inferred")
    return dict(sorted(fields.items())), warnings


def fields_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    paths = args.get("paths") or []
    fields, warnings = discover(ctx, paths, ecs=args.get("ecs", True))
    findings = [
        finding(
            "warning",
            f"field {name} is logged with different types: {', '.join(sorted(f['types']))}",
            rule="kibana.type-conflict",
            uri=f["sources"][0]["uri"],
            line=f["sources"][0].get("line"),
            remediation="log one type, or map the field explicitly in the index template",
        )
        for name, f in fields.items()
        if f["type"] == "conflict"
    ]
    path = write_json(ctx.evidence / "fields.json", {"schema": "dex-trove/kibana-fields@1", "fields": fields})
    counts = {
        k: sum(1 for f in fields.values() if f["type_source"] == k) for k in ("declared", "inferred", "ecs")
    }
    return result(
        ctx,
        "ok",
        fields=fields,
        counts=counts,
        findings=findings,
        warnings=warnings,
        artifacts=[artifact(ctx, path, "application/json", schema="dex-trove/kibana-fields@1")],
        inputs=args,
    )


def _load_spec(ctx: Context, spec_path: str) -> dict[str, Any]:
    path = ctx.path(spec_path)
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ToolError(f"{spec_path}: not valid JSON ({exc})") from exc
    if not isinstance(spec, dict) or not isinstance(spec.get("panels"), list) or not spec["panels"]:
        raise ToolError(
            f"{spec_path}: expected {{'title', 'data_view': {{'title', 'time_field'}}, 'panels': [...]}}"
        )
    view = spec.get("data_view")
    if not isinstance(view, dict) or not view.get("title"):
        raise ToolError(f"{spec_path}: data_view.title (the index pattern, e.g. 'logs-app-*') is required")
    return spec


def check_spec(
    spec: dict[str, Any], fields: dict[str, dict[str, Any]], spec_uri: str
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def need(field: str, allowed: frozenset[str] | set[str], role: str, where: str) -> None:
        entry = fields.get(field)
        if entry is None:
            findings.append(
                finding(
                    "error",
                    f"{where}: field {field!r} isn't logged or mapped anywhere in the source",
                    rule="kibana.missing-field",
                    uri=spec_uri,
                    remediation="log it, map it in the index template, or pick another field",
                )
            )
        elif entry["type"] in {"unknown", "conflict"}:
            findings.append(
                finding(
                    "warning",
                    f"{where}: the type of {field!r} couldn't be verified ({entry['type']})",
                    rule="kibana.unverified-type",
                    uri=spec_uri,
                    status="inferred",
                    remediation="declare it in a mapping or JSON Schema",
                )
            )
        elif entry["type"] not in allowed:
            findings.append(
                finding(
                    "error",
                    f"{where}: {role} needs {'/'.join(sorted(allowed))[:60]}, but {field!r} is {entry['type']}",
                    rule="kibana.type-mismatch",
                    uri=spec_uri,
                )
            )

    view = spec["data_view"]
    time_field = view.get("time_field", "@timestamp")
    need(time_field, frozenset({"date", "date_nanos"}), "the time field", "data_view")
    for i, panel in enumerate(spec["panels"]):
        where = f"panel {i + 1} ({panel.get('title', '?') if isinstance(panel, dict) else '?'})"
        if not isinstance(panel, dict):
            findings.append(finding("error", f"{where}: not an object", rule="kibana.bad-spec", uri=spec_uri))
            continue
        if panel.get("type") not in PANEL_TYPES:
            findings.append(
                finding(
                    "error",
                    f"{where}: type must be one of {', '.join(PANEL_TYPES)}",
                    rule="kibana.bad-spec",
                    uri=spec_uri,
                )
            )
        metric = panel.get("metric") or {"agg": "count"}
        agg = metric.get("agg")
        if agg not in AGGS:
            findings.append(
                finding(
                    "error",
                    f"{where}: metric.agg must be one of {', '.join(sorted(AGGS))}",
                    rule="kibana.bad-spec",
                    uri=spec_uri,
                )
            )
        elif agg != "count":
            if not metric.get("field"):
                findings.append(
                    finding(
                        "error", f"{where}: {agg} needs metric.field", rule="kibana.bad-spec", uri=spec_uri
                    )
                )
            else:
                allowed = SPLITTABLE if agg == "cardinality" else NUMERIC
                need(str(metric["field"]), allowed, f"{agg}", where)
        split = panel.get("split")
        if split:
            if not isinstance(split, dict) or not split.get("field"):
                findings.append(
                    finding("error", f"{where}: split needs a field", rule="kibana.bad-spec", uri=spec_uri)
                )
            else:
                need(str(split["field"]), SPLITTABLE, "a split (terms)", where)
        elif panel.get("type") in {"pie", "table"}:
            findings.append(
                finding(
                    "error",
                    f"{where}: a {panel['type']} panel needs split.field",
                    rule="kibana.bad-spec",
                    uri=spec_uri,
                )
            )
        if len(str(panel.get("filter", ""))) > 2000:
            findings.append(
                finding(
                    "error",
                    f"{where}: filter longer than 2000 characters",
                    rule="kibana.bad-spec",
                    uri=spec_uri,
                )
            )
    return findings


def _fields_for(ctx: Context, args: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return discover(ctx, args.get("paths") or [], ecs=args.get("ecs", True))[0]


def spec_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    spec = _load_spec(ctx, args["spec"])
    findings = check_spec(spec, _fields_for(ctx, args), args["spec"])
    errors = [f for f in findings if f["severity"] == "error"]
    artifacts = []
    if findings:
        artifacts.append(
            artifact(
                ctx, write_sarif(ctx, "dashboard-spec", findings, tool="dex-kibana"), "application/sarif+json"
            )
        )
    return result(
        ctx,
        "invalid" if errors else "valid",
        panels=len(spec["panels"]),
        findings=findings,
        artifacts=artifacts,
        inputs={"spec": spec, "args": args},
    )


def _id(seed: str) -> str:
    return str(uuid.UUID(stable_digest(seed)[:32]))


def _target_version(value: object) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", str(value or ""))
    if not match:
        raise ToolError("target_version must look like 8.14 or 7.17")
    major, minor = int(match.group(1)), int(match.group(2))
    if (major, minor) < (7, 10) or major > 9:
        raise ToolError(
            f"Kibana {major}.{minor} isn't supported: the export targets 7.10 to 9.x and OpenSearch Dashboards 1-2"
        )
    return major, minor


def _vis(panel: dict[str, Any], time_field: str) -> dict[str, Any]:
    kind = PANEL_TYPES[panel["type"]]
    metric = panel.get("metric") or {"agg": "count"}
    agg = "median" if metric["agg"] == "median" else metric["agg"]
    metric_params: dict[str, Any] = {} if agg == "count" else {"field": metric["field"]}
    if agg == "median":
        metric_params["percents"] = [50]
    aggs: list[dict[str, Any]] = [
        {"id": "1", "enabled": True, "type": agg, "schema": "metric", "params": metric_params}
    ]
    if kind in {"line", "histogram", "area"}:
        aggs.append(
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "schema": "segment",
                "params": {
                    "field": time_field,
                    "interval": panel.get("interval", "auto"),
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
            }
        )
    split = panel.get("split")
    if split:
        schema = {"pie": "segment", "table": "bucket", "metric": "group"}.get(kind, "group")
        aggs.append(
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": schema,
                "params": {
                    "field": split["field"],
                    "size": int(split.get("size", 10)),
                    "order": "desc",
                    "orderBy": "1",
                },
            }
        )
    params: dict[str, Any] = {"type": kind, "addTooltip": True, "addLegend": kind != "metric"}
    if kind == "metric":
        params["metric"] = {"percentageMode": False, "colorSchema": "Green to Red", "style": {"fontSize": 60}}
    if kind == "table":
        params.update({"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False})
    if kind == "pie":
        params.update({"isDonut": True, "legendPosition": "right"})
    return {"title": panel.get("title", ""), "type": kind, "params": params, "aggs": aggs}


def build_objects(spec: dict[str, Any]) -> list[dict[str, Any]]:
    view = spec["data_view"]
    time_field = view.get("time_field", "@timestamp")
    seed = stable_digest(spec)
    view_id = _id(seed + ":data-view")
    objects: list[dict[str, Any]] = [
        {
            "id": view_id,
            "type": "index-pattern",
            "migrationVersion": {"index-pattern": MIGRATION["index-pattern"]},
            "attributes": {"title": view["title"], "timeFieldName": time_field},
            "references": [],
        }
    ]
    panels_json, refs = [], []
    for i, panel in enumerate(spec["panels"]):
        vis_id = _id(f"{seed}:panel:{i}")
        search = {
            "query": {"query": str(panel.get("filter", "")), "language": "kuery"},
            "filter": [],
            "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
        }
        objects.append(
            {
                "id": vis_id,
                "type": "visualization",
                "migrationVersion": {"visualization": MIGRATION["visualization"]},
                "attributes": {
                    "title": panel.get("title", f"Panel {i + 1}"),
                    "description": str(panel.get("description", "")),
                    "visState": json.dumps(_vis(panel, time_field), sort_keys=True),
                    "uiStateJSON": "{}",
                    "version": 1,
                    "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(search, sort_keys=True)},
                },
                "references": [
                    {
                        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                        "type": "index-pattern",
                        "id": view_id,
                    }
                ],
            }
        )
        width = 48 if panel.get("type") == "table" else 24
        panels_json.append(
            {
                "version": "7.10.0",
                "panelIndex": str(i + 1),
                "embeddableConfig": {},
                "gridData": {
                    "x": 0 if width == 48 or i % 2 == 0 else 24,
                    "y": (i // 2) * 15,
                    "w": width,
                    "h": 15,
                    "i": str(i + 1),
                },
                "panelRefName": f"panel_{i}",
            }
        )
        refs.append({"name": f"panel_{i}", "type": "visualization", "id": vis_id})
    objects.append(
        {
            "id": _id(seed + ":dashboard"),
            "type": "dashboard",
            "migrationVersion": {"dashboard": MIGRATION["dashboard"]},
            "attributes": {
                "title": spec.get("title", "Dashboard"),
                "description": str(spec.get("description", "")),
                "panelsJSON": json.dumps(panels_json, sort_keys=True),
                "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
                "timeRestore": False,
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(
                        {"query": {"query": "", "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": refs,
        }
    )
    return objects


def validate_ndjson(text: str) -> list[str]:
    """The saved-object contract the import API relies on. Returns problems; empty means it holds."""
    problems: list[str] = []
    objects = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            problems.append(f"line {n}: not JSON")
            continue
        if (
            not isinstance(obj, dict)
            or not obj.get("id")
            or not obj.get("type")
            or not isinstance(obj.get("attributes"), dict)
        ):
            problems.append(f"line {n}: needs id, type and attributes")
            continue
        objects.append(obj)
    seen = {(o["type"], o["id"]) for o in objects}
    if len(seen) != len(objects):
        problems.append("duplicate type/id pairs")
    for obj in objects:
        attrs = obj["attributes"]
        if not attrs.get("title"):
            problems.append(f"{obj['type']} {obj['id']}: no title")
        for key in ("visState", "panelsJSON", "optionsJSON", "uiStateJSON"):
            if key in attrs:
                try:
                    json.loads(attrs[key])
                except (TypeError, ValueError):
                    problems.append(f"{obj['type']} {obj['id']}: {key} isn't a JSON string")
        meta = (attrs.get("kibanaSavedObjectMeta") or {}).get("searchSourceJSON")
        if meta is not None:
            try:
                json.loads(meta)
            except (TypeError, ValueError):
                problems.append(f"{obj['type']} {obj['id']}: searchSourceJSON isn't a JSON string")
        names = {r.get("name") for r in obj.get("references", [])}
        for ref in obj.get("references", []):
            if (ref.get("type"), ref.get("id")) not in seen:
                problems.append(
                    f"{obj['type']} {obj['id']}: reference {ref.get('name')} points to a missing {ref.get('type')}"
                )
        if obj["type"] == "dashboard":
            for panel in json.loads(attrs.get("panelsJSON") or "[]"):
                if panel.get("panelRefName") not in names:
                    problems.append(
                        f"dashboard {obj['id']}: panel {panel.get('panelIndex')} has no reference"
                    )
    return problems


def export_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    spec = _load_spec(ctx, args["spec"])
    version = _target_version(args["target_version"])
    findings = check_spec(spec, _fields_for(ctx, args), args["spec"])
    errors = [f for f in findings if f["severity"] == "error"]
    if errors and not args.get("allow_missing_fields"):
        raise ToolError(
            "the spec has errors, so nothing was exported: "
            + "; ".join(f["message"] for f in errors[:5])
            + ". Fix them (kibana_spec lists all), or pass allow_missing_fields to export anyway."
        )
    objects = build_objects(spec)
    text = "".join(json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n" for o in objects)
    problems = validate_ndjson(text)
    if problems:
        raise ToolError("the generated saved objects failed their contract check: " + "; ".join(problems))
    slug = re.sub(r"[^a-z0-9]+", "-", str(spec.get("title", "dashboard")).lower()).strip("-") or "dashboard"
    path = write_text(ctx.evidence / f"{slug}.ndjson", text)
    manifest = write_json(
        ctx.evidence / f"{slug}.export.json",
        {
            "schema": "dex-trove/kibana-export@1",
            "spec": args["spec"],
            "spec_digest": stable_digest(spec),
            "target_version": f"{version[0]}.{version[1]}",
            "format": "saved objects, 7.10 format (migrated forward on import)",
            "objects": [
                {"type": o["type"], "id": o["id"], "title": o["attributes"]["title"]} for o in objects
            ],
            "ndjson_sha256": sha256_file(path),
            "contract": "passed",
            "verified_import": "not yet: run kibana_import against a test instance to record it",
        },
    )
    return result(
        ctx,
        "exported",
        objects=len(objects),
        target_version=f"{version[0]}.{version[1]}",
        findings=findings,
        artifacts=[
            artifact(ctx, path, "application/x-ndjson", schema="kibana-saved-objects@7.10"),
            artifact(ctx, manifest, "application/json", schema="dex-trove/kibana-export@1"),
        ],
        inputs={"spec": spec, "target": args["target_version"]},
    )


def _target(ctx: Context, name: str) -> dict[str, Any]:
    targets = ctx.config(NAME).get("targets") or {}
    if name not in targets:
        raise ToolError(
            f"no target {name!r} in .dex/kibana.json (targets: {', '.join(sorted(targets)) or 'none'}). Add "
            '{"targets": {"test": {"url": "http://localhost:5601", "environment": "test"}}}.'
        )
    target = dict(targets[name])
    env = str(target.get("environment", "")).lower()
    if env not in {"test", "dev", "staging", "production"}:
        raise ToolError(f"target {name}: environment must be test, dev, staging or production")
    if env == "production":
        raise ToolError(
            f"target {name} is production. Dashboards are never written to production from here: import the "
            "exported NDJSON through your change process (Stack Management > Saved Objects > Import)."
        )
    target.setdefault("space", "default")
    target.setdefault("flavor", "kibana")
    if target["flavor"] not in {"kibana", "opensearch-dashboards"}:
        raise ToolError(f"target {name}: flavor must be kibana or opensearch-dashboards")
    if not re.fullmatch(r"[a-z0-9_-]{1,100}", str(target["space"])):
        raise ToolError(f"target {name}: space must be a Kibana space id")
    return target


def _auth(ctx: Context, flavor: str) -> dict[str, str]:
    headers = {"osd-xsrf": "true"} if flavor == "opensearch-dashboards" else {"kbn-xsrf": "true"}
    if ctx.env.get("KIBANA_API_KEY"):
        headers["Authorization"] = "ApiKey " + ctx.env["KIBANA_API_KEY"]
    elif ctx.env.get("KIBANA_USER") and ctx.env.get("KIBANA_PASSWORD"):
        headers["Authorization"] = basic_auth(ctx.env["KIBANA_USER"], ctx.env["KIBANA_PASSWORD"])
    return headers


def _import_plan(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    target = _target(ctx, args["target"])
    path = ctx.path(args["ndjson"])
    text = path.read_text(encoding="utf-8")
    problems = validate_ndjson(text)
    if problems:
        raise ToolError(f"{args['ndjson']} failed the saved-object contract: " + "; ".join(problems[:5]))
    objects = [json.loads(line) for line in text.splitlines() if line.strip()]
    base = str(target["url"]).rstrip("/")
    prefix = "" if target["space"] == "default" else f"/s/{target['space']}"
    return {
        "action": "kibana.import",
        "target": args["target"],
        "url": base,
        "endpoint": f"{base}{prefix}/api/saved_objects/_import",
        "flavor": target["flavor"],
        "space": target["space"],
        "ndjson": args["ndjson"],
        "sha256": sha256_file(path),
        "overwrite": False,
        "objects": [
            {"type": o["type"], "id": o["id"], "title": o["attributes"].get("title", "")} for o in objects
        ],
    }


def _server_version(ctx: Context, plan: dict[str, Any]) -> str:
    resp = http(
        ctx,
        "GET",
        plan["url"] + "/api/status",
        headers=_auth(ctx, plan["flavor"]),
        service="Kibana",
        auth_hint=AUTH_HINT,
    )
    if resp.status >= 400:
        raise ToolError(f"Kibana answered {resp.status} for /api/status")
    data = resp.json()
    return str((data.get("version") or {}).get("number", "")) if isinstance(data, dict) else ""


def import_preview(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _import_plan(ctx, args)
    version = _server_version(ctx, plan)
    warnings = []
    if not version:
        warnings.append("the target didn't report its version")
    return result(
        ctx,
        "needs-approval",
        plan=plan,
        server_version=version,
        approval=approval_for(plan),
        actions_enabled=ctx.allow_actions,
        warnings=warnings,
        summary=f"Import {len(plan['objects'])} saved objects into {plan['target']} ({plan['url']}, space "
        f"{plan['space']}) without overwriting anything.",
        inputs=args,
    )


def _multipart(name: str, filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = "dex" + stable_digest(data.hex())[:24]
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            "Content-Type: application/ndjson\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def import_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _import_plan(ctx, args)
    require_approval(ctx, plan, args.get("approval"), action="kibana.import")
    version = _server_version(ctx, plan)
    data = ctx.path(args["ndjson"]).read_bytes()
    body, ctype = _multipart("file", Path(args["ndjson"]).name, data)
    resp = http(
        ctx,
        "POST",
        plan["endpoint"] + "?overwrite=false",
        headers={**_auth(ctx, plan["flavor"]), "Content-Type": ctype},
        body=body,
        retries=0,
        service="Kibana",
        auth_hint=AUTH_HINT,
    )
    if resp.status >= 400:
        ctx.audit("failed", action="kibana.import", status=resp.status)
        raise ToolError(
            f"the import was refused ({resp.status}): {resp.body[:300].decode('utf-8', 'replace')}"
        )
    answer = resp.json()
    errors = answer.get("errors") or []
    findings = [
        finding(
            "error",
            f"{e.get('type')} {e.get('id')}: {(e.get('error') or {}).get('type', 'error')}",
            rule="kibana.import-error",
            remediation="conflicts mean the object exists: rename or delete it first",
        )
        for e in errors
    ]
    record = write_json(
        ctx.evidence / f"import-{plan['sha256'][:12]}.json",
        {
            "schema": "dex-trove/kibana-import@1",
            "target": plan["target"],
            "url": plan["url"],
            "space": plan["space"],
            "server_version": version,
            "ndjson_sha256": plan["sha256"],
            "success": bool(answer.get("success")),
            "success_count": answer.get("successCount", 0),
            "errors": errors,
            "recorded_at": now_iso(),
        },
    )
    ctx.audit("imported", action="kibana.import", target=plan["target"], success=bool(answer.get("success")))
    return result(
        ctx,
        "imported" if answer.get("success") else "partial",
        server_version=version,
        success_count=answer.get("successCount", 0),
        findings=findings,
        artifacts=[artifact(ctx, record, "application/json", schema="dex-trove/kibana-import@1")],
        inputs=args,
    )


_PATHS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Folders or files to scan (default: the whole project)",
}
_ECS = {
    "type": "boolean",
    "description": "Assume the ECS base fields (@timestamp, message, log.level, service.name). Default true",
}
_SPEC = {"type": "string", "description": "Dashboard spec JSON in the project"}

TOOLS = [
    Tool(
        "kibana_fields",
        "Fields the application logs or maps, with types (declared, inferred or unknown) and where each comes from.",
        {"paths": _PATHS, "ecs": _ECS},
        fields_tool,
        writes=True,
    ),
    Tool(
        "kibana_spec",
        "Checks a dashboard spec against the logged fields: missing fields, type mismatches, unverified types.",
        {"spec": _SPEC, "paths": _PATHS, "ecs": _ECS},
        spec_tool,
        required=("spec",),
        writes=True,
    ),
    Tool(
        "kibana_export",
        "Writes saved-object NDJSON for the target Kibana version and checks its contract. Imports nothing.",
        {
            "spec": _SPEC,
            "target_version": {"type": "string", "description": "e.g. 8.14"},
            "paths": _PATHS,
            "ecs": _ECS,
            "allow_missing_fields": {"type": "boolean"},
        },
        export_tool,
        required=("spec", "target_version"),
        writes=True,
    ),
    Tool(
        "kibana_import_preview",
        "What an import would send where, the target's version, and an approval digest. Sends nothing.",
        {"ndjson": {"type": "string"}, "target": {"type": "string"}},
        import_preview,
        required=("ndjson", "target"),
    ),
    Tool(
        "kibana_import",
        "Imports the previewed NDJSON into a non-production target, never overwriting. Needs --allow-actions "
        "and the approval digest the user accepted.",
        {"ndjson": {"type": "string"}, "target": {"type": "string"}, "approval": {"type": "string"}},
        import_tool,
        required=("ndjson", "target", "approval"),
        action=True,
    ),
]
