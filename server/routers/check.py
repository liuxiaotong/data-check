"""质检执行路由"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def run_check(payload: dict):
    """执行质检

    接收 samples + schema + ruleset，返回质检结果。
    TODO: 接入 datacheck.checker 核心逻辑
    """
    return {"status": "not_implemented", "message": "质检执行 — 待实现"}


@router.post("/batch")
async def run_batch_check(payload: dict):
    """批量质检

    从 antgather 拉取整批数据执行质检。
    TODO: 对接 antgather API 拉取样本，调用 checker 批量执行
    """
    return {"status": "not_implemented", "message": "批量质检 — 待实现"}
