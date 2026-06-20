"""Tests for events API endpoints"""

import json

from fastapi import status

from web.backend.database.models import UserEvent
from web.backend.services.auth import create_access_token


class TestTrackEvent:
    def test_track_event_unauthenticated(self, client, db_session):
        response = client.post(
            "/api/events/track",
            json={
                "event_type": "click",
                "element_id": "hero-cta",
                "page_path": "/home",
                "element_text": "立即查看",
                "extra_data": {"source": "banner"},
                "session_id": "session-1",
            },
            headers={
                "X-Client-Fingerprint": "fingerprint-1",
                "User-Agent": "pytest-agent",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

        event = db_session.query(UserEvent).one()
        assert event.uid is None
        assert event.session_id == "session-1"
        assert event.event_type == "click"
        assert event.element_id == "hero-cta"
        assert event.page_path == "/home"
        assert event.element_text == "立即查看"
        assert json.loads(event.extra_data) == {"source": "banner"}
        assert event.client_fingerprint == "fingerprint-1"
        assert event.user_agent == "pytest-agent"

    def test_track_event_with_invalid_token_still_succeeds(self, client, db_session):
        response = client.post(
            "/api/events/track",
            json={"event_type": "view", "session_id": "session-2"},
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == status.HTTP_200_OK

        event = db_session.query(UserEvent).one()
        assert event.uid is None
        assert event.event_type == "view"

    def test_track_event_authenticated(self, client, db_session, test_user):
        test_user.uid = "uid-123"
        db_session.commit()
        auth_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': test_user.username})}"
        }

        response = client.post(
            "/api/events/track",
            json={"event_type": "submit", "session_id": "session-3"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK

        event = db_session.query(UserEvent).one()
        assert event.uid == test_user.uid
        assert event.event_type == "submit"


class TestTrackBatch:
    def test_track_batch(self, client, db_session):
        response = client.post(
            "/api/events/track/batch",
            json={
                "events": [
                    {"event_type": "view", "session_id": "session-a"},
                    {
                        "event_type": "click",
                        "session_id": "session-a",
                        "extra_data": {"position": 2},
                    },
                ]
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok", "count": 2}

        events = db_session.query(UserEvent).order_by(UserEvent.id).all()
        assert len(events) == 2
        assert events[0].event_type == "view"
        assert json.loads(events[1].extra_data) == {"position": 2}
