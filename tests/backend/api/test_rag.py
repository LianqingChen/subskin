# pyright: reportAny=false, reportArgumentType=false, reportIndexIssue=false, reportMissingParameterType=false, reportMissingTypeArgument=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedParameter=false

"""Tests for RAG API endpoints."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import status


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events = []
    for chunk in body.split("\n\n"):
        if not chunk.startswith("data: "):
            continue
        events.append(json.loads(chunk[6:]))
    return events


def _make_access_headers(username: str) -> dict[str, str]:
    from web.backend.services.auth import create_access_token

    token = create_access_token({"sub": username, "type": "access"})
    return {"Authorization": f"Bearer {token}"}


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
            "/api/rag/ask-public", json={"question": "What is vitiligo?"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)


class TestUploadTempFile:
    def test_upload_temp_file_authenticated(
        self, client, test_user, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        headers = _make_access_headers(test_user.username)

        response = client.post(
            "/api/rag/upload-temp",
            files={"file": ("report.txt", b"hello report", "text/plain")},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["temp_id"].startswith("tmp_")
        assert data["temp_url"].startswith("/uploads/temp/")
        assert data["mime_type"] == "text/plain"
        assert data["size"] == len(b"hello report")

        saved_file = (
            tmp_path / "data" / "uploads" / "temp" / Path(data["temp_url"]).name
        )
        assert saved_file.exists()
        assert saved_file.read_bytes() == b"hello report"

    def test_upload_temp_file_writes_owner_meta_file(
        self, client, test_user, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        headers = _make_access_headers(test_user.username)

        response = client.post(
            "/api/rag/upload-temp",
            files={"file": ("report.txt", b"hello report", "text/plain")},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        meta_file = (
            tmp_path
            / "data"
            / "uploads"
            / "temp"
            / f"{Path(data['temp_url']).name}.meta"
        )

        assert meta_file.exists()
        assert meta_file.read_text(encoding="utf-8") == str(test_user.id)


class TestPromoteTempUpload:
    def test_promote_temp_upload_rejects_other_users_file(self, monkeypatch, tmp_path):
        from web.backend.api.rag import _promote_temp_upload

        monkeypatch.chdir(tmp_path)
        temp_dir = tmp_path / "data" / "uploads" / "temp"
        temp_dir.mkdir(parents=True)
        source = temp_dir / "tmp_report123.txt"
        source.write_text("secret", encoding="utf-8")
        source.with_name(f"{source.name}.meta").write_text("999", encoding="utf-8")

        promoted = _promote_temp_upload(
            "/uploads/temp/tmp_report123.txt",
            "medical-reports",
            user_id=1,
        )

        assert promoted == "/uploads/temp/tmp_report123.txt"
        assert source.exists()
        assert source.with_name(f"{source.name}.meta").exists()

    def test_promote_temp_upload_moves_owned_file_and_cleans_meta(
        self, monkeypatch, tmp_path
    ):
        from web.backend.api.rag import _promote_temp_upload

        monkeypatch.chdir(tmp_path)
        temp_dir = tmp_path / "data" / "uploads" / "temp"
        temp_dir.mkdir(parents=True)
        source = temp_dir / "tmp_report123.txt"
        source.write_text("owned", encoding="utf-8")
        meta_file = source.with_name(f"{source.name}.meta")
        meta_file.write_text("7", encoding="utf-8")

        promoted = _promote_temp_upload(
            "/uploads/temp/tmp_report123.txt",
            "medical-reports",
            user_id=7,
        )

        assert promoted.startswith("/uploads/medical-reports/")
        target = tmp_path / "data" / promoted.lstrip("/")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "owned"
        assert not source.exists()
        assert not meta_file.exists()


class TestAskQuestionStream:
    @patch("web.backend.api.rag._generate_diary_draft")
    @patch("web.backend.api.rag._interpret_report")
    @patch("web.backend.api.rag._extract_document_text")
    @patch("web.backend.api.rag.answer_question_stream")
    @patch("web.backend.api.rag.search_documents")
    def test_ask_stream_emits_action_cards_for_document_attachment(
        self,
        mock_search_documents,
        mock_answer_stream,
        mock_extract_document_text,
        mock_interpret_report,
        mock_generate_diary_draft,
        client,
        test_user,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.chdir(tmp_path)
        headers = _make_access_headers(test_user.username)
        temp_dir = tmp_path / "data" / "uploads" / "temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "tmp_report123.txt").write_text("TSH 5.2", encoding="utf-8")

        mock_doc = MagicMock(
            title="参考文档",
            source_url="https://example.com/doc",
            content="文档内容",
        )
        mock_search_documents.return_value = [(mock_doc, 0.9)]
        mock_answer_stream.return_value = iter(["第一段", "第二段"])
        mock_extract_document_text.return_value = "TSH 5.2"
        mock_interpret_report.return_value = {
            "report_type": "thyroid",
            "risk_level": "amber",
            "summary": "甲状腺指标需要复查",
            "key_findings": [
                {
                    "name": "TSH",
                    "value": "5.2",
                    "reference": "0.27-4.2",
                    "status": "high",
                    "risk": "amber",
                    "explanation": "提示甲状腺相关指标偏高，建议结合症状和复查判断。",
                }
            ],
            "recommendations": ["1-3个月内复查甲状腺功能。"],
            "disclaimer": "⚠️ 以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。",
        }
        mock_generate_diary_draft.return_value = {
            "type": "diary",
            "title": "2026-04-19 病情日记",
            "content": "<p>今天记录了报告解读。</p>",
            "date": "2026-04-19",
            "privacy": "private",
            "saved": False,
        }

        response = client.post(
            "/api/rag/ask-stream",
            json={"question": "帮我看看报告", "attachment_ids": ["tmp_report123"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        events = _parse_sse_events(response.text)

        assert {
            "type": "thinking",
            "stage": "reading_document",
            "message": "📄 正在解读文档...",
        } in events
        assert any(
            event["type"] == "action_card"
            and event["card"]["type"] == "report"
            and event["card"]["reportType"] == "thyroid"
            and event["card"]["riskLevel"] == "amber"
            and event["card"]["summary"] == "甲状腺指标需要复查"
            and event["card"]["recommendations"] == ["1-3个月内复查甲状腺功能。"]
            for event in events
        )
        assert any(
            event["type"] == "action_card" and event["card"]["type"] == "diary"
            for event in events
        )
        assert events[-1]["type"] == "done"
        mock_extract_document_text.assert_called_once()
        mock_interpret_report.assert_called_once_with("TSH 5.2", "帮我看看报告")
        mock_generate_diary_draft.assert_called_once()

    @patch("web.backend.api.rag._generate_diary_draft")
    @patch("web.backend.api.rag._analyze_uploaded_image")
    @patch("web.backend.api.rag.answer_question_stream")
    @patch("web.backend.api.rag.search_documents")
    def test_ask_stream_emits_vasi_risk_level_for_image_attachment(
        self,
        mock_search_documents,
        mock_answer_stream,
        mock_analyze_uploaded_image,
        mock_generate_diary_draft,
        client,
        test_user,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.chdir(tmp_path)
        headers = _make_access_headers(test_user.username)
        temp_dir = tmp_path / "data" / "uploads" / "temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "tmp_image123.jpg").write_bytes(b"fake-image")

        mock_doc = MagicMock(
            title="参考文档",
            source_url="https://example.com/doc",
            content="文档内容",
        )
        mock_search_documents.return_value = [(mock_doc, 0.9)]
        mock_answer_stream.return_value = iter(["第一段", "第二段"])
        mock_analyze_uploaded_image.return_value = {
            "vasi_score": 12.5,
            "body_site": "面部",
            "classification": "非节段型",
            "stage": "进展期",
            "area_percentage": 6.8,
        }
        mock_generate_diary_draft.return_value = {
            "type": "diary",
            "title": "2026-04-19 病情日记",
            "content": "<p>今天记录了图片分析。</p>",
            "date": "2026-04-19",
            "privacy": "private",
            "saved": False,
        }

        response = client.post(
            "/api/rag/ask-stream",
            json={"question": "帮我看看白斑变化", "attachment_ids": ["tmp_image123"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        events = _parse_sse_events(response.text)

        assert any(
            event["type"] == "action_card"
            and event["card"]["type"] == "vasi"
            and event["card"]["riskLevel"] == "red"
            for event in events
        )


class TestConfirmAction:
    def test_confirm_action_saves_report(self, client, test_user, db_session):
        from web.backend.database.models import MedicalReport

        headers = _make_access_headers(test_user.username)

        response = client.post(
            "/api/rag/confirm-action",
            json={
                "conversation_id": "conv-123",
                "card_type": "report",
                "card_data": {
                    "title": "甲状腺报告",
                    "keyFindings": ["TSH偏高", "建议复查"],
                },
                "action": "save",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "已保存到体检报告"

        report = db_session.query(MedicalReport).one()
        assert report.title == "甲状腺报告"
        assert report.tags == "TSH偏高,建议复查"
