from fastapi.testclient import TestClient

from app.main import app


def test_health_is_ok() -> None:
    response = TestClient(app).get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_interactive_docs_are_exposed() -> None:
    client = TestClient(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
