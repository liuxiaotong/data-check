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
