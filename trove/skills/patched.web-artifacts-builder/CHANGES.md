# Changes from upstream

A fork of `web-artifacts-builder` from <https://github.com/anthropics/skills>, under its Apache-2.0 licence.

`scripts/init-artifact.sh`: it installed pnpm with an unpinned `npm install -g pnpm`. It now uses Corepack, which ships with Node and checks what it downloads against a signature.

Nothing else is changed.
