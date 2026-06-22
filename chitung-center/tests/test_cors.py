from __future__ import annotations

from fastapi.testclient import TestClient

from chitung_center.app import app


def test_cors_allows_local_vite_5174():
    client = TestClient(app)

    response = client.options(
        "/api/whatsapp/auth/status",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
