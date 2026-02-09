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
