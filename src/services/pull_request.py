"""PR CRUD, comments, approvals, merge."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from src.exceptions import handle_aws_error
from src.pagination import DEFAULT_MAX_RESULTS, MAX_RESULTS_CAP


def _paginate(max_results: int | None) -> int:
    if max_results is None:
        return DEFAULT_MAX_RESULTS
    return min(max(1, int(max_results)), MAX_RESULTS_CAP)


def _serialize_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


class PullRequestService:
    """CodeCommit pull request operations; uses auth manager for client."""

    def __init__(self, get_auth_manager: Callable[[], Any]) -> None:
        self._get_auth_manager = get_auth_manager

    def _client(self):
        return self._get_auth_manager().get_client()

    def list_pull_requests(
        self,
        repository_name: str,
        pull_request_status: str = "OPEN",
        next_token: str | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        """List pull request IDs for a repository."""
        client = self._client()
        params: dict[str, Any] = {
            "repositoryName": repository_name,
            "pullRequestStatus": pull_request_status,
        }
        if next_token:
            params["nextToken"] = next_token
        params["maxResults"] = _paginate(max_results)
        try:
            resp = client.list_pull_requests(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return {
            "pullRequestIds": resp.get("pullRequestIds") or [],
            "nextToken": resp.get("nextToken"),
        }

    def get_pull_request(self, pull_request_id: str) -> dict[str, Any]:
        """Get full pull request details."""
        client = self._client()
        try:
            resp = client.get_pull_request(pullRequestId=pull_request_id)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        pr = resp.get("pullRequest")
        if not pr:
            raise RuntimeError(f"Pull request {pull_request_id} not found")
        targets = []
        for t in pr.get("pullRequestTargets") or []:
            target: dict[str, Any] = {
                "repositoryName": t.get("repositoryName") or "",
                "sourceReference": t.get("sourceReference") or "",
                "destinationReference": t.get("destinationReference"),
                "destinationCommit": t.get("destinationCommit"),
                "sourceCommit": t.get("sourceCommit"),
                "mergeBase": t.get("mergeBase"),
            }
            mm = t.get("mergeMetadata")
            if mm:
                target["mergeMetadata"] = {
                    "isMerged": mm.get("isMerged", False),
                    "mergedBy": mm.get("mergedBy"),
                    "mergeCommitId": mm.get("mergeCommitId"),
                    "mergeOption": mm.get("mergeOption"),
                }
            targets.append(target)
        approval_rules = []
        for r in pr.get("approvalRules") or []:
            approval_rules.append({
                "approvalRuleId": r.get("approvalRuleId") or "",
                "approvalRuleName": r.get("approvalRuleName") or "",
                "approvalRuleContent": r.get("approvalRuleContent") or "",
                "ruleContentSha256": r.get("ruleContentSha256") or "",
                "lastModifiedDate": _serialize_dt(r.get("lastModifiedDate")),
                "creationDate": _serialize_dt(r.get("creationDate")),
                "lastModifiedUser": r.get("lastModifiedUser"),
            })
        return {
            "pullRequestId": pr.get("pullRequestId") or "",
            "title": pr.get("title") or "",
            "description": pr.get("description"),
            "lastActivityDate": _serialize_dt(pr.get("lastActivityDate")),
            "creationDate": _serialize_dt(pr.get("creationDate")),
            "pullRequestStatus": pr.get("pullRequestStatus"),
            "authorArn": pr.get("authorArn") or "",
            "revisionId": pr.get("revisionId") or "",
            "clientRequestToken": pr.get("clientRequestToken"),
            "targets": targets,
            "approvalRules": approval_rules,
        }

    def create_pull_request(
        self,
        repository_name: str,
        title: str,
        description: str,
        source_reference: str,
        destination_reference: str,
        client_request_token: str | None = None,
    ) -> dict[str, Any]:
        """Create a pull request."""
        client = self._client()
        params: dict[str, Any] = {
            "title": title,
            "description": description,
            "targets": [
                {
                    "repositoryName": repository_name,
                    "sourceReference": source_reference,
                    "destinationReference": destination_reference,
                },
            ],
        }
        if client_request_token:
            params["clientRequestToken"] = client_request_token
        try:
            resp = client.create_pull_request(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        pr = resp.get("pullRequest")
        if not pr:
            raise RuntimeError("Failed to create pull request")
        return self.get_pull_request(pr.get("pullRequestId", ""))

    def update_pull_request_title(self, pull_request_id: str, title: str) -> dict[str, Any]:
        """Update PR title."""
        client = self._client()
        try:
            client.update_pull_request_title(pullRequestId=pull_request_id, title=title)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return self.get_pull_request(pull_request_id)

    def update_pull_request_description(
        self, pull_request_id: str, description: str
    ) -> dict[str, Any]:
        """Update PR description."""
        client = self._client()
        try:
            client.update_pull_request_description(
                pullRequestId=pull_request_id, description=description
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return self.get_pull_request(pull_request_id)

    def close_pull_request(self, pull_request_id: str) -> dict[str, Any]:
        """Close a pull request."""
        client = self._client()
        try:
            client.update_pull_request_status(
                pullRequestId=pull_request_id, pullRequestStatus="CLOSED"
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return self.get_pull_request(pull_request_id)

    def reopen_pull_request(self, pull_request_id: str) -> dict[str, Any]:
        """Reopen a closed pull request."""
        client = self._client()
        try:
            client.update_pull_request_status(
                pullRequestId=pull_request_id, pullRequestStatus="OPEN"
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return self.get_pull_request(pull_request_id)

    def get_comments(
        self,
        pull_request_id: str,
        repository_name: str | None = None,
        before_commit_id: str | None = None,
        after_commit_id: str | None = None,
        next_token: str | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        """Get comments for a pull request; optionally filter by commit range."""
        client = self._client()
        params: dict[str, Any] = {
            "pullRequestId": pull_request_id,
            "maxResults": _paginate(max_results),
        }
        if next_token:
            params["nextToken"] = next_token
        if repository_name and before_commit_id and after_commit_id:
            params["repositoryName"] = repository_name
            params["beforeCommitId"] = before_commit_id
            params["afterCommitId"] = after_commit_id
        elif repository_name and (not before_commit_id or not after_commit_id):
            raise ValueError(
                "When repositoryName is provided, both beforeCommitId and afterCommitId are required"
            )
        try:
            resp = client.get_comments_for_pull_request(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        comments = []
        for data in resp.get("commentsForPullRequestData") or []:
            for c in data.get("comments") or []:
                loc = c.get("location")
                location = None
                if loc:
                    location = {
                        "filePath": loc.get("filePath") or "",
                        "filePosition": loc.get("filePosition"),
                        "relativeFileVersion": loc.get("relativeFileVersion"),
                    }
                comments.append({
                    "commentId": c.get("commentId") or "",
                    "content": c.get("content") or "",
                    "inReplyTo": c.get("inReplyTo"),
                    "creationDate": _serialize_dt(c.get("creationDate")),
                    "lastModifiedDate": _serialize_dt(c.get("lastModifiedDate")),
                    "authorArn": c.get("authorArn") or "",
                    "deleted": c.get("deleted", False),
                    "clientRequestToken": c.get("clientRequestToken"),
                    "pullRequestId": pull_request_id,
                    "repositoryName": repository_name,
                    "beforeCommitId": before_commit_id,
                    "afterCommitId": after_commit_id,
                    "location": location,
                })
        return {"comments": comments, "nextToken": resp.get("nextToken")}

    def post_comment(
        self,
        pull_request_id: str,
        repository_name: str,
        before_commit_id: str,
        after_commit_id: str,
        content: str,
        file_path: str | None = None,
        file_position: int | None = None,
        relative_file_version: str | None = None,
        client_request_token: str | None = None,
    ) -> dict[str, Any]:
        """Post a comment on a pull request; optional line-level location."""
        client = self._client()
        params: dict[str, Any] = {
            "pullRequestId": pull_request_id,
            "repositoryName": repository_name,
            "beforeCommitId": before_commit_id,
            "afterCommitId": after_commit_id,
            "content": content,
        }
        if client_request_token:
            params["clientRequestToken"] = client_request_token
        if file_path is not None and file_position is not None and relative_file_version:
            params["location"] = {
                "filePath": file_path,
                "filePosition": file_position,
                "relativeFileVersion": relative_file_version,
            }
        try:
            resp = client.post_comment_for_pull_request(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        c = resp.get("comment")
        if not c:
            raise RuntimeError("Failed to post comment")
        loc = c.get("location")
        location = None
        if loc:
            location = {
                "filePath": loc.get("filePath") or "",
                "filePosition": loc.get("filePosition"),
                "relativeFileVersion": loc.get("relativeFileVersion"),
            }
        return {
            "commentId": c.get("commentId") or "",
            "content": c.get("content") or "",
            "inReplyTo": c.get("inReplyTo"),
            "creationDate": _serialize_dt(c.get("creationDate")),
            "lastModifiedDate": _serialize_dt(c.get("lastModifiedDate")),
            "authorArn": c.get("authorArn") or "",
            "deleted": c.get("deleted", False),
            "clientRequestToken": c.get("clientRequestToken"),
            "pullRequestId": pull_request_id,
            "repositoryName": repository_name,
            "beforeCommitId": before_commit_id,
            "afterCommitId": after_commit_id,
            "location": location,
        }

    def update_comment(self, comment_id: str, content: str) -> dict[str, Any]:
        """Update comment content."""
        client = self._client()
        try:
            resp = client.update_comment(commentId=comment_id, content=content)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        c = resp.get("comment")
        if not c:
            raise RuntimeError("Failed to update comment")
        return _comment_to_dict(c)

    def delete_comment(self, comment_id: str) -> dict[str, Any]:
        """Delete (clear content of) a comment."""
        client = self._client()
        try:
            resp = client.delete_comment_content(commentId=comment_id)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        c = resp.get("comment")
        if not c:
            raise RuntimeError("Failed to delete comment")
        return _comment_to_dict(c)

    def reply_to_comment(
        self,
        in_reply_to: str,
        content: str,
        client_request_token: str | None = None,
    ) -> dict[str, Any]:
        """Reply to an existing comment."""
        client = self._client()
        params: dict[str, Any] = {"inReplyTo": in_reply_to, "content": content}
        if client_request_token:
            params["clientRequestToken"] = client_request_token
        try:
            resp = client.post_comment_reply(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        c = resp.get("comment")
        if not c:
            raise RuntimeError("Failed to post reply")
        return _comment_to_dict(c)

    def get_approval_states(
        self, pull_request_id: str, revision_id: str
    ) -> dict[str, Any]:
        """Get approval states for a PR revision."""
        client = self._client()
        try:
            resp = client.get_pull_request_approval_states(
                pullRequestId=pull_request_id, revisionId=revision_id
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        approvals = [
            {
                "approvalState": a.get("approvalState"),
                "userArn": a.get("userArn"),
                "revisionId": revision_id,
            }
            for a in (resp.get("approvals") or [])
        ]
        return {"approvals": approvals}

    def update_approval_state(
        self,
        pull_request_id: str,
        revision_id: str,
        approval_status: str,
    ) -> None:
        """Set approval state to APPROVE or REVOKE."""
        client = self._client()
        try:
            client.update_pull_request_approval_state(
                pullRequestId=pull_request_id,
                revisionId=revision_id,
                approvalState=approval_status,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise

    def evaluate_approval_rules(
        self, pull_request_id: str, revision_id: str
    ) -> dict[str, Any]:
        """Evaluate whether PR meets approval rules."""
        client = self._client()
        try:
            resp = client.evaluate_pull_request_approval_rules(
                pullRequestId=pull_request_id, revisionId=revision_id
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return {"evaluation": resp.get("evaluation")}

    def get_merge_conflicts(
        self,
        repository_name: str,
        destination_commit_specifier: str,
        source_commit_specifier: str,
        merge_option: str,
    ) -> dict[str, Any]:
        """Check for merge conflicts."""
        client = self._client()
        try:
            resp = client.get_merge_conflicts(
                repositoryName=repository_name,
                destinationCommitSpecifier=destination_commit_specifier,
                sourceCommitSpecifier=source_commit_specifier,
                mergeOption=merge_option,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        conflict_meta = resp.get("conflictMetadataList") or []
        return {
            "mergeable": resp.get("mergeable"),
            "destinationCommitId": resp.get("destinationCommitId"),
            "sourceCommitId": resp.get("sourceCommitId"),
            "baseCommitId": resp.get("baseCommitId"),
            "conflictMetadataList": [
                {
                    "filePath": m.get("filePath"),
                    "fileSizes": m.get("fileSizes"),
                    "objectTypes": m.get("objectTypes"),
                    "numberOfConflicts": m.get("numberOfConflicts"),
                }
                for m in conflict_meta
            ],
        }

    def get_merge_options(
        self,
        repository_name: str,
        source_commit_specifier: str,
        destination_commit_specifier: str,
    ) -> dict[str, Any]:
        """Get available merge options for a PR."""
        client = self._client()
        try:
            resp = client.get_merge_options(
                repositoryName=repository_name,
                sourceCommitSpecifier=source_commit_specifier,
                destinationCommitSpecifier=destination_commit_specifier,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return {"mergeOptions": resp.get("mergeOptions") or []}

    def merge_pull_request(
        self,
        pull_request_id: str,
        repository_name: str,
        merge_option: str,
        commit_message: str | None = None,
        author_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Merge a pull request using the given merge option."""
        client = self._client()
        base = {"pullRequestId": pull_request_id, "repositoryName": repository_name}
        try:
            if merge_option == "FAST_FORWARD_MERGE":
                resp = client.merge_pull_request_by_fast_forward(**base)
            elif merge_option == "SQUASH_MERGE":
                params = {**base}
                if commit_message is not None:
                    params["commitMessage"] = commit_message
                if author_name is not None:
                    params["authorName"] = author_name
                if email is not None:
                    params["email"] = email
                resp = client.merge_pull_request_by_squash(**params)
            elif merge_option == "THREE_WAY_MERGE":
                params = {**base}
                if commit_message is not None:
                    params["commitMessage"] = commit_message
                if author_name is not None:
                    params["authorName"] = author_name
                if email is not None:
                    params["email"] = email
                resp = client.merge_pull_request_by_three_way(**params)
            else:
                raise ValueError(f"Unsupported merge option: {merge_option}")
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        pr = resp.get("pullRequest")
        result: dict[str, Any] = {}
        if pr:
            result["pullRequest"] = self.get_pull_request(pr.get("pullRequestId", ""))
        if resp.get("commitId"):
            result["commitId"] = resp.get("commitId")
        return result


def _comment_to_dict(c: dict) -> dict[str, Any]:
    return {
        "commentId": c.get("commentId") or "",
        "content": c.get("content") or "",
        "inReplyTo": c.get("inReplyTo"),
        "creationDate": _serialize_dt(c.get("creationDate")),
        "lastModifiedDate": _serialize_dt(c.get("lastModifiedDate")),
        "authorArn": c.get("authorArn") or "",
        "deleted": c.get("deleted", False),
        "clientRequestToken": c.get("clientRequestToken"),
    }


_pull_request_service: PullRequestService | None = None


def get_pull_request_service() -> PullRequestService:
    from src.auth import get_auth_manager
    global _pull_request_service
    if _pull_request_service is None:
        _pull_request_service = PullRequestService(get_auth_manager)
    return _pull_request_service
