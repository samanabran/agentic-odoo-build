# ADR 0007 — Odoo Image Digest Pinning

**Date:** 2026-05-06
**Status:** Accepted

## Context

When a Docker image tag such as odoo:18.0 is used without a digest, the
underlying image can silently change when Docker Hub updates the tag. This
creates two risks:

1. **Reproducibility**: a developer who ran docker pull odoo:18.0 today and
   another who runs it in three months may get different Python versions,
   patched Odoo files, or changed system libraries — with no warning.
2. **Surprise breakage**: if Docker Hub pushes a security patch that tweaks
   internal Odoo behaviour (e.g., changed check_version() logic), our tests
   pass locally on the old layer but CI silently pulls the new one.

## Decision

Pin the Odoo Docker image to an explicit digest in infra/docker-compose.yml.

**Pinned digest (pulled 2026-05-06):**

`
odoo@sha256:b79d87a4ec1a3806d133e12a07dc06402fc37397eb285663b1acfea2001ae52c
`

This corresponds to odoo:18.0 as of 2026-05-06.

## Consequences

- Every developer and CI runner gets the exact same Odoo layer.
- To update the pin: run docker pull odoo:18.0, capture the new digest with
  docker inspect odoo:18.0 --format '{{.RepoDigests}}', update
  docker-compose.yml, and open a "vendor bump" PR (per ADR 0002 process).
- The ootstrap.sh script continues to reference odoo:18.0 by tag for the
  docker pull step (so it fetches whatever is current at bootstrap time);
  docker-compose.yml uses the pinned digest for deterministic stack launches.

## Alternatives rejected

- **Floating tag odoo:18.0**: non-deterministic; rejected for production parity.
- **Semantic pin odoo:18.0-<build-date>**: Docker Hub does not publish these
  for the official odoo image; digest is the only stable identifier.