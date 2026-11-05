# Changes from upstream

A fork of `azure-kubernetes` from <https://github.com/microsoft/skills>, under its MIT licence.

`azure-kubernetes-app-deploy/templates/dockerfiles/`: the templates used base images by tag alone, and a tag can move. Each `FROM` now has a `@sha256:<DIGEST>` placeholder, `references/base-images.md` says how to fill it in, and the files are named `*.Dockerfile.template`, since they can't build until their placeholders are filled. References to them are updated.

Nothing else is changed.
