"""
Tests for VASI API endpoints
"""

from unittest.mock import patch, AsyncMock
from datetime import datetime
import io

import pytest
from fastapi import status


class TestCreateAssessment:
    """Test POST /assess endpoint"""

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_authenticated(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test authenticated user can create VASI assessment"""
        from web.backend.models.vasi import VASIAssessment
        from web.backend.api.models import VASIAssessmentResponse

        mock_assessment = VASIAssessment(
            id=1,
            user_id=test_user.id,
            image_url="https://cdn.example.com/vasi/test/image.jpg",
            image_key="vasi/1/test.jpg",
            image_hash="abc123",
            vasi_score=25.5,
            body_site="面部",
            area_percentage=15.3,
            classification="非节段型",
            stage="稳定",
            details="{}",
            raw_api_response="{}",
            assessment_source="mock",
            assessment_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_service_instance = AsyncMock()
        mock_service_instance.assess_vasi = AsyncMock(return_value=mock_assessment)
        mock_service.return_value = mock_service_instance

        image_content = b"fake image data"
        files = {"image": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
        data = {"body_site": "面部"}

        response = client.post(
            "/api/vasi/assess", files=files, data=data, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["vasi_score"] == 25.5
        assert result["body_site"] == "面部"

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_unauthenticated(self, mock_service, client):
        """Test unauthenticated user cannot create assessment"""
        image_content = b"fake image data"
        files = {"image": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
        data = {"body_site": "面部"}

        response = client.post("/api/vasi/assess", files=files, data=data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_invalid_image_type(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test creating assessment with invalid image type returns 400"""
        from web.backend.services.vasi import VASIAssessmentError

        mock_service_instance = AsyncMock()
        mock_service_instance.assess_vasi = AsyncMock(
            side_effect=VASIAssessmentError("不支持的图片格式")
        )
        mock_service.return_value = mock_service_instance

        image_content = b"fake image data"
        files = {"image": ("test.gif", io.BytesIO(image_content), "image/gif")}
        data = {"body_site": "面部"}

        response = client.post(
            "/api/vasi/assess", files=files, data=data, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_invalid_body_site(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test creating assessment with invalid body site returns 400"""
        from web.backend.services.vasi import VASIAssessmentError

        mock_service_instance = AsyncMock()
        mock_service_instance.assess_vasi = AsyncMock(
            side_effect=VASIAssessmentError("无效的身体部位")
        )
        mock_service.return_value = mock_service_instance

        image_content = b"fake image data"
        files = {"image": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
        data = {"body_site": "invalid_site"}

        response = client.post(
            "/api/vasi/assess", files=files, data=data, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_missing_image(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test creating assessment without image returns 422"""
        data = {"body_site": "面部"}

        response = client.post("/api/vasi/assess", data=data, headers=auth_headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("web.backend.api.vasi.VASIService")
    def test_create_assessment_missing_body_site(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test creating assessment without body_site returns 422"""
        image_content = b"fake image data"
        files = {"image": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}

        response = client.post("/api/vasi/assess", files=files, headers=auth_headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetHistory:
    """Test GET /history endpoint"""

    @patch("web.backend.api.vasi.VASIService")
    def test_get_history_authenticated(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test authenticated user can get assessment history"""
        from web.backend.models.vasi import VASIAssessment

        mock_assessment = VASIAssessment(
            id=1,
            user_id=test_user.id,
            image_url="https://cdn.example.com/image.jpg",
            vasi_score=25.5,
            body_site="面部",
            area_percentage=15.3,
            stage="稳定",
            classification="非节段型",
            assessment_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_service_instance = mock_service.return_value
        mock_service_instance.get_user_history.return_value = (1, [mock_assessment])

        response = client.get("/api/vasi/history", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_get_history_unauthenticated(self, client):
        """Test unauthenticated user cannot get history"""
        response = client.get("/api/vasi/history")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("web.backend.api.vasi.VASIService")
    def test_get_history_with_filters(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test getting history with filters"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_user_history.return_value = (0, [])

        response = client.get(
            "/api/vasi/history?body_site=面部&start_date=2026-01-01&end_date=2026-12-31",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    @patch("web.backend.api.vasi.VASIService")
    def test_get_history_pagination(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test history pagination"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_user_history.return_value = (5, [])

        response = client.get(
            "/api/vasi/history?offset=10&limit=5", headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service_instance.get_user_history.assert_called_once()

    @patch("web.backend.api.vasi.VASIService")
    def test_get_history_limit_50_max(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test history limit is capped at 50"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_user_history.return_value = (0, [])

        response = client.get("/api/vasi/history?limit=100", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        call_args = mock_service_instance.get_user_history.call_args
        assert call_args[1]["limit"] == 50


class TestGetAssessment:
    """Test GET /assess/{id} endpoint"""

    @patch("web.backend.api.vasi.VASIService")
    def test_get_assessment_valid_id(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test getting assessment by valid ID"""
        from web.backend.models.vasi import VASIAssessment

        mock_assessment = VASIAssessment(
            id=1,
            user_id=test_user.id,
            image_url="https://cdn.example.com/image.jpg",
            vasi_score=25.5,
            body_site="面部",
            area_percentage=15.3,
            stage="稳定",
            classification="非节段型",
            assessment_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_service_instance = mock_service.return_value
        mock_service_instance.get_assessment_by_id.return_value = mock_assessment

        response = client.get("/api/vasi/assess/1", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == 1
        assert data["vasi_score"] == 25.5

    @patch("web.backend.api.vasi.VASIService")
    def test_get_assessment_non_existent(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test getting non-existent assessment returns 404"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_assessment_by_id.return_value = None

        response = client.get("/api/vasi/assess/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "评估记录不存在" in response.json()["detail"]

    def test_get_assessment_unauthenticated(self, client):
        """Test unauthenticated user cannot get assessment"""
        response = client.get("/api/vasi/assess/1")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetTrend:
    """Test GET /trend endpoint"""

    @patch("web.backend.api.vasi.VASIService")
    def test_get_trend_authenticated(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test authenticated user can get trend data"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_trend_data.return_value = {
            "body_site": "面部",
            "period": {"start": "2026-01-01T00:00:00", "end": "2026-01-31T00:00:00"},
            "data": [
                {"date": "2026-01-15T10:00:00", "vasi_score": 25.5, "stage": "稳定"}
            ],
            "summary": {
                "first_score": 30.0,
                "last_score": 25.5,
                "change": -4.5,
                "change_percent": -15.0,
                "trend": "好转",
            },
        }

        response = client.get("/api/vasi/trend", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "body_site" in data
        assert "period" in data
        assert "data" in data
        assert "summary" in data

    def test_get_trend_unauthenticated(self, client):
        """Test unauthenticated user cannot get trend"""
        response = client.get("/api/vasi/trend")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("web.backend.api.vasi.VASIService")
    def test_get_trend_with_body_site(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test getting trend for specific body site"""
        mock_service_instance = mock_service.return_value
        mock_service_instance.get_trend_data.return_value = {
            "body_site": "面部",
            "period": {},
            "data": [],
            "summary": {},
        }

        response = client.get("/api/vasi/trend?body_site=面部", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

    @patch("web.backend.api.vasi.VASIService")
    def test_get_trend_custom_days(self, mock_service, client, test_user, auth_headers):
        """Test getting trend with custom days parameter"""
        mock_service_instance = mock.return_value
        mock_service_instance.get_trend_data.return_value = {
            "body_site": "全部",
            "period": {},
            "data": [],
            "summary": {},
        }

        response = client.get("/api/vasi/trend?days=60", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        call_args = mock_service_instance.get_trend_data.call_args
        assert call_args[1]["days"] == 60

    @patch("web.backend.api.vasi.VASIService")
    def test_get_trend_days_clamp_to_365(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test trend days are clamped to 365 max"""
        mock_service_instance = mock.return_value
        mock_service_instance.get_trend_data.return_value = {
            "body_site": "全部",
            "period": {},
            "data": [],
            "summary": {},
        }

        response = client.get("/api/vasi/trend?days=500", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        call_args = mock_service_instance.get_trend_data.call_args
        assert call_args[1]["days"] == 365

    @patch("web.backend.api.vasi.VASIService")
    def test_get_trend_days_minimum_1(
        self, mock_service, client, test_user, auth_headers
    ):
        """Test trend days are clamped to 1 minimum"""
        mock_service_instance = mock.return_value
        mock_service_instance.get_trend_data.return_value = {
            "body_site": "全部",
            "period": {},
            "data": [],
            "summary": {},
        }

        response = client.get("/api/vasi/trend?days=0", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        call_args = mock_service_instance.get_trend_data.call_args
        assert call_args[1]["days"] == 1
