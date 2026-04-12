"""
Tests for comment service
"""

from datetime import datetime, timedelta

import pytest

from web.backend.services.comment import (
    get_comments_by_page,
    create_comment,
    get_pending_comments,
    approve_comment,
)
from web.backend.database.models import Comment, User
from web.backend.models.comment import CommentCreate


def test_get_comments_by_page_approved_only(
    db_session, test_comment, test_pending_comment
):
    """Test that get_comments_by_page only returns approved comments"""
    comments = get_comments_by_page(db_session, "/test/page")

    assert len(comments) == 1
    assert comments[0].id == test_comment.id
    assert comments[0].approved is True


def test_get_comments_by_page_different_pages(db_session, test_comment, test_user):
    """Test that get_comments_by_page filters by page_path"""
    # Create comment on different page
    other_comment = Comment(
        content="Other page comment",
        page_path="/other/page",
        user_id=test_user.id,
        approved=True,
    )
    db_session.add(other_comment)
    db_session.commit()

    comments = get_comments_by_page(db_session, "/test/page")
    assert len(comments) == 1
    assert comments[0].page_path == "/test/page"

    other_comments = get_comments_by_page(db_session, "/other/page")
    assert len(other_comments) == 1
    assert other_comments[0].page_path == "/other/page"


def test_get_comments_by_page_empty(db_session):
    """Test that get_comments_by_page returns empty list for pages with no comments"""
    comments = get_comments_by_page(db_session, "/nonexistent/page")
    assert len(comments) == 0


def test_get_comments_by_page_ordering(db_session, test_user):
    """Test that get_comments_by_page returns comments in descending order by created_at"""
    older_comment = Comment(
        content="Older comment",
        page_path="/test/page",
        user_id=test_user.id,
        approved=True,
        created_at=datetime.utcnow() - timedelta(hours=2),
    )
    db_session.add(older_comment)
    db_session.commit()

    newer_comment = Comment(
        content="Newer comment",
        page_path="/test/page",
        user_id=test_user.id,
        approved=True,
        created_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(newer_comment)
    db_session.commit()

    comments = get_comments_by_page(db_session, "/test/page")
    assert len(comments) == 2
    assert comments[0].content == "Newer comment"
    assert comments[1].content == "Older comment"


def test_create_comment_default_pending(db_session, test_user):
    """Test that create_comment creates pending comment by default"""
    comment_data = CommentCreate(content="New comment", page_path="/test/page")

    result = create_comment(db_session, comment_data, test_user)

    assert result.id is not None
    assert result.content == "New comment"
    assert result.page_path == "/test/page"
    assert result.user_id == test_user.id
    assert result.username == test_user.username
    assert result.approved is False  # Default is pending


def test_create_comment_saves_to_db(db_session, test_user):
    """Test that create_comment actually saves to database"""
    comment_data = CommentCreate(content="Test comment", page_path="/test/page")

    result = create_comment(db_session, comment_data, test_user)

    # Verify it exists in database
    db_comment = db_session.query(Comment).filter(Comment.id == result.id).first()
    assert db_comment is not None
    assert db_comment.content == "Test comment"
    assert db_comment.approdi is False


def test_create_comment_user_username(db_session, test_user):
    """Test that create_comment includes username from user"""
    test_user.username = "custom_username"
    db_session.commit()

    comment_data = CommentCreate(content="Comment", page_path="/test/page")

    result = create_comment(db_session, comment_data, test_user)
    assert result.username == "custom_username"


def test_get_pending_comments_only_unapproved(
    db_session, test_comment, test_pending_comment
):
    """Test that get_pending_comments only returns unapproved comments"""
    pending = get_pending_comments(db_session)

    assert len(pending) == 1
    assert pending[0].id == test_pending_comment.id
    assert pending[0].approved is False


def test_get_pending_comments_pagination(db_session, test_user):
    """Test get_pending_comments with skip and limit"""
    # Create multiple pending comments
    for i in range(5):
        comment = Comment(
            content=f"Pending comment {i}",
            page_path="/test/page",
            user_id=test_user.id,
            approved=False,
        )
        db_session.add(comment)
    db_session.commit()

    # Test pagination
    page1 = get_pending_comments(db_session, skip=0, limit=2)
    assert len(page1) == 2

    page2 = get_pending_comments(db_session, skip=2, limit=2)
    assert len(page2) == 2

    page3 = get_pending_comments(db_session, skip=4, limit=2)
    assert len(page3) == 1


def test_get_pending_comments_ordering(db_session, test_user):
    """Test that get_pending_comments returns in descending order by created_at"""
    older = Comment(
        content="Older pending",
        page_path="/test/page",
        user_id=test_user.id,
        approved=False,
        created_at=datetime.utcnow() - timedelta(hours=2),
    )
    db_session.add(older)
    db_session.commit()

    newer = Comment(
        content="Newer pending",
        page_path="/test/page",
        user_id=test_user.id,
        approved=False,
        created_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(newer)
    db_session.commit()

    pending = get_pending_comments(db_session)
    assert len(pending) >= 2
    # First should be newer
    assert pending[0].created_at >= pending[1].created_at


def test_approve_comment_approve(db_session, test_pending_comment):
    """Test that approve_comment sets approved=True"""
    result = approve_comment(db_session, test_pending_comment.id, approved=True)

    assert result is not None
    assert result.approved is True

    # Verify in database
    db_session.refresh(result)
    assert result.approved is True


def test_approve_comment_reject(db_session, test_pending_comment):
    """Test that approve_comment can set approved=False"""
    result = approve_comment(db_session, test_pending_comment.id, approved=False)

    assert result is not None
    assert result.approved is False


def test_approve_comment_default_is_approve(db_session, test_pending_comment):
    """Test that approve_comment defaults to approved=True"""
    result = approve_comment(db_session, test_pending_comment.id)

    assert result is not None
    assert result.approved is True


def test_approve_comment_nonexistent(db_session):
    """Test that approve_comment returns None for non-existent comment"""
    result = approve_comment(db_session, 99999)
    assert result is None


def test_approve_comment_already_approved(db_session, test_comment):
    """Test that approve_comment works on already approved comment"""
    assert test_comment.approved is True

    result = approve_comment(db_session, test_comment.id, approved=False)
    assert result.approved is False
