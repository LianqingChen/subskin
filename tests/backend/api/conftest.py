"""Test fixtures for backend API tests"""

from datetime import datetime, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from web.backend.app.main import app
from web.backend.database.database import Base, get_db
from web.backend.database.models import User, Comment, Document


# Test database (in-memory SQLite)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with mocked database session"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user"""
    from web.backend.services.auth import get_password_hash

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an admin user"""
    from web.backend.services.auth import get_password_hash

    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        is_admin=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_comment(db_session: Session, test_user: User) -> Comment:
    """Create a test comment"""
    comment = Comment(
        content="Test comment content",
        page_path="/test-page",
        user_id=test_user.id,
        approved=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)
    return comment


@pytest.fixture
def test_document(db_session: Session) -> Document:
    """Create a test document"""
    doc = Document(
        title="Test Document",
        content="Test document content for RAG",
        source="test",
        source_url="https://example.com/test",
        category="test",
        embedding="[]",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict:
    """Get authentication headers for test user"""
    from jose import jwt
    import os

    # Create JWT token manually
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    expires_delta = timedelta(minutes=30)
    expire = datetime.utcnow() + expires_delta

    payload = {"sub": test_user.username, "exp": expire.timestamp()}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict:
    """Get authentication headers for admin user"""
    from jose import jwt
    import os

    # Create JWT token manually
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    expires_delta = timedelta(minutes=30)
    expire = datetime.utcnow() + expires_delta

    payload = {"sub": admin_user.username, "exp": expire.timestamp()}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"Authorization": f"Bearer {token}"}
