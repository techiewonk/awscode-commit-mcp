"""Tool list and inputSchema; async call_tool delegation to services."""

import asyncio
import json

from mcp.types import Tool

# Diff analyzer size limits (per ref CLAUDE-AI-OPTIMIZATION)
MAX_DIFF_SIZE = 100_000
MAX_BATCH_RESPONSE_SIZE = 200_000
MAX_FILES_PER_BATCH = 5


def get_tools() -> list[Tool]:
    """Return all MCP tools (scaffold, credential, repository, PR, diff)."""
    return [
        Tool(
            name="ping",
            description="Test tool: returns pong and confirms server is running.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Optional message to echo back"},
                },
            },
        ),
        Tool(
            name="aws_creds_refresh",
            description="Manually refreshes AWS credentials. Use when: credentials expired, authentication errors, switched AWS configuration, or testing credential validity. Reloads from configured source (profile/environment).",
            input_schema={"type": "object", "properties": {}},
        ),
        Tool(
            name="aws_profile_switch",
            description="Switches to a different AWS profile for different accounts/roles. Use when: need different AWS account, switch environments (dev/prod), or use different IAM roles.",
            input_schema={
                "type": "object",
                "properties": {
                    "profileName": {
                        "type": "string",
                        "description": "AWS profile name from ~/.aws/credentials (e.g. default, production, dev)",
                    },
                },
                "required": ["profileName"],
            },
        ),
        Tool(
            name="aws_profiles_list",
            description="Lists all available AWS profiles configured in ~/.aws/credentials. Use when: user wants to switch profiles, check available accounts, or troubleshoot authentication.",
            input_schema={"type": "object", "properties": {}},
        ),
        Tool(
            name="aws_creds_status",
            description="Shows current AWS credentials status including validity, expiration, and access key info. Use when: troubleshooting auth issues, checking if credentials expired, or verifying AWS account.",
            input_schema={"type": "object", "properties": {}},
        ),
        # Repository tools
        Tool(
            name="repos_list",
            description="Lists all AWS CodeCommit repositories you have access to. Returns repository metadata including name, ID, description, default branch, creation date, and clone URLs. Supports search filtering and pagination.",
            input_schema={
                "type": "object",
                "properties": {
                    "searchTerm": {"type": "string", "description": "Filter repositories by name or description (case-insensitive substring match)."},
                    "nextToken": {"type": "string", "description": "Pagination token from previous response."},
                    "maxResults": {"type": "number", "description": "Number of repositories to return (1-1000). Default 100."},
                    "sortBy": {"type": "string", "description": "Sort by repositoryName or lastModifiedDate."},
                    "order": {"type": "string", "enum": ["ascending", "descending"], "description": "Sort order."},
                },
            },
        ),
        Tool(
            name="repo_get",
            description="Gets detailed information about a specific repository including metadata, default branch, clone URLs, creation date, and description.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Exact name of the AWS CodeCommit repository."},
                },
                "required": ["repositoryName"],
            },
        ),
        Tool(
            name="branches_list",
            description="Lists all branches in a repository with their latest commit IDs. Essential for understanding branch topology and selecting branches for comparisons and PRs.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository name to list branches from."},
                    "nextToken": {"type": "string", "description": "Pagination token for additional branches."},
                },
                "required": ["repositoryName"],
            },
        ),
        Tool(
            name="branch_get",
            description="Gets detailed information about a specific branch including its latest commit ID and commit details.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository containing the branch."},
                    "branchName": {"type": "string", "description": "Exact branch name (e.g. main, develop). Case-sensitive."},
                },
                "required": ["repositoryName", "branchName"],
            },
        ),
        Tool(
            name="file_get",
            description="Retrieves file content at a given commit/branch. Returns full file content with blobId. For diff-only analysis use file_diff_analyze.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository containing the file."},
                    "commitSpecifier": {"type": "string", "description": "Branch name or commit ID."},
                    "filePath": {"type": "string", "description": "Full path to file from repository root (e.g. src/main.py)."},
                },
                "required": ["repositoryName", "commitSpecifier", "filePath"],
            },
        ),
        Tool(
            name="folder_get",
            description="Lists all files and subdirectories in a folder at a specific commit/branch. Use to explore repository structure.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository to explore."},
                    "commitSpecifier": {"type": "string", "description": "Branch name or commit ID."},
                    "folderPath": {"type": "string", "description": "Path to folder from repository root. Use empty string for root."},
                },
                "required": ["repositoryName", "commitSpecifier", "folderPath"],
            },
        ),
        Tool(
            name="code_search",
            description="Two modes: 1) tree — repository structure in formatted tree view. 2) search — search for patterns within a specific file (regex, literal, function, class, import, variable).",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository to search in."},
                    "commitSpecifier": {"type": "string", "description": "Branch name or commit ID."},
                    "mode": {"type": "string", "enum": ["search", "tree"], "description": "Operation mode: search or tree."},
                    "filePath": {"type": "string", "description": "Required for search mode. Exact file path to search within."},
                    "searchPatterns": {
                        "type": "array",
                        "description": "Required for search mode. Array of {pattern, type} where type is regex|literal|function|class|import|variable.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pattern": {"type": "string"},
                                "type": {"type": "string", "enum": ["regex", "literal", "function", "class", "import", "variable"]},
                                "caseSensitive": {"type": "boolean"},
                            },
                            "required": ["pattern", "type"],
                        },
                    },
                    "treePath": {"type": "string", "description": "For tree mode: root path to list (default repository root)."},
                    "treeDepth": {"type": "number", "description": "For tree mode: maximum depth (default 10)."},
                    "maxResults": {"type": "number", "description": "For search mode: max results per pattern (default 50)."},
                    "includeContext": {"type": "boolean", "description": "For search mode: include surrounding lines (default true)."},
                    "contextLines": {"type": "number", "description": "For search mode: context lines before/after (default 3)."},
                },
                "required": ["repositoryName", "commitSpecifier", "mode"],
            },
        ),
        Tool(
            name="commit_get",
            description="Gets comprehensive details about a specific commit including message, author, committer, timestamp, parent commits, and tree ID.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository containing the commit."},
                    "commitId": {"type": "string", "description": "Full commit SHA ID (40-character hex)."},
                },
                "required": ["repositoryName", "commitId"],
            },
        ),
        Tool(
            name="diff_get",
            description="Gets high-level file differences between commits/branches showing which files changed (A/D/M) with paths and blob IDs. THE MOST CRITICAL tool for code review. After this, use batch_diff_analyze to see what changed in multiple files (git diff only). If diffs don't provide enough context, use file_get without beforeCommitId for full file content, or code_search to find related patterns. For PR reviews use mergeBase as beforeCommitSpecifier, not destinationCommit.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository to compare."},
                    "beforeCommitSpecifier": {"type": "string", "description": "Base commit/branch (comparing FROM). For PR use mergeBase."},
                    "afterCommitSpecifier": {"type": "string", "description": "Compare commit/branch (comparing TO). For PR use sourceCommit."},
                    "beforePath": {"type": "string", "description": "Optional: filter to path in before commit."},
                    "afterPath": {"type": "string", "description": "Optional: filter to path in after commit."},
                    "nextToken": {"type": "string", "description": "Pagination token for large changesets."},
                    "maxResults": {"type": "number", "description": "Max number of differences to return."},
                },
                "required": ["repositoryName", "beforeCommitSpecifier", "afterCommitSpecifier"],
            },
        ),
        Tool(
            name="file_diff_analyze",
            description="Returns ONLY git diff format for a single file - no file content. Shows what changed with precise line numbers. For deleted files returns deletion confirmation only. When diff is not enough context, use file_get WITHOUT beforeCommitId for full file content or code_search for patterns. For new files consider file_get if diff alone doesn't provide enough context.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository containing the file."},
                    "beforeCommitId": {"type": "string", "description": "Commit ID to compare from (use mergeBase from PR for accurate line mapping)."},
                    "afterCommitId": {"type": "string", "description": "Commit ID to compare to (use sourceCommit from PR)."},
                    "filePath": {"type": "string", "description": "Path to the specific file to analyze."},
                    "changeType": {"type": "string", "enum": ["A", "D", "M"], "description": "Change type from diff_get: A=Added, D=Deleted, M=Modified."},
                },
                "required": ["repositoryName", "beforeCommitId", "afterCommitId", "filePath", "changeType"],
            },
        ),
        Tool(
            name="batch_diff_analyze",
            description="Returns ONLY git diff format for multiple files (3-5 max) - no file content. When diffs lack context for proper review use file_get without beforeCommitId for full content or code_search for related patterns. Provides strategic guidance on which files may need additional context.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository name."},
                    "beforeCommitId": {"type": "string", "description": "Base commit ID (use mergeBase from PR targets for accurate analysis)."},
                    "afterCommitId": {"type": "string", "description": "Compare commit ID (use sourceCommit from PR targets)."},
                    "fileDifferences": {
                        "type": "array",
                        "description": "Array of file differences from diff_get response.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "changeType": {"type": "string", "enum": ["A", "D", "M"]},
                                "beforeBlob": {"type": "object", "properties": {"path": {"type": "string"}, "blobId": {"type": "string"}}},
                                "afterBlob": {"type": "object", "properties": {"path": {"type": "string"}, "blobId": {"type": "string"}}},
                            },
                        },
                    },
                },
                "required": ["repositoryName", "beforeCommitId", "afterCommitId", "fileDifferences"],
            },
        ),
        # Pull request tools
        Tool(
            name="prs_list",
            description="Lists pull requests in a repository by status (OPEN/CLOSED). Use when starting a review session, user asks about PRs, or finding a specific PR. Returns PR IDs; always follow with pr_get for each PR you need to analyze.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string", "description": "Repository to list PRs from."},
                    "pullRequestStatus": {"type": "string", "enum": ["OPEN", "CLOSED"], "description": "OPEN for active PRs, CLOSED for completed/abandoned."},
                    "nextToken": {"type": "string", "description": "Pagination token."},
                    "maxResults": {"type": "number", "description": "Max PRs to return."},
                },
                "required": ["repositoryName"],
            },
        ),
        Tool(
            name="pr_get",
            description="Gets complete PR details with critical commit IDs needed for accurate analysis. ESSENTIAL after prs_list. Provides mergeBase (use for beforeCommitId in diff analysis) and sourceCommit/destinationCommit from targets. Extract these for diff_get → batch_diff_analyze → targeted file analysis. Foundation for all subsequent PR analysis and accurate line mapping.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string", "description": "PR ID from prs_list."},
                },
                "required": ["pullRequestId"],
            },
        ),
        Tool(
            name="pr_create",
            description="Creates a new pull request from source branch to destination branch.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "sourceReference": {"type": "string", "description": "Source branch with changes."},
                    "destinationReference": {"type": "string", "description": "Target branch to merge into."},
                    "clientRequestToken": {"type": "string"},
                },
                "required": ["repositoryName", "title", "sourceReference", "destinationReference"],
            },
        ),
        Tool(
            name="pr_update_title",
            description="Updates pull request title.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["pullRequestId", "title"],
            },
        ),
        Tool(
            name="pr_update_desc",
            description="Updates pull request description.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["pullRequestId", "description"],
            },
        ),
        Tool(
            name="pr_close",
            description="Closes a pull request without merging.",
            input_schema={
                "type": "object",
                "properties": {"pullRequestId": {"type": "string"}},
                "required": ["pullRequestId"],
            },
        ),
        Tool(
            name="pr_reopen",
            description="Reopens a previously closed pull request.",
            input_schema={
                "type": "object",
                "properties": {"pullRequestId": {"type": "string"}},
                "required": ["pullRequestId"],
            },
        ),
        Tool(
            name="comments_get",
            description="Gets all comments on a pull request including general and line-specific comments. CRITICAL for PR review workflow. Use when starting a review to see existing feedback or checking if issues were already raised. Simple: pass only pullRequestId for all comments. Filtered: pass pullRequestId + repositoryName + beforeCommitId + afterCommitId together.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "repositoryName": {"type": "string"},
                    "beforeCommitId": {"type": "string"},
                    "afterCommitId": {"type": "string"},
                    "nextToken": {"type": "string"},
                    "maxResults": {"type": "number"},
                },
                "required": ["pullRequestId"],
            },
        ),
        Tool(
            name="comment_post",
            description="Posts a comment on a pull request - either general PR comment or line-specific code comment. Use for PR feedback, questions about changes, or suggesting improvements. Provide filePath, filePosition, and relativeFileVersion for line-level comments (use mergeBase as beforeCommitId for accuracy).",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "repositoryName": {"type": "string"},
                    "beforeCommitId": {"type": "string"},
                    "afterCommitId": {"type": "string"},
                    "content": {"type": "string"},
                    "filePath": {"type": "string"},
                    "filePosition": {"type": "number"},
                    "relativeFileVersion": {"type": "string", "enum": ["BEFORE", "AFTER"]},
                    "clientRequestToken": {"type": "string"},
                },
                "required": ["pullRequestId", "repositoryName", "beforeCommitId", "afterCommitId", "content"],
            },
        ),
        Tool(
            name="comment_update",
            description="Updates existing comment content.",
            input_schema={
                "type": "object",
                "properties": {
                    "commentId": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["commentId", "content"],
            },
        ),
        Tool(
            name="comment_delete",
            description="Deletes (clears content of) a comment.",
            input_schema={
                "type": "object",
                "properties": {"commentId": {"type": "string"}},
                "required": ["commentId"],
            },
        ),
        Tool(
            name="comment_reply",
            description="Replies to an existing comment.",
            input_schema={
                "type": "object",
                "properties": {
                    "inReplyTo": {"type": "string", "description": "Comment ID to reply to."},
                    "content": {"type": "string"},
                    "clientRequestToken": {"type": "string"},
                },
                "required": ["inReplyTo", "content"],
            },
        ),
        Tool(
            name="approvals_get",
            description="Gets current approval states for a PR revision.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "revisionId": {"type": "string"},
                },
                "required": ["pullRequestId", "revisionId"],
            },
        ),
        Tool(
            name="approval_set",
            description="Approve or revoke approval for a pull request.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "revisionId": {"type": "string"},
                    "approvalStatus": {"type": "string", "enum": ["APPROVE", "REVOKE"]},
                },
                "required": ["pullRequestId", "revisionId", "approvalStatus"],
            },
        ),
        Tool(
            name="approval_rules_check",
            description="Evaluates if PR meets all approval rules.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "revisionId": {"type": "string"},
                },
                "required": ["pullRequestId", "revisionId"],
            },
        ),
        Tool(
            name="merge_conflicts_check",
            description="Checks for merge conflicts between source and destination.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string"},
                    "destinationCommitSpecifier": {"type": "string"},
                    "sourceCommitSpecifier": {"type": "string"},
                    "mergeOption": {"type": "string", "enum": ["FAST_FORWARD_MERGE", "SQUASH_MERGE", "THREE_WAY_MERGE"]},
                },
                "required": ["repositoryName", "destinationCommitSpecifier", "sourceCommitSpecifier", "mergeOption"],
            },
        ),
        Tool(
            name="merge_options_get",
            description="Gets available merge strategies for a PR.",
            input_schema={
                "type": "object",
                "properties": {
                    "repositoryName": {"type": "string"},
                    "sourceCommitSpecifier": {"type": "string"},
                    "destinationCommitSpecifier": {"type": "string"},
                },
                "required": ["repositoryName", "sourceCommitSpecifier", "destinationCommitSpecifier"],
            },
        ),
        Tool(
            name="pr_merge",
            description="Merges an approved pull request using the specified merge strategy.",
            input_schema={
                "type": "object",
                "properties": {
                    "pullRequestId": {"type": "string"},
                    "repositoryName": {"type": "string"},
                    "mergeOption": {"type": "string", "enum": ["FAST_FORWARD_MERGE", "SQUASH_MERGE", "THREE_WAY_MERGE"]},
                    "commitMessage": {"type": "string"},
                    "authorName": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["pullRequestId", "repositoryName", "mergeOption"],
            },
        ),
    ]


async def call_tool(name: str, arguments: dict) -> str:
    """Dispatch tool by name; delegates to services. Returns text content."""
    args = arguments or {}
    if name == "ping":
        msg = args.get("message") or "pong"
        return json.dumps({"status": "ok", "message": msg})

    from src.auth import get_auth_manager

    auth = get_auth_manager()
    if name == "aws_creds_refresh":
        auth.refresh_credentials()
        return json.dumps({"status": "ok", "message": "Credentials refreshed successfully."})
    if name == "aws_profile_switch":
        profile_name = args.get("profileName")
        if not profile_name:
            raise ValueError("profileName is required")
        auth.switch_profile(profile_name)
        return json.dumps({"status": "ok", "profile": profile_name, "message": f"Switched to profile: {profile_name}"})
    if name == "aws_profiles_list":
        profiles = auth.list_profiles()
        return json.dumps({"profiles": profiles})
    if name == "aws_creds_status":
        status = auth.get_creds_status()
        return json.dumps({
            "valid": status.valid,
            "source": status.source,
            "profile": status.profile,
            "accessKeyIdPrefix": status.access_key_id_prefix,
            "expiration": status.expiration,
            "message": status.message,
        })

    # Repository and PR tools — run sync boto3 calls in thread pool
    from src.services.repository import get_repository_service
    from src.services.pull_request import get_pull_request_service

    svc = get_repository_service()
    pr_svc = get_pull_request_service()

    async def _run(fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    try:
        if name == "repos_list":
            result = await _run(
                svc.list_repos,
                next_token=args.get("nextToken"),
                sort_by=args.get("sortBy"),
                order=args.get("order"),
                max_results=args.get("maxResults"),
                search_term=args.get("searchTerm"),
            )
            return json.dumps(result, default=_json_default)

        if name == "repo_get":
            repo_name = args.get("repositoryName")
            if not repo_name:
                raise ValueError("repositoryName is required")
            result = await _run(svc.get_repo, repo_name)
            return json.dumps(result, default=_json_default)

        if name == "branches_list":
            repo_name = args.get("repositoryName")
            if not repo_name:
                raise ValueError("repositoryName is required")
            result = await _run(svc.list_branches, repo_name, next_token=args.get("nextToken"))
            return json.dumps(result, default=_json_default)

        if name == "branch_get":
            repo_name = args.get("repositoryName")
            branch_name = args.get("branchName")
            if not repo_name or not branch_name:
                raise ValueError("repositoryName and branchName are required")
            result = await _run(svc.get_branch, repo_name, branch_name)
            return json.dumps(result, default=_json_default)

        if name == "file_get":
            repo_name = args.get("repositoryName")
            commit_spec = args.get("commitSpecifier")
            file_path = args.get("filePath")
            if not repo_name or not commit_spec or not file_path:
                raise ValueError("repositoryName, commitSpecifier, and filePath are required")
            result = await _run(svc.get_file, repo_name, commit_spec, file_path)
            return json.dumps(result, default=_json_default)

        if name == "folder_get":
            repo_name = args.get("repositoryName")
            commit_spec = args.get("commitSpecifier")
            folder_path = args.get("folderPath", "")
            if repo_name is None or commit_spec is None:
                raise ValueError("repositoryName and commitSpecifier are required")
            result = await _run(svc.get_folder, repo_name, commit_spec, folder_path)
            return json.dumps({"items": result}, default=_json_default)

        if name == "code_search":
            repo_name = args.get("repositoryName")
            commit_spec = args.get("commitSpecifier")
            mode = args.get("mode")
            if not repo_name or not commit_spec or not mode:
                raise ValueError("repositoryName, commitSpecifier, and mode are required")
            result = await _run(
                svc.code_search,
                repo_name,
                commit_spec,
                mode,
                file_path=args.get("filePath"),
                search_patterns=args.get("searchPatterns"),
                tree_path=args.get("treePath") or "/",
                tree_depth=args.get("treeDepth") if args.get("treeDepth") is not None else 10,
                max_results=args.get("maxResults") if args.get("maxResults") is not None else 50,
                include_context=args.get("includeContext", True),
                context_lines=args.get("contextLines") if args.get("contextLines") is not None else 3,
            )
            return json.dumps(result, default=_json_default)

        if name == "commit_get":
            repo_name = args.get("repositoryName")
            commit_id = args.get("commitId")
            if not repo_name or not commit_id:
                raise ValueError("repositoryName and commitId are required")
            result = await _run(svc.get_commit, repo_name, commit_id)
            return json.dumps(result, default=_json_default)

        if name == "diff_get":
            repo_name = args.get("repositoryName")
            before = args.get("beforeCommitSpecifier")
            after = args.get("afterCommitSpecifier")
            if not repo_name or not before or not after:
                raise ValueError("repositoryName, beforeCommitSpecifier, and afterCommitSpecifier are required")
            result = await _run(
                svc.get_differences,
                repo_name,
                before,
                after,
                before_path=args.get("beforePath"),
                after_path=args.get("afterPath"),
                next_token=args.get("nextToken"),
                max_results=args.get("maxResults"),
            )
            return json.dumps(result, default=_json_default)

        if name == "file_diff_analyze":
            repo_name = args.get("repositoryName")
            before_id = args.get("beforeCommitId")
            after_id = args.get("afterCommitId")
            file_path = args.get("filePath")
            change_type = args.get("changeType")
            if not all([repo_name, before_id, after_id, file_path, change_type]):
                raise ValueError("repositoryName, beforeCommitId, afterCommitId, filePath, and changeType are required")
            from src.services.diff_analyzer import DiffAnalyzer

            analyzer = DiffAnalyzer(svc)
            if change_type == "D":
                out = await _run(
                    analyzer.analyze_file_diff,
                    repo_name,
                    before_id,
                    after_id,
                    file_path,
                    change_type,
                )
                return json.dumps(out, default=_json_default)
            out = await _run(
                analyzer.analyze_file_diff,
                repo_name,
                before_id,
                after_id,
                file_path,
                change_type,
            )
            payload = json.dumps(out, default=_json_default)
            if len(payload.encode("utf-8")) > MAX_DIFF_SIZE:
                return json.dumps({
                    "status": "DIFF_TOO_LARGE_FOR_SINGLE_RESPONSE",
                    "message": "Diff exceeds 100KB. Use file_get to retrieve full file content for review.",
                    "filePath": file_path,
                    "summary": out.get("summary"),
                    "recommendation": out.get("analysisRecommendation"),
                }, default=_json_default)
            return payload

        if name == "batch_diff_analyze":
            repo_name = args.get("repositoryName")
            before_id = args.get("beforeCommitId")
            after_id = args.get("afterCommitId")
            file_diffs = args.get("fileDifferences") or []
            if not repo_name or not before_id or not after_id:
                raise ValueError("repositoryName, beforeCommitId, and afterCommitId are required")
            if len(file_diffs) > MAX_FILES_PER_BATCH:
                file_diffs = file_diffs[:MAX_FILES_PER_BATCH]
            from src.services.diff_analyzer import DiffAnalyzer

            analyzer = DiffAnalyzer(svc)
            out = await _run(
                analyzer.analyze_batch_diffs,
                repo_name,
                before_id,
                after_id,
                file_diffs,
            )
            payload = json.dumps(out, default=_json_default)
            if len(payload.encode("utf-8")) > MAX_BATCH_RESPONSE_SIZE:
                compact = {
                    "batchRecommendations": out.get("batchRecommendations", {}),
                    "analyses": [
                        {
                            "filePath": a.get("filePath"),
                            "changeType": a.get("changeType"),
                            "summary": a.get("summary"),
                            "recommendation": a.get("analysisRecommendation"),
                            "status": "DIFF_OMITTED_FOR_SIZE",
                        }
                        for a in out.get("analyses", [])
                    ],
                }
                return json.dumps(compact, default=_json_default)
            return payload

        # Pull request tools
        if name == "prs_list":
            repo_name = args.get("repositoryName")
            if not repo_name:
                raise ValueError("repositoryName is required")
            result = await _run(
                pr_svc.list_pull_requests,
                repo_name,
                pull_request_status=args.get("pullRequestStatus") or "OPEN",
                next_token=args.get("nextToken"),
                max_results=args.get("maxResults"),
            )
            return json.dumps(result, default=_json_default)

        if name == "pr_get":
            pr_id = args.get("pullRequestId")
            if not pr_id:
                raise ValueError("pullRequestId is required")
            result = await _run(pr_svc.get_pull_request, pr_id)
            return json.dumps(result, default=_json_default)

        if name == "pr_create":
            repo_name = args.get("repositoryName")
            title = args.get("title")
            source_ref = args.get("sourceReference")
            dest_ref = args.get("destinationReference")
            if not all([repo_name, title, source_ref, dest_ref]):
                raise ValueError("repositoryName, title, sourceReference, and destinationReference are required")
            result = await _run(
                pr_svc.create_pull_request,
                repo_name,
                title,
                args.get("description") or "",
                source_ref,
                dest_ref,
                client_request_token=args.get("clientRequestToken"),
            )
            return json.dumps(result, default=_json_default)

        if name == "pr_update_title":
            pr_id = args.get("pullRequestId")
            title = args.get("title")
            if not pr_id or not title:
                raise ValueError("pullRequestId and title are required")
            result = await _run(pr_svc.update_pull_request_title, pr_id, title)
            return json.dumps(result, default=_json_default)

        if name == "pr_update_desc":
            pr_id = args.get("pullRequestId")
            desc = args.get("description")
            if not pr_id or desc is None:
                raise ValueError("pullRequestId and description are required")
            result = await _run(pr_svc.update_pull_request_description, pr_id, desc)
            return json.dumps(result, default=_json_default)

        if name == "pr_close":
            pr_id = args.get("pullRequestId")
            if not pr_id:
                raise ValueError("pullRequestId is required")
            result = await _run(pr_svc.close_pull_request, pr_id)
            return json.dumps(result, default=_json_default)

        if name == "pr_reopen":
            pr_id = args.get("pullRequestId")
            if not pr_id:
                raise ValueError("pullRequestId is required")
            result = await _run(pr_svc.reopen_pull_request, pr_id)
            return json.dumps(result, default=_json_default)

        if name == "comments_get":
            pr_id = args.get("pullRequestId")
            if not pr_id:
                raise ValueError("pullRequestId is required")
            result = await _run(
                pr_svc.get_comments,
                pr_id,
                repository_name=args.get("repositoryName"),
                before_commit_id=args.get("beforeCommitId"),
                after_commit_id=args.get("afterCommitId"),
                next_token=args.get("nextToken"),
                max_results=args.get("maxResults"),
            )
            return json.dumps(result, default=_json_default)

        if name == "comment_post":
            pr_id = args.get("pullRequestId")
            repo_name = args.get("repositoryName")
            before_id = args.get("beforeCommitId")
            after_id = args.get("afterCommitId")
            content = args.get("content")
            if not all([pr_id, repo_name, before_id, after_id, content]):
                raise ValueError("pullRequestId, repositoryName, beforeCommitId, afterCommitId, and content are required")
            result = await _run(
                pr_svc.post_comment,
                pr_id,
                repo_name,
                before_id,
                after_id,
                content,
                file_path=args.get("filePath"),
                file_position=args.get("filePosition"),
                relative_file_version=args.get("relativeFileVersion"),
                client_request_token=args.get("clientRequestToken"),
            )
            return json.dumps(result, default=_json_default)

        if name == "comment_update":
            comment_id = args.get("commentId")
            content = args.get("content")
            if not comment_id or not content:
                raise ValueError("commentId and content are required")
            result = await _run(pr_svc.update_comment, comment_id, content)
            return json.dumps(result, default=_json_default)

        if name == "comment_delete":
            comment_id = args.get("commentId")
            if not comment_id:
                raise ValueError("commentId is required")
            result = await _run(pr_svc.delete_comment, comment_id)
            return json.dumps(result, default=_json_default)

        if name == "comment_reply":
            in_reply_to = args.get("inReplyTo")
            content = args.get("content")
            if not in_reply_to or not content:
                raise ValueError("inReplyTo and content are required")
            result = await _run(
                pr_svc.reply_to_comment,
                in_reply_to,
                content,
                client_request_token=args.get("clientRequestToken"),
            )
            return json.dumps(result, default=_json_default)

        if name == "approvals_get":
            pr_id = args.get("pullRequestId")
            revision_id = args.get("revisionId")
            if not pr_id or not revision_id:
                raise ValueError("pullRequestId and revisionId are required")
            result = await _run(pr_svc.get_approval_states, pr_id, revision_id)
            return json.dumps(result, default=_json_default)

        if name == "approval_set":
            pr_id = args.get("pullRequestId")
            revision_id = args.get("revisionId")
            approval_status = args.get("approvalStatus")
            if not all([pr_id, revision_id, approval_status]):
                raise ValueError("pullRequestId, revisionId, and approvalStatus are required")
            result = await _run(
                pr_svc.update_approval_state,
                pr_id,
                revision_id,
                approval_status,
            )
            return json.dumps(result, default=_json_default)

        if name == "approval_rules_check":
            pr_id = args.get("pullRequestId")
            revision_id = args.get("revisionId")
            if not pr_id or not revision_id:
                raise ValueError("pullRequestId and revisionId are required")
            result = await _run(pr_svc.evaluate_approval_rules, pr_id, revision_id)
            return json.dumps(result, default=_json_default)

        if name == "merge_conflicts_check":
            repo_name = args.get("repositoryName")
            dest_spec = args.get("destinationCommitSpecifier")
            source_spec = args.get("sourceCommitSpecifier")
            merge_opt = args.get("mergeOption")
            if not all([repo_name, dest_spec, source_spec, merge_opt]):
                raise ValueError("repositoryName, destinationCommitSpecifier, sourceCommitSpecifier, and mergeOption are required")
            result = await _run(
                pr_svc.get_merge_conflicts,
                repo_name,
                dest_spec,
                source_spec,
                merge_opt,
            )
            return json.dumps(result, default=_json_default)

        if name == "merge_options_get":
            repo_name = args.get("repositoryName")
            source_spec = args.get("sourceCommitSpecifier")
            dest_spec = args.get("destinationCommitSpecifier")
            if not all([repo_name, source_spec, dest_spec]):
                raise ValueError("repositoryName, sourceCommitSpecifier, and destinationCommitSpecifier are required")
            result = await _run(
                pr_svc.get_merge_options,
                repo_name,
                source_spec,
                dest_spec,
            )
            return json.dumps(result, default=_json_default)

        if name == "pr_merge":
            pr_id = args.get("pullRequestId")
            repo_name = args.get("repositoryName")
            merge_opt = args.get("mergeOption")
            if not all([pr_id, repo_name, merge_opt]):
                raise ValueError("pullRequestId, repositoryName, and mergeOption are required")
            result = await _run(
                pr_svc.merge_pull_request,
                pr_id,
                repo_name,
                merge_opt,
                commit_message=args.get("commitMessage"),
                author_name=args.get("authorName"),
                email=args.get("email"),
            )
            return json.dumps(result, default=_json_default)

    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except ValueError as e:
        return json.dumps({"error": str(e)})

    raise ValueError(f"Unknown tool: {name}")


def _json_default(obj):
    """JSON serializer for dates and bytes."""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
