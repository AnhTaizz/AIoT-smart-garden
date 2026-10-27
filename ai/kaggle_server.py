"""Kaggle inference API, reusing an already loaded Qwen3 model/tokenizer.

No model is downloaded on import. Notebook usage:
    engine = TransformersEngine(model, tokenizer, model_id=MODEL_ID)
    app = create_app(engine)
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import logging
import re
import secrets
from typing import Any, Literal, Protocol

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

SERVER_VERSION = "smart-garden-kaggle-v1"
DEFAULT_MODEL_ID = "ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu"
DEFAULT_SYSTEM = (
    "Bạn là trợ lý nông nghiệp Smart-Garden. Tư vấn tiếng Việt dễ đọc, có căn cứ. "
    "Hỏi thêm khi thiếu loại cây, giai đoạn hoặc giá thể. Không tự tạo số đo, "
    "không khẳng định bệnh từ một triệu chứng và không có quyền điều khiển bơm. "
    "Chỉ xuất lời tư vấn cho người dùng. /no_think"
)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=64000)


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    messages: list[Message] = Field(min_length=1, max_length=32)
    temperature: float = Field(default=0.7, ge=0, le=2, strict=True)
    max_tokens: int = Field(default=1024, ge=1, le=2048, strict=True)

    @model_validator(mode="after")
    def validate_conversation(self) -> "CompletionRequest":
        turns = self.messages[1:] if self.messages[0].role == "system" else self.messages
        if not turns or len(turns) % 2 == 0 or any(
            turn.role != ("user" if index % 2 == 0 else "assistant")
            for index, turn in enumerate(turns)
        ):
            raise ValueError("Use an optional first system message, then alternating user/assistant turns ending in user")
        if sum(len(message.content) for message in self.messages) > 128000:
            raise ValueError("Conversation exceeds the input size limit")
        return self


@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int


class ContextTooLong(ValueError):
    pass


class InferenceEngine(Protocol):
    model_id: str
    metadata: dict[str, Any]

    def generate(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> GenerationResult: ...


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


class TransformersEngine:
    def __init__(self, model: Any, tokenizer: Any, *, model_id: str = DEFAULT_MODEL_ID, max_context_tokens: int = 8192):
        if not isinstance(getattr(tokenizer, "chat_template", None), str) or not tokenizer.chat_template.strip():
            raise ValueError("Tokenizer của checkpoint chưa có chat_template; cần kiểm tra tokenizer trước khi mở API.")
        if max_context_tokens < 2049:
            raise ValueError("max_context_tokens must be at least 2049")
        self.model = model.eval()
        self.tokenizer = tokenizer
        self.model_id = model_id
        model_limit = getattr(model.config, "max_position_embeddings", max_context_tokens)
        self.max_context_tokens = min(max_context_tokens, model_limit)
        self.metadata = {
            "checkpoint_revision": getattr(model.config, "_commit_hash", None),
            "loaded_model_name": getattr(model.config, "_name_or_path", None),
            "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
            "transformers_version": _package_version("transformers"),
            "torch_version": _package_version("torch"),
            "max_context_tokens": self.max_context_tokens,
            "thinking_requested": False,
        }

    def generate(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> GenerationResult:
        import torch

        # Preserve every role and turn; never replace the client system prompt
        # or collapse the input to messages[-1]['content'].
        inputs = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_tensors="pt",
            return_dict=True,
        ).to(self.model.device)
        input_length = inputs["input_ids"].shape[-1]
        if input_length + max_tokens > self.max_context_tokens:
            raise ContextTooLong("Conversation and requested output exceed the context budget")
        options = {
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0,
            "return_dict_in_generate": False,
            "output_scores": False,
            "pad_token_id": self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            options.update(temperature=temperature, top_p=0.8, top_k=20)
        with torch.inference_mode():
            generated = self.model.generate(**inputs, **options)
        # Decode generated tokens only; decoding the complete sequence leaks the
        # prompt/history and can look like the model is repeating instructions.
        new_tokens = generated[0][input_length:].tolist()
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return GenerationResult(text, input_length, len(new_tokens))


def final_text(text: str) -> str:
    text = re.sub(r"<think\b[^>]*>.*?(?:</think\s*>|$)", "", text, flags=re.I | re.S)
    return re.split(r"</think\s*>", text, flags=re.I)[-1].strip()


def create_app(engine: InferenceEngine, *, api_key: str | None = None) -> FastAPI:
    gate = asyncio.Lock()
    running: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if running:
            await asyncio.gather(*running, return_exceptions=True)

    app = FastAPI(title="Smart-Garden Kaggle API", version=SERVER_VERSION, lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok", "model": engine.model_id, "server_version": SERVER_VERSION,
            "busy": gate.locked(), "inference": engine.metadata,
        }

    @app.post("/v1/chat/completions")
    async def complete(body: CompletionRequest, request: Request) -> dict[str, Any]:
        if api_key and not secrets.compare_digest(request.headers.get("Authorization", ""), f"Bearer {api_key}"):
            raise HTTPException(401, "invalid_api_key")
        if gate.locked():
            raise HTTPException(429, "model_busy", headers={"Retry-After": "5"})
        await gate.acquire()
        messages = [message.model_dump() for message in body.messages]
        if messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": DEFAULT_SYSTEM})
        task = asyncio.create_task(asyncio.to_thread(engine.generate, messages, body.temperature, body.max_tokens))
        running.add(task)

        def finished(job: asyncio.Task) -> None:
            running.discard(job)
            gate.release()
            # Retrieve failures even if the HTTP caller disconnected. The GPU
            # remains reserved until the real worker finishes, not until cancel.
            if not job.cancelled():
                job.exception()

        task.add_done_callback(finished)
        try:
            result = await asyncio.shield(task)
        except ContextTooLong:
            raise HTTPException(422, "context_too_long") from None
        except Exception as error:
            logger.warning("Generation failed: %s", type(error).__name__)
            raise HTTPException(503, "generation_failed") from None
        answer = final_text(result.text)
        if not answer:
            raise HTTPException(502, "empty_response")
        return {
            "response": answer,
            "model": engine.model_id,
            "server_version": SERVER_VERSION,
            "usage": {"prompt_tokens": result.input_tokens, "completion_tokens": result.output_tokens},
        }

    return app
