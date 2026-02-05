"""Tests for QualityReport."""

import tempfile
from pathlib import Path

import pytest

from datacheck.checker import CheckResult
from datacheck.report import QualityReport


@pytest.fixture
def sample_result():
    """Sample check result for testing."""
    return CheckResult(
        success=True,
        total_samples=100,
        passed_samples=92,
        failed_samples=8,
        error_count=2,
        warning_count=5,
        info_count=1,
        pass_rate=0.92,
        rule_results={
            "required_fields": {
                "name": "必填字段检查",
                "passed": 100,
                "failed": 0,
                "severity": "error",
                "failed_samples": [],
            },
            "non_empty": {
                "name": "非空检查",
                "passed": 92,
                "failed": 8,
                "severity": "error",
                "failed_samples": ["sample_1", "sample_2"],
            },
        },
        duplicates=[["sample_5", "sample_6"]],
        failed_sample_ids=["sample_1", "sample_2", "sample_3"],
    )


class TestQualityReport:
    """Tests for QualityReport."""

    def test_to_markdown(self, sample_result):
        """Test markdown report generation."""
        report = QualityReport(sample_result)
        md = report.to_markdown()

        assert "数据质量报告" in md
        assert "92.0%" in md
        assert "🟢 优秀" in md
        assert "必填字段检查" in md
        assert "非空检查" in md

    def test_to_json(self, sample_result):
        """Test JSON report generation."""
        report = QualityReport(sample_result)
        data = report.to_json()

        assert data["summary"]["total_samples"] == 100
        assert data["summary"]["pass_rate"] == 0.92
        assert "rule_results" in data
        assert "duplicates" in data

    def test_save_markdown(self, sample_result):
        """Test saving markdown report."""
        report = QualityReport(sample_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            report.save(str(output_path), "markdown")

            assert output_path.exists()
            content = output_path.read_text()
            assert "数据质量报告" in content

    def test_save_json(self, sample_result):
        """Test saving JSON report."""
        report = QualityReport(sample_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            report.save(str(output_path), "json")

            assert output_path.exists()

    def test_quality_grades(self):
        """Test different quality grades."""
        # Excellent
        result_excellent = CheckResult(pass_rate=0.95, total_samples=100)
        report = QualityReport(result_excellent)
        assert "🟢 优秀" in report.to_markdown()

        # Good
        result_good = CheckResult(pass_rate=0.75, total_samples=100)
        report = QualityReport(result_good)
        assert "🟡 良好" in report.to_markdown()

        # Average
        result_avg = CheckResult(pass_rate=0.55, total_samples=100)
        report = QualityReport(result_avg)
        assert "🟠 一般" in report.to_markdown()

        # Needs improvement
        result_poor = CheckResult(pass_rate=0.35, total_samples=100)
        report = QualityReport(result_poor)
        assert "🔴 需改进" in report.to_markdown()

    def test_custom_title(self, sample_result):
        """Test custom report title."""
        report = QualityReport(sample_result, title="自定义标题")
        md = report.to_markdown()

        assert "自定义标题" in md
