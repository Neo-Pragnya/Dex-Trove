"""Jenkins after a pull request: check, preview, trigger with approval, then follow the build to its result.

Configuration lives in the project, credentials in the environment (``JENKINS_USER``, ``JENKINS_TOKEN``):

.. code-block:: json

    {"url": "https://jenkins.example.com",
     "jobs": {"app/ci": {"parameters": {"BRANCH": {"pattern": "^[A-Za-z0-9._/-]{1,100}$", "required": true},
                                        "SUITE": {"choices": ["smoke", "full"], "default": "smoke"}},
                         "require_pr": {"repo": "acme/app", "checks": "passing"}}},
     "poll": {"max_attempts": 60, "interval_seconds": 10}}

Only jobs listed there can be triggered, only with the parameters listed, each checked against its pattern or
choices. The same job, parameters and pull-request head commit always give the same idempotency key, and a key that
already started a build returns that build instead of starting another.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from dex_trove.mcp import github
from dex_trove.mcp.common import (
    Context,
    ToolError,
    approval_for,
    artifact,
    basic_auth,
    finding,
    http,
    now_iso,
    redact,
    require_approval,
    result,
    stable_digest,
    write_json,
    write_sarif,
)
from dex_trove.mcp.server import Tool

NAME = "jenkins"
TITLE = "Jenkins: approval-gated builds after a pull request"
CAPABILITIES = (
    "CAP-jenkins-trigger-01",
    "CAP-jenkins-trigger-02",
    "CAP-jenkins-trigger-03",
    "CAP-jenkins-trigger-04",
)
INSTRUCTIONS = (
    "Starts allowlisted Jenkins jobs only after a person approves the exact plan. Order: jenkins_check (job allowed? "
    "PR checks passing?), jenkins_preview (shows parameters, scope and an approval digest; show it to the user and "
    "ask), jenkins_trigger with that digest (needs the server started with --allow-actions), then jenkins_status to "
    "follow the build and record evidence. Never call jenkins_trigger without the user's explicit yes."
)
AUTH_HINT = "Set JENKINS_USER and JENKINS_TOKEN (an API token from your Jenkins user page) in the server's environment."
JOB_NAME = re.compile(r"^[A-Za-z0-9 ._-]{1,100}(/[A-Za-z0-9 ._-]{1,100}){0,5}$")
PARAM_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,99}$")
LEDGER = "triggers.json"


def _settings(ctx: Context) -> dict[str, Any]:
    cfg = ctx.config(NAME)
    if not cfg:
        raise ToolError(
            "no .dex/jenkins.json in the project. Create it with the Jenkins url and the jobs that may be started "
            '(for example {"url": "https://jenkins.example.com", "jobs": {"app/ci": {"parameters": {}}}}).'
        )
    if not isinstance(cfg.get("jobs"), dict) or not cfg["jobs"]:
        raise ToolError(".dex/jenkins.json: 'jobs' must list at least one allowed job")
    url = str(ctx.env.get("JENKINS_URL") or cfg.get("url") or "").rstrip("/")
    if not url:
        raise ToolError(".dex/jenkins.json: 'url' is missing (or set JENKINS_URL)")
    return {**cfg, "url": url}


def _job(cfg: dict[str, Any], name: object) -> dict[str, Any]:
    if not isinstance(name, str) or not JOB_NAME.match(name) or ".." in name:
        raise ToolError(f"{name!r} isn't a job name like 'app/ci'")
    spec = cfg["jobs"].get(name)
    if spec is None:
        raise ToolError(
            f"job {name!r} isn't in the allowlist (.dex/jenkins.json lists {', '.join(sorted(cfg['jobs']))})"
        )
    return spec if isinstance(spec, dict) else {}


def _job_url(base: str, name: str) -> str:
    return base + "".join(f"/job/{urllib.parse.quote(part, safe='')}" for part in name.split("/"))


def _headers(ctx: Context, *, required: bool) -> dict[str, str]:
    user, token = ctx.env.get("JENKINS_USER", ""), ctx.env.get("JENKINS_TOKEN", "")
    if user and token:
        return {"Authorization": basic_auth(user, token)}
    if required:
        raise ToolError("no Jenkins credentials. " + AUTH_HINT)
    return {}


def _check_parameters(spec: dict[str, Any], given: object) -> dict[str, str]:
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise ToolError("parameters must be an object of name: value")
    allowed = spec.get("parameters") or {}
    out: dict[str, str] = {}
    for key, value in given.items():
        if key not in allowed:
            raise ToolError(
                f"parameter {key!r} isn't allowed for this job (allowed: {', '.join(sorted(allowed)) or 'none'})"
            )
        if not PARAM_NAME.match(key):
            raise ToolError(f"parameter name {key!r} isn't valid")
        if not isinstance(value, str | int | float):
            raise ToolError(f"parameter {key} must be text, a number or true/false")
        text = str(value).lower() if isinstance(value, bool) else str(value)
        rule = allowed[key] or {}
        if "choices" in rule and text not in [str(c) for c in rule["choices"]]:
            raise ToolError(f"parameter {key}={text!r} isn't one of {', '.join(map(str, rule['choices']))}")
        if "pattern" in rule and not re.fullmatch(str(rule["pattern"]), text):
            raise ToolError(f"parameter {key}={text!r} doesn't match {rule['pattern']}")
        if len(text) > 1000:
            raise ToolError(f"parameter {key} is longer than 1000 characters")
        out[key] = text
    for key, rule in allowed.items():
        rule = rule or {}
        if key not in out and "default" in rule:
            out[key] = str(rule["default"])
        if key not in out and rule.get("required"):
            raise ToolError(f"parameter {key} is required for this job")
    return dict(sorted(out.items()))


def _pr(ctx: Context, spec: dict[str, Any], pr: object) -> dict[str, Any] | None:
    need = spec.get("require_pr")
    if pr is None:
        if need:
            raise ToolError(
                "this job needs a pull request number (pr): it only runs for a PR whose checks pass"
            )
        return None
    repo = (need or {}).get("repo") if isinstance(need, dict) else None
    if not repo:
        raise ToolError(
            "pr was given, but the job has no require_pr.repo in .dex/jenkins.json to look it up in"
        )
    if not isinstance(pr, int) or isinstance(pr, bool):
        raise ToolError("pr must be a pull request number")
    return github.pr_status(ctx, str(repo), pr)


def _pr_problems(spec: dict[str, Any], status: dict[str, Any] | None) -> list[str]:
    if status is None:
        return []
    problems = []
    if status["state"] != "open":
        problems.append(f"PR #{status['number']} is {status['state']}, not open")
    if status["draft"]:
        problems.append(f"PR #{status['number']} is a draft")
    want = (spec.get("require_pr") or {}).get("checks", "passing")
    if want == "passing" and status["checks"] != "passing":
        detail = ", ".join(status["failed"] or status["pending"]) or "no checks reported"
        problems.append(f"PR #{status['number']} checks are {status['checks']} ({detail})")
    return problems


def check(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    cfg = _settings(ctx)
    spec = _job(cfg, args["job"])
    job_url = _job_url(cfg["url"], args["job"])
    resp = http(
        ctx,
        "GET",
        job_url + "/api/json?tree=name,buildable,url,property[parameterDefinitions[name,type]]",
        headers=_headers(ctx, required=False),
        service="Jenkins",
        auth_hint=AUTH_HINT,
    )
    if resp.status == 404:
        raise ToolError(
            f"Jenkins has no job {args['job']!r} at {job_url} (or these credentials can't see it)"
        )
    if resp.status >= 400:
        raise ToolError(f"Jenkins answered {resp.status} for {job_url}")
    info = resp.json()
    server_params = sorted(
        d.get("name", "")
        for p in info.get("property") or []
        for d in (p or {}).get("parameterDefinitions") or []
    )
    allowed = sorted((spec.get("parameters") or {}).keys())
    findings = []
    unknown = sorted(set(allowed) - set(server_params))
    if unknown:
        findings.append(
            finding(
                "warning",
                f"allowlisted parameter(s) {', '.join(unknown)} aren't defined on the Jenkins job",
                rule="jenkins.parameter-drift",
                remediation="update .dex/jenkins.json or the job",
            )
        )
    if not info.get("buildable", True):
        findings.append(finding("error", "the job is disabled in Jenkins", rule="jenkins.not-buildable"))
    status = _pr(ctx, spec, args.get("pr"))
    for problem in _pr_problems(spec, status):
        findings.append(
            finding("error", problem, rule="jenkins.pr-not-ready", remediation="wait for green checks")
        )
    ok = not any(f["severity"] == "error" for f in findings)
    return result(
        ctx,
        "ready" if ok else "blocked",
        job=args["job"],
        job_url=job_url,
        allowed_parameters=allowed,
        jenkins_parameters=server_params,
        pr=status,
        findings=findings,
        inputs=args,
    )


def _plan(ctx: Context, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    cfg = _settings(ctx)
    spec = _job(cfg, args["job"])
    params = _check_parameters(spec, args.get("parameters"))
    status = _pr(ctx, spec, args.get("pr"))
    problems = _pr_problems(spec, status)
    plan = {
        "action": "jenkins.build",
        "server": cfg["url"],
        "job": args["job"],
        "job_url": _job_url(cfg["url"], args["job"]),
        "parameters": params,
        "pr": None if status is None else {k: status[k] for k in ("repo", "number", "head_sha")},
    }
    plan["idempotency_key"] = stable_digest(plan)[:32]
    return plan, problems


def _ledger(ctx: Context) -> dict[str, Any]:
    path = ctx.state / LEDGER
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ToolError(f"{path}: damaged ledger ({exc}); move it aside to continue") from exc
    return data if isinstance(data, dict) else {}


def _save_ledger(ctx: Context, ledger: dict[str, Any]) -> None:
    write_json(ctx.state / LEDGER, ledger)


def preview(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan, problems = _plan(ctx, args)
    earlier = _ledger(ctx).get(plan["idempotency_key"])
    lines = [
        f"Start Jenkins job {plan['job']} on {plan['server']}",
        *(f"  {k} = {v}" for k, v in plan["parameters"].items()),
    ]
    if plan["pr"]:
        lines.append(
            f"For PR #{plan['pr']['number']} in {plan['pr']['repo']} at {plan['pr']['head_sha'][:12]}"
        )
    warnings = ["Starting a build uses CI capacity and may cost money."]
    if earlier:
        warnings.append(
            f"This exact plan already started a build ({earlier.get('queue_url', '')}); triggering returns it."
        )
    return result(
        ctx,
        "blocked" if problems else "needs-approval",
        plan=plan,
        summary="\n".join(lines),
        approval=None if problems else approval_for(plan),
        blocked_by=problems,
        actions_enabled=ctx.allow_actions,
        warnings=warnings,
        inputs=args,
    )


def trigger(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan, problems = _plan(ctx, args)
    if problems:
        raise ToolError("not starting: " + "; ".join(problems))
    require_approval(ctx, plan, args.get("approval"), action="jenkins.build")
    ledger = _ledger(ctx)
    key = plan["idempotency_key"]
    if key in ledger:
        ctx.audit("duplicate", action="jenkins.build", idempotency_key=key)
        return result(
            ctx, "already-triggered", duplicate=True, idempotency_key=key, record=ledger[key], inputs=args
        )
    headers = _headers(ctx, required=True)
    crumb = http(
        ctx,
        "GET",
        plan["server"] + "/crumbIssuer/api/json",
        headers=headers,
        service="Jenkins",
        auth_hint=AUTH_HINT,
    )
    if crumb.status == 200:
        data = crumb.json()
        headers[str(data.get("crumbRequestField", "Jenkins-Crumb"))] = str(data.get("crumb", ""))
    endpoint = "/buildWithParameters" if plan["parameters"] else "/build"
    body = urllib.parse.urlencode(plan["parameters"]).encode()
    resp = http(
        ctx,
        "POST",
        plan["job_url"] + endpoint,
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        body=body,
        retries=0,
        service="Jenkins",
        auth_hint=AUTH_HINT,
    )
    if resp.status not in (200, 201):
        ctx.audit("failed", action="jenkins.build", status=resp.status)
        raise ToolError(
            f"Jenkins didn't accept the build ({resp.status}): {redact(resp.body[:300].decode('utf-8', 'replace'))}"
        )
    queue_url = resp.headers.get("location", "")
    record = {
        "job": plan["job"],
        "parameters": plan["parameters"],
        "pr": plan["pr"],
        "queue_url": queue_url,
        "triggered_at": now_iso(),
        "outcome": None,
    }
    ledger[key] = record
    _save_ledger(ctx, ledger)
    ctx.audit("triggered", action="jenkins.build", idempotency_key=key, queue_url=queue_url)
    return result(ctx, "triggered", duplicate=False, idempotency_key=key, record=record, inputs=args)


def _poll_json(ctx: Context, url: str) -> dict[str, Any]:
    resp = http(
        ctx,
        "GET",
        url.rstrip("/") + "/api/json",
        headers=_headers(ctx, required=False),
        service="Jenkins",
        auth_hint=AUTH_HINT,
    )
    if resp.status >= 400:
        raise ToolError(f"Jenkins answered {resp.status} for {url}")
    data = resp.json()
    return data if isinstance(data, dict) else {}


def status(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    ledger = _ledger(ctx)
    key = args["idempotency_key"]
    record = ledger.get(key)
    if record is None:
        raise ToolError(f"no build was triggered with key {key!r} from this project")
    cfg = _settings(ctx)
    poll = cfg.get("poll") or {}
    attempts = max(1, min(int(args.get("max_attempts") or poll.get("max_attempts", 30)), 360))
    interval = max(0.0, min(float(args.get("interval_seconds", poll.get("interval_seconds", 10))), 120.0))
    build_url = record.get("build_url", "")
    info: dict[str, Any] = {}
    used = 0
    while used < attempts:
        used += 1
        if not build_url:
            queue = _poll_json(ctx, record["queue_url"])
            if queue.get("cancelled"):
                record["outcome"] = "CANCELLED"
                break
            build_url = (queue.get("executable") or {}).get("url", "")
        if build_url:
            info = _poll_json(ctx, build_url)
            if not info.get("building", True) and info.get("result"):
                break
        if used < attempts:
            ctx.sleep(interval)
    finished = bool(info) and not info.get("building", True) and bool(info.get("result"))
    outcome = record.get("outcome") or (info.get("result") if finished else None)
    record.update(
        {"build_url": build_url, "outcome": outcome, "number": info.get("number"), "checked_at": now_iso()}
    )
    ledger[key] = record
    _save_ledger(ctx, ledger)
    findings, warnings, artifacts = [], [], []
    if outcome and outcome != "SUCCESS":
        findings.append(
            finding(
                "error",
                f"Jenkins build {plan_label(record)} finished {outcome}",
                rule="jenkins.build-failed",
                uri=build_url,
                remediation="open the build log",
            )
        )
    if not outcome:
        warnings.append(
            f"still {'queued' if not build_url else 'running'} after {used} check(s); call jenkins_status again"
        )
    evidence = {
        "schema": "dex-trove/jenkins-build@1",
        "idempotency_key": key,
        "job": record["job"],
        "parameters": record["parameters"],
        "pr": record["pr"],
        "queue_url": record["queue_url"],
        "build_url": build_url,
        "number": info.get("number"),
        "outcome": outcome,
        "duration_ms": info.get("duration"),
    }
    path = write_json(ctx.evidence / f"build-{key}.json", evidence)
    artifacts.append(artifact(ctx, path, "application/json", schema="dex-trove/jenkins-build@1"))
    if findings:
        artifacts.append(
            artifact(
                ctx, write_sarif(ctx, f"build-{key}", findings, tool="dex-jenkins"), "application/sarif+json"
            )
        )
    ctx.audit("status", idempotency_key=key, outcome=outcome)
    return result(
        ctx,
        "finished" if outcome else "in-progress",
        build=evidence,
        checks_used=used,
        artifacts=artifacts,
        findings=findings,
        warnings=warnings,
        inputs={"key": key},
    )


def plan_label(record: dict[str, Any]) -> str:
    return f"{record.get('job')} #{record.get('number')}" if record.get("number") else str(record.get("job"))


def list_jobs(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    cfg = _settings(ctx)
    jobs = {
        name: {"parameters": spec.get("parameters") or {}, "require_pr": spec.get("require_pr")}
        for name, spec in sorted(cfg["jobs"].items())
    }
    triggered = [{"idempotency_key": k, **v} for k, v in sorted(_ledger(ctx).items())]
    return result(
        ctx,
        "ok",
        server=cfg["url"],
        jobs=jobs,
        triggered=triggered,
        actions_enabled=ctx.allow_actions,
        credentials="present" if ctx.env.get("JENKINS_USER") and ctx.env.get("JENKINS_TOKEN") else "missing",
        inputs={},
    )


_JOB = {"type": "string", "description": "Job name from .dex/jenkins.json, e.g. 'app/ci'"}
_PARAMS = {"type": "object", "description": "Build parameters (only allowlisted names)"}
_PR = {"type": "integer", "description": "Pull request number whose checks must pass"}

TOOLS = [
    Tool(
        "jenkins_jobs",
        "The allowlisted jobs, their parameter rules, and builds started from this project.",
        {},
        list_jobs,
    ),
    Tool(
        "jenkins_check",
        "Is the job allowlisted, present and enabled in Jenkins, and are the PR's checks passing?",
        {"job": _JOB, "pr": _PR},
        check,
        required=("job",),
    ),
    Tool(
        "jenkins_preview",
        "Validates parameters and shows exactly what would start, with an approval digest. Starts nothing.",
        {"job": _JOB, "parameters": _PARAMS, "pr": _PR},
        preview,
        required=("job",),
    ),
    Tool(
        "jenkins_trigger",
        "Starts the previewed build. Needs --allow-actions and the preview's approval digest, which the "
        "user must have seen and accepted. The same plan never starts twice.",
        {"job": _JOB, "parameters": _PARAMS, "pr": _PR, "approval": {"type": "string"}},
        trigger,
        required=("job", "approval"),
        action=True,
    ),
    Tool(
        "jenkins_status",
        "Follows a started build (bounded checks) and records its URL and outcome as evidence.",
        {
            "idempotency_key": {"type": "string"},
            "max_attempts": {"type": "integer"},
            "interval_seconds": {"type": "number"},
        },
        status,
        required=("idempotency_key",),
        writes=True,
    ),
]
