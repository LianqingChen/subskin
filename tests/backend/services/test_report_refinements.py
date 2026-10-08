"""Synthetic regression for report quantification, timestamps, and quiet completion."""
import asyncio
import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from web.backend.database.models import SkinReport, User
from web.backend.models.vasi import VASIAssessment
from web.backend.services.report_quantification import photo_measurement, pair_photo_measurements, supplement_report_quantification


def measurement(status="measured", reviewed=True):
    return {"version": "rgb-mask-v1", "status": status, "area_percentage": 12.5,
            "lesion_pixels": 125, "skin_pixels": 1000, "color": {"relative_lightness": 8.2},
            "annotation": {"review_state": "user_reviewed" if reviewed else "ai_suggested"}}


def test_partial_single_photo_is_available_without_claiming_change():
    info = {"ref": "va:1", "measurement": measurement("partial")}
    out = photo_measurement(info)
    assert out["area_percentage"] == 12.5 and out["status"] == "partial"
    assert out["scope"] == "individual_photo" and "size_change_percent" not in out
    assert out["relative_lightness"] == 8.2


@pytest.mark.parametrize("info", [{}, {"measurement": measurement(reviewed=False)},
                                  {"measurement": dict(measurement(), version="legacy")}])
def test_unreviewed_or_missing_measurement_never_gets_fabricated_number(info):
    assert photo_measurement(info)["area_percentage"] is None


def test_zero_measurement_is_not_missing():
    info = {"measurement": dict(measurement(), area_percentage=0, lesion_pixels=0)}
    assert photo_measurement(info)["area_percentage"] == 0
    assert photo_measurement(info)["lesion_pixels"] == 0


def test_supplement_owner_check_and_no_report_mutation(monkeypatch):
    import web.backend.services.report_quantification as quant
    records = {"va:1": {"ref": "va:1", "user_id": 1, "date": date(2026, 1, 1), "measurement": measurement()},
               "va:2": {"ref": "va:2", "user_id": 1, "date": date(2026, 2, 1), "measurement": measurement("partial")}}
    monkeypatch.setattr(quant, "load_photo_ref", lambda db, ref: records.get(ref))
    assert pair_photo_measurements(None, 2, "va:1", "va:2") == {}
    payload = {"report_type": "comparison", "status": "completed", "metrics": {"refs": ["va:1", "va:2"], "pair_metrics": {"comparison_status": "not_comparable", "size_change_percent": None}}}
    result = supplement_report_quantification(None, 1, payload)
    pm = result["metrics"]["pair_metrics"]
    assert pm["photo_measurements"]["before"]["area_percentage"] == 12.5
    assert pm["photo_measurement_source"] == "latest_source_records"
    assert pm["comparison_status"] == "not_comparable" and pm["size_change_percent"] is None


@pytest.mark.parametrize("blocker", [None, "partial", "view", "unreviewed"])
def test_automatic_refinement_retries_numeric_measurement(monkeypatch, tmp_path, blocker):
    import web.backend.services.comparison_alignment as alignment
    infos = [{"ref": f"va:{i}", "record_id": i, "user_id": 1, "date": date(2026, i, 1), "body_site": "face", "body_site_label": "面部", "measurement": measurement()} for i in (1, 2)]
    monkeypatch.chdir(tmp_path)
    if blocker == "partial": infos[0]["measurement"]["status"] = "partial"
    if blocker == "view":
        infos[0]["observation"] = {"view": "front"}
        infos[1]["observation"] = {"view": "side"}
    if blocker == "unreviewed": infos[0]["measurement"]["annotation"]["review_state"] = "ai_suggested"
    monkeypatch.setattr(alignment, "describe_comparison", lambda *args: {"summary": "合成图像观察", "status": "completed"})
    rgb_a = np.zeros((100, 100, 3), np.uint8)
    rgb_b = np.ones((100, 100, 3), np.uint8)
    skin = np.ones((100, 100), bool)
    lesion = np.zeros((100, 100), bool)
    transform = np.array([[1., 0, 0], [0, 1., 0]])
    monkeypatch.setattr(alignment, "compare_pair", lambda *args: {"merged": {"comparison_status": "not_comparable", "evidence": {"status": "not_comparable"}}})
    monkeypatch.setattr(alignment, "load_pair", lambda *args: (*infos, b"a", b"b", rgb_a, rgb_b))
    monkeypatch.setattr(alignment, "quality", lambda raw: (1., "good"))
    monkeypatch.setattr(alignment, "prepare", lambda *args: (rgb_a, skin, lesion))
    monkeypatch.setattr(alignment, "automatic_transform", lambda *args: transform)
    monkeypatch.setattr(alignment, "residual_error", lambda *args: .5)
    measure = Mock(return_value={"status": "measured", "size_change_percent": -10, "area_direction": "decreasing", "transform": transform.tolist()})
    monkeypatch.setattr(alignment, "measure_common_roi", measure)
    monkeypatch.setattr(alignment, "save_comparison_preview", lambda *args: {"aligned": True})
    pair, _ = alignment._compare_report_pair(None, 1, "va:1", "va:2")
    assert measure.call_count == (0 if blocker else 1)
    assert pair["merged"]["comparison_status"] == ("visual_only" if blocker else "measured")
    assert pair["merged"]["size_change_percent"] == (None if blocker else -10)


def report_row(**kwargs):
    base = dict(id=1, report_type="comparison", title="合成报告", period_start=None, period_end=None,
                body_site="face", metrics_json=json.dumps({"measurement_version": "common-roi-v1", "generated_at": "2026-09-16T02:05:00Z"}),
                narrative=None, insights_json=None, recommendations_json=None, status="completed", error_message=None,
                is_public=False, share_token=None, created_at=datetime(2026, 9, 16, 2), source_data_json=None, post_id=None, cover_composite_url=None)
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_generation_timestamp_not_share_update_or_request_creation():
    from web.backend.api.skin_report import _report_to_dict
    result = _report_to_dict(report_row())
    assert result["generated_at"] == "2026-09-16T02:05:00Z"
    assert result["created_at"] != result["generated_at"]
    assert _report_to_dict(report_row(status="generating"))["generated_at"] is None
    assert _report_to_dict(report_row(metrics_json='{}'))["generated_at"] is None


def test_public_report_does_not_expose_source_quantification():
    from web.backend.api.skin_report import _report_to_dict
    metrics = {"measurement_version": "common-roi-v1", "pair_metrics": {"photo_measurements": {"before": {"source_ref": "va:1", "area_percentage": 12.5}}}}
    public = _report_to_dict(report_row(metrics_json=json.dumps(metrics)), include_private=False)
    assert "photo_measurements" not in public["metrics"]["pair_metrics"]


@pytest.mark.parametrize("kind", ["comparison", "weekly", "monthly"])
def test_completed_reports_are_saved_without_notification(db_session, monkeypatch, kind):
    import web.backend.api.skin_report as api
    import web.backend.api.notifications as notifications
    user = User(username="synthetic_report_owner", is_active=True)
    db_session.add(user); db_session.commit()
    ids = []
    for month in (1, 2):
        row = VASIAssessment(user_id=user.id, image_url="/synthetic.png", body_site="face", vasi_score=0,
                             area_percentage=0, classification="test", stage="test", assessment_date=datetime(2026, month, 1), status="active")
        db_session.add(row); db_session.flush(); ids.append(row.id)
    db_session.commit()
    targets = []
    monkeypatch.setattr(api.threading, "Thread", lambda target, **kwargs: SimpleNamespace(start=lambda: targets.append(target)))
    monkeypatch.setattr(api, "SessionLocal", lambda: db_session)
    notify = Mock()
    monkeypatch.setattr(notifications, "create_notification", notify)
    def complete(db, *args, report_row, **kwargs):
        report_row.status = "completed"
        report_row.metrics_json = json.dumps({"measurement_version": "common-roi-v1", "generated_at": "2026-09-16T02:05:00Z"})
        db.commit()
    monkeypatch.setattr(api, "generate_comparison_report", complete)
    monkeypatch.setattr(api, "generate_periodic_report", complete)
    if kind == "comparison":
        result = asyncio.run(api.create_comparison_report(api.ComparisonReportRequest(vasi_ids=ids), user, db_session))
    else:
        result = asyncio.run(api.create_periodic_report(api.PeriodicReportRequest(period_type=kind), user, db_session))
    assert len(targets) == 1
    targets[0]()
    saved = db_session.query(SkinReport).filter(SkinReport.id == result["id"]).one()
    assert saved.status == "completed"
    assert json.loads(saved.metrics_json)["generated_at"]
    notify.assert_not_called()
