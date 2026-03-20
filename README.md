# AWS CodeCommit MCP Server (Python)

MCP server for **AWS CodeCommit**: repositories, branches, files, diffs, pull requests, and PR review (comments, approvals, merge). Exposes 30+ tools over stdio for use with Claude, Cursor, or any MCP client.

[AWS CodeCommit](https://docs.aws.amazon.com/codecommit/latest/userguide/welcome.html) is a managed Git-based version control service. This server lets AI assistants and IDEs list repos, read files, get diffs, manage pull requests, post line-level comments, and merge — all via the Model Context Protocol.

---

## Step-by-step installation

### 1. Prerequisites

- **Python 3.12+** (on Windows: install from [python.org](https://www.python.org/downloads/) and check “Add Python to PATH”).
- **AWS access** to CodeCommit (IAM user, role, or SSO with [appropriate permissions](https://docs.aws.amazon.com/codecommit/latest/userguide/auth-and-access-control-permissions.html)).

### 2. Clone and go to the project

```bash
git clone https://github.com/YOUR_ORG/awscode-commit-mcp.git
cd awscode-commit-mcp
```

(Use your actual repo URL/path; on Windows e.g. `cd C:\Users\YOU\Documents\GitHub\awscode-commit-mcp`.)

### 3. Install the package

From the repo root:

```bash
# With pip (works everywhere)
pip install -e .

# Or with uv (if you have uv in PATH)
uv pip install -e .
```

With dev dependencies (pytest, pytest-asyncio):

```bash
pip install -e ".[dev]"
```

### 4. Verify the server runs

In the same folder:

```bash
# Option A — run as module (recommended for Cursor)
python -m src.server

# Option B — run the script (after pip install -e .)
awscodecommit-mcp
```

You should see a log line like `[awscodecommit-mcp] INFO: server starting (stdio)` and then the process waits for input. Press Ctrl+C to stop.

### 5. Add the server in Cursor (MCP)

- Open **Cursor → Settings → MCP** (or edit `mcp.json` directly).
- Add a new MCP server with one of the configs below. Use the **Python module** config if you see “program not found” or “Failed to spawn” with `uv`.

**Most reliable (bootstrap script — no cwd/PYTHONPATH needed):**

Use the **full path** to `run_mcp_server.py`. The script adds the project root to `sys.path` so the server starts even when Cursor’s cwd is wrong. On Windows use double backslashes in JSON.

```json
{
  "mcpServers": {
    "awscodecommit": {
      "command": "python",
      "args": ["C:\\Users\\YOU\\Documents\\GitHub\\awscode-commit-mcp\\run_mcp_server.py"],
      "env": {
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

**Alternative (Python module — needs correct cwd or PYTHONPATH):**

Replace `C:\Users\YOU\...\awscode-commit-mcp` with your actual project path. On Windows use double backslashes in JSON. **Include `cwd` and `PYTHONPATH`** so Python finds the `src` package.

```json
{
  "mcpServers": {
    "awscodecommit": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\Users\\YOU\\Documents\\GitHub\\awscode-commit-mcp",
      "env": {
        "PYTHONPATH": "C:\\Users\\YOU\\Documents\\GitHub\\awscode-commit-mcp",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

To use a named profile instead of env keys:

```json
"env": {
  "AWS_PROFILE": "my-codecommit-profile",
  "AWS_REGION": "us-east-1"
}
```

**Alternative (uv — use only if `uv` is in your system PATH when Cursor starts):**

```json
{
  "mcpServers": {
    "awscodecommit": {
      "command": "uv",
      "args": ["run", "awscodecommit-mcp"],
      "cwd": "C:\\Users\\YOU\\Documents\\GitHub\\awscode-commit-mcp",
      "env": {
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

### 6. Restart Cursor and check MCP

- Restart Cursor (or reload the window) so it picks up the new MCP config.
- In the MCP / Composer panel you should see **awscodecommit** and its tools. If the server fails to start, see **Troubleshooting** below.

---

## Troubleshooting

- **“Connection closed” / “Client closed” / “Pending server creation failed: MCP error -32000”**  
  Cursor often starts the server without the project directory as cwd, so `python -m src.server` can’t find the `src` package and exits immediately. **Fix:** use the **bootstrap script** config (full path to `run_mcp_server.py`) so the server runs regardless of cwd. No `cwd` or `PYTHONPATH` needed.

- **“program not found” / “Failed to spawn”**  
  Use the **Python module** or **bootstrap script** config with the full path to your `python` executable (e.g. your conda env’s `python.exe`) if `python` isn’t in PATH when Cursor starts.

- **Seeing why the server exited**  
  If the process crashes, the server logs the full traceback to stderr. Check Cursor’s MCP log (Output → MCP) for the “FATAL” line and stack trace.

- **“undefined” after list_tools in the MCP log**  
  Cursor’s MCP adapter sometimes prints `undefined` on the line after our log messages. This comes from Cursor’s side (e.g. logging an optional return field). It’s harmless and the tools work normally. We log `list_tools` at DEBUG level to reduce log noise.

---

## Prerequisites (reference)

- **Python 3.12+**
- **boto3** and **MCP** SDK (installed via step 3 above)

---

## Configuration

Authentication uses the **standard AWS credential chain** (in order):

1. **Environment variables** — `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (optional), `AWS_REGION`
2. **Named profile** — `AWS_PROFILE` (uses `~/.aws/credentials` and `~/.aws/config`)
3. **Default chain** — IAM role, EC2 instance profile, SSO, etc.

**Optional:**

- `AWS_CREDENTIALS_FILE` — path to credentials file (default `~/.aws/credentials`)
- `AWS_CONFIG_FILE` — path to config file (default `~/.aws/config`)

See [.env.example](.env.example) for a template.

### Configuration examples

**Option A — Environment variables (e.g. CI or local script)**

```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
# Optional for temporary credentials:
# export AWS_SESSION_TOKEN=...
python -m src.server
```

**Option B — Named profile**

```bash
export AWS_PROFILE=my-codecommit-profile
export AWS_REGION=us-east-1
python -m src.server
```

**Option C — Cursor MCP config (named profile)**

Use the JSON block from **Step 5** above with `"AWS_PROFILE": "my-codecommit-profile"` in `env`.

**Option D — Cursor MCP config (env keys)**

Use the JSON block from **Step 5** and add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (and optionally `AWS_SESSION_TOKEN`) to `env`.

**Option E — Custom credentials/config paths**

```bash
export AWS_PROFILE=work
export AWS_CREDENTIALS_FILE=/path/to/my/credentials
export AWS_CONFIG_FILE=/path/to/my/config
python -m src.server
```

---

## Run (stdio)

The server speaks MCP over **stdio**. Run it directly from the project root:

```bash
python -m src.server
# or (after pip install -e .)
awscodecommit-mcp
```

With uv (if in PATH):

```bash
uv run awscodecommit-mcp
```

Configure your IDE or MCP host to start the server with one of the config patterns above (e.g. Cursor uses `command` + `args` + `cwd` + optional `env`).

---

## Tool groups

| Group | Tools |
|-------|--------|
| **Repository** | `repos_list`, `repo_get`, `branches_list`, `branch_get`, `file_get`, `folder_get`, `code_search`, `commit_get`, `diff_get`, `file_diff_analyze`, `batch_diff_analyze` |
| **Pull requests** | `prs_list`, `pr_get`, `pr_create`, `pr_update_title`, `pr_update_desc`, `pr_close`, `pr_reopen` |
| **Comments** | `comments_get`, `comment_post`, `comment_update`, `comment_delete`, `comment_reply` |
| **Approvals / merge** | `approvals_get`, `approval_set`, `approval_rules_check`, `merge_conflicts_check`, `merge_options_get`, `pr_merge` |
| **Credentials** | `aws_creds_refresh`, `aws_profile_switch`, `aws_profiles_list`, `aws_creds_status` |

For a **PR review workflow** (discovery → diff → comments → approval/merge), see [docs/WORKFLOW.md](docs/WORKFLOW.md).

---

## References

- [AWS CodeCommit User Guide](https://docs.aws.amazon.com/codecommit/latest/userguide/welcome.html)
- [CodeCommit API Reference](https://docs.aws.amazon.com/codecommit/latest/APIReference/)
