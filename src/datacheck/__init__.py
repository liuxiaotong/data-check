"""DataCheck - 数据质检工具

自动化质量检查、异常检测、分布分析。
"""

__version__ = "0.4.0"

from datacheck.checker import DataChecker, CheckResult, BatchCheckResult
from datacheck.rules import Rule, RuleSet
from datacheck.report import QualityReport, BatchQualityReport
from datacheck.fixer import DataFixer, FixResult

__all__ = [
    "DataChecker",
    "CheckResult",
    "BatchCheckResult",
    "Rule",
    "RuleSet",
    "QualityReport",
    "BatchQualityReport",
    "DataFixer",
    "FixResult",
    "__version__",
]
