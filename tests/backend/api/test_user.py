"""
Tests for user API endpoints
"""

from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

import pytest
from fastapi import status


class TestLogin:
    """Test POST /login endpoint"""

    def test_login_valid_credentials(self, client, test_user):
        """Test successful login with valid credentials"""
        with patch("web.backend.api.user.authenticate_user") as mock_auth:
            mock_auth.return_value = test_user

            response = client.post(
                "/api/user/login",
                data={"username": "testuser", "password": "testpass123"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            mock_auth.assert_called_once()

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials returns 401"""
        with patch("web.backend.api.user.authenticate_user") as mock_auth:
            mock_auth.return_value = None

            response = client.post(
                "/api/user/login",
                data={"username": "wronguser", "password": "wrongpass"},
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "用户名或密码错误" in response.json()["detail"]
            mock_auth.assert_called_once()

    def test_login_missing_username(self, client):
        """Test login with missing username returns 422"""
        response = client.post("/api/user/login", data={"password": "testpass123"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetCurrentUser:
    """Test GET /me endpoint"""

    def test_get_current_user_authenticated(self, client, test_user, auth_headers):
        """Test getting current user info when authenticated"""
        response = client.get("/api/user/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True

    def test_get_current_user_unauthenticated(self, client):
        """Test getting current user without authentication returns 401"""
        response = client.get("/api/user/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token returns 401"""
        response = client.get(
            "/api/user/me", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRegister:
    """Test POST /register endpoint"""

    def test_register_new_user(self, client, db_session):
        """Test successful registration of new user"""
        response = client.post(
            "/api/user/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpass123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["is_active"] is True

    def test_register_duplicate_username(self, client, test_user):
        """Test registration with duplicate username returns 400"""
        response = client.post(
            "/api/user/register",
            json={
                "username": "testuser",
                "email": "another@example.com",
                "password": "newpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "用户名已存在" in response.json()["detail"]

    def test_register_missing_fields(self, client):
        """Test registration with missing required fields returns 422"""
        response = client.post("/api/user/register", json={"username": "newuser"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSendSMS:
    """Test POST /send-sms endpoint"""

    @patch("web.backend.api.user.send_sms")
    @patch("web.backend.api.user.create_sms_code")
    def test_send_sms_success(self, mock_create_code, mock_send, client, db_session):
        """Test successful SMS code sending"""
        mock_create_code.return_value = "123456"
        mock_send.return_value = True

        response = client.post("/api/user/send-sms", json={"phone": "+8613800138000"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        mock_create_code.assert_called_once()
        mock_send.assert_called_once()

    @patch("web.backend.api.user.send_sms")
    @patch("web.backend.api.user.create_sms_code")
    def test_send_sms_failure(self, mock_create_code, mock_send, client, db_session):
        """Test SMS sending failure returns 500"""
        mock_create_code.return_value = "123456"
        mock_send.return_value = False

        response = client.post("/api/user/send-sms", json={"phone": "+8613800138000"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "短信发送失败" in response.json()["detail"]

    def test_send_sms_missing_phone(self, client):
        """Test sending SMS without phone number returns 422"""
        response = client.post("/api/user/send-sms", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRegisterByPhone:
    """Test POST /register-by-phone endpoint"""

    @patch("web.backend.api.user.verify_sms_code")
    def test_register_by_phone_valid_code(self, mock_verify, client, db_session):
        """Test successful phone registration with valid code"""
        mock_verify.return_value = True

        response = client.post(
            "/api/user/register-by-phone",
            json={
                "phone": "+8613800138000",
                "code": "123456",
                "password": "testpass123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @patch("web.backend.api.user.verify_sms_code")
    def test_register_by_phone_invalid_code(self, mock_verify, client, db_session):
        """Test phone registration with invalid code returns 400"""
        mock_verify.return_value = False

        response = client.post(
            "/api/user/register-by-phone",
            json={
                "phone": "+8613800138000",
                "code": "000000",
                "password": "testpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "验证码错误或已过期" in response.json()["detail"]

    @patch("web.backend.api.user.verify_sms_code")
    def test_register_by_phone_duplicate_phone(
        self, mock_verify, client, db_session, test_user
    ):
        """Test phone registration with existing phone number returns 400"""
        test_user.phone = "+8613800138000"
        db_session.commit()

        mock_verify.return_value = True

        response = client.post(
            "/api/user/register-by-phone",
            json={
                "phone": "+8613800138000",
                "code": "123456",
                "password": "testpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "该手机号已注册" in response.json()["detail"]


class TestLoginByPhone:
    """Test POST /login-by-phone endpoint"""

    @patch("web.backend.api.user.verify_sms_code")
    def test_login_by_phone_valid_code(self, mock_verify, client, db_session):
        """Test successful phone login with valid code"""
        mock_verify.return_value = True

        response = client.post(
            "/api/user/login-by-phone",
            json={"phone": "+8613800138000", "code": "123456"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @patch("web.backend.api.user.verify_sms_code")
    def test_login_by_phone_invalid_code(self, mock_verify, client, db_session):
        """Test phone login with invalid code returns 401"""
        mock_verify.return_value = False

        response = client.post(
            "/api/user/login-by-phone",
            json={"phone": "+8613800138000", "code": "000000"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "验证码错误或已过期" in response.json()["detail"]

    @patch("web.backend.api.user.verify_sms_code")
    def test_login_by_phone_auto_register(self, mock_verify, client, db_session):
        """Test phone login auto-registers new user"""
        mock_verify.return_value = True

        response = client.post(
            "/api/user/login-by-phone",
            json={"phone": "+8613999999999", "code": "123456"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

    def test_login_by_phone_missing_fields(self, client):
        """Test phone login without required fields returns 422"""
        response = client.post(
            "/api/user/login-by-phone", json={"phone": "+8613800138000"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
