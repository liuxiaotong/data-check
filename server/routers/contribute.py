"""贡献确权路由"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def calculate_contribution(payload: dict):
    """贡献确权计算

    接收判断数据，计算贡献者权重和确权结果。
    TODO: 接入 datacheck.contribute 核心逻辑
    """
    return {"status": "not_implemented", "message": "贡献确权计算 — 待实现"}


@router.post("/batch")
async def batch_contribution(payload: dict):
    """批量贡献确权

    从 antgather 拉取整批判断数据执行确权计算。
    TODO: 对接 antgather API 拉取判断，调用 contribute 批量计算
    """
    return {"status": "not_implemented", "message": "批量贡献确权 — 待实现"}
