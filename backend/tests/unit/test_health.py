from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_shape():
    response = client.get("/api/v1/health")
    body = response.json()
    assert body == {
        "status": "ok",
        "service": "recovery-orchestrator",
        "version": "0.1.0",
    }


def test_health_includes_request_id_header():
    response = client.get("/api/v1/health")
    assert "x-request-id" in {k.lower() for k in response.headers.keys()}


def test_health_reuses_incoming_request_id():
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-fixed-id"})
    assert response.headers["x-request-id"] == "test-fixed-id"


def test_unknown_route_returns_structured_404():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "request_id" in body["error"]


def test_cors_headers_present_for_allowed_origin():
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
