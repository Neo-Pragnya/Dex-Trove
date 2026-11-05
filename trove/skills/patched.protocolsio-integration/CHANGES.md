# Changes from upstream

A fork of `protocolsio-integration` from <https://github.com/K-Dense-AI/claude-scientific-skills>, under its MIT licence.

`scripts/plan_write_request.py`, `_protocol_uri`: the check for a value that's a protocols.io address rather than a URI looked for the text at its start. It now compares the first dotted part, so it can't be read as a check on a URL's host. Values with a dot already fail the pattern above it, so the same values are accepted.

Nothing else is changed.
