"""
内容相关 API
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Document

router = APIRouter()


@router.get("/latest")
async def get_latest(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取最新更新文档列表
    
    Args:
        limit: Maximum number of documents to return (default: 10)
    
    Returns:
        List of latest documents ordered by update time
    """
    latest_docs = (
        db.query(Document)
        .order_by(desc(Document.updated_at))
        .limit(limit)
        .all()
    )
    
    result = []
    for doc in latest_docs:
        result.append({
            "id": doc.id,
            "title": doc.title,
            "source": doc.source,
            "source_url": doc.source_url,
            "category": doc.category,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        })
    
    return {
        "count": len(result),
        "latest": result
    }
