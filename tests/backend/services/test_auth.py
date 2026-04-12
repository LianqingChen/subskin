"""
Tests for auth service
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from web.backend.services.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_current_user,
    auth,
    SECRET_KEY,
    ALGORITHM,
)
from web.backend.database.models import User


def test_verify_password_correct():
    """Test verify_password with correct password"""
    password = "test_password_123"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test verify_password with incorrect password"""
    password = "test_password_123"
    wrong_password = "wrong_password"
    hashed = get_password_hash(password)
    assert verify_password(wrong_password, hashed) is False


def test_get_password_hash():
    """Test that password hashing produces consistent results"""
    password = "test_password_123"
    hashed1 = get_password_hash(password)
    hashed2 = get_password_hash(password)

    # Hashes should be different (bcrypt includes salt)
    assert hashed1 != hashed2

    # But both should verify correctly
    assert verify_password(password, hashed1) is True
    assert verify_password(password, hashed2) is True


def test_create_access_token_default_expiry():
    """Test create_access_token with default expiry (15 minutes)"""
    data = {"sub": "testuser"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify structure
    from jose import jwt

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser"
    assert "exp" in payload

    # Check expiry is approximately 15 minutes from now
    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    expected_exp = now + timedelta(minutes=15)
    time_diff = abs((exp_time - expected_exp).total_seconds())
    assert time_diff < 5  # Allow 5 seconds tolerance


def test_create_access_token_custom_expiry():
    """Test create_access_token with custom expiry"""
    data = {"sub": "testuser"}
    custom_delta = timedelta(hours=2)
    token = create_access_token(data, expires_delta=custom_delta)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify expiry
    from jose import jwt

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    expected_exp = now + custom_delta
    time_diff = abs((exp_time - expected_exp).total_seconds())
    assert time_diff < 5  # Allow 5 seconds tolerance


def test_create_access_token_multiple_fields():
    """Test create_access_token with multiple fields"""
    data = {"sub": "testuser", "user_id": 123, "role": "admin"}
    token = create_access_token(data)

    # Decode and verify all fields
    from jose import jwt

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser"
    assert payload["user_id"] == 123
    assert payload["role"] == "admin"
    assert "exp" in payload


@pytest.mark.asyncio
async def test_authenticate_user_valid_credentials(db_session, test_user):
    """Test authenticate_user with valid username and password"""
    # Create user with known password
    password = "test_password_123"
    test_user.hashed_password = get_password_hash(password)
    db_session.commit()

    result = await authenticate_user(test_user.username, password, db_session)
    assert result is not None
    assert result.username == test_user.username
    assert result.id == test_user.id


@pytest.mark.asyncio
async def test_authenticate_user_invalid_username(db_session):
    """Test authenticate_user with non-existent username"""
    result = await authenticate_user("nonexistent", "password", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(db_session, test_user):
    """Test authenticate_user with wrong password"""
    password = "correct_password"
    test_user.hashed_password = get_password_hash(password)
    db_session.commit()

    result = await authenticate_user(test_user.username, "wrong_password", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_valid_token(db_session, test_user):
    """Test get_current_user with valid JWT token"""
    password = "test_password_123"
    test_user.hashed_password = get_password_hash(password)
    db_session.commit()

    # Create valid token
    token = create_access_token({"sub": test_user.username})

    # Mock the dependency injection
    user = await get_current_user(token=token, db=db_session)
    assert user is not None
    assert user.username == test_user.username
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    """Test get_current_user with invalid JWT token"""
    invalid_token = "invalid.token.string"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=invalid_token, db=db_session)

    assert exc_info.value.status_code == 401
    assert "无法验证凭据" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_expired_token(db_session, test_user):
    """Test get_current_user with expired token"""
    # Create expired token (negative expiry)
    expired_delta = timedelta(minutes=-1)
    token = create_access_token(
        {"sub": test_user.username}, expires_delta=expired_delta
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401
    assert "无法验证凭据" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_nonexistent_user(db_session):
    """Test get_current_user with token for non-existent user"""
    token = create_access_token({"sub": "nonexistent_user"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401
    assert "无法验证凭据" in exc_info.value.detail


def test_auth_alias():
    """Test that auth is an alias for get_current_user"""
    assert auth is get_current_user
