# NomNom

A self-hosted knowledge archiver. When you browse supported pages with the NomNom Tampermonkey userscript installed, their content is automatically captured and saved to a local SQLite database — no clicks required.

## Supported content types

- Reddit threads (title, post body, comments)
- GitHub repositories and discussions
- YouTube videos (transcript + metadata fetched server-side)
- Generic articles and web pages (via Readability)

## Quickstart (Docker)

**Prerequisites**: Docker with Compose plugin installed.

```bash
git clone https://github.com/<your-username>/nomnom.git
cd nomnom
docker compose up -d
curl http://localhost:3002/health
# → {"status":"ok"}
```

Data is stored in a Docker named volume (`nomnom_data`) and persists across container restarts.

## Userscript setup

1. Install [Tampermonkey](https://www.tampermonkey.net/) in your browser.
2. Install the `Universal Knowledge Ingestor (SQLite Edition)` userscript.
3. Ensure `SERVER_URL` in the userscript config points to `http://localhost:3002` (this is the default).
4. Browse to any Reddit thread, GitHub page, or YouTube video — a green toast confirms capture.

## Configuration

All settings via environment variables (defaults shown):

| Variable    | Default           | Description                                |
| ----------- | ----------------- | ------------------------------------------ |
| `PORT`      | `3002`            | Port the receiver listens on               |
| `DB_PATH`   | `/data/nomnom.db` | Path to SQLite database                    |
| `LOG_LEVEL` | `info`            | Log verbosity (`debug`, `info`, `warning`) |

Override in `docker-compose.yml` under the `environment:` key.

## Accessing your data

The SQLite database lives in the `nomnom_data` Docker volume. To inspect it directly:

```bash
# Find the volume mount path
docker volume inspect nomnom_nomnom_data

# Or open it interactively
docker run --rm -it -v nomnom_nomnom_data:/data keinos/sqlite3 sqlite3 /data/nomnom.db \
  "SELECT url, content_type, ingested_at FROM submissions ORDER BY ingested_at DESC LIMIT 20;"
```

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Copy and optionally edit env vars
cp .env.example .env

# Run with auto-reload
uvicorn nomnom.main:app --port 3002 --reload
```

## Running tests

```bash
pytest tests/
```

## Updating

```bash
docker compose pull
docker compose up -d
```
