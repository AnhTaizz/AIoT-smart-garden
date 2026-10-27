"""Generate the uploadable notebook from the canonical Kaggle server source."""

import json
from pathlib import Path
import textwrap


def cell(kind: str, source: str, *, tags: list[str] | None = None) -> dict:
    value = {
        "cell_type": kind,
        "metadata": {"tags": tags} if tags else {},
        "source": textwrap.dedent(source).lstrip("\n").splitlines(keepends=True),
    }
    if kind == "code":
        value.update(execution_count=None, outputs=[])
    return value


def build() -> Path:
    directory = Path(__file__).resolve().parent
    cells = [
        cell("markdown", """
        # Smart-Garden · Qwen3 Kaggle API

        API dùng model `ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu`, giữ đầy đủ system prompt/history và chỉ decode token mới sinh.

        - Bật **Internet** và chọn GPU trong Kaggle Settings.
        - Nếu dán các cell vào notebook đang có `model` và `tokenizer`, chúng được dùng lại; không tải model lần hai.
        - Nếu mở notebook này độc lập, cell model sẽ nạp checkpoint một lần. Cần GPU/RAM phù hợp; có thể dùng cách nạp/quantization đang hoạt động của bạn thay cell này.
        - Thêm secret **NGROK_AUTHTOKEN** trong Kaggle Secrets. **HF_TOKEN** và **CHAT_API_KEY** là tùy chọn.
        - Mặc định dùng lại domain `sly-series-landowner.ngrok-free.dev`. Cell ngrok chỉ thay tunnel có đúng domain này. Đổi `NGROK_DOMAIN` nếu tài khoản của bạn dùng domain khác, hoặc đặt chuỗi rỗng để tự cấp URL.

        Notebook không huấn luyện lại model. Đúng chat template không bảo đảm checkpoint luôn trả lời đúng; cần đọc kết quả kiểm tra cuối.
        """),
        cell("code", '%pip install -q fastapi==0.116.1 "uvicorn[standard]==0.35.0" pyngrok==9.1.0\n'),
        cell("code", """
        import os

        def read_secret(name):
            value = os.environ.get(name)
            if value:
                return value
            try:
                from kaggle_secrets import UserSecretsClient
                return UserSecretsClient().get_secret(name)
            except Exception:
                return None

        MODEL_ID = "ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu"
        if ("model" in globals()) != ("tokenizer" in globals()):
            raise RuntimeError("Cần cả model và tokenizer từ cùng checkpoint. Hãy hoàn tất cell nạp model đang dùng.")
        if "model" not in globals():
            import torch
            import transformers
            from packaging.version import Version
            from transformers import AutoModelForCausalLM, AutoTokenizer
            if not torch.cuda.is_available():
                raise RuntimeError("Chưa có GPU. Bật GPU trong Kaggle Settings rồi chạy lại.")
            if Version(transformers.__version__) < Version("4.51.0"):
                raise RuntimeError("Qwen3 cần transformers >= 4.51.0. Cập nhật thư viện rồi khởi động lại kernel trước khi nạp model.")
            token = read_secret("HF_TOKEN")
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=token)
            dtype_argument = {"dtype": "auto"} if Version(transformers.__version__) >= Version("4.56.0") else {"torch_dtype": "auto"}
            model = AutoModelForCausalLM.from_pretrained(MODEL_ID, device_map="auto", token=token, **dtype_argument)
            print("Đã nạp model:", MODEL_ID)
        else:
            print("Dùng lại model/tokenizer trong phiên hiện tại; không tải thêm weights.")
        """),
        cell("markdown", "## Server API\nCell dưới được sinh từ `ai/kaggle_server.py`. Không thay system prompt của client bằng prompt cố định ở server.\n"),
        cell("code", (directory / "kaggle_server.py").read_text(encoding="utf-8"), tags=["server-source"]),
        cell("code", """
        import json
        import threading
        import time
        import urllib.request
        import uvicorn

        if "smart_garden_thread" in globals() and smart_garden_thread.is_alive():
            raise RuntimeError("Server này đã chạy. Dùng cell health, hoặc dừng server này trước khi khởi động lại.")
        PORT = 8001  # Không giành cổng 8000 của server cũ.
        MAX_CONTEXT_TOKENS = 8192
        SMART_GARDEN_API_KEY = read_secret("CHAT_API_KEY")
        engine = TransformersEngine(model, tokenizer, model_id=MODEL_ID, max_context_tokens=MAX_CONTEXT_TOKENS)
        app = create_app(engine, api_key=SMART_GARDEN_API_KEY)
        smart_garden_server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info"))
        smart_garden_thread = threading.Thread(target=smart_garden_server.run, daemon=True)
        smart_garden_thread.start()
        for _ in range(80):
            if not smart_garden_thread.is_alive():
                raise RuntimeError("Server đã dừng lúc khởi động. Kiểm tra log/cổng 8001.")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as result:
                    health = json.load(result)
                if health.get("server_version") == SERVER_VERSION:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("Server chưa sẵn sàng sau 20 giây.")
        print(json.dumps(health, ensure_ascii=False, indent=2))
        """),
        cell("markdown", """
        ## Mở tunnel ngrok

        Cell này thay tunnel có đúng domain Smart-Garden được cấu hình bên dưới sang server cổng 8001. Các tunnel domain khác được giữ nguyên. Không in token/key.
        """),
        cell("code", """
        from urllib.parse import urlparse
        from pyngrok import ngrok

        NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "sly-series-landowner.ngrok-free.dev").strip()
        ngrok_token = read_secret("NGROK_AUTHTOKEN")
        if ngrok_token:
            ngrok.set_auth_token(ngrok_token)
        if NGROK_DOMAIN:
            for existing in ngrok.get_tunnels():
                if urlparse(existing.public_url).hostname == NGROK_DOMAIN:
                    ngrok.disconnect(existing.public_url)
        tunnel_options = {"domain": NGROK_DOMAIN} if NGROK_DOMAIN else {}
        smart_garden_tunnel = ngrok.connect(addr=PORT, proto="http", **tunnel_options)
        API_URL = smart_garden_tunnel.public_url.rstrip("/") + "/v1/chat/completions"
        HEALTH_URL = smart_garden_tunnel.public_url.rstrip("/") + "/health"
        print("API_URL:", API_URL)
        print("Health:", HEALTH_URL)
        print("Nếu URL đổi, cập nhật CHAT_API_URL trong .env của Smart-Garden.")
        """),
        cell("markdown", """
        ## Kiểm tra system prompt và lịch sử

        Phép thử này kiểm tra checkpoint có làm theo một chỉ dẫn đơn giản và nhớ thông tin ở lượt trước hay không. Kết quả không đạt cần được xem lại trước khi đánh giá nông học; không coi HTTP 200 là model trả lời đúng.
        """),
        cell("code", """
        def local_chat(messages, max_tokens=128):
            body = json.dumps({"messages": messages, "temperature": 0.0, "max_tokens": max_tokens}, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if SMART_GARDEN_API_KEY:
                headers["Authorization"] = "Bearer " + SMART_GARDEN_API_KEY
            request = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=body, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)

        marker = "SMART_GARDEN_SYSTEM_OK"
        system_probe = local_chat([
            {"role": "system", "content": f"Chỉ trả lời chính xác chuỗi {marker}. Không thêm bất kỳ nội dung nào."},
            {"role": "user", "content": "Xin chào."},
        ])
        history_probe = local_chat([
            {"role": "system", "content": "Trả lời ngắn bằng tiếng Việt, chỉ dựa trên thông tin đã nêu."},
            {"role": "user", "content": "Tôi trồng cà chua trong chậu, không phải rau muống."},
            {"role": "assistant", "content": "Mình đã ghi nhận loại cây của bạn."},
            {"role": "user", "content": "Tôi đang trồng cây gì?"},
        ])
        print(json.dumps({
            "system_instruction_ok": system_probe["response"].strip() == marker,
            "system_probe": system_probe,
            "history_probe": history_probe,
        }, ensure_ascii=False, indent=2))
        """),
        cell("markdown", """
        ## Kết nối về dashboard

        1. Giữ phiên Kaggle đang chạy. Trong `.env` ở máy tính, đặt `CHAT_API_URL` bằng URL in ở trên. Nếu đặt secret `CHAT_API_KEY`, điền cùng key trong `.env`; không gửi key vào chat.
        2. Chạy `docker compose up -d --force-recreate backend` tại thư mục Smart-Garden.
        3. Kiểm tra health public có `server_version: smart-garden-kaggle-v1`, rồi mở dashboard để thử lại.

        Muốn dừng **server này**, chạy riêng một cell:

        ```python
        ngrok.disconnect(smart_garden_tunnel.public_url)
        smart_garden_server.should_exit = True
        smart_garden_thread.join(timeout=20)
        ```

        Không dùng `ngrok.kill()` hoặc xóa model nếu phiên notebook còn tác vụ khác. Server bận trả 429; không tự sinh câu trả lời giả khi GPU lỗi hoặc hết context. Không tự cắt system/history khi vượt giới hạn token.
        """),
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for index, entry in enumerate(cells):
        entry["id"] = f"smart-garden-{index:02d}"
    target = directory / "Smart_Garden_Kaggle_Server.ipynb"
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    print(build())
