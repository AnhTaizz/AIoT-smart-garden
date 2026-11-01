from datetime import datetime, timezone
import pytest
from app.irrigation import Policy, parse_proposal, check_observation


@pytest.fixture
def policy():
    return Policy(crop="Cây thử nghiệm", stage="Thử nghiệm", substrate="Giá thể mô phỏng", moisture_stop_pct=80,
                  max_pulse_seconds=2, daily_budget_seconds=10)


def observation():
    t = dict(simulated=True, stale=False, received_at=datetime.now(timezone.utc), boot_id="boot_test", clock_synced=True,
             sensor_status={"soil": "ok", "aht20": "ok"}, soil_moisture_pct=40, temperature_c=28, air_humidity_pct=60)
    s = dict(stale=False, received_at=datetime.now(timezone.utc), boot_id="boot_test", clock_synced=True, relay_state="off", mode="MANUAL")
    return t, s


@pytest.mark.parametrize("raw", [
    'Tôi nghĩ nên tưới', '{"water":true,"duration_seconds":0,"reason":"x"}',
    '{"water":"true","duration_seconds":2,"reason":"x"}',
    '{"water":true,"duration_seconds":100,"reason":"x"}',
    '{"water":false,"duration_seconds":0,"reason":""}',
    '{"water":true,"duration_seconds":2,"reason":"x","command":"pump_on"}',
])
def test_invalid_ai_cannot_become_command(raw):
    with pytest.raises(Exception):
        parse_proposal(raw)


def test_json_decision():
    assert parse_proposal('{"water":false,"duration_seconds":0,"reason":"Chưa đủ căn cứ"}').water is False
    assert parse_proposal('```json\n{"water":true,"duration_seconds":2,"reason":"Thử nghiệm"}\n```').duration_seconds == 2


@pytest.mark.parametrize("field,value", [("simulated", False), ("stale", True), ("clock_synced", False), ("soil_moisture_pct", None), ("soil_moisture_pct", 90)])
def test_observation_blocks_unsafe_inputs(policy, field, value):
    t, s = observation()
    t[field] = value
    assert check_observation(t, s, policy, 30)


def test_requires_fresh_matching_boot_and_off(policy):
    t, s = observation()
    assert check_observation(t, s, policy, 30) is None
    s["boot_id"] = "other_boot"
    assert check_observation(t, s, policy, 30)
    s["boot_id"] = t["boot_id"]
    s["relay_state"] = "on"
    assert check_observation(t, s, policy, 30)


POLICY = {"crop": "Cây thử nghiệm", "stage": "Thử nghiệm", "substrate": "Giá thể mô phỏng", "moisture_stop_pct": 80,
          "max_pulse_seconds": 2, "daily_budget_seconds": 10}


def test_irrigation_api_requires_login(api):
    assert api.client.get("/devices/node_01/irrigation").status_code == 401
    response = api.client.put("/devices/node_01/irrigation", json={"enabled": True, "policy": POLICY})
    assert response.status_code == 401
    api.bridge.publish.assert_not_called()


def test_viewer_cannot_change_irrigation(api):
    api.configure(operator_role="viewer")
    headers = api.login()
    for enabled in (True, False):
        response = api.client.put("/devices/node_01/irrigation", json={"enabled": enabled, "policy": POLICY}, headers=headers)
        assert response.status_code == 403
    api.bridge.publish.assert_not_called()


def test_auto_is_refused_without_a_decision_model(api):
    headers = api.login()
    response = api.client.put("/devices/node_01/irrigation", json={"enabled": True, "policy": POLICY}, headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "not_configured"
    api.bridge.publish.assert_not_called()
