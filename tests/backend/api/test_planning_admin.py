"""Minimal app exercises real administrator dependency without touching the DB."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.backend.api import planning_admin
from web.backend.services.auth import get_current_user
from web.backend.services.planning_archive import PlanningArchive


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'docs/research'
    directory.mkdir(parents=True)
    (directory / 'example.md').write_text('# 示例规划\n\n样例', encoding='utf-8')
    monkeypatch.setattr(planning_admin, 'archive', PlanningArchive(tmp_path))
    app = FastAPI()
    app.include_router(planning_admin.router)
    return TestClient(app)


def authorize(client, admin):
    client.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=admin, phone=None)


def test_anonymous_denied(client):
    for path in ['/api/admin/planning', '/api/admin/planning/document?id=' + 'a' * 64,
                 '/api/admin/planning/resolve?path=docs/research/example.md']:
        assert client.get(path).status_code in {401, 403}


def test_non_admin_denied(client):
    authorize(client, False)
    assert client.get('/api/admin/planning').status_code == 403
    assert client.get('/api/admin/planning/resolve', params={'path': 'docs/research/example.md'}).status_code == 403
    assert client.get('/api/admin/planning/document', params={'id': 'a' * 64}).status_code == 403


def test_admin_read_and_cache_policy(client):
    authorize(client, True)
    result = client.get('/api/admin/planning')
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'private, no-store'
    identity = result.json()['items'][0]['id']
    detail = client.get('/api/admin/planning/document', params={'id': identity})
    assert detail.status_code == 200 and '# 示例规划' in detail.json()['content']
    resolved = client.get('/api/admin/planning/resolve', params={'path': 'docs/research/example.md'})
    assert resolved.json()['id'] == identity
    assert client.post('/api/admin/planning').status_code == 405


@pytest.mark.parametrize('params', [{'page': 0}, {'page_size': 10000}, {'month': '2026-99'}, {'q': 'x' * 201}])
def test_bounded_queries(client, params):
    authorize(client, True)
    assert client.get('/api/admin/planning', params=params).status_code == 422


def test_paths_and_errors(client, monkeypatch):
    authorize(client, True)
    assert client.get('/api/admin/planning/resolve', params={'path': '/etc/passwd'}).status_code == 404
    assert client.get('/api/admin/planning/document', params={'id': '../x'}).status_code == 422
    assert client.get('/api/admin/planning/document', params={'id': 'a' * 64}).status_code == 404
    def fail(**kwargs):
        raise RuntimeError('internal file system information')
    monkeypatch.setattr(planning_admin.archive, 'list_documents', fail)
    response = client.get('/api/admin/planning')
    assert response.status_code == 503
    assert 'internal' not in response.text
