"""Tests for RepositoryService with mocked CodeCommit client."""

import pytest
from botocore.exceptions import ClientError

from src.services.repository import RepositoryService


def test_list_repos_returns_items_and_next_token(mock_codecommit_client, auth_manager_with_mock_client):
    """list_repos returns parsed items and nextToken."""
    mock_codecommit_client.list_repositories.return_value = {
        "repositories": [
            {
                "repositoryName": "my-repo",
                "repositoryId": "repo-id-123",
                "repositoryDescription": "A repo",
            }
        ],
        "nextToken": "next",
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.list_repos()
    assert result["items"]
    assert result["items"][0]["repositoryName"] == "my-repo"
    assert result["nextToken"] == "next"


def test_list_repos_filters_by_search_term(mock_codecommit_client, auth_manager_with_mock_client):
    """list_repos filters items by search_term when provided."""
    mock_codecommit_client.list_repositories.return_value = {
        "repositories": [
            {"repositoryName": "foo-repo", "repositoryDescription": "bar"},
            {"repositoryName": "baz", "repositoryDescription": "qux"},
        ],
        "nextToken": None,
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.list_repos(search_term="foo")
    assert len(result["items"]) == 1
    assert result["items"][0]["repositoryName"] == "foo-repo"


def test_get_repo_returns_metadata(mock_codecommit_client, auth_manager_with_mock_client):
    """get_repo returns repository metadata."""
    mock_codecommit_client.get_repository.return_value = {
        "repositoryMetadata": {
            "repositoryName": "test-repo",
            "repositoryId": "id-1",
            "defaultBranch": "main",
        }
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.get_repo("test-repo")
    assert result["repositoryName"] == "test-repo"
    assert result["defaultBranch"] == "main"


def test_get_repo_raises_on_client_error(mock_codecommit_client, auth_manager_with_mock_client):
    """get_repo raises RuntimeError with message on ClientError."""
    mock_codecommit_client.get_repository.side_effect = ClientError(
        {"Error": {"Code": "RepositoryDoesNotExistException", "Message": "Not found"}},
        "GetRepository",
    )
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    with pytest.raises(RuntimeError, match="Not found|RepositoryDoesNotExist"):
        svc.get_repo("nonexistent")


def test_list_branches_returns_branch_list(mock_codecommit_client, auth_manager_with_mock_client):
    """list_branches returns list of branches with commitIds."""
    mock_codecommit_client.list_branches.return_value = {
        "branches": ["main", "develop"],
        "nextToken": None,
    }
    mock_codecommit_client.get_branch.side_effect = [
        {"branch": {"branchName": "main", "commitId": "c1"}},
        {"branch": {"branchName": "develop", "commitId": "c2"}},
    ]
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.list_branches("my-repo")
    assert len(result["items"]) == 2
    assert result["items"][0]["branchName"] == "main"
    assert result["items"][0]["commitId"] == "c1"


def test_get_file_returns_content(mock_codecommit_client, auth_manager_with_mock_client):
    """get_file returns file content and blobId."""
    mock_codecommit_client.get_file.return_value = {
        "filePath": "src/foo.py",
        "fileMode": "NORMAL",
        "fileSize": 10,
        "blobId": "blob-123",
        "fileContent": b"print(1)",
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.get_file("repo", "main", "src/foo.py")
    assert result["content"] == "print(1)"
    assert result["blobId"] == "blob-123"


def test_diff_get_returns_file_differences(mock_codecommit_client, auth_manager_with_mock_client):
    """get_differences returns list of changed files."""
    mock_codecommit_client.get_differences.return_value = {
        "differences": [
            {
                "beforeBlob": {"path": "old.py", "blobId": "b1"},
                "afterBlob": {"path": "new.py", "blobId": "b2"},
                "changeType": "M",
            }
        ],
        "nextToken": None,
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = RepositoryService(get_auth)
    result = svc.get_differences("repo", "before", "after")
    assert len(result["items"]) == 1
    assert result["items"][0]["changeType"] == "M"
    assert result["items"][0]["afterBlob"]["path"] == "new.py"
