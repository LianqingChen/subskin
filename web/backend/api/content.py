"""
内容相关 API
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/latest")
async def get_latest():
    """获取最新内容列表"""
    return {"message": "not implemented yet"}
