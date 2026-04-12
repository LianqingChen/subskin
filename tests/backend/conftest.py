"""
Shared fixtures for backend service tests
"""

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from web.backend.database.database import Base
from web.backend.database.models import (
    User,
    Comment,
    SMSCode,
    Document,
    Conversation,
    Message,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database session for testing"""
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$test_hashed_password_for_testing",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_user(db_session: Session) -> User:
    """Create a test admin user"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password="$2b$12$admin_hashed_password_for_testing",
        is_active=True,
        is_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_comment(db_session: Session, test_user: User) -> Comment:
    """Create a test comment"""
    comment = Comment(
        content="Test comment content",
        page_path="/test/page",
        user_id=test_user.id,
        approved=True,
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)
    return comment


@pytest.fixture
def test_pending_comment(db_session: Session, test_user: User) -> Comment:
    """Create a pending comment (not approved)"""
    comment = Comment(
        content="Pending comment content",
        page_path="/test/page",
        user_id=test_user.id,
        approved=False,
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)
    return comment


@pytest.fixture
def test_sms_code(db_session: Session) -> SMSCode:
    """Create a test SMS code"""
    from datetime import datetime, timedelta

    sms_code = SMSCode(
        phone="13800138000",
        code="123456",
        expired_at=datetime.utcnow() + timedelta(minutes=5),
        used=False,
    )
    db_session.add(sms_code)
    db_session.commit()
    db_session.refresh(sms_code)
    return sms_code


@pytest.fixture
def test_expired_sms_code(db_session: Session) -> SMSCode:
    """Create an expired SMS code"""
    from datetime import datetime, timedelta

    sms_code = SMSCode(
        phone="13800138001",
        code="654321",
        expired_at=datetime.utcnow() - timedelta(minutes=5),
        used=False,
    )
    db_session.add(sms_code)
    db_session.commit()
    db_session.refresh(sms_code)
    return sms_code


@pytest.fixture
def test_document(db_session: Session) -> Document:
    """Create a test document"""
    document = Document(
        title="Test Document",
        content="Test content for testing RAG functionality",
        source="Test Source",
        source_url="https://example.com/test",
        category="test",
        embedding="[0.1, 0.2, 0.3, 0.4, 0.5]",
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture
def mock_openai_client() -> Generator[MagicMock, None, None]:
    """Mock OpenAI client for testing RAG functions"""
    with patch("web.backend.services.rag.openai.OpenAI") as mock_openai:
        mock_client = MagicMock()

        # Mock embeddings.create
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5])]
        mock_client.embeddings.create.return_value = mock_embedding_response

        # Mock chat.completions.create
        mock_chat_response = MagicMock()
        mock_chat_response.choices = [
            MagicMock(message=MagicMock(content="Test answer"))
        ]
        mock_client.chat.completions.create.return_value = mock_chat_response

        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_sms_send() -> Generator[MagicMock, None, None]:
    """Mock SMS sending for testing"""
    with patch("web.backend.services.sms.send_sms") as mock_send:
        mock_send.return_value = True
        yield mock_send


@pytest.fixture
def set_test_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set test environment variables"""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
    monkeypatch.setenv("ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("SMS_PROVIDER", "log")
