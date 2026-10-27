"""Opt-in real MQTT/DB -> backend -> Kaggle, through the Nginx /api proxy."""

import os

import httpx
import pytest

from helpers import API, FakeDevice, request

pytestmark = pytest.mark.skipif(
    not API or os.getenv("E2E_CHAT_LIVE") != "1",
    reason="Requires running stack and E2E_CHAT_LIVE=1 (makes real Kaggle calls)",
)
PROXY = os.getenv("E2E_CHAT_PROXY_URL", "http://127.0.0.1:5173/api").rstrip("/")


def test_chat_reads_mqtt_data_from_postgres_through_nginx_without_publishing_commands():
    with FakeDevice() as device:
        device.announce()
        sent = device.publish_telemetry(temperature_c=27.3, soil_moisture_pct=38.5)
        device.wait_for_count(1)
        response = httpx.post(PROXY + "/chat", json={
            "message": "Đọc giúp tôi số đo vườn hiện tại. Nếu là mô phỏng, hãy nói rõ.",
            "device_id": device.device_id,
            "include_garden_context": True,
        }, timeout=145)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["reply"].strip()
        assert data["reply_source"] in ("model", "garden_facts")
        context = data["context"]
        assert context["status"] == "included"
        assert context["device_id"] == device.device_id
        assert context["telemetry"]["temperature_c"] == sent["temperature_c"]
        assert context["telemetry"]["soil_moisture_pct"] == sent["soil_moisture_pct"]
        assert context["telemetry"]["simulated"] is True
        assert context["state"]["relay_state"] == "off"
        assert context["telemetry"]["stale"] is False
        assert request("GET", f"/devices/{device.device_id}/commands")[1]["count"] == 0
        assert device.control.empty()


def test_chat_can_disable_context_and_validate_payload_through_nginx():
    invalid = httpx.post(PROXY + "/chat", json={"message": " "}, timeout=10)
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_payload"
    response = httpx.post(PROXY + "/chat", json={
        "message": "Tôi trồng rau trong chậu. Trước khi tưới nên kiểm tra điều gì?",
        "include_garden_context": False,
    }, timeout=145)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["context"]["status"] == "disabled"
    assert data["context"]["telemetry"] is None
    assert data["context"]["state"] is None
