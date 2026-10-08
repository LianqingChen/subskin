from fastapi import status


def test_jssdk_config_returns_503_when_disabled(client, monkeypatch):
    monkeypatch.delenv("WECHAT_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_APP_SECRET", raising=False)

    response = client.get("/api/wechat/jssdk-config?url=https://example.com")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "微信分享配置未启用"
