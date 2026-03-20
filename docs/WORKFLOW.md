# PR Review and CodeCommit Workflow

This MCP server is optimized for AI-assisted pull request reviews and AWS CodeCommit operations. Use this guide for workflow order and tool usage.

## PR Review Workflow

1. **Discovery**: `repos_list` → `prs_list` → `pr_get`
2. **Analysis**: `diff_get` (use mergeBase as beforeCommitSpecifier for PRs) → `file_diff_analyze` / `batch_diff_analyze` → `file_get` when diffs need more context → `comments_get`
3. **Review**: `comment_post` (general or line-level with filePath, filePosition, relativeFileVersion; use mergeBase as beforeCommitId)
4. **Decision**: `approvals_get`, `approval_set` or request changes
5. **Merge**: `approval_rules_check` → `merge_conflicts_check` → `merge_options_get` → `pr_merge`

## Repository Exploration

1. **Structure**: `folder_get` (start with path `""`) → explore directories
2. **Files**: `file_get` for file contents
3. **History**: `commit_get` for commit details
4. **Comparison**: `diff_get` between branches/commits; `code_search` for finding code

## Comment Management

1. **Review existing**: `comments_get` (filter by pullRequestId, etc.)
2. **Add feedback**: `comment_post` (general or line-specific)
3. **Respond**: `comment_reply` for threads
4. **Update/delete**: `comment_update`, `comment_delete`

## Critical tools

- **`diff_get`** — Primary tool for code review; use merge base as before commit for PRs; follow with `batch_diff_analyze` and `file_get` when needed.
- **`pr_get`** — Call after `prs_list` to get mergeBase, sourceCommit, destinationCommit for the diff workflow.
- **`comments_get`** — Use before and after posting to see existing feedback and thread context.

## Validation hints

- Repository names must match exactly.
- Commit IDs are 40-character hex strings.
- File paths: forward slashes, no leading slash.
- Branch names are case-sensitive.
- For line-level comments, provide `filePath`, `filePosition`, and `relativeFileVersion` (use mergeBase as beforeCommitId).

## Best practices

1. **Batch calls**: Get PR details and comments together; use `batch_diff_analyze` for multiple files.
2. **Cache metadata**: Keep pullRequestId, revisionId, and commit IDs for multiple operations.
3. **Verify before merge**: Run `approval_rules_check` and `merge_conflicts_check` before `pr_merge`.
4. **Targeted comments**: Use line-specific `comment_post` with file path and position for precise feedback.
