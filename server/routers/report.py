"""报告生成路由"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from datacheck.checker import CheckResult
from datacheck.report import QualityReport

router = APIRouter()


# ---------- Request 模型 ----------

class ReportRequest(BaseModel):
    """报告生成请求.

    check_result 的结构应与 CheckResult dataclass 对齐:
    - total_samples, passed_samples, failed_samples
    - error_count, warning_count, info_count
    - pass_rate, rule_results, failed_sample_ids
    - duplicates, near_duplicates, distribution, anomalies
    """
    check_result: Dict[str, Any]
    format: str = "json"  # json / markdown / html
    title: str = "数据质量报告"


def _dict_to_check_result(d: Dict[str, Any]) -> CheckResult:
    """将 API 传入的字典还原为 CheckResult dataclass."""
    return CheckResult(
        success=d.get("success", True),
        error=d.get("error", ""),
        total_samples=d.get("total_samples", 0),
        passed_samples=d.get("passed_samples", 0),
        failed_samples=d.get("failed_samples", 0),
        error_count=d.get("error_count", 0),
        warning_count=d.get("warning_count", 0),
        info_count=d.get("info_count", 0),
        pass_rate=d.get("pass_rate", 0.0),
        rule_results=d.get("rule_results", {}),
        failed_sample_ids=d.get("failed_sample_ids", []),
        duplicates=d.get("duplicates", []),
        near_duplicates=d.get("near_duplicates", []),
        distribution=d.get("distribution", {}),
        anomalies=d.get("anomalies", {}),
        anomaly_count=d.get("anomaly_count", 0),
        sampled=d.get("sampled", False),
        sampled_count=d.get("sampled_count", 0),
        original_count=d.get("original_count", 0),
    )


# ---------- 路由 ----------

@router.post("/")
async def generate_report(req: ReportRequest):
    """生成质量报告

    支持 json / markdown / html 三种输出格式。
    """
    if req.format not in ("json", "markdown", "html"):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {req.format}，可选: json / markdown / html",
        )

    check_result = _dict_to_check_result(req.check_result)
    report = QualityReport(result=check_result, title=req.title)

    if req.format == "html":
        return HTMLResponse(content=report.to_html())

    if req.format == "markdown":
        return {"format": "markdown", "content": report.to_markdown()}

    # json
    return report.to_json()
