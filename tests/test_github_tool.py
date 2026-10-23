"""Unit tests for GitHub Scraper and Reader Tool."""

import asyncio
import pytest
from src.tools.github_tool import parse_github_url, read_github_repo, read_github_file
from src.workflows.task_router import TaskRouter


def test_parse_github_url():
    # 1. Standard repo URL
    res1 = parse_github_url("https://github.com/octocat/Hello-World")
    assert res1 is not None
    assert res1["owner"] == "octocat"
    assert res1["repo"] == "Hello-World"
    assert res1["branch"] == "main"

    # 2. File blob URL
    res2 = parse_github_url("https://github.com/psf/requests/blob/main/src/requests/api.py")
    assert res2 is not None
    assert res2["owner"] == "psf"
    assert res2["repo"] == "requests"
    assert res2["branch"] == "main"
    assert res2["path"] == "src/requests/api.py"

    # 3. Invalid URL
    res3 = parse_github_url("https://google.com/search")
    assert res3 is None


def test_read_github_repo_public():
    # Test reading a lightweight public repo
    res = asyncio.run(read_github_repo("https://github.com/octocat/Hello-World"))
    assert "octocat/Hello-World" in res
    assert "Stars:" in res or "Deskripsi:" in res


def test_read_github_file_public():
    # Test reading a public file
    res = asyncio.run(read_github_file("https://github.com/octocat/Hello-World/blob/master/README"))
    assert "Hello-World" in res or "GitHub File:" in res


def test_task_router_routes_github():
    router = TaskRouter()
    mock_tools = [
        {"name": "read_github_repo", "description": "Read GitHub repository"},
        {"name": "read_github_file", "description": "Read GitHub file"},
        {"name": "search_web", "description": "Search web"}
    ]

    selected, scores = router.route_tools("tolong baca github https://github.com/facebook/react", mock_tools)
    selected_names = [t["name"] for t in selected]
    assert "read_github_repo" in selected_names
