"""Integration tests for GitHub repository ingestion."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from nomnom.db.connection import run_migrations
from nomnom.main import create_app
from nomnom.repositories.submission_repository import SubmissionRepository
from nomnom.services.ingestion_service import IngestionService


def _make_app(db_path: str):
    """Create a test app wired to the given DB path."""
    app = create_app()

    @app.on_event("startup")
    async def _setup():
        run_migrations(db_path)
        app.state.repository = SubmissionRepository(db_path)
        app.state.ingestion_service = IngestionService(app.state.repository)

    return app


def _count_records(db_path: str, url: str) -> int:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM submissions WHERE url = ?", (url,)).fetchone()
    conn.close()
    return row[0]


def _get_record(db_path: str, url: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM submissions WHERE url = ?", (url,)).fetchone()
    conn.close()
    return dict(row) if row else None


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    run_migrations(path)
    return path


@pytest.fixture
def client(db_path):
    app = create_app()
    # Override lifespan state directly
    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.repository = SubmissionRepository(db_path)
        app.state.ingestion_service = IngestionService(app.state.repository)
        c.app_state_db_path = db_path
        yield c


def _mock_readme(content: str = "# README"):
    """Patch GithubService.fetch_readme to return a fixed string."""
    mock = AsyncMock(return_value=content)
    return patch("nomnom.services.github_service.GithubService.fetch_readme", mock)


# T009: POST bare repo URL → saved, record has correct fields
def test_save_github_repo(client):
    db = client.app_state_db_path
    with _mock_readme("# My Readme"):
        response = client.post("/", json={"url": "https://github.com/owner/repo", "domain": "github.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"

    record = _get_record(db, "https://github.com/owner/repo")
    assert record is not None
    assert record["url"] == "https://github.com/owner/repo"
    assert record["title"] == "owner/repo"
    assert record["content_type"] == "github_repo"
    import json
    metadata = json.loads(record["metadata"])
    assert metadata == {"owner": "owner", "repo": "repo"}


# T009: POST same URL twice → second is skipped, count unchanged
def test_duplicate_github_repo(client):
    db = client.app_state_db_path
    with _mock_readme():
        client.post("/", json={"url": "https://github.com/owner/repo", "domain": "github.com"})
        response = client.post("/", json={"url": "https://github.com/owner/repo", "domain": "github.com"})
    assert response.json()["status"] == "skipped"
    assert _count_records(db, "https://github.com/owner/repo") == 1


# T015: profile URL → skipped, no record
def test_profile_url_skipped(client):
    db = client.app_state_db_path
    response = client.post("/", json={"url": "https://github.com/owner", "domain": "github.com"})
    assert response.json()["status"] == "skipped"
    assert _count_records(db, "https://github.com/owner") == 0


# T015: orgs URL → skipped, no record
def test_orgs_url_skipped(client):
    db = client.app_state_db_path
    response = client.post("/", json={"url": "https://github.com/orgs/myorg", "domain": "github.com"})
    assert response.json()["status"] == "skipped"
    assert _count_records(db, "https://github.com/orgs/myorg") == 0


# T011: deep link URL → saved, stored url is canonical (sub-path stripped)
def test_deep_link_blob_normalized(client):
    db = client.app_state_db_path
    with _mock_readme():
        response = client.post("/", json={
            "url": "https://github.com/owner/repo/blob/main/somefile.py",
            "domain": "github.com",
        })
    assert response.json()["status"] == "saved"
    assert _get_record(db, "https://github.com/owner/repo") is not None
    assert _count_records(db, "https://github.com/owner/repo/blob/main/somefile.py") == 0


# T011: issue URL → saved, stored url is canonical
def test_deep_link_issue_normalized(client):
    db = client.app_state_db_path
    with _mock_readme():
        response = client.post("/", json={
            "url": "https://github.com/owner2/repo2/issues/42",
            "domain": "github.com",
        })
    assert response.json()["status"] == "saved"
    assert _get_record(db, "https://github.com/owner2/repo2") is not None


# T013: fragment URL after base → skipped, still only 1 record
def test_fragment_dedup(client):
    db = client.app_state_db_path
    with _mock_readme():
        client.post("/", json={"url": "https://github.com/owner/repo", "domain": "github.com"})
        response = client.post("/", json={"url": "https://github.com/owner/repo#readme", "domain": "github.com"})
    assert response.json()["status"] == "skipped"
    assert _count_records(db, "https://github.com/owner/repo") == 1


# T013: fragment URL fresh → saved, stored url has no fragment
def test_fragment_url_saved_without_fragment(client):
    db = client.app_state_db_path
    with _mock_readme():
        response = client.post("/", json={
            "url": "https://github.com/owner3/repo3#installation",
            "domain": "github.com",
        })
    assert response.json()["status"] == "saved"
    assert _get_record(db, "https://github.com/owner3/repo3") is not None
    assert _count_records(db, "https://github.com/owner3/repo3#installation") == 0


# T016: README fetch returns 404 → saved with empty content_markdown
def test_readme_fetch_failure_still_saves(client):
    db = client.app_state_db_path
    with patch("nomnom.services.github_service.GithubService.fetch_readme", AsyncMock(return_value="")):
        response = client.post("/", json={"url": "https://github.com/owner4/repo4", "domain": "github.com"})
    assert response.json()["status"] == "saved"
    record = _get_record(db, "https://github.com/owner4/repo4")
    assert record is not None
    assert record["content_markdown"] == ""
