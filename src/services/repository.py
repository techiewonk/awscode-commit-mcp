"""Repos, branches, file, folder, blob, commit, differences, tree/search."""

from __future__ import annotations

import re
from typing import Any, Callable

from src.exceptions import handle_aws_error
from src.pagination import DEFAULT_MAX_RESULTS, MAX_RESULTS_CAP


def _paginate(max_results: int | None) -> int:
    if max_results is None:
        return DEFAULT_MAX_RESULTS
    return min(max(1, int(max_results)), MAX_RESULTS_CAP)


class RepositoryService:
    """CodeCommit repository operations; uses auth manager for client."""

    def __init__(self, get_auth_manager: Callable[[], Any]) -> None:
        self._get_auth_manager = get_auth_manager

    def _client(self):
        return self._get_auth_manager().get_client()

    def list_repos(
        self,
        next_token: str | None = None,
        sort_by: str | None = None,
        order: str | None = None,
        max_results: int | None = None,
        search_term: str | None = None,
    ) -> dict[str, Any]:
        """List repositories; optional client-side filter by search_term."""
        client = self._client()
        params: dict[str, Any] = {}
        if next_token:
            params["nextToken"] = next_token
        if sort_by:
            params["sortBy"] = sort_by
        if order:
            params["order"] = order
        n = _paginate(max_results)
        params["maxResults"] = n
        try:
            resp = client.list_repositories(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        items = []
        for r in (resp.get("repositories") or []):
            repo = {
                "repositoryName": r.get("repositoryName") or "",
                "repositoryId": r.get("repositoryId") or "",
                "repositoryDescription": r.get("repositoryDescription"),
                "defaultBranch": r.get("defaultBranch"),
                "lastModifiedDate": r.get("lastModifiedDate"),
                "creationDate": r.get("creationDate"),
                "cloneUrlHttp": r.get("cloneUrlHttp"),
                "cloneUrlSsh": r.get("cloneUrlSsh"),
                "arn": r.get("Arn"),
            }
            if search_term:
                term = search_term.lower()
                name = (repo["repositoryName"] or "").lower()
                desc = (repo["repositoryDescription"] or "").lower()
                if term in name or term in desc:
                    items.append(repo)
            else:
                items.append(repo)
        return {"items": items, "nextToken": resp.get("nextToken")}

    def get_repo(self, repository_name: str) -> dict[str, Any]:
        """Get repository metadata."""
        client = self._client()
        try:
            resp = client.get_repository(repositoryName=repository_name)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        r = resp.get("repositoryMetadata") or {}
        return {
            "repositoryName": r.get("repositoryName") or "",
            "repositoryId": r.get("repositoryId") or "",
            "repositoryDescription": r.get("repositoryDescription"),
            "defaultBranch": r.get("defaultBranch"),
            "lastModifiedDate": r.get("lastModifiedDate"),
            "creationDate": r.get("creationDate"),
            "cloneUrlHttp": r.get("cloneUrlHttp"),
            "cloneUrlSsh": r.get("cloneUrlSsh"),
            "arn": r.get("Arn"),
        }

    def list_branches(
        self,
        repository_name: str,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """List branches; each branch's commitId fetched via get_branch."""
        client = self._client()
        params: dict[str, Any] = {"repositoryName": repository_name}
        if next_token:
            params["nextToken"] = next_token
        try:
            resp = client.list_branches(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        branches = resp.get("branches") or []
        items = []
        for b in branches:
            try:
                br = self.get_branch(repository_name, b)
                items.append(br)
            except Exception:
                items.append({"branchName": b, "commitId": ""})
        return {"items": items, "nextToken": resp.get("nextToken")}

    def get_branch(self, repository_name: str, branch_name: str) -> dict[str, Any]:
        """Get branch with commit ID."""
        client = self._client()
        try:
            resp = client.get_branch(
                repositoryName=repository_name,
                branchName=branch_name,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        b = resp.get("branch") or {}
        return {
            "branchName": b.get("branchName") or branch_name,
            "commitId": b.get("commitId") or "",
        }

    def get_commit(self, repository_name: str, commit_id: str) -> dict[str, Any]:
        """Get commit details."""
        client = self._client()
        try:
            resp = client.get_commit(
                repositoryName=repository_name,
                commitId=commit_id,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        c = resp.get("commit")
        if not c:
            raise RuntimeError(f"Commit {commit_id} not found")
        author = c.get("author")
        committer = c.get("committer")
        return {
            "commitId": c.get("commitId") or "",
            "treeId": c.get("treeId") or "",
            "parents": c.get("parents") or [],
            "message": c.get("message"),
            "author": {
                "name": author.get("name") or "",
                "email": author.get("email") or "",
                "date": author.get("date") or "",
            } if author else None,
            "committer": {
                "name": committer.get("name") or "",
                "email": committer.get("email") or "",
                "date": committer.get("date") or "",
            } if committer else None,
            "additionalData": c.get("additionalData"),
        }

    def get_differences(
        self,
        repository_name: str,
        before_commit_specifier: str,
        after_commit_specifier: str,
        before_path: str | None = None,
        after_path: str | None = None,
        next_token: str | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        """Get file-level differences between two commits."""
        client = self._client()
        params: dict[str, Any] = {
            "repositoryName": repository_name,
            "beforeCommitSpecifier": before_commit_specifier,
            "afterCommitSpecifier": after_commit_specifier,
            "MaxResults": _paginate(max_results),
        }
        if before_path is not None:
            params["beforePath"] = before_path
        if after_path is not None:
            params["afterPath"] = after_path
        if next_token:
            params["nextToken"] = next_token
        try:
            resp = client.get_differences(**params)
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        items = []
        for d in (resp.get("differences") or []):
            change_type = d.get("changeType") or "M"
            before_blob = d.get("beforeBlob")
            after_blob = d.get("afterBlob")
            items.append({
                "changeType": change_type,
                "beforeBlob": {
                    "blobId": before_blob.get("blobId") or "",
                    "path": before_blob.get("path") or "",
                    "mode": before_blob.get("mode") or "",
                } if before_blob else None,
                "afterBlob": {
                    "blobId": after_blob.get("blobId") or "",
                    "path": after_blob.get("path") or "",
                    "mode": after_blob.get("mode") or "",
                } if after_blob else None,
            })
        return {"items": items, "nextToken": resp.get("nextToken")}

    def get_file(
        self,
        repository_name: str,
        commit_specifier: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Get file content and blob ID."""
        client = self._client()
        try:
            resp = client.get_file(
                repositoryName=repository_name,
                commitSpecifier=commit_specifier,
                filePath=file_path,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        content = resp.get("fileContent")
        if content is None:
            raise RuntimeError(f"File {file_path} not found at {commit_specifier}")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return {
            "content": content,
            "blobId": resp.get("blobId") or "",
        }

    def get_folder(
        self,
        repository_name: str,
        commit_specifier: str,
        folder_path: str,
    ) -> list[dict[str, Any]]:
        """List files and subfolders in a folder."""
        client = self._client()
        path = folder_path if folder_path else "/"
        try:
            resp = client.get_folder(
                repositoryName=repository_name,
                commitSpecifier=commit_specifier,
                folderPath=path,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        files = []
        for f in (resp.get("files") or []):
            files.append({
                "absolutePath": f.get("absolutePath") or "",
                "blobId": f.get("blobId") or "",
                "fileMode": f.get("fileMode") or "FILE",
            })
        for s in (resp.get("subFolders") or []):
            files.append({
                "absolutePath": s.get("absolutePath") or "",
                "blobId": s.get("treeId") or "",
                "fileMode": "folder",
            })
        return files

    def get_blob(self, repository_name: str, blob_id: str) -> bytes:
        """Get blob content (binary)."""
        client = self._client()
        try:
            resp = client.get_blob(
                repositoryName=repository_name,
                blobId=blob_id,
            )
        except Exception as e:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                raise RuntimeError(handle_aws_error(e)) from e
            raise
        return resp.get("content") or b""

    def get_repository_tree(
        self,
        repository_name: str,
        commit_specifier: str,
        tree_path: str = "",
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Build tree structure and formatted tree string."""
        def build(tree_path: str, depth: int) -> dict:
            if depth >= max_depth:
                return {}
            out = {}
            path = tree_path if tree_path else "/"
            try:
                items = self.get_folder(repository_name, commit_specifier, tree_path)
            except Exception:
                return out
            for item in items:
                ap = item.get("absolutePath") or ""
                mode = item.get("fileMode") or ""
                name = ap.split("/")[-1] if ap else ""
                if not name:
                    continue
                if mode == "folder":
                    out[name + "/"] = build(ap, depth + 1)
                else:
                    out[name] = None
            return out

        tree = build(tree_path, 0)

        def count(t: dict) -> tuple[int, int]:
            files, folders = 0, 0
            for k, v in t.items():
                if v is None:
                    files += 1
                elif isinstance(v, dict):
                    folders += 1
                    f, fo = count(v)
                    files += f
                    folders += fo
            return files, folders

        files_count, folders_count = count(tree)

        def to_tree_str(t: dict, prefix: str = "") -> str:
            lines = []
            keys = sorted(t.keys())
            for i, k in enumerate(keys):
                is_last = i == len(keys) - 1
                branch = "└── " if is_last else "├── "
                lines.append(prefix + branch + k)
                v = t[k]
                if isinstance(v, dict) and v:
                    ext = "    " if is_last else "│   "
                    lines.append(to_tree_str(v, prefix + ext))
            return "\n".join(lines)

        tree_str = to_tree_str(tree) if tree else ""
        return {
            "repositoryName": repository_name,
            "commitSpecifier": commit_specifier,
            "treePath": tree_path or "/",
            "maxDepth": max_depth,
            "totalFiles": files_count,
            "totalFolders": folders_count,
            "treeFormatted": tree_str,
            "rawStructure": tree,
        }

    def code_search(
        self,
        repository_name: str,
        commit_specifier: str,
        mode: str,
        file_path: str | None = None,
        search_patterns: list[dict] | None = None,
        tree_path: str = "/",
        tree_depth: int = 10,
        max_results: int = 50,
        include_context: bool = True,
        context_lines: int = 3,
    ) -> dict[str, Any]:
        """Tree mode: repository structure. Search mode: search in file with patterns."""
        if mode == "tree":
            tree_path_clean = "" if tree_path == "/" else tree_path.rstrip("/")
            return self.get_repository_tree(
                repository_name,
                commit_specifier,
                tree_path_clean,
                tree_depth,
            )
        if mode == "search":
            if not file_path or not search_patterns:
                raise ValueError("search mode requires filePath and searchPatterns")
            return self._search_in_file(
                repository_name,
                commit_specifier,
                file_path,
                search_patterns,
                max_results=max_results,
                include_context=include_context,
                context_lines=context_lines,
            )
        raise ValueError("mode must be 'tree' or 'search'")

    def _search_in_file(
        self,
        repository_name: str,
        commit_specifier: str,
        file_path: str,
        search_patterns: list[dict],
        max_results: int = 50,
        include_context: bool = True,
        context_lines: int = 3,
    ) -> dict[str, Any]:
        """Search for patterns in file content."""
        file_result = self.get_file(repository_name, commit_specifier, file_path)
        content = file_result["content"]
        lines = content.split("\n")
        context_lines = min(10, max(0, context_lines))
        results = []
        for sp in search_patterns:
            pattern = sp.get("pattern") or ""
            ptype = sp.get("type") or "literal"
            case_sensitive = sp.get("caseSensitive", False)
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                if ptype == "regex":
                    if pattern.startswith("/") and "/" in pattern[1:]:
                        last = pattern.rfind("/")
                        regex_pattern = pattern[1:last]
                        if "i" in pattern[last:]:
                            flags = re.IGNORECASE
                        rx = re.compile(regex_pattern, flags)
                    else:
                        rx = re.compile(pattern, flags)
                elif ptype == "function":
                    rx = re.compile(
                        rf"(function\s+{re.escape(pattern)}\s*\(|{re.escape(pattern)}\s*[:=]\s*function|{re.escape(pattern)}\s*\([^)]*\)\s*=>)",
                        flags,
                    )
                elif ptype == "class":
                    rx = re.compile(rf"class\s+{re.escape(pattern)}\b", flags)
                elif ptype == "import":
                    rx = re.compile(rf"(import.*{re.escape(pattern)}|from\s+['\"].*{re.escape(pattern)})", flags)
                elif ptype == "variable":
                    rx = re.compile(rf"\b{re.escape(pattern)}\b", flags)
                else:
                    rx = re.compile(re.escape(pattern), flags)
            except re.error:
                rx = re.compile(re.escape(pattern), flags)
            matches = []
            for i, line in enumerate(lines):
                if len(matches) >= max_results:
                    break
                if rx.search(line):
                    ctx = None
                    if include_context:
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        ctx = {
                            "before": lines[start:i],
                            "after": lines[i + 1:end],
                        }
                    matches.append({
                        "lineNumber": i + 1,
                        "line": line.strip(),
                        "matchCount": len(rx.findall(line)),
                        "context": ctx,
                    })
            results.append({
                "pattern": pattern,
                "type": ptype,
                "matches": matches,
                "totalMatches": len(matches),
            })
        return {
            "repositoryName": repository_name,
            "commitSpecifier": commit_specifier,
            "filePath": file_path,
            "fileSize": len(content),
            "totalLines": len(lines),
            "searchPatterns": search_patterns,
            "results": results,
            "summary": {
                "totalPatterns": len(search_patterns),
                "totalMatches": sum(r["totalMatches"] for r in results),
            },
        }


_repository_service: RepositoryService | None = None


def get_repository_service() -> RepositoryService:
    """Return singleton RepositoryService (uses get_auth_manager)."""
    global _repository_service
    if _repository_service is None:
        from src.auth import get_auth_manager
        _repository_service = RepositoryService(get_auth_manager)
    return _repository_service
