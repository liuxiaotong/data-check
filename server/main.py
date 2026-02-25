"""data-check 在线服务 — FastAPI 应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import check, contribute, report, fix

app = FastAPI(
    title="data-check API",
    version="0.1.0",
    description="数据质检、贡献确权、报告生成、数据修复",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(check.router, prefix="/api/check", tags=["check"])
app.include_router(contribute.router, prefix="/api/contribute", tags=["contribute"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(fix.router, prefix="/api/fix", tags=["fix"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "data-check", "version": settings.version}
