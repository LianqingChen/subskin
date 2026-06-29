"""Regression tests for AuditLogService.

Covers:
- ``AuditLogService.log`` classmethod kwarg mapping (actor_id/details → user_id/detail).
- ``get_log_by_target`` IDOR prevention: a non-admin actor passing
  ``actor_user_id`` may only see their own actions on a target, never another
  user's — even when they can name the target_id.
"""

from web.backend.services.audit import AuditLogService


def test_log_classmethod_maps_actor_and_details(db_session, test_user):
    log = AuditLogService.log(
        db_session,
        action="share_post",
        actor_id=test_user.id,
        target_type="post",
        target_id="42",
        details={"scope": "community", "post_title": "你好"},
        ip_address="203.0.113.7",
    )

    assert log.id is not None
    assert log.user_id == test_user.id
    assert log.action == "share_post"
    assert log.target_type == "post"
    assert log.target_id == 42
    assert '"scope": "community"' in log.detail
    # IP is masked at storage time — never stored raw.
    assert log.ip_address != "203.0.113.7"


def test_get_log_by_target_filters_by_actor_to_prevent_idor(db_session, test_user, test_admin_user):
    # Two actors act on the SAME target (e.g. both share post id 99).
    AuditLogService.log(
        db_session, action="share_post", actor_id=test_user.id,
        target_type="post", target_id=99,
    )
    AuditLogService.log(
        db_session, action="share_post", actor_id=test_admin_user.id,
        target_type="post", target_id=99,
    )

    # test_user asks for the audit trail of post 99 but scopes to their own
    # actions — they must NOT see admin's action (IDOR prevention).
    total, logs = AuditLogService(db_session).get_log_by_target(
        target_type="post", target_id=99, actor_user_id=test_user.id,
    )
    assert total == 1
    assert len(logs) == 1
    assert logs[0].user_id == test_user.id

    # Admin path (actor_user_id=None) returns the full trail.
    total_all, all_logs = AuditLogService(db_session).get_log_by_target(
        target_type="post", target_id=99, actor_user_id=None,
    )
    assert total_all == 2
    assert {log.user_id for log in all_logs} == {test_user.id, test_admin_user.id}
