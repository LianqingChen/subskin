"""Tests for auth service"""

import asyncio
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
    get_current_user_optional,
    auth,
    get_required_user,
    SECRET_KEY,
    ALGORITHM,
)
from web.backend.database.models import User


def test_verify_password_correct():
    """Test verify_password with correct password"""
    password = "test_password_123"  # pragma: allowlist secret
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test verify_password with incorrect password"""
    password = "test_password_123"  # pragma: allowlist secret
    wrong_password = "wrong_password"  # pragma: allowlist secret
    hashed = get_password_hash(password)
    assert verify_password(wrong_password, hashed) is False


def test_get_password_hash():
    """Test that password hashing produces consistent results"""
    password = "test_password_123"  # pragma: allowlist secret
    hashed1 = get_password_hash(password)
    hashed2 = get_password_hash(password)

    # Hashes should be different (bcrypt includes salt)
    assert hashed1 != hashed2

    # But both should verify correctly
    assert verify_password(password, hashed1) is True
    assert verify_password(password, hashed2) is True


def test_create_access_token_default_expiry():
    """Test create_access_token with the configured default expiry.

    The default ACCESS_TOKEN_EXPIRE_MINUTES is 10080 (7 days), not 15 minutes —
    the previous assertion expected 15 minutes and failed against the real
    default. Assert against the imported constant so this stays correct if the
    default is reconfigured.
    """
    from web.backend.services.auth import ACCESS_TOKEN_EXPIRE_MINUTES

    data = {"sub": "testuser"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify structure
    from jose import jwt

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser"
    assert "exp" in payload

    # Check expiry is approximately ACCESS_TOKEN_EXPIRE_MINUTES from now.
    # utcfromtimestamp keeps the comparison in UTC (server may run in a non-UTC
    # timezone; fromtimestamp would inject the local offset).
    exp_time = datetime.utcfromtimestamp(payload["exp"])
    now = datetime.utcnow()
    expected_exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    time_diff = abs((exp_time - expected_exp).total_seconds())
    # Allow up to 60 seconds tolerance (7-day expiry → second-level skew is noise)
    assert time_diff < 60


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
    # Use utcfromtimestamp so the expiry is comparable to datetime.utcnow().
    # fromtimestamp() returns local time, which on a non-UTC server (e.g.
    # Asia/Shanghai, UTC+8) introduces an 8-hour offset and makes the assertion
    # fail even though the token expiry is correct.
    exp_time = datetime.utcfromtimestamp(payload["exp"])
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
    password = "test_password_123"  # pragma: allowlist secret
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
    password = "correct_password"  # pragma: allowlist secret
    test_user.hashed_password = get_password_hash(password)
    db_session.commit()

    result = await authenticate_user(test_user.username, "wrong_password", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_valid_token(db_session, test_user):
    """Test get_current_user with valid JWT token"""
    password = "test_password_123"  # pragma: allowlist secret
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
    invalid_token = "invalid.token.string"  # pragma: allowlist secret

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


def test_get_current_user_optional_without_token_returns_none(db_session):
    result = asyncio.run(get_current_user_optional(token=None, db=db_session))
    assert result is None


def test_get_current_user_optional_invalid_token_returns_none(db_session):
    result = asyncio.run(
        get_current_user_optional(token="invalid.token", db=db_session)
    )
    assert result is None


def test_auth_alias():
    """Test that ``auth`` is the required-user dependency.

    ``auth`` is an alias for ``get_required_user`` (the strict 401-raising
    dependency), not ``get_current_user``. Both enforce authentication, but
    ``get_required_user`` is the canonical required-auth dependency used
    across the API.
    """
    assert auth is get_required_user
    assert callable(auth)
