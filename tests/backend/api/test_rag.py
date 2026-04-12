"""
Tests for RAG API endpoints
"""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest
from fastapi import status


class TestAskQuestion:
    """Test POST /ask endpoint"""

    @patch("web.backend.api.rag.answer_question")
    def test_ask_question_authenticated(
        self, mock_answer, client, test_user, auth_headers
    ):
        """Test authenticated user can ask questions"""
        from web.backend.models.rag import QuestionResponse, Source

        mock_answer.return_value = QuestionResponse(
            answer="Test answer",
            sources=[
                Source(
                    title="Test Source",
                    url="https://example.com/source",
                    snippet="Test snippet",
                )
            ],
        )

        response = client.post(
            "/api/rag/ask",
            json={"question": "What is vitiligo?", "conversation_id": "test-conv-123"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        mock_answer.assert_called_once()

    @patch("web.backend.api.rag.answer_question")
    def test_ask_question_unauthenticated(self, mock_answer, client):
        """Test unauthenticated user cannot ask questions"""
        response = client.post(
            "/api/rag/ask",
            json={"question": "What is vitiligo?", "conversation_id": "test-conv-123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_answer.assert_not_called()

    @patch("web.backend.api.rag.answer_question")
    def test_ask_question_invalid_token(self, mock_answer, client):
        """Test asking question with invalid token returns 401"""
        response = client.post(
            "/api/rag/ask",
            json={"question": "What is vitiligo?"},
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_answer.assert_not_called()

    @patch("web.backend.api.rag.answer_question")
    def test_ask_question_without_conversation_id(
        self, mock_answer, client, test_user, auth_headers
    ):
        """Test asking question without conversation_id"""
        from web.backend.models.rag import QuestionResponse

        mock_answer.return_value = QuestionResponse(answer="Test answer", sources=[])

        response = client.post(
            "/api/rag/ask", json={"question": "What is vitiligo?"}, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        mock_answer.assert_called_once()

    def test_ask_question_missing_question(self, client, auth_headers):
        """Test asking question without question parameter returns 422"""
        response = client.post("/api/rag/ask", json={}, headers=auth_headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ask_question_empty_question(self, client, auth_headers):
        """Test asking question with empty question"""
        response = client.post(
            "/api/rag/ask", json={"question": ""}, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK


class TestAskQuestionPublic:
    """Test POST /ask-public endpoint"""

    @patch("web.backend.api.rag.answer_question")
    def test_ask_public_no_auth_required(self, mock_answer, client):
        """Test public endpoint does not require authentication"""
        from web.backend.models.rag import QuestionResponse, Source

        mock_answer.return_value = QuestionResponse(
            answer="Public test answer",
            sources=[
                Source(
                    title="Public Source",
                    url="https://example.com/public",
                    snippet="Public snippet",
                )
            ],
        )

        response = client.post(
            "/api/rag/ask-public",
            json={
                "question": "What is vitiligo?",
                "conversation_id": "public-conv-123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        mock_answer.assert_called_once()

    @patch("web.backend.api.rag.answer_question")
    def test_ask_public_valid_question(self, mock_answer, client):
        """Test public endpoint with valid question"""
        from web.backend.models.rag import QuestionResponse

        mock_answer.return_value = QuestionResponse(
            answer="Answer to public question", sources=[]
        )

        response = client.post(
            "/api/rag/ask-public", json={"topic": "Treatment options"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("web.backend.api.rag.answer_question")
    def test_ask_public_without_conversation_id(self, mock_answer, client):
        """Test public endpoint without conversation_id"""
        from web.backend.models.rag import QuestionResponse

        mock_answer.return_value = QuestionResponse(
            answer="Answer without conversation", sources=[]
        )

        response = client.post(
            "/api/rag/ask-public", json={"question": "What is vitiligo?"}
        )

        assert response.status_code == status.HTTP_200_OK
        mock_answer.assert_called_once()

    def test_ask_public_missing_question(self, client):
        """Test public endpoint without question returns 422"""
        response = client.post("/api/rag/ask-public", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("web.backend.api.rag.answer_question")
    def test_ask_public_response_structure(self, mock_answer, client):
        """Test public endpoint returns correct response structure"""
        from web.backend.models.rag import QuestionResponse

        mock_answer.return_value = QuestionResponse(
            answer="Test answer",
            sources=[
                {
                    "title": "Source 1",
                    "url": "https://example.com/1",
                    "snippet": "Snippet 1",
                }
            ],
        )

        response = client.post(
            "/api/rag/ask-public", json={"question": "Test question"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
