"""质检执行路由"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from datacheck.checker import DataChecker
from datacheck.rules import (
    RuleSet,
    get_annotation_ruleset,
    get_preference_ruleset,
    get_sft_ruleset,
)

router = APIRouter()


# ---------- Request / Response 模型 ----------

class CheckRequest(BaseModel):
    samples: List[Dict[str, Any]]
    schema_def: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    ruleset: Optional[str] = None  # default / sft / preference / annotation
    custom_rules_yaml: Optional[str] = None  # YAML 文件路径或内联 YAML 名称

    model_config = {"populate_by_name": True}


class BatchCheckRequest(BaseModel):
    batch_id: str
    antgather_url: Optional[str] = None
    service_token: Optional[str] = None


# ---------- 预设规则集映射 ----------

_PRESET_RULESETS = {
    "default": lambda: RuleSet(),
    "sft": get_sft_ruleset,
    "preference": get_preference_ruleset,
    "annotation": get_annotation_ruleset,
}


def _build_ruleset(preset: Optional[str], custom_yaml: Optional[str]) -> RuleSet:
    """根据参数构造 RuleSet 实例."""
    if custom_yaml:
        # custom_rules_yaml 是 YAML 文件路径
        return RuleSet.from_config(custom_yaml)

    if preset and preset in _PRESET_RULESETS:
        return _PRESET_RULESETS[preset]()

    return RuleSet()


# ---------- 路由 ----------

@router.post("/")
async def run_check(req: CheckRequest):
    """执行质检

    接收 samples + schema + ruleset，返回质检结果。
    """
    if not req.samples:
        raise HTTPException(status_code=400, detail="samples 不能为空")

    ruleset = _build_ruleset(req.ruleset, req.custom_rules_yaml)
    checker = DataChecker(ruleset)
    result = checker.check(req.samples, req.schema_def)

    return {
        "success": result.success,
        "total_samples": result.total_samples,
        "passed_samples": result.passed_samples,
        "failed_samples": result.failed_samples,
        "pass_rate": round(result.pass_rate, 4),
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "info_count": result.info_count,
        "rule_results": result.rule_results,
        "failed_sample_ids": result.failed_sample_ids,
        "duplicates": result.duplicates,
        "near_duplicates": result.near_duplicates,
        "anomaly_count": result.anomaly_count,
    }


@router.post("/batch")
async def run_batch_check(req: BatchCheckRequest):
    """批量质检

    从 antgather 拉取整批数据执行质检。
    当前为骨架实现，拉取逻辑后续补齐。
    """
    # TODO: 通过 httpx 从 antgather 拉取 batch 数据
    # url = f"{req.antgather_url or settings.antgather_url}/api/batches/{req.batch_id}/samples"
    # headers = {"Authorization": f"Bearer {req.service_token}"}
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(url, headers=headers)
    #     data = resp.json()
    # samples = data["samples"]
    # schema = data.get("schema", {})
    # checker = DataChecker()
    # result = checker.check(samples, schema)
    # return asdict(result)

    return {
        "status": "not_implemented",
        "batch_id": req.batch_id,
        "message": "批量质检 — 拉取逻辑待对接 antgather API",
    }
