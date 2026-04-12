"""
Tests for comment admin API endpoints
"""

from datetime import datetime

import pytest
from fastapi import status


class TestListPendingComments:
    """Test GET /pending endpoint"""

    def test_get_pending_comments_admin(
        self, client, admin_user, admin_headers, db_session
    ):
        """Test admin can get pending comments"""
        from web.backend.database.models import Comment, User

        user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        pending_comment = Comment(
            content="Pending comment",
            page_path="/test-page",
            user_id=user.id,
            approved=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(pending_comment)
        db_session.commit()

        response = client.get("/api/admin/comment/pending", headers=admin_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["content"] == "Pending comment"
        assert data[0]["approved"] is False

    def test_get_pending_comments_non_admin(self, client, test_user, auth_headers):
        """Test non-admin cannot get pending comments"""
        response = client.get("/api/admin/comment/pending", headers=auth_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "需要管理员权限" in response.json()["detail"]

    def test_get_pending_comments_unauthenticated(self, client):
        """Test unauthenticated user cannot get pending comments"""
        response = client.get("/api/admin/comment/pending")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_pending_comments_pagination(
        self, client, admin_user, admin_headers, db_session
    ):
        """Test pagination of pending comments"""
        from web.backend.database.models import Comment, User

        user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        for i in range(5):
            comment = Comment(
                content=f"Pending comment {i}",
                page_path="/test-page",
                user_id=user.id,
                approved=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(comment)
        db_session.commit()

        response = client.get(
            "/api/admin/comment/pending?skip=2&limit=2", headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2


class TestApproveComment:
    """Test POST /{comment_id}/approve endpoint"""

    def test_approve_comment_admin(self, client, admin_user, admin_headers, db_session):
        """Test admin can approve a comment"""
        from web.backend.database.models import Comment, User

        user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        comment = Comment(
            content="Pending comment",
            page_path="/test-page",
            user_id=user.id,
            approved=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(comment)
        db_session.commit()

        response = client.post(
            f"/api/admin/comment/{comment.id}/approve?approved=true",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["approved"] is True

        db_session.refresh(comment)
        assert comment.approved is True

    def test_reject_comment_admin(self, client, admin_user, admin_headers, db_session):
        """Test admin can reject a comment"""
        from web.backend.database.models import Comment, User

        user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        comment = Comment(
            content="Pending comment",
            page_path="/test-page",
            user_id=user.id,
            approved=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(comment)
        db_session.commit()

        response = client.post(
            f"/api/admin/comment/{comment.id}/approve?approved=false",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["approved"] is False

        db_session.refresh(comment)
        assert comment.approved is False

    def test_approve_comment_non_admin(self, client, test_user, auth_headers):
        """Test non-admin cannot approve comments"""
        response = client.post("/api/admin/comment/1/approve", headers=auth_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "需要管理员权限" in response.json()["detail"]

    def test_approve_comment_unauthenticated(self, client):
        """Test unauthenticated user cannot approve comments"""
        response = client.post("/api/admin/comment/1/approve")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_approve_non_existent_comment(self, client, admin_user, admin_headers):
        """Test approving non-existent comment returns 404"""
        response = client.post(
            "/api/admin/comment/99999/approve", headers=admin_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "评论不存在" in response.json()["detail"]

    def test_approve_comment_default_approved(
        self, client, admin_user, admin_headers, db_session
    ):
        """Test approve endpoint defaults to approved=true"""
        from web.backend.database.models import Comment, User

        user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        comment = Comment(
            content="Pending comment",
            page_path="/test-page",
            user_id=user.id,
            approved=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(comment)
        db_session.commit()

        response = client.post(
            f"/api/admin/comment/{comment.id}/approve", headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["approved"] is True
