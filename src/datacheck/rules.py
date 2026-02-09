"""Quality check rules."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Severity(Enum):
    """Rule severity levels."""

    ERROR = "error"  # Must fix
    WARNING = "warning"  # Should fix
    INFO = "info"  # Nice to fix


@dataclass
class RuleResult:
    """Result of a single rule check."""

    rule_id: str
    rule_name: str
    passed: bool
    severity: Severity
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    sample_ids: List[str] = field(default_factory=list)


@dataclass
class Rule:
    """A quality check rule.

    Attributes:
        id: Unique rule identifier
        name: Human-readable name
        description: What this rule checks
        severity: How serious violations are
        check_fn: Function that performs the check
        enabled: Whether rule is active
    """

    id: str
    name: str
    description: str
    severity: Severity = Severity.WARNING
    check_fn: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None
    enabled: bool = True

    def check(self, sample: Dict[str, Any], schema: Dict[str, Any]) -> RuleResult:
        """Check a sample against this rule."""
        if not self.enabled or self.check_fn is None:
            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                passed=True,
                severity=self.severity,
            )

        try:
            passed = self.check_fn(sample, schema)
            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                passed=passed,
                severity=self.severity,
                message="" if passed else f"违反规则: {self.name}",
            )
        except Exception as e:
            return RuleResult(
                rule_id=self.id,
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"规则检查异常: {str(e)}",
            )


class RuleSet:
    """A collection of quality check rules."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: Dict[str, Rule] = {}
        self._load_builtin_rules()

    def _load_builtin_rules(self):
        """Load built-in rules."""
        # Required fields
        self.add_rule(
            Rule(
                id="required_fields",
                name="必填字段检查",
                description="检查是否包含所有必填字段",
                severity=Severity.ERROR,
                check_fn=self._check_required_fields,
            )
        )

        # Non-empty check
        self.add_rule(
            Rule(
                id="non_empty",
                name="非空检查",
                description="检查关键字段是否为空",
                severity=Severity.ERROR,
                check_fn=self._check_non_empty,
            )
        )

        # Length check
        self.add_rule(
            Rule(
                id="length_bounds",
                name="长度边界检查",
                description="检查文本长度是否在合理范围内",
                severity=Severity.WARNING,
                check_fn=self._check_length_bounds,
            )
        )

        # Duplicate check (placeholder, needs context)
        self.add_rule(
            Rule(
                id="no_duplicates",
                name="重复检查",
                description="检查是否存在重复内容",
                severity=Severity.WARNING,
                check_fn=None,  # Handled at dataset level
                enabled=False,
            )
        )

        # Format check
        self.add_rule(
            Rule(
                id="format_valid",
                name="格式检查",
                description="检查数据格式是否正确",
                severity=Severity.ERROR,
                check_fn=self._check_format,
            )
        )

        # Language consistency
        self.add_rule(
            Rule(
                id="language_consistency",
                name="语言一致性",
                description="检查文本语言是否一致",
                severity=Severity.INFO,
                check_fn=self._check_language,
            )
        )

        # Score validity
        self.add_rule(
            Rule(
                id="score_valid",
                name="评分有效性",
                description="检查评分是否在有效范围内",
                severity=Severity.ERROR,
                check_fn=self._check_score_valid,
            )
        )

        # Text quality rules
        from datacheck.text_rules import check_pii, check_garbled_text, check_repetitive_text

        self.add_rule(
            Rule(
                id="pii_detection",
                name="隐私信息检测",
                description="检查是否包含邮箱、手机号、身份证号等隐私信息",
                severity=Severity.WARNING,
                check_fn=check_pii,
            )
        )

        self.add_rule(
            Rule(
                id="garbled_text",
                name="乱码检测",
                description="检查是否包含乱码或异常字符",
                severity=Severity.WARNING,
                check_fn=check_garbled_text,
            )
        )

        self.add_rule(
            Rule(
                id="repetitive_text",
                name="重复文本检测",
                description="检查文本中是否存在过度重复内容",
                severity=Severity.WARNING,
                check_fn=check_repetitive_text,
            )
        )

    @classmethod
    def from_config(cls, config_path: str) -> "RuleSet":
        """Load rules from a YAML configuration file.

        Requires PyYAML: pip install knowlyr-datacheck[yaml]
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("YAML 支持需要 PyYAML。请运行: pip install knowlyr-datacheck[yaml]")

        from pathlib import Path

        config_path = Path(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        ruleset = cls(name=config.get("name", config_path.stem))

        for i, rule_def in enumerate(config.get("rules", [])):
            field_name = rule_def["field"]
            check_type = rule_def["check"]
            severity = Severity(rule_def.get("severity", "warning"))
            enabled = rule_def.get("enabled", True)
            rule_id = f"config_{field_name}_{check_type}_{i}"

            check_fn = cls._build_config_check_fn(field_name, check_type, rule_def)

            ruleset.add_rule(Rule(
                id=rule_id,
                name=rule_def.get("message", f"{field_name} {check_type} 检查"),
                description=f"配置文件规则: {field_name} {check_type}",
                severity=severity,
                check_fn=check_fn,
                enabled=enabled,
            ))

        return ruleset

    @staticmethod
    def _build_config_check_fn(
        field_name: str, check_type: str, rule_def: dict
    ) -> Callable[[Dict[str, Any], Dict[str, Any]], bool]:
        """Build a check function from config definition."""
        if check_type == "required":
            return lambda sample, schema: field_name in sample.get("data", sample)

        elif check_type == "non_empty":
            def _check(sample, schema):
                data = sample.get("data", sample)
                val = data.get(field_name)
                if val is None:
                    return False
                if isinstance(val, str) and len(val.strip()) == 0:
                    return False
                return True
            return _check

        elif check_type == "min_length":
            min_len = rule_def.get("value", 1)
            return lambda sample, schema: len(
                sample.get("data", sample).get(field_name, "")
            ) >= min_len

        elif check_type == "max_length":
            max_len = rule_def.get("value", 100000)
            return lambda sample, schema: len(
                sample.get("data", sample).get(field_name, "")
            ) <= max_len

        elif check_type == "regex":
            pattern = re.compile(rule_def.get("pattern", ".*"))
            return lambda sample, schema: bool(
                pattern.search(sample.get("data", sample).get(field_name, ""))
            )

        elif check_type == "enum":
            allowed = set(rule_def.get("values", []))
            return lambda sample, schema: sample.get("data", sample).get(field_name) in allowed

        else:
            raise ValueError(f"未知的检查类型: {check_type}")

    def add_rule(self, rule: Rule):
        """Add a rule to the set."""
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str):
        """Remove a rule from the set."""
        if rule_id in self.rules:
            del self.rules[rule_id]

    def enable_rule(self, rule_id: str, enabled: bool = True):
        """Enable or disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled

    def get_enabled_rules(self) -> List[Rule]:
        """Get all enabled rules."""
        return [r for r in self.rules.values() if r.enabled]

    # Built-in check functions

    @staticmethod
    def _check_required_fields(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check required fields are present."""
        fields = schema.get("fields", [])
        data = sample.get("data", sample)

        for f in fields:
            if f.get("required", True):
                field_name = f.get("name")
                if field_name and field_name not in data:
                    return False
        return True

    @staticmethod
    def _check_non_empty(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check key fields are not empty."""
        data = sample.get("data", sample)

        for key, value in data.items():
            if key in ["id", "metadata"]:
                continue
            if isinstance(value, str) and len(value.strip()) == 0:
                return False
        return True

    @staticmethod
    def _check_length_bounds(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check text length is within bounds."""
        data = sample.get("data", sample)
        constraints = schema.get("constraints", {})

        min_length = constraints.get("min_length", 1)
        max_length = constraints.get("max_length", 100000)

        for key, value in data.items():
            if isinstance(value, str):
                if len(value) < min_length or len(value) > max_length:
                    return False
        return True

    @staticmethod
    def _check_format(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check data format is valid."""
        data = sample.get("data", sample)
        fields = {f["name"]: f for f in schema.get("fields", [])}

        for key, value in data.items():
            if key not in fields:
                continue

            field_def = fields[key]
            field_type = field_def.get("type", "text")

            if field_type == "number":
                if not isinstance(value, (int, float)):
                    return False
            elif field_type == "list":
                if not isinstance(value, list):
                    return False
            elif field_type == "json":
                if not isinstance(value, (dict, list)):
                    return False

        return True

    @staticmethod
    def _check_language(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check language consistency (basic heuristic)."""
        data = sample.get("data", sample)

        # Simple check: if one field has Chinese, others should too
        has_chinese = []

        for key, value in data.items():
            if isinstance(value, str) and len(value) > 10:
                chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", value))
                ratio = chinese_chars / len(value) if len(value) > 0 else 0
                has_chinese.append(ratio > 0.1)

        if len(has_chinese) < 2:
            return True

        # Check consistency
        return len(set(has_chinese)) == 1

    @staticmethod
    def _check_score_valid(sample: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Check score is within valid range."""
        data = sample.get("data", sample)
        rubric = schema.get("scoring_rubric", [])

        if not rubric:
            return True

        valid_scores = {r.get("score") for r in rubric}

        # Check common score field names
        for key in ["score", "rating", "label", "grade"]:
            if key in data:
                score = data[key]
                if score is not None and score not in valid_scores:
                    return False

        return True


# Preset rule sets


def get_sft_ruleset() -> RuleSet:
    """Get rule set for SFT data."""
    ruleset = RuleSet("sft")

    # Add SFT-specific rules
    ruleset.add_rule(
        Rule(
            id="instruction_quality",
            name="指令质量",
            description="检查指令是否清晰具体",
            severity=Severity.WARNING,
            check_fn=lambda s, _: len(s.get("data", s).get("instruction", "")) >= 10,
        )
    )

    ruleset.add_rule(
        Rule(
            id="response_quality",
            name="回复质量",
            description="检查回复是否足够详细",
            severity=Severity.WARNING,
            check_fn=lambda s, _: len(s.get("data", s).get("response", "")) >= 20,
        )
    )

    return ruleset


def get_preference_ruleset() -> RuleSet:
    """Get rule set for preference data."""
    ruleset = RuleSet("preference")

    # Add preference-specific rules
    ruleset.add_rule(
        Rule(
            id="chosen_rejected_different",
            name="chosen/rejected 差异",
            description="检查 chosen 和 rejected 是否不同",
            severity=Severity.ERROR,
            check_fn=lambda s, _: (
                s.get("data", s).get("chosen") != s.get("data", s).get("rejected")
            ),
        )
    )

    return ruleset
