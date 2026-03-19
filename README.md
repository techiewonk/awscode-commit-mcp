# AWS CodeCommit MCP Server (Python)

MCP server for **AWS CodeCommit**: repositories, branches, files, diffs, pull requests, and PR review (comments, approvals, merge). Exposes 30+ tools over stdio for use with Claude, Cursor, or any MCP client.

## Prerequisites

- **Python 3.11+**
- **AWS access** to CodeCommit (IAM user, role, or SSO with appropriate permissions)
- **boto3** and **MCP** SDK (installed via dependencies)

## Install

```bash
# From repo root
uv pip install -e .
# or
pip install -e .
```

With dev dependencies (pytest):

```bash
uv pip install -e ".[dev]"
```

## Configuration

Authentication uses the standard AWS credential chain (in order):

1. **Environment variables** — `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (optional), `AWS_REGION`
2. **Named profile** — `AWS_PROFILE` (uses `~/.aws/credentials` and `~/.aws/config`)
3. **Default chain** — IAM role, EC2 instance profile, SSO, etc.

Optional:

- `AWS_CREDENTIALS_FILE` — path to credentials file (default `~/.aws/credentials`)
- `AWS_CONFIG_FILE` — path to config file (default `~/.aws/config`)

See [.env.example](.env.example) for a template.

## Run (stdio)

The server speaks MCP over **stdio**. Configure your IDE or MCP host to run:

```bash
uv run awscodecommit-mcp
# or
python -m src
```

**Cursor / IDE** — in MCP settings, use for example:

- `command`: `uv` (or `python`)
- `args`: `["run", "awscodecommit-mcp"]` or `["-m", "src"]`
- Optional `env`: `AWS_PROFILE`, `AWS_REGION`, etc.

## Tool groups

- **Repository**: `repos_list`, `repo_get`, `branches_list`, `branch_get`, `file_get`, `folder_get`, `code_search`, `commit_get`, `diff_get`, `file_diff_analyze`, `batch_diff_analyze`
- **Pull requests**: `prs_list`, `pr_get`, `pr_create`, `pr_update_title`, `pr_update_desc`, `pr_close`, `pr_reopen`
- **Comments**: `comments_get`, `comment_post`, `comment_update`, `comment_delete`, `comment_reply`
- **Approvals / merge**: `approvals_get`, `approval_set`, `approval_rules_check`, `merge_conflicts_check`, `merge_options_get`, `pr_merge`
- **Credentials**: `aws_creds_refresh`, `aws_profile_switch`, `aws_profiles_list`, `aws_creds_status`

For a **PR review workflow** (discovery → diff → comments → approval/merge), see [docs/WORKFLOW.md](docs/WORKFLOW.md).

## References

- [AWS CodeCommit User Guide](https://docs.aws.amazon.com/codecommit/)
- [CodeCommit API Reference](https://docs.aws.amazon.com/codecommit/latest/APIReference/)
