"""Literal admin image-label paths must not be swallowed by ``/{label_id}``.

Regression: GET ``queue``/``choices``/``export``/``training-manifest`` were
declared after GET ``/admin/image-labels/{label_id}``, so the parameter route
matched first and the admin UI got HTTP 422. Route matching only; no DB.
"""
import pytest
from fastapi import FastAPI
from starlette.routing import Match

from web.backend.api import image_label

PREFIX = "/api/vasi/admin/image-labels"


@pytest.fixture(scope="module")
def app():
    app = FastAPI()
    app.include_router(image_label.router, prefix="/api/vasi")
    return app


def _first_match(app, method, path):
    scope = {"type": "http", "method": method, "path": path, "query_string": b"", "headers": []}
    for route in app.routes:
        kind, _ = route.matches(scope)
        if kind == Match.FULL:
            return route.path
    return None


@pytest.mark.parametrize(
    "method,tail",
    [
        ("GET", "queue"),
        ("GET", "choices"),
        ("GET", "export"),
        ("GET", "training-manifest"),
        ("GET", "stats"),
        ("POST", "upload"),
        ("POST", "sync-assessments"),
        ("POST", "batch-status"),
        ("POST", "training-export"),
    ],
)
def test_literal_paths_are_not_shadowed(app, method, tail):
    matched = _first_match(app, method, f"{PREFIX}/{tail}")
    assert matched == f"{PREFIX}/{tail}"


@pytest.mark.parametrize(
    "method,tail",
    [("GET", "12"), ("POST", "12/label"), ("GET", "12/annotations"), ("DELETE", "12/annotations")],
)
def test_numeric_ids_still_reach_parameter_routes(app, method, tail):
    matched = _first_match(app, method, f"{PREFIX}/{tail}")
    assert matched is not None and "label_id" in matched
