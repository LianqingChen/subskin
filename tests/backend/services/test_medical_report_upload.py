import pytest

from web.backend.services.community import CommunityService


def test_upload_report_accepts_png(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = CommunityService(db_session)
    content = b"\x89PNG\r\n\x1a\nfake-png-body"

    result = service.upload_file(
        user_id=1,
        filename="report.png",
        content=content,
        subdir="reports",
    )

    assert result["url"].startswith("/uploads/reports/")
    assert (tmp_path / "data/uploads/reports").exists()


def test_upload_report_rejects_spoofed_png(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = CommunityService(db_session)

    with pytest.raises(ValueError, match="magic byte"):
        service.upload_file(
            user_id=1,
            filename="report.png",
            content=b"not-a-png",
            subdir="reports",
        )


def test_upload_report_rejects_disallowed_document(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = CommunityService(db_session)

    with pytest.raises(ValueError, match="不支持的文件格式"):
        service.upload_file(
            user_id=1,
            filename="report.exe",
            content=b"MZ",
            subdir="reports",
        )
