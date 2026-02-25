"""贡献确权路由"""

import json
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from datacheck.contribute import (
    calculate_contributions,
    contributions_to_json,
)

router = APIRouter()


# ---------- Request / Response 模型 ----------

class ContributeRequest(BaseModel):
    responses: List[Dict[str, Any]]
    schema_def: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    base_weights: Optional[Dict[str, float]] = None
    dataset_created_at: Optional[str] = None
    annotator_id: str = "unknown"

    model_config = {"populate_by_name": True}


class BatchContributeRequest(BaseModel):
    batch_id: str
    antgather_url: Optional[str] = None
    service_token: Optional[str] = None


# ---------- 路由 ----------

@router.post("/")
async def calculate_contribution(req: ContributeRequest):
    """贡献确权计算

    接收判断/标注结果数据，计算贡献者权重和确权结果。
    通过临时文件桥接 calculate_contributions() 的文件路径接口。
    """
    if not req.responses:
        raise HTTPException(status_code=400, detail="responses 不能为空")

    # calculate_contributions() 接受文件路径，写临时 JSON 文件适配
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"responses": req.responses}, f, ensure_ascii=False)
        responses_path = f.name

    schema_path = None
    if req.schema_def:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(req.schema_def, f, ensure_ascii=False)
            schema_path = f.name

    try:
        result = calculate_contributions(
            responses_path=responses_path,
            schema_path=schema_path,
            base_weights=req.base_weights,
            dataset_created_at=req.dataset_created_at,
            annotator_id=req.annotator_id,
        )
        return contributions_to_json(result)
    finally:
        # 清理临时文件
        import os
        os.unlink(responses_path)
        if schema_path:
            os.unlink(schema_path)


@router.post("/batch")
async def batch_contribution(req: BatchContributeRequest):
    """批量贡献确权

    从 antgather 拉取整批判断数据执行确权计算。
    当前为骨架实现，拉取逻辑后续补齐。
    """
    # TODO: 通过 httpx 从 antgather 拉取 batch 判断数据
    # url = f"{req.antgather_url}/api/batches/{req.batch_id}/judgments"
    # headers = {"Authorization": f"Bearer {req.service_token}"}
    # ...

    return {
        "status": "not_implemented",
        "batch_id": req.batch_id,
        "message": "批量贡献确权 — 拉取逻辑待对接 antgather API",
    }
