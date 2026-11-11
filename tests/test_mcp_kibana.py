"""Kibana server: fields from source, spec checks, NDJSON contract, gated import against a fake Kibana."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp_fakes import Fake, serve

from dex_trove.mcp import kibana
from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

TEMPLATE = {
    "index_patterns": ["logs-app-*"],
    "template": {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "duration_ms": {"type": "long"},
                "http": {"properties": {"route": {"type": "keyword"}, "status": {"type": "integer"}}},
                "user": {"properties": {"id": {"type": "keyword"}}},
            }
        }
    },
}
PY = """
import logging, structlog
logger = logging.getLogger(__name__)
log = structlog.get_logger()

def checkout(cart, user):
    logger.info("checkout", extra={"cart_items": 3, "payment.provider": "card", "amount": 9.5})
    log.info("order_placed", order_id=cart.id, retries=0, express=True)
    logger.error("failed", exc_info=True, extra={"amount": "n/a"})
"""
JS = "logger.info({ queue: 'emails', depth: 12, ok: true, who: user.id }, 'queued')\n"
SPEC = {
    "title": "Checkout health",
    "data_view": {"title": "logs-app-*", "time_field": "@timestamp"},
    "panels": [
        {"title": "Errors over time", "type": "line", "filter": "log.level:error"},
        {"title": "Average latency", "type": "metric", "metric": {"agg": "avg", "field": "duration_ms"}},
        {"title": "Requests by route", "type": "bar", "split": {"field": "http.route", "size": 5}},
        {
            "title": "Users by route",
            "type": "table",
            "metric": {"agg": "cardinality", "field": "user.id"},
            "split": {"field": "http.route"},
        },
    ],
}


def project(tmp_path: Path, spec: dict | None = None) -> Path:  # type: ignore[type-arg]
    (tmp_path / "elastic").mkdir()
    (tmp_path / "elastic/template.json").write_text(json.dumps(TEMPLATE))
    (tmp_path / "app").mkdir()
    (tmp_path / "app/checkout.py").write_text(PY)
    (tmp_path / "app/queue.js").write_text(JS)
    (tmp_path / "dashboards").mkdir()
    (tmp_path / "dashboards/checkout.json").write_text(json.dumps(spec or SPEC))
    return tmp_path


def make(root: Path, *, allow: bool = False, env: dict[str, str] | None = None) -> Server:
    ctx = Context(root=root, server="kibana", allow_actions=allow, env=env or {})
    return Server("kibana", kibana.INSTRUCTIONS, list(kibana.TOOLS), ctx)


def test_fields_come_from_mappings_and_log_calls(tmp_path: Path) -> None:
    out = make(project(tmp_path)).call("kibana_fields", {})
    f = out["fields"]
    assert f["http.route"]["type"] == "keyword" and f["http.route"]["type_source"] == "declared"
    assert f["duration_ms"]["type"] == "long"
    assert f["cart_items"]["type"] == "long" and f["cart_items"]["type_source"] == "inferred"
    assert f["cart_items"]["sources"][0] == {"uri": "app/checkout.py", "line": 7, "origin": "inferred"}
    assert f["order_id"]["type"] == "unknown" and f["express"]["type"] == "boolean"
    assert "exc_info" not in f
    assert f["depth"]["type"] == "long" and f["queue"]["type"] == "keyword" and f["who"]["type"] == "unknown"
    assert f["amount"]["type"] == "conflict"
    assert out["findings"][0]["rule"] == "kibana.type-conflict"
    assert f["log.level"]["type_source"] == "ecs"
    assert (tmp_path / "dex-evidence/kibana/fields.json").is_file()


def test_spec_flags_missing_and_mismatched_fields(tmp_path: Path) -> None:
    good = make(project(tmp_path)).call("kibana_spec", {"spec": "dashboards/checkout.json"})
    assert good["status"] == "valid", good["findings"]
    bad_spec = {
        **SPEC,
        "panels": [
            {"title": "p95", "type": "metric", "metric": {"agg": "avg", "field": "latency"}},
            {"title": "by text", "type": "pie", "split": {"field": "message"}},
            {"title": "sum unknown", "type": "metric", "metric": {"agg": "sum", "field": "order_id"}},
            {"title": "pie no split", "type": "pie"},
        ],
    }
    (tmp_path / "dashboards/bad.json").write_text(json.dumps(bad_spec))
    out = make(tmp_path).call("kibana_spec", {"spec": "dashboards/bad.json"})
    rules = [f["rule"] for f in out["findings"]]
    assert out["status"] == "invalid"
    assert rules == [
        "kibana.missing-field",
        "kibana.type-mismatch",
        "kibana.unverified-type",
        "kibana.bad-spec",
    ]
    assert (tmp_path / "dex-evidence/kibana/dashboard-spec.sarif").is_file()


def test_export_is_a_valid_stable_ndjson(tmp_path: Path) -> None:
    server = make(project(tmp_path))
    a = server.call("kibana_export", {"spec": "dashboards/checkout.json", "target_version": "8.14"})
    b = server.call("kibana_export", {"spec": "dashboards/checkout.json", "target_version": "8.14"})
    assert a["status"] == "exported" and a["objects"] == 6
    assert a["artifacts"][0]["sha256"] == b["artifacts"][0]["sha256"] and a["digest"] == b["digest"]
    text = (tmp_path / a["artifacts"][0]["path"]).read_text()
    assert kibana.validate_ndjson(text) == []
    objects = [json.loads(line) for line in text.splitlines()]
    assert [o["type"] for o in objects] == ["index-pattern"] + ["visualization"] * 4 + ["dashboard"]
    vis = json.loads(objects[3]["attributes"]["visState"])
    assert vis["type"] == "histogram" and vis["aggs"][2]["params"]["field"] == "http.route"
    assert (
        json.loads(objects[1]["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"])["query"]["query"]
        == "log.level:error"
    )
    assert len(json.loads(objects[-1]["attributes"]["panelsJSON"])) == 4


def test_export_refuses_bad_specs_and_versions(tmp_path: Path) -> None:
    server = make(
        project(
            tmp_path,
            {**SPEC, "panels": [{"title": "x", "type": "metric", "metric": {"agg": "avg", "field": "nope"}}]},
        )
    )
    with pytest.raises(ToolError, match="nothing was exported"):
        server.call("kibana_export", {"spec": "dashboards/checkout.json", "target_version": "8.14"})
    for version in ("7.9", "eight"):
        with pytest.raises(ToolError, match="target_version|isn't supported"):
            server.call(
                "kibana_export",
                {"spec": "dashboards/checkout.json", "target_version": version, "allow_missing_fields": True},
            )
    with pytest.raises(ToolError, match="not found"):
        server.call("kibana_spec", {"spec": "missing.json"})


def test_contract_catches_broken_files() -> None:
    assert "line 1: not JSON" in kibana.validate_ndjson("{x\n")
    dangling = json.dumps(
        {
            "id": "a",
            "type": "visualization",
            "attributes": {"title": "t", "visState": "{}"},
            "references": [{"name": "r", "type": "index-pattern", "id": "gone"}],
        }
    )
    assert "missing index-pattern" in kibana.validate_ndjson(dangling)[0]


def _targets(root: Path, url: str) -> None:
    (root / ".dex").mkdir(exist_ok=True)
    (root / ".dex/kibana.json").write_text(
        json.dumps(
            {
                "targets": {
                    "test": {"url": url, "environment": "test"},
                    "prod": {"url": "https://kibana.example.com", "environment": "production"},
                }
            }
        )
    )


def test_import_is_gated_and_never_touches_production(tmp_path: Path) -> None:
    root = project(tmp_path)
    exported = make(root).call(
        "kibana_export", {"spec": "dashboards/checkout.json", "target_version": "8.14"}
    )
    ndjson = exported["artifacts"][0]["path"]
    with serve() as fake:
        _route(fake)
        _targets(root, fake.base)
        with pytest.raises(ToolError, match="never written to production"):
            make(root).call("kibana_import_preview", {"ndjson": ndjson, "target": "prod"})
        preview = make(root).call("kibana_import_preview", {"ndjson": ndjson, "target": "test"})
        assert preview["server_version"] == "8.14.1" and len(preview["plan"]["objects"]) == 6
        with pytest.raises(ToolError, match="actions are off"):
            make(root).call(
                "kibana_import", {"ndjson": ndjson, "target": "test", "approval": preview["approval"]}
            )
        assert not [s for s in fake.seen if s.method == "POST"]
        out = make(root, allow=True, env={"KIBANA_API_KEY": "k"}).call(
            "kibana_import", {"ndjson": ndjson, "target": "test", "approval": preview["approval"]}
        )
        assert out["status"] == "imported" and out["success_count"] == 6
        post = [s for s in fake.seen if s.method == "POST"][0]
        assert post.path == "/api/saved_objects/_import?overwrite=false"
        assert post.headers["kbn-xsrf"] == "true" and post.headers["authorization"] == "ApiKey k"
        assert b'"type":"dashboard"' in post.body and "multipart/form-data" in post.headers["content-type"]


def test_import_reports_conflicts(tmp_path: Path) -> None:
    root = project(tmp_path)
    ndjson = make(root).call("kibana_export", {"spec": "dashboards/checkout.json", "target_version": "8.14"})[
        "artifacts"
    ][0]["path"]
    with serve() as fake:
        _route(fake, conflict=True)
        _targets(root, fake.base)
        preview = make(root).call("kibana_import_preview", {"ndjson": ndjson, "target": "test"})
        out = make(root, allow=True).call(
            "kibana_import", {"ndjson": ndjson, "target": "test", "approval": preview["approval"]}
        )
        assert out["status"] == "partial" and out["findings"][0]["rule"] == "kibana.import-error"


def _route(fake: Fake, *, conflict: bool = False) -> None:
    fake.json("GET", "/api/status", {"version": {"number": "8.14.1"}})

    def imp(seen):  # type: ignore[no-untyped-def]
        if seen.headers.get("kbn-xsrf") != "true":
            return 400, {}, b"missing kbn-xsrf"
        count = seen.body.count(b'"type":')
        answer = (
            {
                "success": False,
                "successCount": 5,
                "errors": [{"type": "dashboard", "id": "d", "error": {"type": "conflict"}}],
            }
            if conflict
            else {"success": True, "successCount": count // 1 if count < 6 else 6, "errors": []}
        )
        return 200, {"Content-Type": "application/json"}, json.dumps(answer).encode()

    fake.routes[("POST", "/api/saved_objects/_import?overwrite=false")] = imp
