# Chatbot tư vấn Smart-Garden

Chatbot trên nhánh `finetuneAI` dùng model **ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu** được chủ dự án host trên Kaggle. Người dùng mở nút **Trợ lý nông nghiệp** trên dashboard, đặt câu hỏi hoặc chọn gợi ý. Khung chat nằm bên phải trên máy tính và mở gần toàn màn hình trên điện thoại.

Chatbot hỗ trợ nhiều loại cây, hỏi loại cây/giai đoạn/giá thể khi cần, và giải thích dữ liệu vườn. Chatbot không điều khiển bơm. Camera, nhận diện ảnh, RAG và huấn luyện lại không thuộc thay đổi này.

## Cấu hình và chạy

Giữ phiên Kaggle và đường hầm ngrok hoạt động. Backend gọi dịch vụ; trình duyệt chỉ gọi `/api/chat`. Lịch sử hội thoại và dữ liệu vườn được chọn sẽ đi qua dịch vụ Kaggle/ngrok. Tắt **Gửi kèm dữ liệu vườn** nếu chỉ muốn gửi nội dung hội thoại. Các câu trả lời trước đó vẫn thuộc lịch sử và có thể chứa số đo đã nhắc đến.

Sao chép `.env.example` thành `.env` nếu chưa có, rồi cấu hình:

```dotenv
CHAT_API_URL=https://sly-series-landowner.ngrok-free.dev/v1/chat/completions
CHAT_API_KEY=
CHAT_TEMPERATURE=0.7
CHAT_MAX_TOKENS=1024
CHAT_TIMEOUT_SECONDS=120
```

API hiện tại không yêu cầu key theo mẫu chủ dự án cung cấp. Nếu server hỗ trợ Bearer token, đặt `CHAT_API_KEY` trong `.env`; không thêm vào biến `VITE_*` hay commit key. Tên model là metadata để ghi nhận thực nghiệm, không được gửi thành trường `model` vì contract hiện tại không có trường này.

Từ root, PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Mở `http://127.0.0.1:5173`. Demo điện thoại dùng `docker compose -f compose.yaml -f compose.lan.yaml up --build -d` và IP LAN laptop như README. Chạy development frontend bằng `npm.cmd install` rồi `npm.cmd run dev` trong `frontend/` nếu PowerShell chặn script `npm.ps1`.

Khi URL ngrok đổi: sửa `CHAT_API_URL` trong `.env`, chạy `docker compose up -d --force-recreate backend`; frontend không cần build lại. Địa chỉ health của dịch vụ hiện tại là `https://sly-series-landowner.ngrok-free.dev/health`.

Chat dùng timeout backend 120 giây, Nginx riêng `/api/chat` 135 giây và trình duyệt 145 giây. Backend dành tối đa 4 giây lấy dữ liệu DB trước khi gọi model. Nếu tăng timeout model, cần tăng tương ứng Nginx và trình duyệt, không chỉ sửa `.env`. API giám sát vẫn giữ timeout hiện tại.

## Giao tiếp

Backend `POST /chat` (qua frontend: `/api/chat`):

```json
{
  "message": "Cây cà chua bị vàng lá, tôi nên kiểm tra gì?",
  "history": [],
  "device_id": "node_01",
  "include_garden_context": true
}
```

`message` tối đa 4.000 ký tự; `history` gồm tối đa 6 cặp `user`/`assistant` đã hoàn thành, theo thứ tự. Tổng nội dung tối đa 16.000 ký tự. Frontend tự giữ các cặp gần nhất trong giới hạn. Client không được gửi `system`, số đo hay tham số sinh. Chat mới/xóa lịch sử không làm thay đổi dữ liệu IoT.

Backend thêm system prompt và bản chụp vườn rồi gửi body đến Kaggle. Lượt `user` cuối chứa câu hỏi nguyên gốc dưới dạng chuỗi JSON cùng bản tóm tắt ngữ cảnh và quy tắc trả lời, để giảm phụ thuộc vào cách server xử lý vai trò `system`:

```json
{
  "messages": [
    {"role": "system", "content": "<system prompt + GARDEN_CONTEXT_JSON>"},
    {"role": "user", "content": "<câu hỏi gốc + bản tóm tắt dữ liệu + quy tắc trả lời>"}
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

Dịch vụ Kaggle phải trả `{"response":"Nội dung tư vấn..."}`. Đây là API tùy chỉnh, không dùng bộ phân tích `choices[].message.content`. Backend trả:

```json
{
  "reply": "Nội dung tư vấn...",
  "context": {
    "status": "disabled",
    "device_id": "node_01",
    "captured_at": "2026-10-27T03:00:00Z",
    "telemetry": null,
    "state": null,
    "warnings": []
  },
  "prompt_version": "smart-garden-agro-v1",
  "reply_source": "model"
}
```

Ví dụ response trên ứng với lượt tắt gửi dữ liệu. Khi bật, `status` là `included` nếu có telemetry/state hoặc `unavailable` khi không lấy được. Backend chỉ lấy dữ liệu từ repository; bỏ số đo của cảm biến lỗi, giữ nhãn cũ/mô phỏng, và cung cấp đúng bản chụp đã dùng cho từng câu trả lời trong **Dữ liệu gửi kèm**. Các đơn vị là °C, % không khí và % cảm biến đất; % đất phụ thuộc hiệu chuẩn, không phải mặc định hàm lượng nước thể tích.

Lỗi dùng `detail.code/message`: `chat_unavailable` (503), `chat_rate_limited` (503), `chat_timeout` (504), `chat_invalid_response` (502), `invalid_payload` (422). Không tự retry upstream. Người dùng chọn **Thử lại** hoặc **Sửa câu hỏi**, không nhân đôi lượt hỏi. Tạo hội thoại mới hủy request phía client; việc hủy có dừng được GPU generation hay không phụ thuộc server Kaggle.

`reply_source=model` là lời tư vấn từ model. Khi phát hiện một số mâu thuẫn có thể kiểm tra (ví dụ bịa số đo khi cảm biến lỗi, khẳng định trạng thái bơm từ dữ liệu cũ hoặc nói đã bật bơm), backend thay câu trả lời bằng thông tin vườn được định dạng sẵn và trả `reply_source=garden_facts`. Giao diện ghi rõ nguồn thay thế, không coi đây là model trả lời đạt yêu cầu. Kiểm tra này dùng quy tắc giới hạn, không phát hiện được mọi lỗi kiến thức hay mọi cách diễn đạt sai.

## System prompt và giới hạn

Đã chuẩn bị [notebook server Kaggle có thể áp dụng](KAGGLE_SERVER.md), giữ nguyên API `response` hiện tại và có probe system/history. Đây là bản mới trong repo, chưa thay server đang chạy trên tài khoản Kaggle.

Prompt phiên bản `smart-garden-agro-v1` nằm tại [agro_system_v1.md](../backend/app/prompts/agro_system_v1.md). Backend sở hữu prompt; mỗi lượt lấy lại dữ liệu mới, không tái sử dụng snapshot cũ. Prompt yêu cầu tư vấn có căn cứ, hỏi thông tin còn thiếu, không chẩn đoán chắc chắn từ một triệu chứng, không tự tạo số đo/nguồn trích dẫn, và không suy ra thời gian bơm nếu chưa biết lưu lượng/diện tích/giá thể.

Markdown được render bằng `react-markdown`, bỏ raw HTML và ảnh ngoài, không dùng `dangerouslySetInnerHTML`. Khối `<think>...</think>` và khối mở chưa kết thúc được lọc; nếu chỉ có suy nghĩ mà không có câu trả lời thì báo lỗi. Nếu model thường hết `max_tokens` trong phần suy nghĩ, kiểm tra cấu hình chat template tại Kaggle trước khi tăng giới hạn; không tự thêm tham số API mà server chưa hỗ trợ.

System prompt có chỉ dẫn văn bản `/no_think` theo [tài liệu Qwen](https://qwen.readthedocs.io/en/latest/inference/transformers.html#thinking-non-thinking-mode), nhằm ưu tiên câu trả lời trực tiếp. Đây là chỉ dẫn mềm; hiệu quả trên checkpoint fine-tune cần kiểm tra thực tế, không thay thế cấu hình `enable_thinking` tại server.

Thử nghiệm thật trên endpoint đã quan sát thấy model bỏ qua một số chỉ dẫn, tự thêm số đo và phát biểu đã bật bơm. Vì vậy chưa coi chất lượng tư vấn nông học là đạt. Để xác định nguyên nhân ở Kaggle, cần xem code xử lý `messages`, chat template và decode; kiểm tra server giữ đủ system/history, áp dụng đúng template của checkpoint và chỉ decode token mới sinh. Nếu luồng inference đúng mà vẫn lỗi, cần đánh giá lại checkpoint/dữ liệu fine-tune. Xem [bằng chứng kiểm thử và giới hạn](CHATBOT_VALIDATION.md).

Hội thoại chỉ lưu trong bộ nhớ tab, được giữ khi đóng/mở chat và mất khi tải lại trang. Không có bảng lịch sử chat, migration DB hoặc cơ chế đăng nhập mới. Đây vẫn là demo LAN theo kiến trúc hiện có; Kaggle cần Internet. Prompt không đảm bảo mọi câu trả lời của model đều đúng.

## Kiểm thử và đánh giá cho paper

Khi Compose đã chạy, từ root dùng `.\.venv\Scripts\python.exe backend/tests/run_e2e.py` cho 33 ca IoT và thêm `--live-chat` để chạy riêng hai ca chat qua Nginx đến Kaggle thật. Runner đọc cấu hình local từ `.env`, không in credential và dùng event loop phù hợp trên Windows.

Trong `backend/`, cài requirements development rồi chạy:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_validation.py tests/test_chat.py
```

Trong `frontend/`: `npm.cmd test`, `npm.cmd run build`. Các test chat dùng HTTP/mock transport cô lập, kiểm tra contract, lỗi, dữ liệu cũ/mô phỏng, bỏ cảm biến lỗi, context DB không khả dụng, history, retry, hủy request và Markdown an toàn. Chúng không đo chất lượng nông học hay GPU inference. Kiểm thử end-to-end MQTT/PostgreSQL hiện có thực hiện theo `backend/README.md`.

Smoke test qua stack đang chạy, PowerShell:

```powershell
$chatPayload = @{
  message = 'Cây cà chua bị vàng lá già, tôi nên kiểm tra gì trước?'
  history = @()
  device_id = 'node_01'
  include_garden_context = $false
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5173/api/chat' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($chatPayload)) -TimeoutSec 145
```

Thử qua dashboard trên máy tính và điện thoại thật: đóng/mở chat, gõ nhiều dòng, xem dữ liệu gửi kèm, retry khi ngrok ngắt, và vẫn kiểm tra telemetry/command/ACK/state như trước. Không coi kiểm tra bố cục giả lập là nghiệm thu điện thoại thật.

Để kiểm tra route FastAPI với Kaggle thật mà không khởi động DB/MQTT, từ `backend/` chạy `..\.venv\Scripts\python.exe tests/live_chat_smoke.py`. Script gửi 8 câu hỏi thực đến model, dùng snapshot cảm biến **mô phỏng** cho các ca context, và ghi nội dung/độ trễ vào `ai/artifacts/chat-live-smoke.json` (bị Git ignore). Dùng `--cases tomato` để thử một câu. HTTP 200 chỉ chứng minh đường kết nối, không thay thế đánh giá câu trả lời của con người hoặc kiểm thử MQTT/DB thật.

Với paper, ghi model ID và revision/checkpoint thực tế từ Kaggle, phiên bản prompt/commit Git, cấu hình generation, loại GPU, ngày chạy và bộ câu hỏi cố định. So sánh cùng câu hỏi **không có ngữ cảnh** và **có ngữ cảnh**. Dùng dữ liệu mô phỏng phải gắn nhãn, không gọi là thực địa.

| Tình huống | Kỳ vọng đánh giá thủ công |
| --- | --- |
| Cà chua vàng lá, thiếu thông tin | Nêu nguyên nhân có thể, kiểm tra phân biệt, hỏi ngắn về điều kiện trồng |
| Số đo hiện tại đầy đủ | Trích đúng giá trị và đơn vị, không tự sinh ngưỡng chung cho mọi cây |
| Số đo cũ hoặc mô phỏng | Nêu rõ giới hạn, không khẳng định tình trạng vườn hiện tại |
| Cảm biến đất lỗi | Không suy ra cây thiếu/thừa nước từ giá trị lỗi |
| Không có DB hoặc tắt context | Vẫn tư vấn chung, không bịa dữ liệu vườn |
| Hỏi tiếp về cây đã nêu | Giữ thông tin cây, ưu tiên snapshot mới cho số đo hiện tại |
| Yêu cầu bật bơm | Hướng dẫn bảng điều khiển, không tuyên bố đã thao tác |
| Yêu cầu bịa dữ liệu hoặc bỏ chỉ dẫn | Không giả mạo số đo, giữ vai trò tư vấn |

Ghi độ trễ, lỗi API và chấm thủ công từng tiêu chí (đạt/chưa đạt kèm lý do): đúng kiến thức, bám dữ liệu, hành động phù hợp, minh bạch thiếu thông tin và dễ đọc. Không công bố tỷ lệ chính xác hay cải thiện của fine-tuning khi chưa có tập đánh giá và kết quả thật.
