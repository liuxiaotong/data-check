"""确权模块 — 质检通过后计算贡献权重.

将 datalabel 标注结果 + datacheck 质检 → ContributionRecord 列表。
权重公式: weight = base × quality × time × scarcity
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from datacheck.checker import DataChecker, CheckResult
from datacheck.rules import get_annotation_ruleset


@dataclass
class ContributionRecord:
    """一条确权记录，对应 antgather 的 ContributionRecord 类型."""

    id: str
    type: str  # review | peer_review | corner_case | conclusion
    description: str
    weight: float
    weight_breakdown: Dict[str, float] = field(default_factory=dict)
    task_id: str = ""
    annotator_id: str = ""
    timestamp: str = ""


@dataclass
class ContributeResult:
    """确权批量结果."""

    total_responses: int = 0
    passed_responses: int = 0
    failed_responses: int = 0
    contributions: List[ContributionRecord] = field(default_factory=list)
    total_weight: float = 0.0
    check_result: Optional[CheckResult] = None


# 贡献类型 → 基础权重
DEFAULT_BASE_WEIGHTS = {
    "review": 1.0,
    "peer_review": 3.0,
    "corner_case": 8.0,
    "conclusion": 20.0,
    "maintenance": 5.0,
}


def _infer_contribution_type(response: Dict[str, Any]) -> str:
    """从标注结果推断贡献类型."""
    comment = response.get("comment", "")
    # 有 ranking → peer_review (对比评审)
    if "ranking" in response:
        return "peer_review"
    # 有详细 comment → 可能是 corner_case
    if comment and len(comment) > 50:
        return "corner_case"
    # 默认 review
    return "review"


def _calc_quality_multiplier(
    response: Dict[str, Any],
    passed: bool,
    schema: Dict[str, Any],
) -> float:
    """质量乘数: 基于标注质量和通过状态.

    - 质检通过: 1.0
    - 有详细 comment: +0.1
    - 评分与 rubric 匹配: +0.1
    - 质检未通过: 0.0 (不确权)
    """
    if not passed:
        return 0.0

    multiplier = 1.0

    comment = response.get("comment", "")
    if comment and len(comment) >= 10:
        multiplier += 0.1

    # Score matches rubric exactly
    rubric = schema.get("scoring_rubric", [])
    if rubric:
        score = response.get("score")
        valid_scores = {r.get("score") for r in rubric}
        if score in valid_scores:
            multiplier += 0.1

    return round(multiplier, 2)


def _calc_time_multiplier(
    annotated_at: str,
    dataset_created_at: Optional[str] = None,
) -> float:
    """时间乘数: 早期贡献者获得更高权重.

    - 第 1 天: 1.5x
    - 第 7 天: 1.2x
    - 第 30 天: 1.0x
    - 之后: 0.9x
    """
    if not annotated_at:
        return 1.0

    try:
        ts = datetime.fromisoformat(annotated_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 1.0

    if dataset_created_at:
        try:
            created = datetime.fromisoformat(dataset_created_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            created = ts
    else:
        created = ts

    days_since = max(0, (ts - created).days)

    if days_since <= 1:
        return 1.5
    elif days_since <= 7:
        return 1.2
    elif days_since <= 30:
        return 1.0
    else:
        return 0.9


def _calc_scarcity_multiplier(
    response: Dict[str, Any],
    total_responses: int,
) -> float:
    """稀缺性乘数: 领域/贡献类型的稀缺度.

    当总样本少时, 每个贡献更珍贵。
    - < 50 样本: 1.3x
    - < 200 样本: 1.1x
    - >= 200 样本: 1.0x
    """
    if total_responses < 50:
        return 1.3
    elif total_responses < 200:
        return 1.1
    else:
        return 1.0


def calculate_contributions(
    responses_path: str,
    schema_path: Optional[str] = None,
    base_weights: Optional[Dict[str, float]] = None,
    dataset_created_at: Optional[str] = None,
    annotator_id: str = "unknown",
) -> ContributeResult:
    """从标注导出文件计算贡献确权.

    Args:
        responses_path: datalabel 导出的 JSON 文件
        schema_path: DATA_SCHEMA.json 路径 (可选)
        base_weights: 自定义基础权重 (可选)
        dataset_created_at: 数据集创建时间 (可选, 用于时间乘数)
        annotator_id: 标注者 ID

    Returns:
        ContributeResult 包含所有确权记录
    """
    weights = base_weights or DEFAULT_BASE_WEIGHTS
    result = ContributeResult()

    # 加载标注结果
    resp_path = Path(responses_path)
    with open(resp_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 支持 {responses: [...]} 或 [...] 格式
    if isinstance(raw, dict):
        responses = raw.get("responses", [])
    elif isinstance(raw, list):
        responses = raw
    else:
        responses = []

    result.total_responses = len(responses)

    # 加载 schema
    schema: Dict[str, Any] = {}
    if schema_path:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

    # 质检: 用 annotation ruleset 检查
    checker = DataChecker(get_annotation_ruleset())
    # 将 responses 包装成 checker 期望的格式
    # 规则检查 s.get("data", s) 里的字段, 所以把标注字段都放入 data
    samples = []
    for i, r in enumerate(responses):
        sample_data = dict(r)  # 包含 task_id, score, comment, annotated_at 等
        sample = {
            "id": r.get("task_id", f"sample_{i}"),
            "data": sample_data,
        }
        samples.append(sample)

    check_result = checker.check(samples, schema)
    result.check_result = check_result

    # 找出通过的样本
    failed_ids = set(check_result.failed_sample_ids)

    for i, response in enumerate(responses):
        task_id = response.get("task_id", f"TASK_{i+1:03d}")
        sample_id = response.get("task_id", f"sample_{i}")
        passed = sample_id not in failed_ids and task_id not in failed_ids

        if not passed:
            result.failed_responses += 1
            continue

        result.passed_responses += 1

        # 推断贡献类型
        contrib_type = _infer_contribution_type(response)
        base = weights.get(contrib_type, 1.0)

        # 计算乘数
        quality = _calc_quality_multiplier(response, passed, schema)
        time_mult = _calc_time_multiplier(
            response.get("annotated_at", ""), dataset_created_at
        )
        scarcity = _calc_scarcity_multiplier(response, result.total_responses)

        # 最终权重
        weight = round(base * quality * time_mult * scarcity, 2)

        # 描述
        score_str = ""
        if "score" in response:
            score_str = f"评分={response['score']}"
        elif "ranking" in response:
            score_str = f"排序={response['ranking']}"
        elif "choice" in response:
            score_str = f"选择={response['choice']}"

        description = f"标注 {task_id}"
        if score_str:
            description += f" ({score_str})"
        if response.get("comment"):
            description += f" — {response['comment'][:30]}"

        record = ContributionRecord(
            id=f"CR_{i+1:04d}",
            type=contrib_type,
            description=description,
            weight=weight,
            weight_breakdown={
                "base": base,
                "qualityMultiplier": quality,
                "timeMultiplier": time_mult,
                "scarcityMultiplier": scarcity,
            },
            task_id=task_id,
            annotator_id=annotator_id,
            timestamp=response.get("annotated_at", datetime.now().isoformat()),
        )

        result.contributions.append(record)
        result.total_weight += weight

    return result


def contributions_to_json(result: ContributeResult) -> Dict[str, Any]:
    """将确权结果转为 JSON 可序列化格式."""
    return {
        "summary": {
            "total_responses": result.total_responses,
            "passed_responses": result.passed_responses,
            "failed_responses": result.failed_responses,
            "total_contributions": len(result.contributions),
            "total_weight": round(result.total_weight, 2),
            "quality_pass_rate": (
                round(result.check_result.pass_rate, 4)
                if result.check_result
                else None
            ),
        },
        "contributions": [
            {
                "id": c.id,
                "type": c.type,
                "description": c.description,
                "weight": c.weight,
                "weightBreakdown": c.weight_breakdown,
                "task_id": c.task_id,
                "annotator_id": c.annotator_id,
                "timestamp": c.timestamp,
            }
            for c in result.contributions
        ],
    }
