"""报告生成路由"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def generate_report(payload: dict):
    """生成质量报告

    支持 json / markdown / html 三种输出格式。
    TODO: 接入 datacheck.report 核心逻辑
    """
    return {"status": "not_implemented", "message": "报告生成 — 待实现"}
