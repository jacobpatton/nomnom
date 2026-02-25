# Quickstart: NomNom Receiver — Homelab Deployment

**Time to deploy**: ~5 minutes
**Requirements**: Docker Engine installed on the target machine

---

## 1. Prerequisites

Install Docker Engine on the homelab machine:

- **Debian/Ubuntu**: https://docs.docker.com/engine/install/ubuntu/
- **Raspberry Pi / ARM**: https://docs.docker.com/engine/install/raspberry-pi-os/

Verify it's running:

```bash
docker version
```

---

## 2. One-Time: Make the GHCR Image Public

This step is required so you can pull the image without credentials. Do this once after the first GitHub Actions build completes.

1. Go to: `https://github.com/users/jacobpatton/packages/container/nomnom-receiver/settings`
2. Scroll to **Danger Zone** → **Change package visibility**
3. Set to **Public**
4. Confirm

After this, anyone with `docker-compose.yml` can pull the image without a GitHub account or token.

---

## 3. Deploy

Copy `docker-compose.yml` to your homelab machine (or paste its contents into a new file). Then:

```bash
docker compose up -d
```

Docker will pull the image from GHCR and start the service in the background.

---

## 4. Verify

```bash
# Check the service is healthy
curl http://localhost:3002/health
# Expected: {"status":"ok"}

# Check container status
docker compose ps
```

The service is ready when the health check shows `healthy`.

---

## 5. Upgrade

When a new version is published:

```bash
docker compose pull
docker compose up -d
```

This replaces the running container with the new image. Your data is preserved in the named volume.

---

## 6. Access the Database

The SQLite database is stored in a Docker-managed named volume. To find the file on the host:

```bash
docker volume inspect nomnom_data
# Look for the "Mountpoint" field — typically /var/lib/docker/volumes/nomnom_data/_data/nomnom.db
```

Query the database directly:

```bash
# Find the mount path
DBPATH=$(docker volume inspect nomnom_data --format '{{ .Mountpoint }}')/nomnom.db

# List recent entries
sqlite3 "$DBPATH" "SELECT url, title, content_type, ingested_at FROM submissions ORDER BY ingested_at DESC LIMIT 10;"
```

---

## 7. Stop / Remove

```bash
# Stop the service (data preserved)
docker compose down

# Stop and remove the data volume (DELETES ALL DATA)
docker compose down -v
```

---

## Configuration Reference

All configuration is via environment variables in `docker-compose.yml`:

| Variable    | Default           | Description                                        |
| ----------- | ----------------- | -------------------------------------------------- |
| `DB_PATH`   | `/data/nomnom.db` | Path inside the container to the SQLite database   |
| `LOG_LEVEL` | `info`            | Log verbosity: `debug`, `info`, `warning`, `error` |

To change the host port (if 3002 is taken), edit the `ports` line:

```yaml
ports:
  - "3003:3002" # Maps host port 3003 → container port 3002
```

---

## Backup

```bash
# Create a backup archive of the database
docker run --rm \
  -v nomnom_data:/data \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/nomnom-backup-$(date +%Y%m%d).tar.gz /data
```
