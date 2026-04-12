"""
Tests for VASI service
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from web.backend.services.vasi import VASIService, VASIAssessmentError
from web.backend.database.models import User


@pytest.fixture
def vasi_service(db_session):
    """Create VASI service instance"""
    return VASIService(db_session)


def test_validate_input_valid_image(vasi_service):
    """Test _validate_input with valid inputs"""
    # Should not raise exception
    vasi_service._validate_input(
        image_file=b"fake_image_data" * 100, body_site="面部", image_type="image/jpeg"
    )


def test_validate_input_image_too_large(vasi_service):
    """Test _validate_input rejects oversized image"""
    oversized_image = b"x" * (vasi_service.MAX_IMAGE_SIZE + 1)

    with pytest.raises(VASIAssessmentError) as exc_info:
        vasi_service._validate_input(
            image_file=oversized_image, body_site="面部", image_type="image/jpeg"
        )

    assert "图片过大" in str(exc_info.value)


def test_validate_input_invalid_image_type(vasi_service):
    """Test _validate_input rejects unsupported image type"""
    with pytest.raises(VASIAssessmentError) as exc_info:
        vasi_service._validate_input(
            image_file=b"fake_image", body_site="面部", image_type="image/gif"
        )

    assert "不支持的图片格式" in str(exc_info.value)


def test_validate_input_invalid_body_site(vasi_service):
    """Test _validate_input rejects invalid body site"""
    with pytest.raises(VASIAssessmentError) as exc_info:
        vasi_service._validate_input(
            image_file=b"fake_image", body_site="invalid_site", image_type="image/jpeg"
        )

    assert "无效的身体部位" in str(exc_info.value)


def test_validate_input_valid_body_sites(vasi_service):
    """Test _validate_input accepts all valid body sites"""
    valid_sites = ["面部", "颈部", "躯干", "上肢", "下肢", "其他"]

    for site in valid_sites:
        vasi_service._validate_input(
            image_file=b"fake_image", body_site=site, image_type="image/jpeg"
        )


def test_validate_input_edge_case_exact_max_size(vasi_service):
    """Test _validate_input accepts image at max size limit"""
    exact_size_image = b"x" * vasi_service.MAX_IMAGE_SIZE

    vasi_service._validate_input(
        image_file=exact_size_image, body_site="面部", image_type="image/jpeg"
    )


@pytest.mark.asyncio
async def test_assess_vasi_creates_record(vasi_service, test_user):
    """Test that assess_vasi creates database record"""
    with patch.object(
        vasi_service, "_upload_image", new_callable=AsyncMock
    ) as mock_upload:
        with patch.object(
            vasi_service, "_call_vasi_api", new_callable=AsyncMock
        ) as mock_api:
            # Mock upload to return URL and key
            mock_upload.return_value = (
                "https://cdn.example.com/test.jpg",
                "vasi/1/123_abc.jpg",
            )

            # Mock API response
            mock_api.return_value = {
                "vasi_score": 25.5,
                "area_percentage": 15.2,
                "classification": "非节段型",
                "stage": "稳定",
                "details": {"confidence": 0.92},
                "raw_response": {"test": "data"},
                "source": "mock",
            }

            assessment = await vasi_service.assess_vasi(
                user_id=test_user.id,
                image_file=b"test_image",
                body_site="面部",
                image_type="image/jpeg",
                image_filename="test.jpg",
            )

            assert assessment.id is not None
            assert assessment.user_id == test_user.id
            assert assessment.vasi_score == 25.5
            assert assessment.body_site == "面部"
            assert assessment.assessment_source == "mock"


@pytest.mark.asyncio
async def test_assess_vasi_calls_upload(vasi_service, test_user):
    """Test that assess_vasi calls image upload"""
    with patch.object(
        vasi_service, "_upload_image", new_callable=AsyncMock
    ) as mock_upload:
        with patch.object(
            vasi_service, "_call_vasi_api", new_callable=AsyncMock
        ) as mock_api:
            mock_upload.return_value = ("url", "key")
            mock_api.return_value = {
                "vasi_score": 10.0,
                "area_percentage": 5.0,
                "classification": "非节段型",
                "stage": "好转",
                "raw_response": {},
            }

            await vasi_service.assess_vasi(
                user_id=test_user.id,
                image_file=b"test_image",
                body_site="面部",
                image_type="image/jpeg",
                image_filename="test.jpg",
            )

            mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_assess_vasi_calls_api(vasi_service, test_user):
    """Test that assess_vasi calls VASI API"""
    with patch.object(
        vasi_service, "_upload_image", new_callable=AsyncMock
    ) as mock_upload:
        with patch.object(
            vasi_service, "_call_vasi_api", new_callable=AsyncMock
        ) as mock_api:
            mock_upload.return_value = ("url", "key")
            mock_api.return_value = {
                "vasi_score": 20.0,
                "area_percentage": 10.0,
                "classification": "非节段型",
                "stage": "稳定",
                "raw_response": {},
            }

            await vasi_service.assess_vasi(
                user_id=test_user.id,
                image_file=b"test_image",
                body_site="面部",
                image_type="image/jpeg",
                image_filename="test.jpg",
            )

            mock_api.assert_called_once_with(b"test_image")


def test_get_user_history_empty(vasi_service, test_user):
    """Test get_user_history returns empty for user with no assessments"""
    total, assessments = vasi_service.get_user_history(test_user.id)

    assert total == 0
    assert len(assessments) == 0


def test_get_user_history_with_data(vasi_service, test_user, db_session):
    """Test get_user_history returns user assessments"""
    from web.backend.database.models import VASIAssessment
    import json

    from web.backend.database.models import VASIAssessment

    assessment1 = VASIAssessment(
        user_id=test_user.id,
        image_url="url1",
        image_key="key1",
        vasi_score=25.5,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment1)

    assessment2 = VASIAssessment(
        user_id=test_user.id,
        image_url="url2",
        image_key="key2",
        vasi_score=30.0,
        body_site="颈部",
        area_percentage=20.0,
        classification="非节段型",
        stage="扩散",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment2)
    db_session.commit()

    total, assessments = vasi_service.get_user_history(test_user.id)

    assert total == 2
    assert len(assessments) == 2


def test_get_user_history_filters_by_body_site(vasi_service, test_user, db_session):
    """Test get_user_history filters by body site"""
    from web.backend.database.models import VASIAssessment
    import json

    assessment_face = VASIAssessment(
        user_id=test_user.id,
        image_url="url1",
        image_key="key1",
        vasi_score=25.0,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment_face)

    assessment_neck = VASIAssessment(
        user_id=test_user.id,
        image_url="url2",
        image_key="key2",
        vasi_score=30.0,
        body_site="颈部",
        area_percentage=20.0,
        classification="非节段型",
        stage="扩散",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment_neck)
    db_session.commit()

    # Filter by face
    total, assessments = vasi_service.get_user_history(test_user.id, body_site="面部")
    assert total == 1
    assert assessments[0].body_site == "面部"


def test_get_user_history_pagination(vasi_service, test_user, db_session):
    """Test get_user_history pagination"""
    from web.backend.database.models import VASIAssessment
    import json

    for i in range(5):
        assessment = VASIAssessment(
            user_id=test_user.id,
            image_url=f"url{i}",
            image_key=f"key{i}",
            vasi_score=10.0 + i,
            body_site="面部",
            area_percentage=5.0,
            classification="非节段型",
            stage="稳定",
            details=json.dumps({}),
            raw_api_response=json.dumps({}),
            assessment_date=datetime.utcnow() - timedelta(hours=i),
        )
        db_session.add(assessment)
    db_session.commit()

    # Test limit
    total, assessments = vasi_service.get_user_history(test_user.id, limit=2)
    assert total == 5
    assert len(assessments) == 2

    # Test offset
    total, assessments = vasi_service.get_user_history(test_user.id, offset=2, limit=2)
    assert len(assessments) == 2


def test_get_user_history_date_filter(vasi_service, test_user, db_session):
    """Test get_user_history date filtering"""
    from web.backend.database.models import VASIAssessment
    import json

    now = datetime.utcnow()

    old_assessment = VASIAssessment(
        user_id=test_user.id,
        image_url="url1",
        image_key="key1",
        vasi_score=25.0,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=10),
    )
    db_session.add(old_assessment)

    recent_assessment = VASIAssessment(
        user_id=test_user.id,
        image_url="url2",
        image_key="key2",
        vasi_score=30.0,
        body_site="颈部",
        area_percentage=20.0,
        classification="非节段型",
        stage="扩散",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=2),
    )
    db_session.add(recent_assessment)
    db_session.commit()

    # Filter by start_date
    start_date = now - timedelta(days=5)
    total, assessments = vasi_service.get_user_history(
        test_user.id, start_date=start_date
    )
    assert total == 1


def test_get_assessment_by_id_valid(vasi_service, test_user, db_session):
    """Test get_assessment_by_id returns correct assessment"""
    from web.backend.database.models import VASIAssessment
    import json

    assessment = VASIAssessment(
        user_id=test_user.id,
        image_url="url",
        image_key="key",
        vasi_score=25.0,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)

    result = vasi_service.get_assessment_by_id(assessment.id, test_user.id)
    assert result is not None
    assert result.id == assessment.id


def test_get_assessment_by_id_wrong_user(vasi_service, test_user, db_session):
    """Test get_assessment_by_id returns None for wrong user"""
    from web.backend.database.models import VASIAssessment
    import json

    assessment = VASIAssessment(
        user_id=999,  # Different user
        image_url="url",
        image_key="key",
        vasi_score=25.0,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)

    result = vasi_service.get_assessment_by_id(assessment.id, test_user.id)
    assert result is None


def test_get_assessment_by_id_nonexistent(vasi_service, test_user):
    """Test get_assessment_by_id returns None for non-existent ID"""
    result = vasi_service.get_assessment_by_id(99999, test_user.id)
    assert result is None


def test_get_trend_data_empty(vasi_service, test_user):
    """Test get_trend_data returns empty structure for no data"""
    trend = vasi_service.get_trend_data(test_user.id)

    assert "body_site" in trend
    assert "period" in trend
    assert "data" in trend
    assert "summary" in trend
    assert len(trend["data"]) == 0
    assert trend["summary"]["trend"] == "无数据"


def test_get_trend_data_with_assessments(vasi_service, test_user, db_session):
    """Test get_trend_data calculates trend correctly"""
    from web.backend.database.models import VASIAssessment
    import json

    now = datetime.utcnow()

    assessment1 = VASIAssessment(
        user_id=test_user.id,
        image_url="url1",
        image_key="key1",
        vasi_score=30.0,
        body_site="面部",
        area_percentage=20.0,
        classification="非节段型",
        stage="扩散",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=3),
    )
    db_session.add(assessment1)

    assessment2 = VASIAssessment(
        user_id=test_user.id,
        image_url="url2",
        image_key="key2",
        vasi_score=25.0,
        body_site="面部",
        area_percentage=15.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=1),
    )
    db_session.add(assessment2)
    db_session.commit()

    trend = vasi_service.get_trend_data(test_user.id, body_site="面部", days=30)

    assert len(trend["data"]) == 2
    assert trend["summary"]["first_score"] == 30.0
    assert trend["summary"]["last_score"] == 25.0
    assert trend["summary"]["change"] == -5.0
    assert trend["summary"]["trend"] == "好转"


def test_get_trend_data_trend_calculation(vasi_service, test_user, db_session):
    """Test get_trend_data trend classification"""
    from web.backend.database.models import VASIAssessment
    import json

    now = datetime.utcnow()

    # Test "稳定" trend (change < 5%)
    stable = VASIAssessment(
        user_id=test_user.id,
        image_url="url1",
        image_key="key1",
        vasi_score=30.0,
        body_site="面部",
        area_percentage=20.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=2),
    )
    db_session.add(stable)

    stable2 = VASIAssessment(
        user_id=test_user.id,
        image_url="url2",
        image_key="key2",
        vasi_score=30.5,
        body_site="面部",
        area_percentage=20.0,
        classification="非节段型",
        stage="稳定",
        details=json.dumps({}),
        raw_api_response=json.dumps({}),
        assessment_date=now - timedelta(days=1),
    )
    db_session.add(stable2)
    db_session.commit()

    trend = vasi_service.get_trend_data(test_user.id, body_site="面部", days=30)
    assert trend["summary"]["trend"] == "稳定"
