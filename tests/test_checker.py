"""Tests for DataChecker."""

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
