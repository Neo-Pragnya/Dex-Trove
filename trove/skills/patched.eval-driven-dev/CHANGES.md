# Changes from upstream

A fork of `eval-driven-dev` from <https://github.com/github/awesome-copilot>, under its MIT licence.

`resources/setup.sh`: a plain `pip install` took whatever versions it found. It now installs from `resources/pixie-requirements.txt`, which pins every package by hash, so what's downloaded can't change unnoticed. Projects using uv or Poetry already had a lockfile. To move to a newer version, regenerate that file with `uv pip compile --universal --generate-hashes`.

Nothing else is changed.
