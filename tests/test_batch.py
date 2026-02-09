"""Tests for batch directory checking."""

import json

import pytest

from datacheck.checker import DataChecker, BatchCheckResult
from datacheck.report import BatchQualityReport


@pytest.fixture
def batch_dir(tmp_path):
    """Create a directory with multiple data files."""
    # Valid JSON file
    data1 = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence."},
        {"instruction": "Explain ML", "response": "ML is machine learning."},
    ]
    (tmp_path / "train.json").write_text(json.dumps(data1), encoding="utf-8")

    # JSONL file with some issues
    lines = [
        json.dumps({"instruction": "Q1", "response": "A1"}),
        json.dumps({"instruction": "", "response": "A2"}),  # empty instruction
    ]
    (tmp_path / "val.jsonl").write_text("\n".join(lines), encoding="utf-8")

    # Nested CSV file
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "test.csv").write_text(
        "instruction,response\nHello,World\nFoo,Bar\n", encoding="utf-8"
    )

    # Non-data file (should be skipped)
    (tmp_path / "readme.txt").write_text("This is not data", encoding="utf-8")

    return tmp_path


class TestCheckDirectory:
    """Tests for DataChecker.check_directory()."""

    def test_discovers_supported_files(self, batch_dir):
        checker = DataChecker()
        result = checker.check_directory(str(batch_dir))
        assert result.total_files == 3
        assert "readme.txt" not in str(result.file_results.keys())

    def test_aggregate_stats(self, batch_dir):
        checker = DataChecker()
        result = checker.check_directory(str(batch_dir))
        assert result.total_samples == 6  # 2 + 2 + 2
        assert result.total_passed_samples + result.total_failed_samples == result.total_samples
        assert 0 <= result.overall_pass_rate <= 1.0

    def test_pattern_filtering(self, batch_dir):
        checker = DataChecker()
        result = checker.check_directory(str(batch_dir), patterns=["*.jsonl"])
        assert result.total_files == 1
        assert any("val.jsonl" in k for k in result.file_results)

    def test_empty_directory(self, tmp_path):
        checker = DataChecker()
        result = checker.check_directory(str(tmp_path))
        assert result.total_files == 0
        assert result.overall_pass_rate == 1.0

    def test_file_error_handling(self, tmp_path):
        # Create a corrupt JSON file
        (tmp_path / "bad.json").write_text("{invalid json", encoding="utf-8")
        (tmp_path / "good.json").write_text(
            json.dumps([{"text": "hello"}]), encoding="utf-8"
        )

        checker = DataChecker()
        result = checker.check_directory(str(tmp_path))
        assert len(result.skipped_files) == 1
        assert result.total_files == 2  # Both counted
        assert len(result.file_results) == 1  # Only good file has result

    def test_callbacks(self, batch_dir):
        checker = DataChecker()
        calls = []

        def on_start(path, idx, total):
            calls.append((path, idx, total))

        checker.check_directory(str(batch_dir), on_file_start=on_start)
        assert len(calls) == 3
        assert calls[0][1] == 1  # first index
        assert calls[-1][2] == 3  # total

    def test_relative_paths(self, batch_dir):
        checker = DataChecker()
        result = checker.check_directory(str(batch_dir))
        # Keys should be relative paths (no absolute paths)
        for key in result.file_results:
            assert not key.startswith("/")

    def test_passed_failed_files(self, batch_dir):
        checker = DataChecker()
        result = checker.check_directory(str(batch_dir))
        assert result.passed_files + result.failed_files <= result.total_files


class TestBatchQualityReport:
    """Tests for BatchQualityReport."""

    @pytest.fixture
    def sample_batch_result(self):
        from datacheck.checker import CheckResult
        result = BatchCheckResult(
            directory="/data",
            total_files=2,
            passed_files=1,
            failed_files=1,
            total_samples=100,
            total_passed_samples=85,
            total_failed_samples=15,
            overall_pass_rate=0.85,
            total_error_count=10,
            total_warning_count=5,
            file_results={
                "train.json": CheckResult(
                    total_samples=60, passed_samples=55, failed_samples=5,
                    pass_rate=55/60, error_count=3, warning_count=2,
                ),
                "val.jsonl": CheckResult(
                    total_samples=40, passed_samples=30, failed_samples=10,
                    pass_rate=30/40, error_count=7, warning_count=3,
                ),
            },
        )
        return result

    def test_to_markdown(self, sample_batch_result):
        report = BatchQualityReport(sample_batch_result)
        md = report.to_markdown()
        assert "批量数据质量报告" in md
        assert "train.json" in md
        assert "val.jsonl" in md
        assert "85.0%" in md

    def test_to_json(self, sample_batch_result):
        report = BatchQualityReport(sample_batch_result)
        data = report.to_json()
        assert "aggregate" in data
        assert "files" in data
        assert data["aggregate"]["total_files"] == 2
        assert data["aggregate"]["overall_pass_rate"] == 0.85
        assert "train.json" in data["files"]

    def test_to_html(self, sample_batch_result):
        report = BatchQualityReport(sample_batch_result)
        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "批量数据质量报告" in html
        assert "train.json" in html

    def test_save_markdown(self, sample_batch_result, tmp_path):
        report = BatchQualityReport(sample_batch_result)
        output = str(tmp_path / "batch.md")
        report.save(output, "markdown")
        content = (tmp_path / "batch.md").read_text()
        assert "批量数据质量报告" in content

    def test_skipped_files(self):
        result = BatchCheckResult(
            directory="/data",
            total_files=1,
            skipped_files=["bad.json: JSON decode error"],
        )
        report = BatchQualityReport(result)
        md = report.to_markdown()
        assert "跳过文件" in md
        assert "bad.json" in md
