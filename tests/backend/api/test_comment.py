"""
Tests for comment API endpoints
"""

from unittest.mock import patch
from datetime import datetime

import pytest
from fastapi import status


class TestListComments:
    """Test GET /{page_path} endpoint"""

    def test_get_comments_by_page(self, client, test_comment):
        """Test getting approved comments for a page"""
        response = client.get("/api/comment/test-page")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["content"] == "Test comment content"
        assert data[0]["approved"] is True

    def test_get_comments_empty_page(self, client):
        """Test getting comments for page with no comments"""
        response = client.get("/api/comment/non-existent-page")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @patch("web.backend.api.comment.get_comments_by_page")
    def test_get_comments_only_approved(self, mock_get_comments, client, db_session):
        """Test only approved comments are returned"""
        from web.backend.database.models import Comment, User

        user = User(
            username="user2",
            email="user2@example.com",
            hashed_password="hash",
            is_active=True,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        approved_comment = Comment(
            content="Approved comment",
            page_path="/test-page-2",
            user_id=user.id,
            approved=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        pending_comment = Comment(
            content="Pending comment",
            page_path="/test-page-2",
            user_id=user.id,
            approved=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add_all([approved_comment, pending_comment])
        db_session.commit()

        response = client.get("/api/comment/test-page-2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["approved"] is True
        assert data[0]["content"] == "Approved comment"


class TestAddComment:
    """Test POST / endpoint"""

    def test_add_comment_authenticated(self, client, test_user, auth_headers):
        """Test adding comment when authenticated"""
        response = client.post(
            "/api/comment/",
            json={"content": "New test comment", "page_path": "/test-new-page"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["content"] == "New test comment"
        assert data["page_path"] == "/test-new-page"
        assert data["username"] == "testuser"
        assert data["approved"] is False  # New comments require approval

    def test_add_comment_unauthenticated(self, client):
        """Test adding comment without authentication returns 401"""
        response = client.post(
            "/api/comment/",
            json={"content": "New test comment", "page_path": "/test-new"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_comment_invalid_token(self, client):
        """Test adding comment with invalid token returns 401"""
        response = client.post(
            "/api/comment/",
            json={"content": "New test comment", "page_path": "/test-new"},
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_comment_missing_content(self, client, auth_headers):
        """Test adding comment without content returns 422"""
        response = client.post(
            "/api/comment/", json={"page_path": "/test-new"}, headers=auth_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_add_comment_missing_page_path(self, client, auth_headers):
        """Test adding comment without page_path returns 422"""
        response = client.post(
            "/api/comment/", json={"content": "Test content"}, headers=auth_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_add_comment_empty_content(self, client, auth_headers):
        """Test adding comment with empty content"""
        response = client.post(
            "/api/comment/",
            json={"content": "", "page_path": "/test-new"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["content"] == ""
