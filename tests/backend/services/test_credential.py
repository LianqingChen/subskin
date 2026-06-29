"""Tests for credential service."""

import json
from typing import cast

import pytest
from fastapi import HTTPException

from web.backend.exceptions import CredentialConflictError
from web.backend.database.models import UserCredential
from web.backend.services.auth import get_password_hash
from web.backend.services.credential import (
    bind_credential,
    find_credential,
    find_user_by_credential,
    get_user_credentials,
    unbind_credential,
    user_has_password,
    verify_credential,
)


def test_bind_credential_creates_record(db_session, test_user):
    credential = bind_credential(db_session, test_user.id, "phone", "13800138000")
    found_user = find_user_by_credential(db_session, "phone", "13800138000")

    assert credential.id is not None
    assert credential.user_id == test_user.id
    assert cast(str, cast(object, credential.cred_type)) == "phone"
    assert cast(str, cast(object, credential.cred_id)) == "13800138000"
    assert found_user is not None
    assert cast(int, cast(object, found_user.id)) == test_user.id


def test_bind_credential_rejects_taken_identifier(
    db_session, test_user, test_admin_user
):
    db_session.add(
        UserCredential(
            user_id=test_admin_user.id,
            cred_type="phone",
            cred_id="13800138000",
            verified=True,
        )
    )
    db_session.commit()

    # bind_credential raises a domain CredentialConflictError (the API layer
    # converts it to HTTP 400). The service contract is the domain exception,
    # not HTTPException directly.
    with pytest.raises(CredentialConflictError) as exc_info:
        bind_credential(db_session, test_user.id, "phone", "13800138000")

    assert "已绑定其他账号" in str(exc_info.value)


def test_bind_credential_rejects_duplicate_type_for_same_user(db_session, test_user):
    bind_credential(db_session, test_user.id, "phone", "13800138000")

    with pytest.raises(CredentialConflictError) as exc_info:
        bind_credential(db_session, test_user.id, "phone", "13900139000")

    assert "您已绑定" in str(exc_info.value)


def test_unbind_credential_rejects_last_login_method(db_session, test_user):
    password_credential = find_credential(db_session, test_user.id, "password")
    db_session.delete(password_credential)
    db_session.commit()

    only_credential = find_credential(db_session, test_user.id, "email")

    assert only_credential is not None
    assert (
        unbind_credential(
            db_session, cast(int, cast(object, only_credential.id)), test_user.id
        )
        is False
    )


def test_unbind_credential_deletes_when_user_has_multiple_methods(
    db_session, test_user
):
    phone_credential = bind_credential(db_session, test_user.id, "phone", "13800138000")

    assert (
        unbind_credential(
            db_session, cast(int, cast(object, phone_credential.id)), test_user.id
        )
        is True
    )
    assert (
        db_session.query(UserCredential)
        .filter(UserCredential.id == phone_credential.id)
        .first()
        is None
    )


def test_verify_and_password_helpers(db_session, test_user):
    password_credential = find_credential(db_session, test_user.id, "password")
    db_session.delete(password_credential)
    db_session.commit()

    password_hash = get_password_hash("new-password-123")
    password_credential = bind_credential(
        db_session,
        test_user.id,
        "password",
        "password",
        credential_data=json.dumps({"hashed_password": password_hash}),
    )

    assert user_has_password(db_session, test_user.id) is True
    assert (
        verify_credential(db_session, cast(int, cast(object, password_credential.id)))
        is True
    )
    db_session.refresh(password_credential)
    assert password_credential.verified is True
    assert len(get_user_credentials(db_session, test_user.id)) == 2
