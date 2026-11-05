# Base Image Policy

How the skill chooses container base images. Goal: **no version number is
stored in this repo** — the concrete tag is resolved when the Dockerfile is
generated, so templates never go stale.

## Rules

1. **Never pin minor/patch.** Use a floating **major** (or major.minor) tag.
   Floating tags receive security patches automatically — a frozen patch tag
   does not.
2. **Resolve `<LATEST_STABLE_*>` at generation time.** When generating a
   Dockerfile, replace each placeholder with the current stable major the
   project targets (see "Resolution" below), then keep that major tag in the
   output. A major tag is concrete, so it satisfies Deployment Safeguard DS009
   (no `:latest`).
3. **Prefer the Microsoft/Azure Linux image when one exists and the project
   has no reason to avoid it.** These are first-party, signed, and rebuilt for
   CVEs. They are listed below as the preferred option; the current default
   source is kept for drop-in compatibility.

## Per-language images

| Language | Default source (template today) | Tag policy | Preferred Microsoft / Azure Linux image |
|----------|---------------------------------|-----------|------------------------------------------|
| .NET | `mcr.microsoft.com/dotnet/{sdk,aspnet}` | floating major (e.g. `9.0`) | already Microsoft ✓ |
| Java | `eclipse-temurin:<maj>-{jdk,jre}-alpine` | floating major LTS | `mcr.microsoft.com/openjdk/jdk:<maj>-azurelinux` (also `-distroless`) |
| Python | `mcr.microsoft.com/azurelinux/base/python:<maj.min>` | floating major.minor | already Microsoft ✓ |
| Node | `node:<maj>-alpine` | floating major LTS | `mcr.microsoft.com/azurelinux/base/nodejs:<maj>` |
| Go | build `golang:<ver>-alpine`, runtime `gcr.io/distroless/static-debian12` | floating major.minor | `mcr.microsoft.com/oss/go/microsoft/golang:<ver>-azurelinux3.0` |
| Rust | build `rust:<ver>-slim`, runtime `gcr.io/distroless/cc-debian12` | floating major.minor | `mcr.microsoft.com/azurelinux/base/rust:<maj.min>` |

> The Go and Rust **runtime** stages keep the literal
> `gcr.io/distroless/*-debian12` names and do **not** use a `<LATEST_STABLE_*>`
> placeholder: distroless images are identified by base-OS variant (the Debian
> release), not by language version, and they float their patch level within
> that Debian release. This asymmetry with the build stages is intentional —
> don't "fix" it by adding a placeholder.

> Adopting the Microsoft Azure Linux images for Node/Go/Rust changes the
> in-image package manager (`tdnf`, not `apk`/`apt`) and the non-root-user
> setup. That migration is intentionally **out of scope** here — this file
> documents the target so a later change can adopt it.

## Resolution

To fill a `<LATEST_STABLE_*>` placeholder at generation time, in order of
preference:

1. **Explicit check.** Query the registry or release channel for the current
   stable major, e.g.:
   - .NET / Java / Go (Microsoft): `az acr manifest list-metadata` against the
     MCR repo, or the image's tag list.
   - Python / Node / Rust: the language's published release channel (Docker
     Hub tag list, or the language's downloads page).
2. **Fallback.** If no check is possible (offline, no registry access), use the
   latest stable major you know, and add a comment in the generated Dockerfile:
   `# verify this is still the current stable major`.

Why floating majors are maintenance-free: Microsoft major tags always carry
the latest minor and are rebuilt for CVEs on a regular cadence; Docker Hub
`-slim`/`-alpine` tags float their patch level the same way. A major tag is
therefore both stable to reference and current for security.

## Pin the base image by digest

A tag can move, so what you tested isn't necessarily what the next build pulls. The templates have `@sha256:<DIGEST>` after each image. Once you've chosen the tag, replace that with its digest, and keep the tag for people to read:

```bash
docker buildx imagetools inspect node:22-alpine --format '{{json .Manifest.Digest}}'
```

```dockerfile
FROM node:22-alpine@sha256:<the digest it printed> AS build
```

## Pin what's installed too

- **Python:** the template installs with `--require-hashes`, so `requirements.txt` needs a hash for every package. Make it with `uv pip compile requirements.in --generate-hashes -o requirements.txt`.
- **.NET:** the template restores with `--locked-mode`, so commit a `packages.lock.json`. Make it by setting `RestorePackagesWithLockFile` to `true` in the project and running `dotnet restore` once.

