from datetime import datetime, timedelta, timezone
from dataclasses import replace
import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import httpx
from starlette.requests import Request
import pytest
from app import irrigation
from app.irrigation import Policy, parse_proposal, check_observation, decision_user_message, history_summary
from app.auth import Session
from app.config import Settings

# get_profile is called in-process below, so its SessionDep is passed explicitly.
VIEWER = Session("test-viewer", "viewer", datetime.now(timezone.utc) + timedelta(hours=1), bytes(32))


@pytest.fixture
def policy():
    return Policy(crop="Cây thử nghiệm", stage="Thử nghiệm", substrate="Giá thể mô phỏng", moisture_stop_pct=80,
                  max_pulse_seconds=2, daily_budget_seconds=10)


def observation():
    t = dict(simulated=True, stale=False, received_at=datetime.now(timezone.utc), boot_id="boot_test", clock_synced=True,
             sensor_status={"soil": "ok", "aht20": "ok"}, soil_moisture_pct=40, temperature_c=28, air_humidity_pct=60)
    s = dict(stale=False, received_at=datetime.now(timezone.utc), boot_id="boot_test", clock_synced=True, relay_state="off", mode="MANUAL")
    return t, s


def real_observation():
    t, s = observation()
    now = datetime.now(timezone.utc)
    t.update(device_id="node_01", simulated=False, measured_at=now)
    s.update(device_id="node_01", reported_at=now)
    return t, s


def test_real_esp32_requires_explicit_device_and_authenticated_broker(policy):
    t, s = real_observation()
    assert check_observation(t, s, policy, 30)
    assert check_observation(t, s, policy, 30, real_device_ids=("node_02",), broker_authenticated=True)
    assert check_observation(t, s, policy, 30, real_device_ids=("node_01",))
    assert check_observation(t, s, policy, 30, real_device_ids=("node_01",), broker_authenticated=True) is None


def test_real_device_rejects_simulator_with_same_id(policy):
    t, s = real_observation()
    t["simulated"] = True
    assert check_observation(t, s, policy, 30, real_device_ids=("node_01",), broker_authenticated=True)


@pytest.mark.parametrize("kind,field,value", [
    ("telemetry", "sensor_status", {"soil": "error", "aht20": "ok"}),
    ("telemetry", "soil_moisture_pct", None),
    ("telemetry", "temperature_c", float("nan")),
    ("telemetry", "air_humidity_pct", 101),
    ("telemetry", "clock_synced", False),
    ("state", "boot_id", "previous_boot"),
    ("state", "device_id", "node_02"),
    ("state", "relay_state", "on"),
    ("state", "mode", "AUTO"),
])
def test_real_esp32_keeps_sensor_and_state_protections(policy, kind, field, value):
    t, s = real_observation()
    (t if kind == "telemetry" else s)[field] = value
    assert check_observation(t, s, policy, 30, real_device_ids=("node_01",), broker_authenticated=True)


@pytest.mark.parametrize("field", ["measured_at", "reported_at"])
@pytest.mark.parametrize("offset", [-60, 60])
def test_real_rejects_old_or_future_device_time(policy, field, offset):
    t, s = real_observation()
    (t if field == "measured_at" else s)[field] = datetime.now(timezone.utc) + timedelta(seconds=offset)
    assert check_observation(t, s, policy, 30, real_device_ids=("node_01",), broker_authenticated=True)


def test_real_device_configuration_is_explicit(monkeypatch):
    monkeypatch.delenv("IRRIGATION_REAL_DEVICE_IDS", raising=False)
    assert Settings.from_env().irrigation_real_device_ids == ()
    monkeypatch.setenv("IRRIGATION_REAL_DEVICE_IDS", "node_01, node_02")
    assert Settings.from_env().irrigation_real_device_ids == ("node_01", "node_02")
    monkeypatch.setenv("IRRIGATION_REAL_DEVICE_IDS", "garden/+/control")
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("change", ["none", "simulator", "sensor_error", "reboot", "stop", "over_limit", "invalid_ai", "broker_credentials", "original_measurement_expired"])
def test_real_supervisor_rechecks_before_dispatch(policy, monkeypatch, change):
    """In-process physical payloads; all model, storage and command I/O are mocked."""
    async def run():
        now = datetime.now(timezone.utc)
        profile = dict(device_id="node_01", lease_token=uuid4(), policy=policy.model_dump(),
                       revision=1, enabled=True, lease_until=now + timedelta(seconds=180), last_attempt=None)
        current = dict(profile)
        original_t, original_s = real_observation()
        fresh_t, fresh_s = real_observation()
        if change == "simulator": fresh_t["simulated"] = True
        if change == "sensor_error": fresh_t["sensor_status"] = {"soil": "error", "aht20": "ok"}
        if change == "reboot": fresh_s["boot_id"] = fresh_t["boot_id"] = "new_boot"
        if change == "stop": current["enabled"] = False

        async def execute(sql, params=()):
            if "pg_try_advisory_lock" in sql: row = {"acquired": True}
            elif "SELECT * FROM irrigation_profile" in sql: row = current
            elif "COALESCE(sum(reserved_seconds)" in sql: row = {"spent": 0}
            else: row = None
            return SimpleNamespace(fetchone=AsyncMock(return_value=row))

        conn = SimpleNamespace(execute=AsyncMock(side_effect=execute), commit=AsyncMock(), rollback=AsyncMock())
        @asynccontextmanager
        async def connection():
            yield conn
        settings = replace(Settings.from_env(), irrigation_real_device_ids=("node_01",),
                           mqtt_username="test_backend", mqtt_password="test-only",
                           chat_api_url="http://ai.test/decide")  # mocked model; BC-02 has no default URL
        issue = AsyncMock()
        app = SimpleNamespace(state=SimpleNamespace(settings=settings,
                              pool=SimpleNamespace(connection=connection), issue_irrigation_command=issue))
        captured = []
        async def model_reply(request):
            captured.append(request)
            if change == "original_measurement_expired":
                # Age the captured observation independently of new telemetry.
                original_t["measured_at"] = now - timedelta(seconds=60)
            if change == "broker_credentials":
                app.state.settings = replace(settings, mqtt_password=None)
            answer = ('{"water":true,"duration_seconds":3,"reason":"Test response"}' if change == "over_limit"
                      else 'invalid' if change == "invalid_ai"
                      else '{"water":true,"duration_seconds":2,"reason":"Test response"}')
            return httpx.Response(200, json={"response": answer})
        recorded = AsyncMock(return_value=uuid4())
        monkeypatch.setattr(irrigation, "snapshot", AsyncMock(side_effect=[(original_t, original_s), (fresh_t, fresh_s)]))
        monkeypatch.setattr(irrigation, "history", AsyncMock(return_value=[]))
        monkeypatch.setattr(irrigation, "record", recorded)
        monkeypatch.setattr(irrigation.repository, "list_commands", AsyncMock(return_value=[]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(model_reply)) as client:
            app.state.chat_client = client
            await irrigation.evaluate(app, profile)
        assert len(captured) == 1
        if change == "none":
            issue.assert_awaited_once()
            call = issue.await_args
            assert call.args[0] == "node_01"
            assert call.args[1].action == "pump_on" and call.args[1].duration_seconds == 2
            assert recorded.await_args.args[3] == "reserved"
            assert recorded.await_args.args[6] == 2
            assert call.kwargs["command_id"] == recorded.await_args.args[7]
        else:
            issue.assert_not_awaited()
            assert recorded.await_args.args[3] in ("blocked", "cancelled", "error")
            assert not any("last_attempt=now()" in call.args[0] for call in conn.execute.await_args_list)
    asyncio.run(run())


@pytest.mark.parametrize("forecast", ["fresh", "unavailable", "disabled"])
def test_forecast_is_model_input_only_and_never_blocks_evaluation(policy, monkeypatch, forecast):
    """Simulator path with mocked I/O: weather reaches the model but the guards ignore it."""
    from app import weather
    async def run():
        now = datetime.now(timezone.utc)
        profile = dict(device_id="node_01", lease_token=uuid4(), policy=policy.model_dump(),
                       revision=1, enabled=True, lease_until=now + timedelta(seconds=180), last_attempt=None)

        async def execute(sql, params=()):
            if "pg_try_advisory_lock" in sql: row = {"acquired": True}
            elif "SELECT * FROM irrigation_profile" in sql: row = profile
            elif "COALESCE(sum(reserved_seconds)" in sql: row = {"spent": 0}
            else: row = None
            return SimpleNamespace(fetchone=AsyncMock(return_value=row))

        conn = SimpleNamespace(execute=AsyncMock(side_effect=execute), commit=AsyncMock(), rollback=AsyncMock())
        @asynccontextmanager
        async def connection():
            yield conn
        settings = replace(Settings.from_env(), chat_api_url="http://ai.test/decide",
                           weather_enabled=forecast != "disabled", weather_latitude=21.03, weather_longitude=105.85)
        cache = weather.WeatherCache()
        if forecast == "fresh":
            start = now.replace(minute=0, second=0, microsecond=0)
            cache.fetched_at = now
            cache.hours = weather.parse_forecast({"hourly": {
                "time": [int(start.timestamp()) + 3600 * i for i in range(12)],
                "precipitation_probability": [90] * 12, "precipitation": [1.0] * 12, "temperature_2m": [30.0] * 12}})
        issue = AsyncMock()
        app = SimpleNamespace(state=SimpleNamespace(settings=settings, weather_cache=cache,
                              pool=SimpleNamespace(connection=connection), issue_irrigation_command=issue))
        captured = []
        async def model_reply(request):
            captured.append(request)
            return httpx.Response(200, json={"response": '{"water":true,"duration_seconds":2,"reason":"Test response"}'})
        t, s = observation()
        monkeypatch.setattr(irrigation, "snapshot", AsyncMock(return_value=(t, s)))
        monkeypatch.setattr(irrigation, "history", AsyncMock(return_value=[]))
        monkeypatch.setattr(irrigation, "record", AsyncMock(return_value=uuid4()))
        monkeypatch.setattr(irrigation.repository, "list_commands", AsyncMock(return_value=[]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(model_reply)) as client:
            app.state.chat_client = client
            await irrigation.evaluate(app, profile)
        body = json.loads(captured[0].content)
        content = body["messages"][1]["content"]
        assert content.endswith(irrigation.FORMAT_REMINDER)
        sent = json.loads(content.split("\n\n", 1)[0])
        assert sent["prompt_version"] == irrigation.PROMPT_VERSION
        assert sent["decision_source"] == "ai"  # no rule threshold configured
        assert sent["weather"]["status"] == forecast
        assert "không bao giờ dùng thời tiết làm lý do để tưới" in body["messages"][0]["content"]
        if forecast == "fresh":
            assert sent["weather"]["kind"] == "forecast"
            assert sent["weather"]["max_precipitation_probability_pct"] == 90
        else:
            assert set(sent["weather"]) == {"status", "reason"}
        # The server-side decision path is unchanged by the forecast.
        issue.assert_awaited_once()
    asyncio.run(run())


@pytest.mark.parametrize("real_ids,scope", [((), "simulator_only"), (("node_01",), "real_device")])
def test_profile_reports_server_execution_scope_without_arming(monkeypatch, real_ids, scope):
    async def run():
        row = {"device_id": "node_01", "enabled": False, "policy": {}}
        cursor = SimpleNamespace(fetchone=AsyncMock(return_value=row))
        conn = SimpleNamespace(execute=AsyncMock(return_value=cursor))
        @asynccontextmanager
        async def connection(): yield conn
        app = SimpleNamespace(state=SimpleNamespace(settings=replace(Settings.from_env(), irrigation_real_device_ids=real_ids),
                              pool=SimpleNamespace(connection=connection), issue_irrigation_command=AsyncMock()))
        monkeypatch.setattr(irrigation, "history", AsyncMock(return_value=[]))
        response = await irrigation.get_profile("node_01", Request({"type": "http", "app": app}), VIEWER)
        assert response["execution_scope"] == scope
        assert response["profile"]["enabled"] is False
        app.state.issue_irrigation_command.assert_not_awaited()
    asyncio.run(run())


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


def test_model_history_drops_nested_observations():
    # Each stored observation embeds the previous history; passing it on made the
    # prompt double every evaluation until the model server failed with 503.
    rows = [{"id": i, "device_id": "node_01", "created_at": datetime.now(timezone.utc), "status": "error",
             "reason": "AI lỗi", "proposal": None, "reserved_seconds": 0, "command_id": None,
             "observation": {"history": [{"observation": "x" * 5000}]}, "command_status": None,
             "device_ack": None, "confirmed_relay_state": None} for i in range(8)]
    summary = history_summary(rows)
    assert len(summary) == 5
    assert all("observation" not in item and "device_ack" not in item for item in summary)
    message = decision_user_message({"history": summary, "policy": {"max_pulse_seconds": 2}})
    assert len(message) < 2000
    nested = decision_user_message({"history": history_summary([{**rows[0], "observation": {"history": summary}}])})
    assert len(nested) < 2000  # bounded no matter how many evaluations came before


def test_decision_message_ends_with_the_json_format():
    message = decision_user_message({"telemetry": {"soil_moisture_pct": 30}, "policy": {"moisture_stop_pct": 35, "max_pulse_seconds": 60}})
    assert message.startswith('{"telemetry"')
    assert message.endswith(irrigation.FORMAT_REMINDER)
    # Deterministic fact line, so the model does not have to read the JSON comparison.
    assert "Độ ẩm đất hiện tại 30%, thấp hơn ngưỡng ngừng tưới 35%; max_pulse_seconds=60." in message
    # No concrete reason example: v3's "Đất đủ ẩm" was copied verbatim by the model.
    assert "Đất đủ ẩm" not in irrigation.FORMAT_REMINDER and "Đất khô" not in irrigation.FORMAT_REMINDER
    assert "Thiếu độ ẩm đất" in decision_user_message({"telemetry": {"soil_moisture_pct": None}})


def test_rule_threshold_cannot_exceed_stop_threshold():
    with pytest.raises(Exception):
        Policy.model_validate({**POLICY, "force_water_below_pct": 81})
    assert Policy.model_validate({**POLICY, "force_water_below_pct": 80}).force_water_below_pct == 80
    assert Policy.model_validate(POLICY).force_water_below_pct is None  # stored policies stay valid


def run_simulator_evaluation(monkeypatch, policy, *, last_attempt=None, spent=0, soil=40):
    """Simulator path with mocked I/O. Returns (model requests, issue mock, record mock)."""
    async def run():
        now = datetime.now(timezone.utc)
        profile = dict(device_id="node_01", lease_token=uuid4(), policy=policy.model_dump(),
                       revision=1, enabled=True, lease_until=now + timedelta(seconds=180), last_attempt=last_attempt)

        async def execute(sql, params=()):
            if "pg_try_advisory_lock" in sql: row = {"acquired": True}
            elif "SELECT * FROM irrigation_profile" in sql: row = profile
            elif "COALESCE(sum(reserved_seconds)" in sql: row = {"spent": spent}
            else: row = None
            return SimpleNamespace(fetchone=AsyncMock(return_value=row))

        conn = SimpleNamespace(execute=AsyncMock(side_effect=execute), commit=AsyncMock(), rollback=AsyncMock())
        @asynccontextmanager
        async def connection():
            yield conn
        issue = AsyncMock()
        app = SimpleNamespace(state=SimpleNamespace(settings=replace(Settings.from_env(), chat_api_url="http://ai.test/decide"),
                              pool=SimpleNamespace(connection=connection), issue_irrigation_command=issue))
        captured = []
        async def model_reply(request):
            captured.append(request)
            return httpx.Response(200, json={"response": '{"water":false,"duration_seconds":0,"reason":"Test response"}'})
        t, s = observation()
        t["soil_moisture_pct"] = soil
        recorded = AsyncMock(return_value=uuid4())
        monkeypatch.setattr(irrigation, "snapshot", AsyncMock(return_value=(t, s)))
        monkeypatch.setattr(irrigation, "history", AsyncMock(return_value=[]))
        monkeypatch.setattr(irrigation, "record", recorded)
        monkeypatch.setattr(irrigation.repository, "list_commands", AsyncMock(return_value=[]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(model_reply)) as client:
            app.state.chat_client = client
            await irrigation.evaluate(app, profile)
        return captured, issue, recorded
    return asyncio.run(run())


def test_rule_waters_below_threshold_without_asking_the_model(monkeypatch):
    policy = Policy.model_validate({**POLICY, "max_pulse_seconds": 60, "force_water_below_pct": 50})
    captured, issue, recorded = run_simulator_evaluation(monkeypatch, policy, soil=40)
    assert captured == []
    issue.assert_awaited_once()
    assert issue.await_args.args[1].action == "pump_on" and issue.await_args.args[1].duration_seconds == 10
    observation_arg, status, reason = recorded.await_args.args[2:5]
    assert observation_arg["decision_source"] == "rule" and status == "reserved"
    assert reason.startswith("Luật ngưỡng:")  # labelled, never presented as the AI's decision


def test_rule_pulse_is_capped_by_max_pulse(monkeypatch):
    policy = Policy.model_validate({**POLICY, "force_water_below_pct": 50})  # max_pulse_seconds=2
    _, issue, _ = run_simulator_evaluation(monkeypatch, policy, soil=40)
    assert issue.await_args.args[1].duration_seconds == 2


@pytest.mark.parametrize("case", ["cooldown", "budget"])
def test_rule_still_respects_cooldown_and_budget(monkeypatch, case):
    policy = Policy.model_validate({**POLICY, "force_water_below_pct": 50})
    kwargs = {"last_attempt": datetime.now(timezone.utc)} if case == "cooldown" else {"spent": 9}
    captured, issue, recorded = run_simulator_evaluation(monkeypatch, policy, **kwargs)
    assert captured == []
    issue.assert_not_awaited()
    assert recorded.await_args.args[3] == "blocked"


def test_rule_at_or_above_threshold_asks_the_model(monkeypatch):
    policy = Policy.model_validate({**POLICY, "force_water_below_pct": 40})
    captured, issue, recorded = run_simulator_evaluation(monkeypatch, policy, soil=40)
    assert len(captured) == 1
    issue.assert_not_awaited()
    assert recorded.await_args.args[2]["decision_source"] == "ai"
    assert recorded.await_args.args[3] == "no_water"
