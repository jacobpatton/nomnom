from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nomnom.services.github_service import GithubService


@pytest.fixture
def svc():
    return GithubService()


# T008: normalize_url basic cases
def test_normalize_url_bare_repo(svc):
    result = svc.normalize_url("https://github.com/owner/repo")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


def test_normalize_url_strips_subpath(svc):
    result = svc.normalize_url("https://github.com/owner/repo/blob/main/file.py")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


def test_normalize_url_strips_fragment(svc):
    result = svc.normalize_url("https://github.com/owner/repo#readme")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


# T008: fetch_readme mocked
@pytest.mark.asyncio
async def test_fetch_readme_200(svc):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "# Hello"

    with patch("nomnom.services.github_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await svc.fetch_readme("owner", "repo")
    assert result == "# Hello"


@pytest.mark.asyncio
async def test_fetch_readme_404(svc):
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("nomnom.services.github_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await svc.fetch_readme("owner", "repo")
    assert result == ""


@pytest.mark.asyncio
async def test_fetch_readme_timeout(svc):
    import httpx

    with patch("nomnom.services.github_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await svc.fetch_readme("owner", "repo")
    assert result == ""


# T014: normalize_url rejection cases
def test_normalize_url_profile_url(svc):
    result = svc.normalize_url("https://github.com/owner")
    assert result is None


def test_normalize_url_blocked_prefix_orgs(svc):
    result = svc.normalize_url("https://github.com/orgs/myorg/teams")
    assert result is None


def test_normalize_url_blocked_prefix_settings(svc):
    result = svc.normalize_url("https://github.com/settings/profile")
    assert result is None


# T010: deep link normalization (US2)
def test_normalize_url_deep_blob(svc):
    result = svc.normalize_url("https://github.com/owner/repo/blob/main/file.py")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


def test_normalize_url_issues(svc):
    result = svc.normalize_url("https://github.com/owner/repo/issues/42")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


def test_normalize_url_tree(svc):
    result = svc.normalize_url("https://github.com/owner/repo/tree/feature-branch")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


# T012: fragment stripping (US3)
def test_normalize_url_fragment_readme(svc):
    result = svc.normalize_url("https://github.com/owner/repo#readme")
    assert result == ("https://github.com/owner/repo", "owner", "repo")


def test_normalize_url_fragment_installation(svc):
    result = svc.normalize_url("https://github.com/owner/repo#installation")
    assert result == ("https://github.com/owner/repo", "owner", "repo")
