# Changes from upstream

A fork of `bmad` from <https://github.com/bmad-code-org/BMAD-METHOD>, under its MIT licence.

`scripts/setup.py`: the version pattern could take exponential time on a crafted prerelease string, for example from an edited lockfile, so the command stalled. An identifier part now reads its leading digits first, so there's one way to match. It accepts exactly the same versions.

Nothing else is changed.
