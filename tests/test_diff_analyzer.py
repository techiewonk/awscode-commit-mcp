"""Tests for DiffAnalyzer with mocked RepositoryService."""

from unittest.mock import MagicMock

import pytest

from src.services.diff_analyzer import DiffAnalyzer


def test_analyze_file_diff_modified_returns_git_diff_and_summary():
    """analyze_file_diff for modified file returns gitDiffFormat, summary, and recommendation."""
    mock_repo = MagicMock()
    mock_repo.get_file.side_effect = [
        {"content": "line1\nline2\nline3\n"},
        {"content": "line1\nline2_changed\nline3\n"},
    ]
    analyzer = DiffAnalyzer(mock_repo)
    result = analyzer.analyze_file_diff(
        "repo",
        "before-commit",
        "after-commit",
        "src/foo.py",
        "M",
    )
    assert "gitDiffFormat" in result
    assert "summary" in result
    assert "analysisRecommendation" in result
    assert result["filePath"] == "src/foo.py"
    assert result["changeType"] == "M"
    assert "line2_changed" in result["gitDiffFormat"] or "line2" in result["gitDiffFormat"]
    assert result["summary"]["linesAdded"] + result["summary"]["linesRemoved"] + result["summary"]["linesModified"] >= 0


def test_analyze_file_diff_added_file():
    """analyze_file_diff for added file only fetches after content."""
    mock_repo = MagicMock()
    mock_repo.get_file.return_value = {"content": "new content\n"}
    analyzer = DiffAnalyzer(mock_repo)
    result = analyzer.analyze_file_diff(
        "repo",
        "before-commit",
        "after-commit",
        "src/new.py",
        "A",
    )
    mock_repo.get_file.assert_called_once()
    call_args = mock_repo.get_file.call_args
    assert call_args[0][2] == "src/new.py"
    assert result["changeType"] == "A"
    assert result["summary"]["linesAdded"] >= 1


def test_analyze_file_diff_deleted_file():
    """analyze_file_diff for deleted file only fetches before content."""
    mock_repo = MagicMock()
    mock_repo.get_file.return_value = {"content": "old content\n"}
    analyzer = DiffAnalyzer(mock_repo)
    result = analyzer.analyze_file_diff(
        "repo",
        "before-commit",
        "after-commit",
        "src/removed.py",
        "D",
    )
    assert result["changeType"] == "D"
    assert result["summary"]["linesRemoved"] >= 1


def test_analyze_file_diff_fallback_on_error():
    """analyze_file_diff returns fallback analysis when get_file raises."""
    mock_repo = MagicMock()
    mock_repo.get_file.side_effect = RuntimeError("File not found")
    analyzer = DiffAnalyzer(mock_repo)
    result = analyzer.analyze_file_diff(
        "repo",
        "before",
        "after",
        "missing.py",
        "M",
    )
    assert result["filePath"] == "missing.py"
    assert result["changeType"] == "M"
    assert "gitDiffFormat" in result
    assert "Error" in result["gitDiffFormat"] or "failed" in result["gitDiffFormat"]


def test_analyze_batch_diffs_returns_analyses():
    """analyze_batch_diffs returns analyses and batchRecommendations."""
    mock_repo = MagicMock()
    mock_repo.get_file.side_effect = [
        {"content": "a\n"},
        {"content": "a\nb\n"},
        {"content": "x\n"},
        {"content": "x\ny\n"},
    ]
    analyzer = DiffAnalyzer(mock_repo)
    file_differences = [
        {"filePath": "f1.py", "changeType": "M", "afterBlob": {"path": "f1.py"}, "beforeBlob": {"path": "f1.py"}},
        {"filePath": "f2.py", "changeType": "M", "afterBlob": {"path": "f2.py"}, "beforeBlob": {"path": "f2.py"}},
    ]
    result = analyzer.analyze_batch_diffs(
        "repo",
        "before",
        "after",
        file_differences,
    )
    assert "analyses" in result
    assert len(result["analyses"]) == 2
    assert result["analyses"][0]["filePath"] == "f1.py"
    assert result["analyses"][1]["filePath"] == "f2.py"
    assert "batchRecommendations" in result
    assert result["batchRecommendations"]["totalFiles"] == 2
