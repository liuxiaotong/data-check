"""Tests for CLI commands."""

import json

import pytest
from click.testing import CliRunner

from datacheck.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def valid_data_file(tmp_path):
    """Create a valid JSON data file."""
    data = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence."},
        {"instruction": "Explain ML", "response": "ML is machine learning."},
        {"instruction": "Define DL", "response": "DL is deep learning."},
    ]
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def mixed_data_file(tmp_path):
    """Create a data file with some invalid samples."""
    data = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence."},
        {"instruction": "", "response": "ML is machine learning."},  # empty instruction
        {"instruction": "Define DL", "response": ""},  # empty response
    ]
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


class TestThreshold:
    """Tests for --threshold and --strict options."""

    def test_default_threshold_pass(self, runner, valid_data_file):
        result = runner.invoke(main, ["check", valid_data_file])
        assert result.exit_code == 0

    def test_high_threshold_fail(self, runner, mixed_data_file):
        result = runner.invoke(main, ["check", mixed_data_file, "--threshold", "1.0"])
        assert result.exit_code == 1
        assert "低于阈值" in result.output

    def test_low_threshold_pass(self, runner, mixed_data_file):
        result = runner.invoke(main, ["check", mixed_data_file, "--threshold", "0.1"])
        assert result.exit_code == 0

    def test_strict_mode_with_warnings(self, runner, mixed_data_file):
        result = runner.invoke(main, ["check", mixed_data_file, "--strict"])
        assert result.exit_code == 1
        assert "严格模式" in result.output

    def test_strict_mode_clean(self, runner, valid_data_file):
        result = runner.invoke(main, ["check", valid_data_file, "--strict"])
        assert result.exit_code == 0


class TestRulesFile:
    """Tests for --rules-file option."""

    def test_rules_file(self, runner, tmp_path):
        # Create YAML rules file
        rules_yaml = tmp_path / "rules.yaml"
        rules_yaml.write_text(
            "rules:\n"
            "  - field: instruction\n"
            "    check: min_length\n"
            "    value: 5\n"
            "    severity: error\n",
            encoding="utf-8",
        )

        # Create data file
        data = [
            {"instruction": "What is AI?", "response": "AI is..."},
            {"instruction": "Hi", "response": "Hello"},  # too short
        ]
        data_path = tmp_path / "data.json"
        data_path.write_text(json.dumps(data), encoding="utf-8")

        result = runner.invoke(
            main, ["check", str(data_path), "--rules-file", str(rules_yaml)]
        )
        # Should complete (rules file loaded successfully)
        assert "正在检查" in result.output


class TestInferCommand:
    """Tests for the infer command."""

    def test_infer_stdout(self, runner, valid_data_file):
        result = runner.invoke(main, ["infer", valid_data_file])
        assert result.exit_code == 0
        assert "推断完成" in result.output
        assert "instruction" in result.output

    def test_infer_to_file(self, runner, valid_data_file, tmp_path):
        output = str(tmp_path / "schema.json")
        result = runner.invoke(main, ["infer", valid_data_file, "-o", output])
        assert result.exit_code == 0
        assert "Schema 已保存" in result.output

        import json
        from pathlib import Path
        schema = json.loads(Path(output).read_text())
        assert "fields" in schema


class TestFixCommand:
    """Tests for the fix command."""

    def test_fix_basic(self, runner, tmp_path):
        data = [
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "  Q2  ", "response": "A2"},
        ]
        data_path = tmp_path / "data.json"
        data_path.write_text(json.dumps(data), encoding="utf-8")

        output = str(tmp_path / "fixed.jsonl")
        result = runner.invoke(main, ["fix", str(data_path), "-o", output])
        assert result.exit_code == 0
        assert "修复完成" in result.output
        assert "去除重复" in result.output

    def test_fix_with_pii(self, runner, tmp_path):
        data = [{"text": "Email me at user@example.com"}]
        data_path = tmp_path / "data.json"
        data_path.write_text(json.dumps(data), encoding="utf-8")

        output = str(tmp_path / "fixed.jsonl")
        result = runner.invoke(main, ["fix", str(data_path), "-o", output, "--strip-pii"])
        assert result.exit_code == 0
        assert "PII 脱敏" in result.output


class TestHTMLFormat:
    """Tests for HTML format in check command."""

    def test_check_html_output(self, runner, valid_data_file, tmp_path):
        output = str(tmp_path / "report.html")
        result = runner.invoke(main, ["check", valid_data_file, "-f", "html", "-o", output])
        assert result.exit_code == 0

        from pathlib import Path
        content = Path(output).read_text()
        assert "<!DOCTYPE html>" in content


class TestCompareCommand:
    """Tests for the compare command."""

    def test_compare_two_files(self, runner, tmp_path):
        data1 = [{"instruction": "Q1", "response": "A1"}]
        data2 = [{"instruction": "Q2", "response": "A2"}, {"instruction": "Q3", "response": "A3"}]

        f1 = tmp_path / "data1.json"
        f2 = tmp_path / "data2.json"
        f1.write_text(json.dumps(data1), encoding="utf-8")
        f2.write_text(json.dumps(data2), encoding="utf-8")

        result = runner.invoke(main, ["compare", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "数据分布对比报告" in result.output


class TestRulesCommand:
    """Tests for the rules command."""

    def test_list_rules(self, runner):
        result = runner.invoke(main, ["rules"])
        assert result.exit_code == 0
        assert "可用规则" in result.output
        assert "预设规则集" in result.output


class TestDiffCommand:
    """Tests for the diff command."""

    def test_diff_two_reports(self, runner, tmp_path):
        report_a = {
            "title": "报告 A",
            "generated_at": "2025-01-01",
            "summary": {"total_samples": 100, "passed_samples": 90, "failed_samples": 10,
                        "pass_rate": 0.9, "error_count": 5, "warning_count": 3},
            "rule_results": {},
            "duplicates": [],
        }
        report_b = {
            "title": "报告 B",
            "generated_at": "2025-01-02",
            "summary": {"total_samples": 100, "passed_samples": 95, "failed_samples": 5,
                        "pass_rate": 0.95, "error_count": 2, "warning_count": 1},
            "rule_results": {},
            "duplicates": [],
        }
        fa = tmp_path / "a.json"
        fb = tmp_path / "b.json"
        fa.write_text(json.dumps(report_a), encoding="utf-8")
        fb.write_text(json.dumps(report_b), encoding="utf-8")

        result = runner.invoke(main, ["diff", str(fa), str(fb)])
        assert result.exit_code == 0
        assert "质量报告对比" in result.output

    def test_diff_save_output(self, runner, tmp_path):
        report = {
            "summary": {"total_samples": 10, "passed_samples": 10, "failed_samples": 0,
                        "pass_rate": 1.0, "error_count": 0, "warning_count": 0},
        }
        fa = tmp_path / "a.json"
        fb = tmp_path / "b.json"
        fa.write_text(json.dumps(report), encoding="utf-8")
        fb.write_text(json.dumps(report), encoding="utf-8")

        output = str(tmp_path / "diff.md")
        result = runner.invoke(main, ["diff", str(fa), str(fb), "-o", output])
        assert result.exit_code == 0
        assert "对比报告已保存" in result.output


class TestWatchCommand:
    """Tests for the watch command."""

    def test_watch_missing_watchdog(self, runner, monkeypatch):
        """Test that watch command shows helpful error when watchdog is not installed."""
        import datacheck.cli as cli_mod

        # Simulate watchdog not being installed by patching the import
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def mock_import(name, *args, **kwargs):
            if name == "watchdog.observers" or name == "watchdog.events":
                raise ImportError("No module named 'watchdog'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)
        result = runner.invoke(cli_mod.main, ["watch", "."])
        # Should fail with helpful message (exit code 1)
        assert result.exit_code == 1
        assert "watchdog" in result.output


class TestBatchCheck:
    """Tests for check command with directory input."""

    def test_check_directory(self, runner, tmp_path):
        data = [{"instruction": "Q1", "response": "A1"}]
        (tmp_path / "a.json").write_text(json.dumps(data), encoding="utf-8")
        (tmp_path / "b.json").write_text(json.dumps(data), encoding="utf-8")

        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code == 0
        assert "批量数据质量检查结果" in result.output

    def test_check_directory_output(self, runner, tmp_path):
        data = [{"instruction": "Q1", "response": "A1"}]
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.json").write_text(json.dumps(data), encoding="utf-8")

        output = str(tmp_path / "report.md")
        result = runner.invoke(main, ["check", str(data_dir), "-o", output])
        assert result.exit_code == 0
        assert "报告已保存" in result.output

    def test_check_directory_json(self, runner, tmp_path):
        data = [{"text": "hello"}]
        (tmp_path / "d.json").write_text(json.dumps(data), encoding="utf-8")

        output = str(tmp_path / "report.json")
        result = runner.invoke(main, ["check", str(tmp_path), "-f", "json", "-o", output])
        assert result.exit_code == 0

        from pathlib import Path
        report = json.loads(Path(output).read_text())
        assert "aggregate" in report
        assert "files" in report

    def test_check_directory_threshold_fail(self, runner, tmp_path):
        data = [
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "", "response": ""},  # will fail non_empty
        ]
        (tmp_path / "bad.json").write_text(json.dumps(data), encoding="utf-8")

        result = runner.invoke(main, ["check", str(tmp_path), "--threshold", "1.0"])
        assert result.exit_code == 1

    def test_check_directory_strict(self, runner, tmp_path):
        data = [
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "", "response": ""},  # warning
        ]
        (tmp_path / "d.json").write_text(json.dumps(data), encoding="utf-8")

        result = runner.invoke(main, ["check", str(tmp_path), "--strict"])
        assert result.exit_code == 1
        assert "严格模式" in result.output
