"""Tests for DataFixer."""

import json

import pytest

from datacheck.fixer import DataFixer


@pytest.fixture
def fixer():
    return DataFixer()


@pytest.fixture
def samples_with_dupes():
    return [
        {"data": {"instruction": "Q1", "response": "A1"}},
        {"data": {"instruction": "Q1", "response": "A1"}},  # duplicate
        {"data": {"instruction": "Q2", "response": "A2"}},
    ]


@pytest.fixture
def samples_with_whitespace():
    return [
        {"data": {"instruction": "  hello  ", "response": "world  "}},
        {"data": {"instruction": "clean", "response": "data"}},
    ]


@pytest.fixture
def samples_with_empty():
    return [
        {"data": {"instruction": "Q1", "response": "A1"}},
        {"data": {"instruction": "", "response": ""}},
        {"data": {"instruction": None, "response": None}},
    ]


class TestDedup:
    def test_removes_duplicates(self, fixer, samples_with_dupes):
        fixed, result = fixer.fix(samples_with_dupes, trim=False, remove_empty=False)
        assert result.duplicates_removed == 1
        assert len(fixed) == 2

    def test_no_dedup_flag(self, fixer, samples_with_dupes):
        fixed, result = fixer.fix(samples_with_dupes, dedup=False, trim=False, remove_empty=False)
        assert result.duplicates_removed == 0
        assert len(fixed) == 3


class TestTrim:
    def test_trims_whitespace(self, fixer, samples_with_whitespace):
        fixed, result = fixer.fix(
            samples_with_whitespace, dedup=False, remove_empty=False
        )
        assert result.trimmed_count == 2
        assert fixed[0]["data"]["instruction"] == "hello"
        assert fixed[0]["data"]["response"] == "world"

    def test_no_trim_flag(self, fixer, samples_with_whitespace):
        fixed, result = fixer.fix(
            samples_with_whitespace, dedup=False, trim=False, remove_empty=False
        )
        assert result.trimmed_count == 0
        assert fixed[0]["data"]["instruction"] == "  hello  "


class TestRemoveEmpty:
    def test_removes_empty_samples(self, fixer, samples_with_empty):
        fixed, result = fixer.fix(samples_with_empty, dedup=False, trim=False)
        assert result.empty_removed == 2  # empty strings + None sample
        assert len(fixed) == 1  # only Q1 has actual values

    def test_removes_all_null_sample(self, fixer):
        samples = [
            {"data": {"a": None, "b": None}},
            {"data": {"a": "ok", "b": None}},
        ]
        fixed, result = fixer.fix(samples, dedup=False, trim=False)
        assert result.empty_removed == 1
        assert len(fixed) == 1


class TestStripPII:
    def test_redacts_email(self, fixer):
        samples = [{"data": {"text": "Contact me at user@example.com please"}}]
        fixed, result = fixer.fix(
            samples, dedup=False, trim=False, remove_empty=False, strip_pii=True
        )
        assert result.pii_redacted_count == 1
        assert "[EMAIL]" in fixed[0]["data"]["text"]
        assert "user@example.com" not in fixed[0]["data"]["text"]

    def test_redacts_phone(self, fixer):
        samples = [{"data": {"text": "Call me at 13812345678"}}]
        fixed, result = fixer.fix(
            samples, dedup=False, trim=False, remove_empty=False, strip_pii=True
        )
        assert result.pii_redacted_count == 1
        assert "[PHONE]" in fixed[0]["data"]["text"]

    def test_redacts_id_card(self, fixer):
        samples = [{"data": {"text": "ID: 110101199001011234"}}]
        fixed, result = fixer.fix(
            samples, dedup=False, trim=False, remove_empty=False, strip_pii=True
        )
        assert result.pii_redacted_count == 1
        assert "[ID]" in fixed[0]["data"]["text"]

    def test_no_pii_no_redaction(self, fixer):
        samples = [{"data": {"text": "Hello world, this is clean text"}}]
        fixed, result = fixer.fix(
            samples, dedup=False, trim=False, remove_empty=False, strip_pii=True
        )
        assert result.pii_redacted_count == 0


class TestFixFile:
    def test_fix_file(self, fixer, tmp_path):
        data = [
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "Q1", "response": "A1"},  # dup
            {"instruction": "  Q2  ", "response": "  A2  "},
        ]
        input_path = tmp_path / "data.json"
        input_path.write_text(json.dumps(data), encoding="utf-8")

        output_path = tmp_path / "fixed.jsonl"
        result = fixer.fix_file(str(input_path), str(output_path))

        assert result.total_input == 3
        assert result.duplicates_removed == 1
        assert result.trimmed_count == 2
        assert output_path.exists()

        # Verify output is JSONL
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # Should not raise


class TestFixResult:
    def test_result_counts(self, fixer):
        samples = [
            {"data": {"instruction": "Q1", "response": "A1"}},
            {"data": {"instruction": "Q1", "response": "A1"}},
        ]
        fixed, result = fixer.fix(samples)
        assert result.total_input == 2
        assert result.total_output == 1
        assert result.duplicates_removed == 1
