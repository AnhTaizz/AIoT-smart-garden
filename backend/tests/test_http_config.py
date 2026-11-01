from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.http_config import configure_cors


def client_for(origins):
    app = FastAPI()
    configure_cors(app, replace(Settings.from_env(), cors_origins=tuple(origins)))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return TestClient(app)


@pytest.mark.parametrize("origin", [
    "https://web.example.com", "https://localhost", "capacitor://localhost",
])
def test_explicit_web_and_native_origins_can_read_api(origin):
    response = client_for([origin]).get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers


def test_command_preflight_allows_json_post():
    response = client_for(["https://web.example.com"]).options(
        "/devices/node_01/commands",
        headers={"Origin": "https://web.example.com",
                 "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "Content-Type"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://web.example.com"


def test_other_origin_and_method_are_not_allowed():
    client = client_for(["https://web.example.com"])
    response = client.get("/health", headers={"Origin": "https://other.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    response = client.options("/health", headers={
        "Origin": "https://web.example.com", "Access-Control-Request-Method": "DELETE",
    })
    assert response.status_code == 400


def test_origin_list_is_configurable_and_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://web.example.com/ , capacitor://localhost ,, ")
    assert Settings.from_env().cors_origins == ("https://web.example.com", "capacitor://localhost")
    monkeypatch.setenv("CORS_ORIGINS", "")
    assert Settings.from_env().cors_origins == ()
    assert "access-control-allow-origin" not in client_for([]).get(
        "/health", headers={"Origin": "https://web.example.com"},
    ).headers


def test_wildcard_origin_is_rejected():
    with pytest.raises(ValueError, match="explicit origins"):
        client_for(["*"])
