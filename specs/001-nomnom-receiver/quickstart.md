# Quickstart: NomNom Receiver

**Feature**: 001-nomnom-receiver | **Date**: 2026-02-24

---

## Prerequisites

- Docker + Docker Compose v2 installed
- The NomNom Tampermonkey userscript installed in your browser

---

## Run with Docker Compose (recommended)

```bash
# Clone the repo
git clone https://github.com/<your-username>/nomnom.git
cd nomnom

# Start the receiver
docker compose up -d

# Verify it's running
curl http://localhost:3002/health
# → { "status": "ok" }
```

Browse to any supported page (Reddit thread, GitHub repo, YouTube video) — the userscript will automatically submit the content and show a green toast on success.

---

## Run locally (development)

```bash
# Requires Python 3.12+
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the server
python -m uvicorn nomnom.main:app --host 0.0.0.0 --port 3002 --reload
```

---

## Configuration

All configuration via environment variables (with defaults):

| Variable    | Default           | Description                  |
| ----------- | ----------------- | ---------------------------- |
| `PORT`      | `3002`            | Port the receiver listens on |
| `DB_PATH`   | `/data/nomnom.db` | Path to SQLite database file |
| `LOG_LEVEL` | `info`            | Uvicorn log level            |

In Docker Compose, the SQLite database is persisted in a named volume (`nomnom_data`). To find it:

```bash
docker volume inspect nomnom_nomnom_data
```

---

## Updating

```bash
docker compose pull
docker compose up -d
```

Data persists in the named volume across updates.

---

## Running Tests

```bash
# From repo root with virtualenv active
pytest tests/
```
