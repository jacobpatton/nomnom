# Implementation Plan: NomNom Homelab Container Deployment

**Branch**: `002-ghcr-compose-deploy` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-ghcr-compose-deploy/spec.md`

## Summary

Most infrastructure already exists: a working `Dockerfile`, a `docker-compose.yml` referencing the GHCR image, and a GitHub Actions workflow that builds and pushes multi-arch images on merge to `main`. The remaining work is small:

1. **Add inline comments** to `docker-compose.yml` so every configurable line is self-documenting for homelab operators
2. **Make the GHCR package public** — one-time manual step in GitHub settings (cannot be automated)
3. **Write a deployment quickstart** so an operator knows exactly what to do

## Technical Context

**Tooling**: Docker Compose v2, GitHub Actions, GitHub Container Registry (GHCR)
**Storage**: No new entities — data volume already defined in existing compose file
**Testing**: Manual smoke test (pull image, `docker compose up -d`, verify `/health`)
**Target Platform**: Linux with Docker Engine, amd64 or arm64
**Project Type**: Infrastructure / deployment configuration
**Performance Goals**: Service reachable within 30 seconds of `docker compose up -d`
**Constraints**: Zero source code required on target machine; image publicly pullable without credentials
**Scale/Scope**: Single-user homelab; one Docker host

## Constitution Check

Constitution template is unfilled for this project — no enforced gates. Complexity is minimal (rename one file, add comments, write one doc).

## Project Structure

### Documentation (this feature)

```text
specs/002-ghcr-compose-deploy/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Files Modified / Created at Repository Root

```text
docker-compose.yml                     # MODIFIED — inline comments added
.github/workflows/docker-publish.yml   # VERIFIED — no changes needed
Dockerfile                             # VERIFIED — no changes needed
.dockerignore                          # VERIFIED — no changes needed
```

**Structure Decision**: Deployment-only change. No new source directories. Existing workflow and Dockerfile require no modification.

---

## Phase 0: Research

### Finding 1: Compose File Name

- **Decision**: Keep `docker-compose.yml` as-is (user preference)
- **Rationale**: The file already references the GHCR image and works standalone. `docker-compose.yml` is universally recognized and supported by all Docker Compose versions.

### Finding 2: GHCR package visibility

- **Decision**: Set to Public manually in GitHub settings (one-time, post-first-push)
- **Rationale**: GHCR packages are **private by default** even when the repository is public. There is no workflow YAML key to set visibility. The operator must visit `https://github.com/users/<owner>/packages/container/nomnom-receiver/settings` after the first push and set visibility to Public.
- **Alternative rejected**: GitHub API call in workflow to set visibility — requires additional PAT with `write:packages`; too complex for a one-time action.
- **Impact**: This is the only non-automatable step. It is documented in quickstart.md as a prerequisite.

### Finding 3: Image reference consistency

- **Decision**: Keep `ghcr.io/jacobpatton/nomnom-receiver:latest`
- **Rationale**: The existing `docker-compose.yml` already uses this reference. The GH Actions workflow publishes to `ghcr.io/${{ github.repository_owner }}/nomnom-receiver`, which resolves identically. No changes needed to the workflow.

### Finding 4: Existing workflow is complete

The existing `.github/workflows/docker-publish.yml` already covers all requirements:

- Triggers on push to `main` ✓
- QEMU + Buildx for multi-arch (amd64 + arm64) ✓
- Logs in via `GITHUB_TOKEN` ✓
- Tags `latest` + `sha-<hash>` ✓
- GHA layer cache ✓

**No workflow changes needed.**

---

## Phase 1: Design

### Data Model

No entities. Deployment-only feature.

### Contracts

No new API contracts. The receiver's HTTP interface is unchanged and documented in `specs/001-nomnom-receiver/contracts/ingest-endpoint.md`.

### `compose.yaml` Content

Structurally identical to the existing `docker-compose.yml`. Changes: filename, inline comments on every configurable line.

```yaml
# compose.yaml — NomNom Receiver homelab deployment
# Requirements: Docker Engine on Linux (amd64 or arm64)
# Usage: docker compose up -d

services:
  nomnom-receiver:
    # Pre-built image from GitHub Container Registry.
    # Run `docker compose pull && docker compose up -d` to upgrade.
    image: ghcr.io/jacobpatton/nomnom-receiver:latest

    ports:
      # Host:container port mapping.
      # Change the left side (e.g. "3003:3002") if port 3002 is taken.
      # Bound to loopback only — not exposed directly on the LAN.
      - "127.0.0.1:3002:3002"

    volumes:
      # Named volume for the SQLite database.
      # Data persists across container restarts and image upgrades.
      - nomnom_data:/data

    environment:
      # Path inside the container where the database file is stored.
      DB_PATH: /data/nomnom.db
      # Log verbosity. Options: debug, info, warning, error.
      LOG_LEVEL: info

    # Restart on crash or host reboot. Stop manually with: docker compose down
    restart: unless-stopped

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3002/health"]
      interval: 30s # Check every 30 seconds
      timeout: 5s # Fail if no response in 5 seconds
      retries: 3 # Mark unhealthy after 3 consecutive failures
      start_period: 10s # Allow 10 seconds on first start

volumes:
  nomnom_data:
    # Docker-managed named volume.
    # Inspect with: docker volume inspect nomnom_data
```

### `quickstart.md` Outline

```text
1. Prerequisites — Docker Engine installed
2. One-time: make GHCR package public (GitHub settings URL + steps)
3. Deploy — copy compose.yaml, run docker compose up -d
4. Verify — curl http://localhost:3002/health
5. Upgrade — docker compose pull && docker compose up -d
6. Data access — docker volume inspect nomnom_data → find SQLite file path
7. Stop — docker compose down (data preserved in volume)
```

---

## Complexity Tracking

No violations. All changes trace directly to the user's request.
