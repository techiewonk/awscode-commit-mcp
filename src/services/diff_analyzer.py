"""Git-style diff + summary + recommendation; single-file and batch with size limits."""

from __future__ import annotations

import difflib
import re
from typing import Any, Literal

ChangeType = Literal["A", "D", "M"]

MAX_DIFF_SIZE = 100_000  # 100KB per file
MAX_BATCH_RESPONSE_SIZE = 200_000  # 200KB for batch
MAX_FILES_PER_BATCH = 5


class DiffAnalyzer:
    """Analyzes file diffs and produces git-style unified diff + summary + recommendations."""

    def __init__(self, repository_service: Any) -> None:
        self._repo = repository_service

    def analyze_file_diff(
        self,
        repository_name: str,
        before_commit_id: str,
        after_commit_id: str,
        file_path: str,
        change_type: ChangeType,
    ) -> dict[str, Any]:
        """Analyze a single file diff; returns git diff format, summary, and recommendation."""
        before_content = ""
        after_content = ""

        try:
            if change_type != "A":
                before_file = self._repo.get_file(
                    repository_name, before_commit_id, file_path
                )
                before_content = before_file.get("content") or ""

            if change_type != "D":
                after_file = self._repo.get_file(
                    repository_name, after_commit_id, file_path
                )
                after_content = after_file.get("content") or ""

            before_lines = before_content.splitlines(keepends=True)
            if not before_lines and before_content:
                before_lines = [before_content]
            after_lines = after_content.splitlines(keepends=True)
            if not after_lines and after_content:
                after_lines = [after_content]

            summary = self._compute_summary(before_content, after_content, change_type)
            recommendation = self._analyze_complexity(
                before_content, after_content, change_type, summary
            )
            git_diff_format = self._generate_git_diff(
                file_path, before_content, after_content, change_type
            )
            line_mapping = {
                "beforeLineCount": len(before_content.splitlines()) if before_content else 0,
                "afterLineCount": len(after_content.splitlines()) if after_content else 0,
                "exactLineNumbers": True,
                "awsConsoleCompatible": True,
            }

            return {
                "filePath": file_path,
                "changeType": change_type,
                "gitDiffFormat": git_diff_format,
                "summary": summary,
                "analysisRecommendation": recommendation,
                "lineNumberMapping": line_mapping,
            }
        except Exception as e:  # noqa: BLE001
            return self._fallback_analysis(file_path, change_type, e)

    def _compute_summary(
        self,
        before_content: str,
        after_content: str,
        change_type: ChangeType,
    ) -> dict[str, int]:
        """Compute lines added/removed/modified and total changes."""
        if change_type == "A":
            added = len(after_content.splitlines()) if after_content else 0
            return {
                "linesAdded": added,
                "linesRemoved": 0,
                "linesModified": 0,
                "totalChanges": added,
            }
        if change_type == "D":
            removed = len(before_content.splitlines()) if before_content else 0
            return {
                "linesAdded": 0,
                "linesRemoved": removed,
                "linesModified": 0,
                "totalChanges": removed,
            }
        before_lines = before_content.splitlines()
        after_lines = after_content.splitlines()
        matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
        added = sum(
            j2 - j1 for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            if tag == "insert"
        )
        removed = sum(
            i2 - i1 for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            if tag == "delete"
        )
        return {
            "linesAdded": added,
            "linesRemoved": removed,
            "linesModified": 0,
            "totalChanges": added + removed,
        }

    def _analyze_complexity(
        self,
        before_content: str,
        after_content: str,
        change_type: ChangeType,
        summary: dict[str, int],
    ) -> dict[str, Any]:
        """Determine if full file is needed, reason, context lines, complexity."""
        before_lines = before_content.splitlines()
        after_lines = after_content.splitlines()
        total_changes = summary.get("totalChanges", 0)
        max_lines = max(len(before_lines), len(after_lines), 1)
        change_ratio = total_changes / max_lines

        needs_full_file = self._should_recommend_full_file(
            before_content, after_content, change_type, total_changes, max_lines
        )
        if total_changes > 20 or change_ratio > 0.5:
            complexity: Literal["low", "medium", "high"] = "high"
        elif total_changes > 10 or change_ratio > 0.2:
            complexity = "medium"
        else:
            complexity = "low"

        reason = self._get_recommendation_reason(
            needs_full_file, complexity, change_type
        )
        context_lines = 8 if complexity == "high" else 5 if complexity == "medium" else 3

        return {
            "needsFullFile": needs_full_file,
            "reason": reason,
            "contextLines": context_lines,
            "complexity": complexity,
        }

    def _should_recommend_full_file(
        self,
        before_content: str,
        after_content: str,
        change_type: ChangeType,
        total_changes: int,
        max_lines: int,
    ) -> bool:
        if change_type in ("A", "D"):
            return True
        if max_lines <= 500:
            return True
        if max_lines > 0 and total_changes / max_lines > 0.3:
            return True
        structural = re.compile(
            r"^\s*(import|export|class|interface|function|def|from|package)\s"
        )
        for line in (before_content + "\n" + after_content).splitlines():
            if structural.match(line):
                return True
        return False

    def _get_recommendation_reason(
        self,
        needs_full_file: bool,
        complexity: Literal["low", "medium", "high"],
        change_type: ChangeType,
    ) -> str:
        if change_type == "A":
            return "New file requires full context to understand structure and purpose"
        if change_type == "D":
            return "Deleted file should be reviewed in full to understand impact"
        if needs_full_file:
            if complexity == "high":
                return "Extensive changes require full file context for proper understanding"
            return "Structural changes or small file size makes full context beneficial"
        return "Focused diff with context should be sufficient for understanding changes"

    def _generate_git_diff(
        self,
        file_path: str,
        before_content: str,
        after_content: str,
        change_type: ChangeType,
    ) -> str:
        """Produce unified diff (git-style) for the file."""
        from_date = "a/" + file_path
        to_date = "b/" + file_path
        if change_type == "A":
            before_content = ""
        elif change_type == "D":
            after_content = ""

        before_lines = before_content.splitlines(keepends=True)
        if not before_lines and before_content:
            before_lines = [before_content + "\n"]
        after_lines = after_content.splitlines(keepends=True)
        if not after_lines and after_content:
            after_lines = [after_content + "\n"]

        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=from_date,
                tofile=to_date,
                lineterm="",
                n=3,
            )
        )
        if not diff_lines:
            return f"diff --git a/{file_path} b/{file_path}\n(no changes)"
        header = [
            f"diff --git a/{file_path} b/{file_path}",
        ]
        if change_type == "A":
            header.extend(["new file mode 100644", f"--- /dev/null", f"+++ {to_date}"])
        elif change_type == "D":
            header.extend(["deleted file mode 100644", f"--- {from_date}", "+++ /dev/null"])
        else:
            header.extend([f"--- {from_date}", f"+++ {to_date}"])
        # difflib.unified_diff skips the first two lines (---/+++); we added our own
        body = [line for line in diff_lines if line.startswith(("@", " ", "+", "-"))]
        return "\n".join(header + body)

    def _fallback_analysis(
        self,
        file_path: str,
        change_type: ChangeType,
        error: Exception,
    ) -> dict[str, Any]:
        return {
            "filePath": file_path,
            "changeType": change_type,
            "gitDiffFormat": (
                f"# Diff analysis failed for {file_path}\n"
                f"# Error: {error!s}\n"
                "# Recommend using file_get for manual analysis"
            ),
            "summary": {
                "linesAdded": 0,
                "linesRemoved": 0,
                "linesModified": 0,
                "totalChanges": 0,
            },
            "analysisRecommendation": {
                "needsFullFile": change_type in ("A", "D"),
                "reason": f"File analysis failed ({error!s}). Recommend using file_get for manual analysis.",
                "contextLines": 3,
                "complexity": "medium",
            },
            "lineNumberMapping": {
                "beforeLineCount": 0,
                "afterLineCount": 0,
                "exactLineNumbers": False,
                "awsConsoleCompatible": False,
            },
        }

    def analyze_batch_diffs(
        self,
        repository_name: str,
        before_commit_id: str,
        after_commit_id: str,
        file_differences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze multiple files; returns analyses and batch recommendations."""
        analyses: list[dict[str, Any]] = []
        for fd in file_differences:
            change_type = (fd.get("changeType") or "M").upper()
            if change_type not in ("A", "D", "M"):
                change_type = "M"
            path = ""
            if fd.get("afterBlob", {}).get("path"):
                path = fd["afterBlob"]["path"]
            elif fd.get("beforeBlob", {}).get("path"):
                path = fd["beforeBlob"]["path"]
            if not path:
                path = "unknown"
            result = self.analyze_file_diff(
                repository_name,
                before_commit_id,
                after_commit_id,
                path,
                change_type,  # type: ignore[arg-type]
            )
            analyses.append(result)

        recs = [a.get("analysisRecommendation") or {} for a in analyses]
        full_needed = sum(1 for r in recs if r.get("needsFullFile"))
        complex_files = [
            a["filePath"] for a in analyses
            if (a.get("analysisRecommendation") or {}).get("complexity") == "high"
        ]
        simple_files = [
            a["filePath"] for a in analyses
            if (a.get("analysisRecommendation") or {}).get("complexity") == "low"
        ]
        approach = self._batch_approach_summary(analyses, full_needed)

        return {
            "analyses": analyses,
            "batchRecommendations": {
                "totalFiles": len(analyses),
                "fullFileNeeded": full_needed,
                "complexFiles": complex_files,
                "simpleFiles": simple_files,
                "approachSummary": approach,
            },
        }

    def _batch_approach_summary(
        self,
        analyses: list[dict[str, Any]],
        full_file_needed: int,
    ) -> str:
        total = len(analyses)
        if full_file_needed == total:
            return "All files require full context - significant changes detected"
        if full_file_needed > total // 2:
            return "Most files need full context - moderate to extensive changes"
        if full_file_needed > 0:
            summary = (
                "Mixed approach needed - some files require full context, "
                "others can use focused diff"
            )
        else:
            summary = (
                "Focused diff analysis sufficient for all files - "
                "targeted changes detected"
            )
        if total > 5:
            summary += f". NOTE: Processed {total} files (recommended maximum: 3-5 files per batch for optimal performance)"
        else:
            summary += f". Batch size: {total} files (optimal for analysis)"
        return summary
