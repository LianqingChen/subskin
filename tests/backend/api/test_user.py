"""
Tests for user API endpoints
"""

import json
from typing import Optional
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

import pytest
from fastapi import status

from web.backend.database.models import User as DBUser, UserCredential


def _create_credential(
    db_session,
    user: DBUser,
    cred_type: str,
    cred_id: str,
    verified: bool = True,
    credential_data: Optional[str] = None,
) -> UserCredential:
    credential = UserCredential(
        user_id=user.id,
        cred_type=cred_type,
        cred_id=cred_id,
        verified=verified,
        credential_data=credential_data,
    )
    db_session.add(credential)
    db_session.commit()
    db_session.refresh(credential)
    return credential


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

        user = db_session.query(DBUser).filter(DBUser.username == "newuser").first()
        assert user is not None
        credentials = (
            db_session.query(UserCredential)
            .filter(UserCredential.user_id == user.id)
            .order_by(UserCredential.cred_type.asc())
            .all()
        )
        assert [credential.cred_type for credential in credentials] == [
            "email",
            "password",
        ]

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
        assert response.json()["detail"] == "注册信息无效，请检查输入"

    def test_register_duplicate_email_returns_generic_error(self, client, test_user):
        response = client.post(
            "/api/user/register",
            json={
                "username": "another-user",
                "email": "test@example.com",
                "password": "newpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "注册信息无效，请检查输入"

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
        mock_send.return_value = (True, "123456")

        response = client.post("/api/user/send-sms", json={"phone": "13800138000"})

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
        mock_send.return_value = (False, "")

        response = client.post("/api/user/send-sms", json={"phone": "13800138000"})

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
                "phone": "13800138000",
                "code": "123456",
                "password": "testpass123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        user = db_session.query(DBUser).filter(DBUser.phone == "13800138000").first()
        assert user is not None
        credentials = (
            db_session.query(UserCredential)
            .filter(UserCredential.user_id == user.id)
            .order_by(UserCredential.cred_type.asc())
            .all()
        )
        assert [credential.cred_type for credential in credentials] == [
            "password",
            "phone",
        ]

    @patch("web.backend.api.user.verify_sms_code")
    def test_register_by_phone_invalid_code(self, mock_verify, client, db_session):
        """Test phone registration with invalid code returns 400"""
        mock_verify.return_value = False

        response = client.post(
            "/api/user/register-by-phone",
            json={
                "phone": "13800138000",
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
        test_user.phone = "13800138000"
        db_session.commit()
        _create_credential(db_session, test_user, "phone", "13800138000")

        mock_verify.return_value = True

        response = client.post(
            "/api/user/register-by-phone",
            json={
                "phone": "13800138000",
                "code": "123456",
                "password": "testpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "该手机号已注册，请直接登录"


class TestLoginByPhone:
    """Test POST /login-by-phone endpoint"""

    @patch("web.backend.api.user.verify_sms_code")
    def test_login_by_phone_valid_code(self, mock_verify, client, db_session):
        """Test successful phone login with valid code"""
        mock_verify.return_value = True

        user = DBUser(username="phone-user", phone="13800138000", is_active=True)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        _create_credential(db_session, user, "phone", "13800138000")

        response = client.post(
            "/api/user/login-by-phone",
            json={"phone": "13800138000", "code": "123456"},
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
            json={"phone": "13800138000", "code": "000000"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "验证码错误或已过期" in response.json()["detail"]

    @patch("web.backend.api.user.verify_sms_code")
    def test_login_by_phone_requires_existing_account(
        self, mock_verify, client, db_session
    ):
        """Test phone login no longer auto-registers new user"""
        mock_verify.return_value = True

        response = client.post(
            "/api/user/login-by-phone",
            json={"phone": "13999999999", "code": "123456"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "该手机号未注册，请先注册"

    def test_login_by_phone_missing_fields(self, client):
        """Test phone login without required fields returns 422"""
        response = client.post(
            "/api/user/login-by-phone", json={"phone": "13800138000"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPasswordAndCredentialFlows:
    @patch("web.backend.api.user.verify_password")
    def test_login_by_phone_password_uses_password_credential(
        self, mock_verify_password, client, db_session, test_user
    ):
        test_user.phone = "13800138000"
        test_user.hashed_password = "stale-backward-compatible-password"
        db_session.commit()
        _create_credential(db_session, test_user, "phone", "13800138000")

        password_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        password_credential.credential_data = json.dumps(
            {"hashed_password": "credential-password-hash"}
        )
        db_session.commit()
        mock_verify_password.return_value = True

        response = client.post(
            "/api/user/login-by-phone-password",
            json={"phone": "13800138000", "password": "testpass123"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_verify_password.assert_called_once_with(
            "testpass123", "credential-password-hash"
        )

    @patch("web.backend.api.user.verify_email_code")
    def test_login_by_email_requires_existing_account(
        self, mock_verify, client, db_session
    ):
        mock_verify.return_value = True

        response = client.post(
            "/api/user/login-by-email",
            json={"email": "missing@example.com", "code": "123456"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "该邮箱未注册，请先注册"

    @patch("web.backend.api.user.verify_password")
    def test_login_by_email_password(
        self, mock_verify_password, client, db_session, test_user
    ):
        password_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        password_credential.credential_data = json.dumps(
            {"hashed_password": "email-password-hash"}
        )
        db_session.commit()
        mock_verify_password.return_value = True

        response = client.post(
            "/api/user/login-by-email-password",
            json={"email": "test@example.com", "password": "testpass123"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_verify_password.assert_called_once_with(
            "testpass123", "email-password-hash"
        )

    @patch("web.backend.api.user.verify_sms_code")
    def test_bind_phone_creates_credential(
        self, mock_verify, client, db_session, test_user, auth_headers
    ):
        mock_verify.return_value = True

        response = client.post(
            "/api/user/bind-phone",
            json={"phone": "13800138000", "code": "123456"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "手机号绑定成功"
        db_session.refresh(test_user)
        assert test_user.phone == "13800138000"

    def test_list_credentials_returns_bound_credentials(
        self, client, db_session, test_user, auth_headers
    ):
        _create_credential(db_session, test_user, "phone", "13800138000")

        response = client.get("/api/user/credentials", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        assert sorted(item["cred_type"] for item in response.json()) == [
            "email",
            "password",
            "phone",
        ]

    def test_unbind_credential_rejects_last_method(
        self, client, db_session, test_user, auth_headers
    ):
        password_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        db_session.delete(password_credential)
        db_session.commit()

        email_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "email",
            )
            .first()
        )

        response = client.delete(
            f"/api/user/credentials/{email_credential.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "无法解绑最后一个登录方式"

    def test_set_password_creates_password_credential(
        self, client, db_session, test_user, auth_headers
    ):
        existing_password = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        db_session.delete(existing_password)
        db_session.commit()

        response = client.post(
            "/api/user/set-password",
            json={"password": "newpass123"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        password_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        assert password_credential is not None
        assert password_credential.credential_data is not None

    @patch("web.backend.api.user.verify_email_code")
    def test_reset_password_updates_password_credential(
        self, mock_verify, client, db_session, test_user
    ):
        mock_verify.return_value = True

        response = client.post(
            "/api/user/reset-password",
            json={
                "credential_id": "test@example.com",
                "cred_type": "email",
                "code": "123456",
                "new_password": "newpass123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        password_credential = (
            db_session.query(UserCredential)
            .filter(
                UserCredential.user_id == test_user.id,
                UserCredential.cred_type == "password",
            )
            .first()
        )
        assert password_credential is not None
        payload = json.loads(password_credential.credential_data)
        assert payload["hashed_password"]


class TestRegisterByEmail:
    @patch("web.backend.api.user.verify_email_code")
    def test_register_by_email_duplicate_username_returns_generic_error(
        self, mock_verify, client, test_user
    ):
        mock_verify.return_value = True

        response = client.post(
            "/api/user/register-by-email",
            json={
                "username": "testuser",
                "email": "fresh@example.com",
                "password": "testpass123",
                "code": "123456",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "注册信息无效，请检查输入"

    @patch("web.backend.api.user.verify_email_code")
    def test_register_by_email_duplicate_email_returns_generic_error(
        self, mock_verify, client, test_user
    ):
        mock_verify.return_value = True

        response = client.post(
            "/api/user/register-by-email",
            json={
                "username": "fresh-user",
                "email": "test@example.com",
                "password": "testpass123",
                "code": "123456",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "该邮箱已注册，请直接登录"
