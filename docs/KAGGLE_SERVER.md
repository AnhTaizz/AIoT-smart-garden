# Server Kaggle cho chatbot Smart-Garden

Notebook sẵn để tải lên Kaggle: [Smart_Garden_Kaggle_Server.ipynb](../ai/Smart_Garden_Kaggle_Server.ipynb). Mã nguồn chuẩn nằm tại [kaggle_server.py](../ai/kaggle_server.py); notebook được sinh từ file này bằng `python ai/build_kaggle_notebook.py`.

Đây là bản server thay thế có thể kiểm tra được, chưa áp dụng vào phiên Kaggle đang chạy. Chưa có mã server cũ hoặc quyền truy cập notebook của chủ dự án để xác nhận nguyên nhân gốc. Checkpoint fine-tune vẫn cần đánh giá thực tế sau khi áp dụng.

## Chạy trên Kaggle

1. Import notebook trên vào Kaggle, bật **Internet** và chọn GPU. Hoặc sao chép các cell vào notebook hiện tại để dùng lại biến `model` và `tokenizer` đã nạp. Nếu mở độc lập, cell model nạp `ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu` một lần; có thể dùng cách nạp/quantization đang hoạt động của bạn để phù hợp GPU hiện có.
2. Thêm secret `NGROK_AUTHTOKEN` và cho phép notebook đọc secret. `HF_TOKEN` tùy chọn cho Hugging Face; `CHAT_API_KEY` tùy chọn nếu cần Bearer token. Không điền key thật vào mã hoặc gửi vào chat.
3. Chạy các cell theo thứ tự. Server dùng cổng **8001** để tránh trùng server cũ ở 8000. Mặc định tunnel dùng lại domain `sly-series-landowner.ngrok-free.dev`; chỉ tunnel của đúng domain này được chuyển sang server mới, các domain khác được giữ nguyên.
4. Kiểm tra health public có `server_version: smart-garden-kaggle-v1`. Xem kết quả probe system/history ở cell cuối. Nếu probe vẫn không đạt, cần kiểm tra tokenizer/checkpoint và dữ liệu fine-tune, không kết luận rằng đổi server đã làm model chính xác.
5. Đặt `CHAT_API_URL` trong `.env` máy tính bằng URL notebook in ra. Nếu sử dụng `CHAT_API_KEY`, đặt cùng key trong `.env`. Sau đó chạy:

```powershell
docker compose up -d --force-recreate backend
```

Nếu domain giữ nguyên thì URL API không đổi. Giữ phiên Kaggle hoạt động khi dùng chatbot. Khi ngrok/session hết hiệu lực, dashboard báo lỗi kết nối để người dùng thử lại.

## Điều chỉnh inference

- Giữ nguyên toàn bộ `messages`: system prompt từ backend, các cặp lịch sử và câu hỏi cuối. Server chỉ thêm prompt mặc định ngắn khi client không gửi system; không thay prompt client bằng prompt cố định.
- Dùng `tokenizer.apply_chat_template(..., add_generation_prompt=True, enable_thinking=False)` của chính checkpoint và truyền tokenized input vào model. Không chỉ lấy `messages[-1]["content"]`.
- Cắt bỏ input token trước khi decode; chỉ trả token mới sinh để tránh lặp prompt và lịch sử. Đây là cách dùng được minh họa trong [hướng dẫn Qwen3](https://huggingface.co/Qwen/Qwen3-8B).
- Với sampling, dùng `temperature` từ request, `top_p=0.8`, `top_k=20` theo hướng dẫn non-thinking của [Qwen3](https://huggingface.co/Qwen/Qwen3-8B). `temperature=0` chọn greedy, phục vụ probe ngắn; không gửi thêm các tham số sampling khi greedy.
- Tối đa một tác vụ GPU mỗi lúc. Tác vụ đang chạy giữ quyền sử dụng GPU đến khi worker hoàn tất, kể cả khi HTTP caller hủy request. Tác vụ mới lúc GPU bận nhận HTTP 429; `/health` vẫn phản hồi.
- Mặc định giới hạn tổng input + output **8.192 token**, output tối đa **2.048 token**. Nếu vượt giới hạn, trả 422 `context_too_long`; không âm thầm bỏ system/history. Có thể tăng `MAX_CONTEXT_TOKENS` trong notebook khi đã kiểm tra giới hạn model và bộ nhớ GPU.
- Model/tokenizer thiếu `chat_template` thì dừng với thông báo rõ; không tự thay tokenizer khác. Lỗi generation trả 503; câu trả lời rỗng sau khi bỏ khối thinking trả 502, không tạo câu tư vấn giả.

## Contract giữ nguyên

```json
{
  "messages": [{"role": "user", "content": "Cây cà chua bị vàng lá"}],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

`POST /v1/chat/completions` vẫn trả trường `response` dạng chuỗi. Metadata thêm gồm `model`, `server_version` và `usage`; backend hiện tại chỉ đọc `response`, nên tương thích.

`GET /health` thêm phiên bản server, cờ bận, revision checkpoint nếu có, hash chat template và phiên bản thư viện. Đây là thông tin ghi nhận thực nghiệm, không phải điểm chất lượng của model.

API chỉ nhận một system ở đầu (nếu có), rồi các lượt user/assistant xen kẽ, kết thúc bằng user. Không nhận danh sách rỗng, nội dung trắng hoặc tham số vượt giới hạn. System prompt nông nghiệp đầy đủ tiếp tục do backend Smart-Garden quản lý.

## Kiểm thử và giới hạn

Từ root repo, với môi trường backend development đã cài:

```powershell
.\.venv\Scripts\python.exe -m pytest -q ai/tests/test_kaggle_server.py
```

15 ca đã qua, gồm giữ system/history, decode đúng phần token mới, tắt thinking ở chat template, giữ hợp đồng API, auth tùy chọn, overflow context, lỗi generation và hủy request khi worker còn chạy. Test dùng model/tokenizer giả để kiểm tra orchestration; chưa chạy weights Qwen3 thực trên GPU bằng bản server mới.

Notebook chưa được thực thi trong tài khoản Kaggle của bạn. Không cam kết checkpoint sẽ tuân thủ prompt chỉ vì server áp dụng đúng template. Sau khi chạy notebook, dùng lại bộ câu hỏi trong [hướng dẫn chatbot](CHATBOT.md), ghi health metadata và đánh giá nội dung bởi người có chuyên môn. Không tính câu thay thế `garden_facts` của backend là model trả lời đúng.
