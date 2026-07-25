"""
内容相关 API
"""

import os
import glob
import re
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Document

router = APIRouter()

BRIEFING_DIR = "/root/subskin/data/briefings"


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


@router.get("/daily-briefing")
async def get_daily_briefing():
    """获取最新每日研究简报（今日必读）
    
    Returns:
        最新简报的日期、标题和统计信息
    """
    if not os.path.exists(BRIEFING_DIR):
        return {"available": False, "briefing": None}
    
    files = sorted(glob.glob(os.path.join(BRIEFING_DIR, "daily_*.md")), reverse=True)
    if not files:
        return {"available": False, "briefing": None}
    
    latest_file = files[0]
    fname = os.path.basename(latest_file)
    date_str = fname.replace("daily_", "").replace(".md", "")
    
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse statistics from content
        stats = []
        total_match = re.search(r"今日共新增/更新.*?(\d+)", content)
        total = int(total_match.group(1)) if total_match else 0
        
        # Extract source lines
        for line in content.split("\n"):
            if "**" in line and "+" in line:
                # Parse: S/A 📜 **PubMed 权威研究论文**: +7314
                match = re.search(r"\*\*(.+?)\*\*.*?\+(\d+)", line)
                if match:
                    stats.append({
                        "source": match.group(1),
                        "count": int(match.group(2)),
                    })
        
        return {
            "available": True,
            "briefing": {
                "date": date_str,
                "total": total,
                "stats": stats[:5],  # Top 5 sources
                "summary": f"今日新增 {total} 项白癜风相关研究进展",
            }
        }
    except Exception:
        return {"available": False, "briefing": None}


@router.get("/timeline")
async def get_research_timeline(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取研究进展时间线
    
    按时间聚合文档数据，展示研究进展时间线
    """
    from sqlalchemy import func
    
    # Get documents grouped by month
    results = (
        db.query(
            func.strftime('%Y-%m', Document.created_at).label('month'),
            func.count(Document.id).label('count'),
        )
        .group_by('month')
        .order_by(func.strftime('%Y-%m', Document.created_at).desc())
        .limit(limit)
        .all()
    )
    
    timeline = []
    for row in results:
        # Get sample documents for this month
        month_start = row.month + "-01"
        sample_docs = (
            db.query(Document)
            .filter(func.strftime('%Y-%m', Document.created_at) == row.month)
            .order_by(desc(Document.created_at))
            .limit(3)
            .all()
        )
        
        timeline.append({
            "month": row.month,
            "count": row.count,
            "highlights": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "source": doc.source,
                    "category": doc.category,
                }
                for doc in sample_docs
            ]
        })
    
    return {"timeline": timeline}
