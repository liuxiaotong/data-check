"""DataCheck - 数据质检工具

自动化质量检查、异常检测、分布分析。
"""

__version__ = "0.5.0"

from datacheck.checker import DataChecker, CheckResult, BatchCheckResult
from datacheck.rules import Rule, RuleSet
from datacheck.report import QualityReport, BatchQualityReport
from datacheck.fixer import DataFixer, FixResult
from datacheck.contribute import calculate_contributions, ContributionRecord, ContributeResult

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
    "calculate_contributions",
    "ContributionRecord",
    "ContributeResult",
    "__version__",
]
