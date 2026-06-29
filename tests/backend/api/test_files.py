from datetime import datetime, timedelta

from fastapi import status

from web.backend.app.main import app
from web.backend.services.auth import create_access_token


def _get_cors_options() -> dict[str, object]:
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            return middleware.kwargs
    raise AssertionError("CORSMiddleware not configured")


def _make_access_headers(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username, "type": "access"})
    return {"Authorization": f"Bearer {token}"}


class TestFileServing:
    def test_serve_file_requires_authentication(self, client, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        uploads_dir = tmp_path / "data" / "uploads" / "temp"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        (uploads_dir / "report.txt").write_text("hello", encoding="utf-8")

        response = client.get("/api/files/serve/temp/report.txt")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_serve_file_returns_file_for_authenticated_user(
        self, client, test_user, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        uploads_dir = tmp_path / "data" / "uploads" / "temp"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path = uploads_dir / "report.txt"
        file_path.write_text("hello", encoding="utf-8")
        # Temp files require a sidecar .meta naming the owner.
        (uploads_dir / "report.txt.meta").write_text(
            str(test_user.id), encoding="utf-8"
        )

        response = client.get(
            "/api/files/serve/temp/report.txt",
            headers=_make_access_headers(test_user.username),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"hello"

    def test_serve_temp_file_rejects_non_owner(
        self, client, test_user, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        uploads_dir = tmp_path / "data" / "uploads" / "temp"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        (uploads_dir / "victim.txt").write_text("secret", encoding="utf-8")
        (uploads_dir / "victim.txt.meta").write_text("999999", encoding="utf-8")

        response = client.get(
            "/api/files/serve/temp/victim.txt",
            headers=_make_access_headers(test_user.username),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestTempCleanup:
    def test_cleanup_temp_removes_only_stale_files(
        self, client, test_user, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        temp_dir = tmp_path / "data" / "uploads" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        stale_file = temp_dir / "stale.txt"
        stale_file.write_text("stale", encoding="utf-8")
        stale_time = (datetime.now() - timedelta(hours=25)).timestamp()
        import os

        os.utime(stale_file, (stale_time, stale_time))

        fresh_file = temp_dir / "fresh.txt"
        fresh_file.write_text("fresh", encoding="utf-8")

        response = client.delete(
            "/api/files/cleanup-temp",
            headers=_make_access_headers(test_user.username),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted_count"] == 1
        assert not stale_file.exists()
        assert fresh_file.exists()


class TestCorsConfiguration:
    def test_cors_uses_specific_default_origins(self):
        options = _get_cors_options()

        # Origins cover all three environments (production, staging, admin) plus
        # the local dev servers. Update both here and app/main.py when origins
        # change.
        assert options["allow_origins"] == [
            "https://subskin.cn",
            "https://www.subskin.cn",
            "https://admin.subskin.cn",
            "https://staging.subskin.cn",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:5174",  # admin dev server
        ]
        assert options["allow_credentials"] is True
