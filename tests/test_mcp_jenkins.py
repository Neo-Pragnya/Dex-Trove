"""Jenkins server against a fake Jenkins and a fake GitHub on 127.0.0.1."""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp_fakes import Fake, serve

from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

AUTH = "Basic dXNlcjp0b2tlbg=="  # user:token


@pytest.fixture
def fake() -> Iterator[Fake]:
    with serve() as f:
        f.json(
            "GET",
            "/job/app/job/ci/api/json?tree=name,buildable,url,property[parameterDefinitions[name,type]]",
            {
                "name": "ci",
                "buildable": True,
                "property": [{"parameterDefinitions": [{"name": "BRANCH"}, {"name": "SUITE"}]}],
            },
        )
        f.json("GET", "/crumbIssuer/api/json", {"crumb": "c1", "crumbRequestField": "Jenkins-Crumb"})
        f.routes[("POST", "/job/app/job/ci/buildWithParameters")] = lambda s: (
            (201, {"Location": f.base + "/queue/item/7/"}, b"")
            if s.headers.get("jenkins-crumb") == "c1"
            else (403, {}, b"no crumb")
        )
        f.sequence(
            "GET",
            "/queue/item/7/api/json",
            [{"why": "waiting"}, {"executable": {"url": f.base + "/job/app/job/ci/42/", "number": 42}}],
        )
        f.sequence(
            "GET",
            "/job/app/job/ci/42/api/json",
            [
                {"building": True, "number": 42},
                {"building": False, "result": "SUCCESS", "number": 42, "duration": 1234},
            ],
        )
        f.json(
            "GET",
            "/repos/acme/app/pulls/5",
            {
                "state": "open",
                "draft": False,
                "head": {"sha": "abc123", "ref": "feat"},
                "html_url": "https://github.com/acme/app/pull/5",
            },
        )
        f.json(
            "GET",
            "/repos/acme/app/commits/abc123/check-runs?per_page=100",
            {"check_runs": [{"name": "ci", "status": "completed", "conclusion": "success"}]},
        )
        f.json("GET", "/repos/acme/app/commits/abc123/status", {"statuses": []})
        yield f


def make(tmp_path: Path, fake: Fake, *, allow: bool = False, creds: bool = True) -> Server:
    from dex_trove.mcp import jenkins

    (tmp_path / ".dex").mkdir(exist_ok=True)
    (tmp_path / ".dex/jenkins.json").write_text(
        json.dumps(
            {
                "url": fake.base,
                "jobs": {
                    "app/ci": {
                        "parameters": {
                            "BRANCH": {"pattern": "^[a-z0-9/-]+$", "required": True},
                            "SUITE": {"choices": ["smoke", "full"], "default": "smoke"},
                        },
                        "require_pr": {"repo": "acme/app", "checks": "passing"},
                    }
                },
            }
        )
    )
    env = {"GH_TOKEN": "t", "GITHUB_API_URL": fake.base}
    if creds:
        env |= {"JENKINS_USER": "user", "JENKINS_TOKEN": "token"}
    ctx = Context(root=tmp_path, server="jenkins", allow_actions=allow, env=env, sleep=lambda _s: None)
    return Server("jenkins", jenkins.INSTRUCTIONS, list(jenkins.TOOLS), ctx)


ARGS = {"job": "app/ci", "parameters": {"BRANCH": "feat"}, "pr": 5}


def test_check_reports_ready_and_drift(tmp_path: Path, fake: Fake) -> None:
    out = make(tmp_path, fake).call("jenkins_check", {"job": "app/ci", "pr": 5})
    assert out["status"] == "ready"
    assert out["pr"]["checks"] == "passing" and out["pr"]["head_sha"] == "abc123"
    with pytest.raises(ToolError, match="isn't in the allowlist"):
        make(tmp_path, fake).call("jenkins_check", {"job": "other/job"})


def test_failing_checks_block(tmp_path: Path, fake: Fake) -> None:
    fake.json(
        "GET",
        "/repos/acme/app/commits/abc123/check-runs?per_page=100",
        {"check_runs": [{"name": "lint", "status": "completed", "conclusion": "failure"}]},
    )
    out = make(tmp_path, fake).call("jenkins_preview", ARGS)
    assert out["status"] == "blocked" and out["approval"] is None
    assert "lint" in out["blocked_by"][0]
    with pytest.raises(ToolError, match="not starting"):
        make(tmp_path, fake, allow=True).call("jenkins_trigger", {**ARGS, "approval": "sha256:x"})


def test_parameters_are_checked(tmp_path: Path, fake: Fake) -> None:
    server = make(tmp_path, fake)
    for params, msg in [
        ({"BRANCH": "Bad Branch!"}, "doesn't match"),
        ({"BRANCH": "x", "SUITE": "all"}, "isn't one of"),
        ({"BRANCH": "x", "DEPLOY": "prod"}, "isn't allowed"),
        ({}, "is required"),
    ]:
        with pytest.raises(ToolError, match=msg):
            server.call("jenkins_preview", {**ARGS, "parameters": params})
    with pytest.raises(ToolError, match="needs a pull request"):
        server.call("jenkins_preview", {"job": "app/ci", "parameters": {"BRANCH": "x"}})


def test_no_trigger_by_default(tmp_path: Path, fake: Fake) -> None:
    preview = make(tmp_path, fake).call("jenkins_preview", ARGS)
    assert preview["status"] == "needs-approval" and preview["plan"]["parameters"] == {
        "BRANCH": "feat",
        "SUITE": "smoke",
    }
    with pytest.raises(ToolError, match="actions are off"):
        make(tmp_path, fake).call("jenkins_trigger", {**ARGS, "approval": preview["approval"]})
    with pytest.raises(ToolError, match="doesn't match"):
        make(tmp_path, fake, allow=True).call(
            "jenkins_trigger", {**ARGS, "parameters": {"BRANCH": "other"}, "approval": preview["approval"]}
        )
    assert not [s for s in fake.seen if s.method == "POST"]


def test_trigger_once_then_follow(tmp_path: Path, fake: Fake) -> None:
    preview = make(tmp_path, fake).call("jenkins_preview", ARGS)
    server = make(tmp_path, fake, allow=True)
    first = server.call("jenkins_trigger", {**ARGS, "approval": preview["approval"]})
    assert first["status"] == "triggered" and first["record"]["queue_url"].endswith("/queue/item/7/")
    posts = [s for s in fake.seen if s.method == "POST"]
    assert len(posts) == 1 and posts[0].headers["authorization"] == AUTH
    assert urllib.parse.parse_qs(posts[0].body.decode()) == {"BRANCH": ["feat"], "SUITE": ["smoke"]}
    again = server.call("jenkins_trigger", {**ARGS, "approval": preview["approval"]})
    assert again["status"] == "already-triggered" and again["duplicate"] is True
    assert len([s for s in fake.seen if s.method == "POST"]) == 1

    done = server.call("jenkins_status", {"idempotency_key": first["idempotency_key"], "interval_seconds": 0})
    assert done["status"] == "finished" and done["build"]["outcome"] == "SUCCESS"
    assert done["build"]["build_url"].endswith("/job/app/job/ci/42/")
    evidence = tmp_path / done["artifacts"][0]["path"]
    assert evidence.is_file() and json.loads(evidence.read_text())["outcome"] == "SUCCESS"
    jobs = server.call("jenkins_jobs", {})
    assert jobs["triggered"][0]["outcome"] == "SUCCESS"
    events = [
        json.loads(line)["event"] for line in (tmp_path / ".dex/mcp/audit.jsonl").read_text().splitlines()
    ]
    assert events[:3] == ["approved", "triggered", "approved"] and "duplicate" in events


def test_failed_build_is_a_finding_in_sarif(tmp_path: Path, fake: Fake) -> None:
    fake.sequence(
        "GET", "/job/app/job/ci/42/api/json", [{"building": False, "result": "FAILURE", "number": 42}]
    )
    preview = make(tmp_path, fake).call("jenkins_preview", ARGS)
    server = make(tmp_path, fake, allow=True)
    key = server.call("jenkins_trigger", {**ARGS, "approval": preview["approval"]})["idempotency_key"]
    out = server.call("jenkins_status", {"idempotency_key": key, "interval_seconds": 0})
    assert out["findings"][0]["rule"] == "jenkins.build-failed"
    sarif = json.loads((tmp_path / f"dex-evidence/jenkins/build-{key}.sarif").read_text())
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def test_polling_is_bounded(tmp_path: Path, fake: Fake) -> None:
    fake.sequence("GET", "/queue/item/7/api/json", [{"why": "waiting"}])
    preview = make(tmp_path, fake).call("jenkins_preview", ARGS)
    server = make(tmp_path, fake, allow=True)
    key = server.call("jenkins_trigger", {**ARGS, "approval": preview["approval"]})["idempotency_key"]
    out = server.call("jenkins_status", {"idempotency_key": key, "max_attempts": 3, "interval_seconds": 0})
    assert out["status"] == "in-progress" and out["checks_used"] == 3 and "queued" in out["warnings"][0]


def test_unauthenticated_requests_fail(tmp_path: Path, fake: Fake) -> None:
    preview = make(tmp_path, fake).call("jenkins_preview", ARGS)
    with pytest.raises(ToolError, match="no Jenkins credentials"):
        make(tmp_path, fake, allow=True, creds=False).call(
            "jenkins_trigger", {**ARGS, "approval": preview["approval"]}
        )
    fake.require = {"authorization": AUTH}
    with pytest.raises(ToolError, match="401 unauthenticated.*JENKINS_USER"):
        make(tmp_path, fake, creds=False).call("jenkins_check", {"job": "app/ci"})


def test_same_input_same_digest(tmp_path: Path, fake: Fake) -> None:
    a = make(tmp_path, fake).call("jenkins_preview", ARGS)
    b = make(tmp_path, fake).call("jenkins_preview", ARGS)
    assert a["digest"] == b["digest"] and a["approval"] == b["approval"]


def test_plain_http_only_on_loopback(tmp_path: Path, fake: Fake) -> None:
    server = make(tmp_path, fake)
    (tmp_path / ".dex/jenkins.json").write_text(
        json.dumps({"url": "http://jenkins.example.com", "jobs": {"a": {}}})
    )
    with pytest.raises(ToolError, match="plain http"):
        server.call("jenkins_check", {"job": "a"})
