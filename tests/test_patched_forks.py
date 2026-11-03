"""The forks in forks/ fix what they say they fix, and record where they came from."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
FORK = ROOT / "trove" / "skills" / "patched.hf-cloud-sagemaker-iam-preflight"


def check_role() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_role", FORK / "scripts" / "check_role.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def role(**statement: object) -> dict[str, object]:
    base = {
        "Effect": "Allow",
        "Principal": {"Service": "sagemaker.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }
    return {"AssumeRolePolicyDocument": {"Statement": [{**base, **statement}]}}


def test_the_policy_upstream_ships_passes() -> None:
    policy = json.loads((FORK / "references" / "trust-policy.json").read_text())
    assert check_role().trust_allows_sagemaker({"AssumeRolePolicyDocument": policy})


@pytest.mark.parametrize(
    "statement",
    [
        {"Principal": {"Service": ["ec2.amazonaws.com", "sagemaker.amazonaws.com"]}},
        {"Action": ["sts:AssumeRole"]},
    ],
    ids=["list-of-services", "list-of-actions"],
)
def test_real_shapes_pass(statement: dict[str, object]) -> None:
    assert check_role().trust_allows_sagemaker(role(**statement))


@pytest.mark.parametrize(
    "statement",
    [
        {"Principal": {"Service": "sagemaker.amazonaws.com.example.org"}},
        {"Principal": {"Service": "ec2.amazonaws.com"}},
        {"Principal": {"AWS": "arn:aws:iam::1:role/sagemaker.amazonaws.com"}},
        {"Principal": "*"},
        {"Effect": "Deny"},
        {"Action": "sts:TagSession"},
    ],
    ids=["lookalike-service", "other-service", "name-in-another-field", "wildcard", "deny", "other-action"],
)
def test_what_the_substring_check_wrongly_passed_is_refused(statement: dict[str, object]) -> None:
    assert not check_role().trust_allows_sagemaker(role(**statement))


def test_a_policy_with_a_single_statement_object_is_read() -> None:
    doc = {"AssumeRolePolicyDocument": {"Statement": role()["AssumeRolePolicyDocument"]["Statement"][0]}}  # type: ignore[index]
    assert check_role().trust_allows_sagemaker(doc)


def test_the_fork_keeps_its_licence_and_says_what_changed() -> None:
    assert "Apache License" in (FORK / "LICENSE").read_text()
    assert "Changes from upstream" in (FORK / "CHANGES.md").read_text()
    record = json.loads((FORK / "dex.json").read_text())
    assert record["forked_from"]["key"] == "skill:huggingface/hf-cloud-sagemaker-iam-preflight"
    assert record["license"]["spdx"] == "Apache-2.0"
