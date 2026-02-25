"""数据修复路由"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def fix_data(payload: dict):
    """数据修复

    支持去重、去空白、PII 脱敏等修复操作。
    TODO: 接入 datacheck.fixer 核心逻辑
    """
    return {"status": "not_implemented", "message": "数据修复 — 待实现"}
