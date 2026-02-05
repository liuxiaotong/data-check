"""DataCheck - 数据质检工具

自动化质量检查、异常检测、分布分析。
"""

__version__ = "0.1.0"

from datacheck.checker import DataChecker, CheckResult
from datacheck.rules import Rule, RuleSet
from datacheck.report import QualityReport

__all__ = [
    "DataChecker",
    "CheckResult",
    "Rule",
    "RuleSet",
    "QualityReport",
    "__version__",
]
