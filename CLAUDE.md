# Nomnom Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-24

## Active Technologies
- Python 3.12 + FastAPI, Pydantic v2, sqlite3 (stdlib), youtube-transcript-api (001-nomnom-receiver)
- SQLite (WAL mode), URL as UNIQUE key (001-nomnom-receiver)
- No new entities — data volume already defined in existing compose file (002-ghcr-compose-deploy)
- Python 3.12 + FastAPI, Pydantic v2, `httpx` (for async HTTP — already available or trivially added), sqlite3 (stdlib) (001-github-repo-support)
- SQLite WAL mode — existing `submissions` table, no migration needed (001-github-repo-support)

- Python 3.12 + FastAPI, Uvicorn, Pydantic, yt-dlp, youtube-transcript-api (001-nomnom-receiver)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.12: Follow standard conventions

## Recent Changes
- 001-github-repo-support: Added Python 3.12 + FastAPI, Pydantic v2, `httpx` (for async HTTP — already available or trivially added), sqlite3 (stdlib)
- 002-ghcr-compose-deploy: Added No new entities — data volume already defined in existing compose file
- 001-nomnom-receiver: Added Python 3.12 + FastAPI, Pydantic v2, sqlite3 (stdlib), youtube-transcript-api


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
