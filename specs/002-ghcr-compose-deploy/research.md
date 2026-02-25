# Research: NomNom Homelab Container Deployment

**Feature**: 002-ghcr-compose-deploy | **Date**: 2026-02-24

## Decision 1: Compose File Name

- **Decision**: `compose.yaml` (rename from `docker-compose.yml`)
- **Rationale**: Docker Compose v2 prefers `compose.yaml` as the canonical filename. It resolves files in order: `compose.yaml` → `compose.yml` → `docker-compose.yml`. Using the canonical name satisfies the user's explicit requirement ("deployable from a `compose.yaml` file, alone") and aligns with the Docker Compose v2 specification.
- **Alternatives considered**: Keeping `docker-compose.yml` — works functionally but doesn't match the stated requirement and is the legacy name.

## Decision 2: GHCR Package Visibility

- **Decision**: Manual one-time action in GitHub Package settings to set visibility to Public
- **Rationale**: GitHub Container Registry packages are private by default, even from public repositories. The GitHub Actions workflow using `GITHUB_TOKEN` can push images but cannot change package visibility. After the first successful push, the operator must go to `https://github.com/users/<owner>/packages/container/nomnom-receiver/settings` and set visibility to Public.
- **Alternatives considered**:
  - GitHub API call in the workflow using a PAT with `write:packages` scope — adds credential management complexity for a one-time action; rejected.
  - Using a public container registry (Docker Hub) — would require Docker Hub account; GHCR is integrated with GitHub Actions via `GITHUB_TOKEN`; rejected.

## Decision 3: Image Reference Format

- **Decision**: `ghcr.io/jacobbednarz/nomnom-receiver:latest`
- **Rationale**: This matches what the existing workflow publishes. Using `latest` as the tag in `compose.yaml` means the operator gets updates with `docker compose pull` without editing the file — satisfying FR-010. The `sha-<hash>` tag published by the workflow provides an audit trail but is not required in `compose.yaml`.
- **Alternatives considered**: Using `ghcr.io/${{ github.repository }}` style reference — not possible in a static YAML file consumed outside of GitHub Actions context.

## Decision 4: Port Binding Strategy

- **Decision**: `127.0.0.1:3002:3002` (loopback-only)
- **Rationale**: The receiver is a local-network tool. Binding to loopback prevents accidental exposure on the LAN interface. Users who need LAN access should configure a reverse proxy (e.g., Caddy, Nginx) in front of the service — this is standard homelab practice and out of scope for v1.
- **Alternatives considered**: `0.0.0.0:3002:3002` (all interfaces) — exposes the service to the LAN without any auth; rejected for security reasons.

## Decision 5: Existing Workflow and Dockerfile

- **Decision**: No changes needed
- **Rationale**: The existing `.github/workflows/docker-publish.yml` already implements all requirements: multi-arch build (amd64/arm64), push on merge to `main`, GHCR authentication via `GITHUB_TOKEN`, and GHA layer caching. The `Dockerfile` uses a multi-stage build with a non-root user and is production-ready. Both are verified correct as-is.
