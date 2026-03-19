"""Tests for PullRequestService with mocked CodeCommit client."""

import pytest
from botocore.exceptions import ClientError

from src.services.pull_request import PullRequestService


def test_list_pull_requests_returns_ids(mock_codecommit_client, auth_manager_with_mock_client):
    """list_pull_requests returns pullRequestIds and nextToken."""
    mock_codecommit_client.list_pull_requests.return_value = {
        "pullRequestIds": ["pr-1", "pr-2"],
        "nextToken": None,
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    result = svc.list_pull_requests("my-repo", pull_request_status="OPEN")
    assert result["pullRequestIds"] == ["pr-1", "pr-2"]


def test_get_pull_request_returns_details(mock_codecommit_client, auth_manager_with_mock_client):
    """get_pull_request returns full PR with targets and mergeBase."""
    mock_codecommit_client.get_pull_request.return_value = {
        "pullRequest": {
            "pullRequestId": "pr-123",
            "title": "Fix bug",
            "description": "Description",
            "pullRequestStatus": "OPEN",
            "authorArn": "arn:aws:iam::123:user/me",
            "revisionId": "rev-1",
            "pullRequestTargets": [
                {
                    "repositoryName": "repo",
                    "sourceReference": "refs/heads/feature",
                    "destinationReference": "refs/heads/main",
                    "sourceCommit": "src-commit",
                    "destinationCommit": "dest-commit",
                    "mergeBase": "merge-base-commit",
                }
            ],
        }
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    result = svc.get_pull_request("pr-123")
    assert result["pullRequestId"] == "pr-123"
    assert result["title"] == "Fix bug"
    assert len(result["targets"]) == 1
    assert result["targets"][0]["mergeBase"] == "merge-base-commit"


def test_get_pull_request_raises_when_not_found(mock_codecommit_client, auth_manager_with_mock_client):
    """get_pull_request raises RuntimeError when PR not found."""
    mock_codecommit_client.get_pull_request.return_value = {}
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    with pytest.raises(RuntimeError, match="not found"):
        svc.get_pull_request("pr-nonexistent")


def test_create_pull_request_returns_pr_details(mock_codecommit_client, auth_manager_with_mock_client):
    """create_pull_request returns full PR details (calls get_pull_request after create)."""
    mock_codecommit_client.create_pull_request.return_value = {
        "pullRequest": {
            "pullRequestId": "pr-new",
            "title": "New PR",
        }
    }
    mock_codecommit_client.get_pull_request.return_value = {
        "pullRequest": {
            "pullRequestId": "pr-new",
            "title": "New PR",
            "description": "Body",
            "pullRequestStatus": "OPEN",
            "authorArn": "arn:aws:iam::123:user/me",
            "revisionId": "rev-1",
            "pullRequestTargets": [],
        }
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    result = svc.create_pull_request(
        "repo",
        title="New PR",
        description="Body",
        source_reference="refs/heads/feature",
        destination_reference="refs/heads/main",
    )
    assert result["pullRequestId"] == "pr-new"
    assert result["title"] == "New PR"


def test_post_comment_calls_api(mock_codecommit_client, auth_manager_with_mock_client):
    """post_comment calls API with required and optional params."""
    mock_codecommit_client.post_comment_for_pull_request.return_value = {
        "comment": {"commentId": "comment-1", "content": "Hello"},
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    result = svc.post_comment(
        pull_request_id="pr-1",
        repository_name="repo",
        before_commit_id="before",
        after_commit_id="after",
        content="Hello",
        file_path="src/foo.py",
        file_position=10,
        relative_file_version="AFTER",
    )
    assert result["commentId"] == "comment-1"
    mock_codecommit_client.post_comment_for_pull_request.assert_called_once()


def test_get_approval_states_returns_approvals(mock_codecommit_client, auth_manager_with_mock_client):
    """get_approval_states returns approvals with approvalState and userArn."""
    mock_codecommit_client.get_pull_request_approval_states.return_value = {
        "approvals": [
            {
                "approvalState": "APPROVED",
                "userArn": "arn:aws:iam::123:user/approver",
            }
        ],
    }
    get_auth = lambda: auth_manager_with_mock_client
    svc = PullRequestService(get_auth)
    result = svc.get_approval_states("pr-1", revision_id="rev-1")
    assert len(result["approvals"]) == 1
    assert result["approvals"][0]["approvalState"] == "APPROVED"
