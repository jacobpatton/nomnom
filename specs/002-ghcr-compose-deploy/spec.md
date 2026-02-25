# Feature Specification: NomNom Homelab Container Deployment

**Feature Branch**: `002-ghcr-compose-deploy`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "containerize this so I can push it to GHCR & deploy it to my homelab via Docker Compose. I want it to be deployable from a compose.yaml file, alone."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - One-File Homelab Deployment (Priority: P1)

As a homelab operator, I want to deploy the NomNom receiver on any machine by copying a single `compose.yaml` file and running one command — no source code, no build tools, no dependency installation required.

**Why this priority**: This is the stated goal: self-contained deployment. If a homelab operator has to do anything beyond copying one file and running one command, the feature has not succeeded.

**Independent Test**: Copy only `compose.yaml` to a machine with Docker installed (no source code present). Run `docker compose up -d`. Confirm the service is reachable and accepting submissions within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a machine with Docker installed and no source code present, **When** the operator runs `docker compose up -d` with the provided `compose.yaml`, **Then** the receiver starts, is reachable on port 3002, and returns a healthy status.
2. **Given** the service is running, **When** the operator stops and restarts the container, **Then** all previously stored data is still accessible — nothing is lost.
3. **Given** the service is running, **When** the userscript sends a submission, **Then** it is accepted and stored as expected.
4. **Given** the operator wants to change the data storage location or log level, **When** they edit the environment variables in `compose.yaml`, **Then** the service uses the new configuration on next start.

---

### User Story 2 - Automatic Image Publishing on Merge (Priority: P2)

As a developer, I want the container image to be automatically built and pushed to the GitHub Container Registry whenever changes are merged to the main branch, so the homelab deployment always has access to the latest version without manual intervention.

**Why this priority**: Without this, the homelab operator has to manually build and push the image every time the code changes. Automating this is what makes the single-file deployment sustainable.

**Independent Test**: Merge a code change to main. Without any manual steps, confirm a new container image is available on GHCR with the `latest` tag within 10 minutes.

**Acceptance Scenarios**:

1. **Given** a code change is merged to the main branch, **When** the automated build completes, **Then** a new image is available at the GHCR image reference used in `compose.yaml`.
2. **Given** the image is published, **When** the homelab operator runs `docker compose pull && docker compose up -d` on their machine, **Then** the service updates to the new version.
3. **Given** the build succeeds, **Then** the image is available for both common processor architectures (Intel/AMD and ARM) so the service runs on a variety of homelab hardware.

---

### User Story 3 - Publicly Accessible Image (Priority: P3)

As a homelab operator, I want to pull the container image without needing to authenticate with the container registry, so deployment requires no credentials or registry setup.

**Why this priority**: If the image is private, the homelab operator must configure registry credentials before they can pull the image, breaking the "compose.yaml alone" requirement.

**Independent Test**: On a machine with no GHCR credentials configured, run `docker pull <image-reference>`. Confirm it succeeds without authentication errors.

**Acceptance Scenarios**:

1. **Given** no registry authentication is configured on the host machine, **When** Docker attempts to pull the image via `docker compose up`, **Then** the pull succeeds without prompting for credentials.
2. **Given** the image is public, **Then** anyone with the `compose.yaml` file can deploy the service without any registry account or token.

---

### Edge Cases

- What happens when the operator runs `docker compose up` before the first image has been published to the registry?
- What happens if the data volume already contains a database from a previous version — does a new container upgrade gracefully?
- What if port 3002 is already in use on the homelab machine?
- What happens if the homelab machine loses power mid-write — is the database left in a consistent state?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: A `compose.yaml` file MUST exist in the repository that, by itself, is sufficient to deploy the receiver service on any machine with Docker installed — no source code or build step required.
- **FR-002**: The `compose.yaml` MUST reference a pre-built image from the GitHub Container Registry rather than building locally.
- **FR-003**: The image MUST be publicly accessible on GHCR so no registry authentication is needed to pull it.
- **FR-004**: The `compose.yaml` MUST configure a named volume so stored data persists across container restarts and upgrades.
- **FR-005**: The `compose.yaml` MUST include a health check so Docker can report whether the service is ready.
- **FR-006**: The `compose.yaml` MUST be configured with a restart policy so the service automatically recovers from crashes or reboots.
- **FR-007**: The image MUST be automatically built and published to GHCR whenever a change is merged to the main branch, without any manual steps.
- **FR-008**: The published image MUST support both AMD64 and ARM64 processor architectures to accommodate common homelab hardware.
- **FR-009**: The `compose.yaml` MUST include inline comments explaining each configurable value so the operator understands what to change for their environment.
- **FR-010**: The image reference in `compose.yaml` MUST use a stable tag so the file does not need to be updated to receive new versions.

### Key Entities

- **Container Image**: The packaged, runnable form of the receiver service. Stored on GHCR. Tagged with `latest` and a unique build identifier. Built for multiple processor architectures.
- **Compose File**: The single deployment artifact (`compose.yaml`). Defines the service, its image reference, port mapping, volume, environment variables, health check, and restart policy.
- **Data Volume**: A named storage volume where the receiver's database is stored. Survives container replacement, restart, and upgrades.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A homelab operator with no prior knowledge of the project can go from zero to a running service in under 5 minutes, using only `compose.yaml` and a machine with Docker.
- **SC-002**: After a code change is merged, the updated image is available on GHCR within 10 minutes, with no manual steps required.
- **SC-003**: The service can be stopped and restarted, and 100% of previously stored submissions are still retrievable — no data loss.
- **SC-004**: The image can be pulled and the service started on both AMD64 and ARM64 hardware without modification to `compose.yaml`.
- **SC-005**: Pulling and starting the image from `compose.yaml` requires zero registry credentials or authentication configuration on the homelab machine.

## Assumptions

- The GitHub repository is public, or the operator has separately configured GHCR package visibility to public. Public repositories default to public package visibility.
- The homelab machine has Docker Engine installed and running. No other prerequisites are assumed.
- Port 3002 is the default. The operator can change the host-side port binding in `compose.yaml` if it conflicts with another service.
- The `latest` tag is sufficient for v1 — pinned version tags for rollback are out of scope.
- A `Dockerfile` already exists in the repository and produces a working image. This feature focuses on the publication pipeline and the standalone `compose.yaml`, not the image build process.
- The automated build triggers on merges to the `main` branch only.
