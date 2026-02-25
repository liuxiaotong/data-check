"""数据修复路由"""

from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from datacheck.fixer import DataFixer

router = APIRouter()


# ---------- Request / Response 模型 ----------

class FixRequest(BaseModel):
    samples: List[Dict[str, Any]]
    dedup: bool = True
    trim: bool = True
    remove_empty: bool = True
    strip_pii: bool = False


# ---------- 路由 ----------

@router.post("/")
async def fix_data(req: FixRequest):
    """数据修复

    支持去重、去空白、删除空样本、PII 脱敏等修复操作。
    返回修复后的 samples + 修复统计。
    """
    if not req.samples:
        raise HTTPException(status_code=400, detail="samples 不能为空")

    fixer = DataFixer()
    fixed_samples, result = fixer.fix(
        samples=req.samples,
        dedup=req.dedup,
        trim=req.trim,
        remove_empty=req.remove_empty,
        strip_pii=req.strip_pii,
    )

    return {
        "samples": fixed_samples,
        "stats": {
            "total_input": result.total_input,
            "total_output": result.total_output,
            "duplicates_removed": result.duplicates_removed,
            "empty_removed": result.empty_removed,
            "trimmed_count": result.trimmed_count,
            "pii_redacted_count": result.pii_redacted_count,
        },
    }
