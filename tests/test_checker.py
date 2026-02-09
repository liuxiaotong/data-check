"""Tests for DataChecker."""

import json

import pytest

from datacheck.checker import DataChecker
from datacheck.rules import RuleSet, Severity


@pytest.fixture
def sample_schema():
    """Sample schema for testing."""
    return {
        "fields": [
            {"name": "instruction", "type": "text", "required": True},
            {"name": "response", "type": "text", "required": True},
        ],
        "scoring_rubric": [
            {"score": 1, "label": "Bad"},
            {"score": 2, "label": "OK"},
            {"score": 3, "label": "Good"},
        ],
    }


@pytest.fixture
def valid_samples():
    """Valid samples for testing."""
    return [
        {"id": "1", "data": {"instruction": "What is AI?", "response": "AI is..."}},
        {"id": "2", "data": {"instruction": "Explain ML", "response": "ML is..."}},
        {"id": "3", "data": {"instruction": "Define DL", "response": "DL is..."}},
    ]


@pytest.fixture
def invalid_samples():
    """Invalid samples for testing."""
    return [
        {"id": "1", "data": {"instruction": "What is AI?", "response": ""}},  # Empty response
        {"id": "2", "data": {"instruction": "", "response": "ML is..."}},  # Empty instruction
        {"id": "3", "data": {"response": "DL is..."}},  # Missing instruction
    ]


class TestDataChecker:
    """Tests for DataChecker."""

    def test_check_valid_samples(self, sample_schema, valid_samples):
        """Test checking valid samples."""
        checker = DataChecker()
        result = checker.check(valid_samples, sample_schema)

        assert result.total_samples == 3
        assert result.passed_samples == 3
        assert result.failed_samples == 0
        assert result.pass_rate == 1.0

    def test_check_invalid_samples(self, sample_schema, invalid_samples):
        """Test checking invalid samples."""
        checker = DataChecker()
        result = checker.check(invalid_samples, sample_schema)

        assert result.total_samples == 3
        assert result.failed_samples > 0
        assert result.pass_rate < 1.0

    def test_check_empty_samples(self, sample_schema):
        """Test checking empty sample list."""
        checker = DataChecker()
        result = checker.check([], sample_schema)

        assert result.total_samples == 0
        assert result.pass_rate == 1.0

    def test_duplicate_detection(self, sample_schema):
        """Test duplicate detection."""
        samples = [
            {"id": "1", "data": {"instruction": "Same", "response": "Same"}},
            {"id": "2", "data": {"instruction": "Same", "response": "Same"}},  # Duplicate
            {"id": "3", "data": {"instruction": "Different", "response": "Different"}},
        ]

        checker = DataChecker()
        result = checker.check(samples, sample_schema)

        assert len(result.duplicates) == 1
        assert set(result.duplicates[0]) == {"1", "2"}

    def test_distribution_analysis(self, sample_schema, valid_samples):
        """Test distribution analysis."""
        checker = DataChecker()
        result = checker.check(valid_samples, sample_schema)

        assert "fields" in result.distribution
        assert "instruction" in result.distribution["fields"]
        assert "response" in result.distribution["fields"]

    def test_rule_results(self, sample_schema, valid_samples):
        """Test rule results are recorded."""
        checker = DataChecker()
        result = checker.check(valid_samples, sample_schema)

        assert len(result.rule_results) > 0
        for rule_id, rule_data in result.rule_results.items():
            assert "name" in rule_data
            assert "passed" in rule_data
            assert "failed" in rule_data


class TestFileLoading:
    """Tests for file loading (JSON/JSONL/CSV)."""

    def test_load_jsonl(self, tmp_path):
        path = tmp_path / "data.jsonl"
        lines = [
            json.dumps({"instruction": "Q1", "response": "A1"}),
            json.dumps({"instruction": "Q2", "response": "A2"}),
        ]
        path.write_text("\n".join(lines), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path))
        assert result.total_samples == 2

    def test_load_jsonl_with_blank_lines(self, tmp_path):
        path = tmp_path / "data.jsonl"
        lines = [
            json.dumps({"instruction": "Q1", "response": "A1"}),
            "",
            json.dumps({"instruction": "Q2", "response": "A2"}),
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path))
        assert result.total_samples == 2

    def test_load_csv(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text(
            "instruction,response\nWhat is AI?,AI is...\nExplain ML,ML is...\n",
            encoding="utf-8",
        )

        checker = DataChecker()
        result = checker.check_file(str(path))
        assert result.total_samples == 2

    def test_load_json_list(self, tmp_path):
        path = tmp_path / "data.json"
        data = [{"instruction": "Q1", "response": "A1"}]
        path.write_text(json.dumps(data), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path))
        assert result.total_samples == 1

    def test_load_json_with_samples_key(self, tmp_path):
        path = tmp_path / "data.json"
        data = {"samples": [{"instruction": "Q1", "response": "A1"}]}
        path.write_text(json.dumps(data), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path))
        assert result.total_samples == 1


class TestSampling:
    """Tests for sampling mode."""

    def test_sample_count(self, tmp_path):
        path = tmp_path / "data.json"
        samples = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(100)]
        path.write_text(json.dumps(samples), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path), sample_count=10)
        assert result.sampled is True
        assert result.sampled_count == 10
        assert result.original_count == 100
        assert result.total_samples == 10

    def test_sample_rate(self, tmp_path):
        path = tmp_path / "data.json"
        samples = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(100)]
        path.write_text(json.dumps(samples), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path), sample_rate=0.1)
        assert result.sampled is True
        assert result.sampled_count == 10
        assert result.original_count == 100

    def test_no_sampling_when_count_exceeds(self, tmp_path):
        path = tmp_path / "data.json"
        samples = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(5)]
        path.write_text(json.dumps(samples), encoding="utf-8")

        checker = DataChecker()
        result = checker.check_file(str(path), sample_count=100)
        assert result.sampled is False
        assert result.total_samples == 5


class TestRuleSet:
    """Tests for RuleSet."""

    def test_default_ruleset(self):
        """Test default ruleset has rules."""
        ruleset = RuleSet()
        assert len(ruleset.rules) > 0

    def test_enable_disable_rule(self):
        """Test enabling and disabling rules."""
        ruleset = RuleSet()

        # Disable a rule
        ruleset.enable_rule("required_fields", False)
        assert ruleset.rules["required_fields"].enabled is False

        # Re-enable
        ruleset.enable_rule("required_fields", True)
        assert ruleset.rules["required_fields"].enabled is True

    def test_get_enabled_rules(self):
        """Test getting enabled rules."""
        ruleset = RuleSet()

        all_rules = list(ruleset.rules.values())
        enabled_rules = ruleset.get_enabled_rules()

        # Some rules may be disabled by default
        assert len(enabled_rules) <= len(all_rules)

    def test_add_custom_rule(self):
        """Test adding custom rule."""
        from datacheck.rules import Rule

        ruleset = RuleSet()
        custom_rule = Rule(
            id="custom_rule",
            name="Custom Rule",
            description="A custom test rule",
            severity=Severity.WARNING,
            check_fn=lambda s, _: True,
        )

        ruleset.add_rule(custom_rule)
        assert "custom_rule" in ruleset.rules


class TestInferSchema:
    """Tests for schema inference."""

    def test_infer_basic_types(self):
        samples = [
            {"data": {"name": "Alice", "age": 30, "score": 4.5}},
            {"data": {"name": "Bob", "age": 25, "score": 3.8}},
        ]
        schema = DataChecker.infer_schema(samples)

        assert "fields" in schema
        assert schema["fields"]["name"]["type"] == "string"
        assert schema["fields"]["age"]["type"] == "integer"
        assert schema["fields"]["score"]["type"] == "number"

    def test_infer_required_fields(self):
        samples = [{"data": {"a": "x", "b": "y"}} for _ in range(20)]
        # Add one missing 'b'
        samples.append({"data": {"a": "x"}})
        schema = DataChecker.infer_schema(samples)

        assert schema["fields"]["a"]["required"] is True
        # b present in 20/21 = 95.2%, still required
        assert schema["fields"]["b"]["required"] is True

    def test_infer_string_length(self):
        samples = [
            {"data": {"text": "hi"}},
            {"data": {"text": "hello world"}},
        ]
        schema = DataChecker.infer_schema(samples)

        assert schema["fields"]["text"]["min_length"] == 2
        assert schema["fields"]["text"]["max_length"] == 11

    def test_infer_enum_values(self):
        samples = [
            {"data": {"score": 1}},
            {"data": {"score": 2}},
            {"data": {"score": 3}},
            {"data": {"score": 1}},
        ]
        schema = DataChecker.infer_schema(samples)

        assert "enum" in schema["fields"]["score"]
        assert sorted(schema["fields"]["score"]["enum"]) == [1, 2, 3]

    def test_infer_empty_samples(self):
        schema = DataChecker.infer_schema([])
        assert schema["fields"] == {}
        assert schema["sample_count"] == 0

    def test_infer_schema_file(self, tmp_path):
        data = [
            {"instruction": "Q1", "response": "A1", "score": 5},
            {"instruction": "Q2", "response": "A2", "score": 4},
        ]
        path = tmp_path / "data.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        output = tmp_path / "schema.json"
        checker = DataChecker()
        schema = checker.infer_schema_file(str(path), str(output))

        assert output.exists()
        assert "fields" in schema
        assert "instruction" in schema["fields"]

    def test_infer_nullable_field(self):
        samples = [
            {"data": {"a": "x", "b": None}},
            {"data": {"a": "y", "b": "z"}},
        ]
        schema = DataChecker.infer_schema(samples)
        assert schema["fields"]["b"].get("nullable") is True


class TestProgressCallback:
    """Tests for progress callback."""

    def test_progress_called(self, tmp_path):
        data = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(10)]
        path = tmp_path / "data.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        checker = DataChecker()
        checker.check_file(str(path), on_progress=on_progress)

        assert len(progress_calls) == 10
        assert progress_calls[0] == (1, 10)
        assert progress_calls[-1] == (10, 10)

    def test_progress_with_sampling(self, tmp_path):
        data = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(100)]
        path = tmp_path / "data.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        checker = DataChecker()
        checker.check_file(str(path), sample_count=10, on_progress=on_progress)

        assert len(progress_calls) == 10
