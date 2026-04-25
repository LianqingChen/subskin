"""
社交关系 API：关注/取关/拉黑/举报
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, UserFollow, UserBlock, UserReport
from web.backend.services.auth import auth

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_target_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("/follow/{user_id}")
async def follow_user(
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """关注用户"""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能关注自己")

    _validate_target_user(db, user_id)

    # 检查是否已拉黑
    existing_block = (
        db.query(UserBlock)
        .filter_by(blocker_id=current_user.id, blocked_id=user_id)
        .first()
    )
    if existing_block:
        raise HTTPException(status_code=400, detail="不能关注已拉黑的用户")

    existing = (
        db.query(UserFollow)
        .filter_by(followee_id=user_id, follower_id=current_user.id)
        .first()
    )
    if existing:
        return {"status": "ok", "message": "已关注"}

    follow = UserFollow(followee_id=user_id, follower_id=current_user.id)
    db.add(follow)
    db.commit()
    return {"status": "ok", "message": "关注成功"}


@router.delete("/follow/{user_id}")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """取消关注"""
    follow = (
        db.query(UserFollow)
        .filter_by(followee_id=user_id, follower_id=current_user.id)
        .first()
    )
    if not follow:
        raise HTTPException(status_code=404, detail="未关注该用户")

    db.delete(follow)
    db.commit()
    return {"status": "ok", "message": "已取消关注"}


@router.get("/follow/following")
async def list_following(
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """我关注的用户列表"""
    follows = (
        db.query(UserFollow)
        .filter_by(follower_id=current_user.id)
        .order_by(UserFollow.created_at.desc())
        .all()
    )
    result = []
    for f in follows:
        user = db.query(User).filter_by(id=f.followee_id).first()
        if user:
            result.append({
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar_url,
                "followed_at": f.created_at.isoformat() if f.created_at else None,
            })
    return {"items": result, "total": len(result)}


@router.get("/follow/followers")
async def list_followers(
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """关注我的用户列表"""
    follows = (
        db.query(UserFollow)
        .filter_by(followee_id=current_user.id)
        .order_by(UserFollow.created_at.desc())
        .all()
    )
    result = []
    for f in follows:
        user = db.query(User).filter_by(id=f.follower_id).first()
        if user:
            result.append({
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar_url,
                "followed_at": f.created_at.isoformat() if f.created_at else None,
            })
    return {"items": result, "total": len(result)}


@router.post("/block/{user_id}")
async def block_user(
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """拉黑用户（自动取关）"""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能拉黑自己")

    _validate_target_user(db, user_id)

    existing = (
        db.query(UserBlock)
        .filter_by(blocker_id=current_user.id, blocked_id=user_id)
        .first()
    )
    if existing:
        return {"status": "ok", "message": "已拉黑"}

    # 自动取关（双向）
    follow = (
        db.query(UserFollow)
        .filter_by(followee_id=user_id, follower_id=current_user.id)
        .first()
    )
    if follow:
        db.delete(follow)
    reverse_follow = (
        db.query(UserFollow)
        .filter_by(followee_id=current_user.id, follower_id=user_id)
        .first()
    )
    if reverse_follow:
        db.delete(reverse_follow)

    block = UserBlock(blocker_id=current_user.id, blocked_id=user_id)
    db.add(block)
    db.commit()
    return {"status": "ok", "message": "已拉黑"}


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """取消拉黑"""
    block = (
        db.query(UserBlock)
        .filter_by(blocker_id=current_user.id, blocked_id=user_id)
        .first()
    )
    if not block:
        raise HTTPException(status_code=404, detail="未拉黑该用户")

    db.delete(block)
    db.commit()
    return {"status": "ok", "message": "已取消拉黑"}


@router.get("/block/list")
async def list_blocked(
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """已拉黑用户列表"""
    blocks = (
        db.query(UserBlock)
        .filter_by(blocker_id=current_user.id)
        .order_by(UserBlock.created_at.desc())
        .all()
    )
    result = []
    for b in blocks:
        user = db.query(User).filter_by(id=b.blocked_id).first()
        if user:
            result.append({
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar_url,
                "blocked_at": b.created_at.isoformat() if b.created_at else None,
            })
    return {"items": result, "total": len(result)}


@router.post("/report")
async def report_user(
    target_user_id: int,
    reason: str,
    post_id: int = None,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """举报用户"""
    if current_user.id == target_user_id:
        raise HTTPException(status_code=400, detail="不能举报自己")

    _validate_target_user(db, target_user_id)

    report = UserReport(
        reporter_id=current_user.id,
        target_user_id=target_user_id,
        post_id=post_id,
        reason=reason,
    )
    db.add(report)
    db.commit()
    return {"status": "ok", "message": "举报已提交"}
