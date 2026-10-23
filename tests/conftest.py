from __future__ import annotations

import json
from pathlib import Path

import pytest

from dex_trove.sources import Source

MIT = """MIT License

Copyright (c) 2026 Upstream Authors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, subject to the following
conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions
of the Software.
"""

PROPRIETARY = """© 2025 Example, PBC. All rights reserved.

LICENSE: Use of these materials is governed by your agreement with Example.
ADDITIONAL RESTRICTIONS: users may not distribute, sublicense, or transfer these materials to any third party.
"""

OFL = "Copyright 2012 Font Authors\n\nThis Font Software is licensed under the SIL Open Font License, Version 1.1.\n"


def skill(
    root: Path, name: str, body: str = "Do the thing.", fm: str = "", files: dict[str, str] | None = None
) -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: '{name} skill for tests'\n{fm}---\n\n# {name}\n\n{body}\n"
    )
    for rel, text in (files or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    return d


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A miniature awesome-copilot-shaped repo covering each admission rule."""
    root = tmp_path / "upstream"
    root.mkdir()
    (root / "LICENSE").write_text(MIT)
    skill(root, "alpha")
    skill(root, "closed", files={"LICENSE.txt": PROPRIETARY})
    skill(root, "apache-declared", fm="license: Apache-2.0\n")
    skill(root, "see-file", fm="license: Complete terms in LICENSE.txt\n", files={"LICENSE.txt": MIT})
    skill(root, "fonts", files={"canvas-fonts/Foo-OFL.txt": OFL, "canvas-fonts/Foo.ttf": "binary"})
    # Credential-shaped strings are assembled at runtime so the sdist (which ships tests/) holds none.
    skill(root, "leaky", files={"cfg.env": "AWS_KEY=" + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n"})
    skill(root, "teaching", body='Never do this: const API_KEY = "' + "sk_" + "live_abc123xyz789abc" + '";')
    skill(root, "runner", files={"scripts/run.sh": "echo hi\n"})
    (root / "agents").mkdir()
    (root / "agents" / "Helper.agent.md").write_text(
        "---\nname: Helper\ndescription: 'Helps.'\n---\n\nYou help.\n"
    )
    (root / "instructions").mkdir()
    (root / "instructions" / "py.instructions.md").write_text(
        "---\napplyTo: '**/*.py'\ndescription: 'Python rules'\n---\n\n# Python\n\nUse types.\n"
    )
    (root / "plugins" / "kit").mkdir(parents=True)
    (root / "plugins" / "kit" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "kit",
                "description": "A kit",
                "version": "2.1.0",
                "extensions": {
                    "com.github.awesome-copilot": {
                        "skills": ["./skills/alpha/", "./skills/closed/"],
                        "agents": ["./agents/helper.md"],
                    }
                },
            }
        )
    )
    (root / "plugins" / "canvas").mkdir(parents=True)
    (root / "plugins" / "canvas" / "plugin.json").write_text(
        json.dumps({"name": "canvas", "description": "x"})
    )
    return root


@pytest.fixture
def source() -> Source:
    return Source(id="up", title="Upstream", adapter="awesome-copilot", repo="https://github.com/example/up")


@pytest.fixture
def trove(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    t = tmp_path / "trove"
    t.mkdir()
    monkeypatch.setenv("DEX_TROVE_ROOT", str(t))
    return t
