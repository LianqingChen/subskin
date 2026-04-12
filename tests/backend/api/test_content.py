"""
Tests for content API endpoints
"""

from datetime import datetime

import pytest
from fastapi import status


class TestGetLatestContent:
    """Test GET /latest endpoint"""

    def test_get_latest_default_limit(self, client, db_session, test_document):
        """Test getting latest content with default limit"""
        from web.backend.database.models import Document

        doc2 = Document(
            title="Second Document",
            content="Second document content",
            source="test",
            source_url="https://example.com/doc2",
            category="test",
            embedding="[]",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(doc2)
        db_session.commit()

        response = client.get("/api/content/latest")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert "latest" in data
        assert isinstance(data["latest"], list)
        assert len(data["latest"]) == 2

    def test_get_latest_custom_limit(self, client, db_session, test_document):
        """Test getting latest content with custom limit"""
        from web.backend.database.models import Document

        for i in range(5):
            doc = Document(
                title=f"Document {i}",
                content=f"Content {i}",
                source="test",
                source_url=f"https://example.com/doc{i}",
                category="test",
                embedding="[]",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(doc)
        db_session.commit()

        response = client.get("/api/content/latest?limit=3")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["latest"]) == 3

    def test_get_latest_empty_database(self, client, db_session):
        """Test getting latest content from empty database"""
        response = client.get("/api/content/latest")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["latest"] == []

    def test_get_latest_zero_limit(self, client, db_session, test_document):
        """Test getting latest content with limit=0"""
        response = client.get("/api/content/latest?limit=0")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["latest"] == []

    def test_get_latest_large_limit(self, client, db_session, test_document):
        """Test getting latest content with large limit"""
        from web.backend.database.models import Document

        for i in range(20):
            doc = Document(
                title=f"Document {i}",
                content=f"Content {i}",
                source="test",
                source_url=f"https://example.com/doc{i}",
                category="test",
                embedding="[]",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(doc)
        db_session.commit()

        response = client.get("/api/content/latest?limit=100")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["latest"]) > 0

    def test_get_latest_response_structure(self, client, db_session, test_document):
        """Test latest content response has correct structure"""
        response = client.get("/api/content/latest")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "count" in data
        assert "latest" in data

        if len(data["latest"]) > 0:
            doc = data["latest"][0]
            assert "id" in doc
            assert "title" in doc
            assert "source" in doc
            assert "source_url" in doc
            assert "category" in doc
            assert "created_at" in doc
            assert "updated_at" in doc

    def test_get_latest_ordered_by_updated_at(self, client, db_session):
        """Test latest content is ordered by updated_at descending"""
        from web.backend.database.models import Document

        base_time = datetime.utcnow()

        doc1 = Document(
            title="Oldest",
            content="Content",
            source="test",
            source_url="https://example.com/doc1",
            category="test",
            embedding="[]",
            created_at=base_time,
            updated_at=base_time,
        )
        doc2 = Document(
            title="Newest",
            content="Content",
            source="test",
            source_url="https://example.com/doc2",
            category="test",
            embedding="[]",
            created_at=base_time,
            updated_at=base_time.replace(microsecond=base_time.microsecond + 100000),
        )
        db_session.add_all([doc1, doc2])
        db_session.commit()

        response = client.get("/api/content/latest")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        if len(data["latest"]) >= 2:
            assert data["latest"][0]["title"] == "Newest"
