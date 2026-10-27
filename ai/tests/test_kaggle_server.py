import asyncio
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaggle_server import ContextTooLong, GenerationResult, TransformersEngine, create_app


class FakeEngine:
    model_id = "test-model"
    metadata = {"checkpoint_revision": "test-only"}

    def __init__(self):
        self.calls = []

    def generate(self, messages, temperature, max_tokens):
        self.calls.append((messages, temperature, max_tokens))
        return GenerationResult("<think>not displayed</think> **Kiểm tra đất trước.**", 12, 8)


def test_preserves_custom_system_and_history_and_keeps_api_contract():
    engine = FakeEngine()
    turns = [{"role": "system", "content": "SYSTEM_MARKER"},
             {"role": "user", "content": "Tôi trồng cà chua"},
             {"role": "assistant", "content": "Cây bao nhiêu tuổi?"},
             {"role": "user", "content": "Hai tuần"}]
    with TestClient(create_app(engine)) as client:
        response = client.post("/v1/chat/completions", json={"messages": turns, "temperature": 0.7, "max_tokens": 1024})
        assert response.status_code == 200
        assert response.json()["response"] == "**Kiểm tra đất trước.**"
        assert engine.calls == [(turns, 0.7, 1024)]
        assert response.json()["usage"] == {"prompt_tokens": 12, "completion_tokens": 8}
        assert client.get("/health").json()["server_version"] == "smart-garden-kaggle-v1"


def test_user_only_example_adds_default_system_and_optional_auth():
    engine = FakeEngine()
    with TestClient(create_app(engine, api_key="unit-test-only")) as client:
        body = {"messages": [{"role": "user", "content": "Xin chào"}]}
        assert client.post("/v1/chat/completions", json=body).status_code == 401
        assert not engine.calls
        assert client.post("/v1/chat/completions", json=body, headers={"Authorization": "Bearer unit-test-only"}).status_code == 200
        assert [item["role"] for item in engine.calls[0][0]] == ["system", "user"]


@pytest.mark.parametrize("payload", [
    {"messages": []},
    {"messages": [{"role": "user", "content": " "}]},
    {"messages": [{"role": "assistant", "content": "x"}]},
    {"messages": [{"role": "user", "content": "x"}, {"role": "system", "content": "x"}]},
    {"messages": [{"role": "user", "content": "x"}], "temperature": True},
    {"messages": [{"role": "user", "content": "x"}], "max_tokens": "1024"},
    {"messages": [{"role": "user", "content": "x"}], "max_tokens": 2049},
])
def test_invalid_requests_do_not_call_model(payload):
    engine = FakeEngine()
    with TestClient(create_app(engine)) as client:
        assert client.post("/v1/chat/completions", json=payload).status_code == 422
    assert engine.calls == []


def test_generation_errors_do_not_expose_internal_details():
    engine = FakeEngine()

    def broken(*args):
        raise RuntimeError("private model path and credentials")

    engine.generate = broken
    with TestClient(create_app(engine)) as client:
        response = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "x"}]})
        assert response.status_code == 503
        assert "private" not in response.text


def test_cancelled_request_does_not_release_gpu_while_worker_is_running():
    async def scenario():
        engine = FakeEngine()
        entered, release = threading.Event(), threading.Event()

        def slow(*args):
            entered.set()
            assert release.wait(5)
            return GenerationResult("Tư vấn", 3, 2)

        engine.generate = slow
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(engine)), base_url="http://test") as client:
            body = {"messages": [{"role": "user", "content": "x"}]}
            task = asyncio.create_task(client.post("/v1/chat/completions", json=body))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert (await client.get("/health")).json()["busy"] is True
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert (await client.post("/v1/chat/completions", json=body)).status_code == 429
            finally:
                release.set()
            for _ in range(100):
                if not (await client.get("/health")).json()["busy"]:
                    break
                await asyncio.sleep(.01)
            assert (await client.get("/health")).json()["busy"] is False
            assert (await client.post("/v1/chat/completions", json=body)).status_code == 200

    asyncio.run(scenario())


class Tokens(list):
    @property
    def shape(self):
        return (1, len(self))

    def __getitem__(self, key):
        value = super().__getitem__(key)
        return Tokens(value) if isinstance(key, slice) else value

    def tolist(self):
        return list(self)


class Batch(dict):
    def to(self, device):
        assert device == "fake-device"
        return self


class FakeTokenizer:
    chat_template = "test-template-with-enable_thinking"
    pad_token_id = None
    eos_token_id = 2

    def apply_chat_template(self, messages, **kwargs):
        self.messages, self.options = messages, kwargs
        return Batch(input_ids=Tokens([1, 2, 3]))

    def decode(self, ids, **kwargs):
        assert ids == [90, 91], "Only new tokens may be decoded"
        assert kwargs == {"skip_special_tokens": True}
        return "Kiểm tra đất."


class FakeModel:
    config = SimpleNamespace(max_position_embeddings=4096, _commit_hash="test-revision")
    device = "fake-device"

    def eval(self):
        return self

    def generate(self, **kwargs):
        self.options = kwargs
        return [Tokens([1, 2, 3, 90, 91])]


@pytest.mark.parametrize("temperature", [0, 0.7])
def test_transformers_engine_uses_chat_template_and_decodes_only_new_tokens(monkeypatch, temperature):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    tokenizer, model = FakeTokenizer(), FakeModel()
    engine = TransformersEngine(model, tokenizer)
    messages = [{"role": "system", "content": "keep this"}, {"role": "user", "content": "x"}]
    result = engine.generate(messages, temperature, 1024)
    assert tokenizer.messages == messages
    assert tokenizer.options["enable_thinking"] is False
    assert tokenizer.options["add_generation_prompt"] is True
    assert result == GenerationResult("Kiểm tra đất.", 3, 2)
    assert model.options["max_new_tokens"] == 1024
    assert model.options["pad_token_id"] == 2
    assert ("temperature" in model.options) is (temperature > 0)


def test_context_overflow_is_rejected_without_dropping_system_or_history(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    engine = TransformersEngine(FakeModel(), FakeTokenizer(), max_context_tokens=2049)
    with pytest.raises(ContextTooLong):
        engine.generate([{"role": "user", "content": "x"}], 0.7, 2048)


def test_notebook_embeds_current_server_source():
    root = Path(__file__).resolve().parents[1]
    notebook_path = root / "Smart_Garden_Kaggle_Server.ipynb"
    if not notebook_path.exists():
        pytest.fail("The runnable Kaggle notebook has not been generated")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    embedded = next(cell for cell in notebook["cells"] if cell.get("metadata", {}).get("tags") == ["server-source"])
    assert "".join(embedded["source"]) == (root / "kaggle_server.py").read_text(encoding="utf-8")
