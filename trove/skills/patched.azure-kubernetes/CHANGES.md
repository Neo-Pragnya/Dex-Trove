# Changes from upstream

A fork of `azure-kubernetes` from <https://github.com/microsoft/skills>, under its MIT licence.

`azure-kubernetes-app-deploy/templates/dockerfiles/`: the templates used base images by tag alone, and a tag can move. Each `FROM` now has a `@sha256:<DIGEST>` placeholder, `references/base-images.md` says how to fill it in, and the files are named `*.Dockerfile.template`, since they can't build until their placeholders are filled. References to them are updated.

The Python template installs with `--require-hashes`, and the .NET one restores with `--locked-mode`, so what's installed can't change unnoticed. `references/base-images.md` says how to make what they need.

Nothing else is changed.
