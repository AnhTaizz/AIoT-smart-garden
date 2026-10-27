# Kiểm thử chatbot — 2026-10-27

Model do chủ dự án cung cấp: `ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu`. Không xác minh được revision checkpoint, GPU hay mã inference phía Kaggle chỉ từ health endpoint; không suy diễn các thông tin này trong paper.

## Kiểm tra tự động

- Backend: **96 passed** khi chạy `python -m pytest -q tests/test_chat.py tests/test_validation.py`; có một cảnh báo deprecation của Starlette/AnyIO, không có test lỗi.
- Frontend: **18 passed** khi chạy `npm.cmd test`; `npm.cmd run build` thành công, gồm kiểm tra TypeScript.
- `git diff --check` sạch.
- Cấu hình development và LAN: `docker compose --env-file .env.example config --quiet` và biến thể `-f compose.yaml -f compose.lan.yaml` đều thành công.
- Chromium headless: đã kiểm tra trực quan khung chat trên desktop 1440×1000; các viewport 390×844, 320×640 và 390×420 không tràn ngang, composer nằm trong khung nhìn. Chưa thử điện thoại vật lý/bàn phím iOS hoặc Android thực tế.
- Docker Desktop đã được khởi động; `docker compose up --build -d` build và chạy đủ PostgreSQL, Mosquitto, backend và frontend/Nginx. Frontend test/build trong image cũng thành công.
- E2E IoT với MQTT/PostgreSQL thật: **33 ca đạt**. Lượt đầu 30 ca qua, ba ca async PostgreSQL gặp event loop Proactor trên Windows; sau khi dùng runner WindowsSelector, ba ca đó qua. Không thay đổi logic điều khiển để làm test qua.
- E2E chat qua frontend/Nginx → FastAPI → Kaggle thật: **2 passed in 33,42s**. Telemetry MQTT của device ID ngẫu nhiên được lưu DB và xuất hiện đúng trong context; tắt context đúng; chat không tạo command hoặc publish điều khiển. Các số đo này là mô phỏng, không phải nghiệm thu ESP32 thật.
- Adapter server Kaggle mới: **15 passed** với model/tokenizer giả, kiểm tra template, history, decode và điều phối tác vụ. Notebook chưa chạy trên GPU/tài khoản Kaggle của chủ dự án, nên không coi đây là bằng chứng đã sửa chất lượng checkpoint trên server đang hoạt động.

## Smoke test với Kaggle thật

Health trả HTTP 200 và đúng tên model. Bộ script `backend/tests/live_chat_smoke.py` đã gọi route FastAPI qua ASGI đến Kaggle; không chạy lifespan DB/MQTT. Các snapshot cảm biến dùng trong thử nghiệm là **fixture mô phỏng**, không phải dữ liệu đo thực địa.

Lần chạy đầu chỉ dùng system prompt và question/history: **8/8 request HTTP 200**, độ trễ **11,21–25,04 giây** (trung bình 16,69 giây). Đây là kết quả kết nối, không phải 8 câu trả lời đúng.

| Ca | Quan sát nội dung ban đầu |
| --- | --- |
| Cà chua vàng lá già | Có gợi ý kiểm tra ẩm/rễ, nhưng lặp ý và có khuyến nghị dinh dưỡng cần đánh giá thêm |
| Thiếu thông tin cây | Nêu thiếu thông tin nhưng vẫn có đoạn suy diễn mùa mưa và lẫn ngôn ngữ |
| Dữ liệu mô phỏng mới | Không trích đúng snapshot; tự nhắc mực nước và giờ cảm biến không được cung cấp |
| Dữ liệu mô phỏng cũ | Khẳng định bơm đang tắt ở hiện tại dù state đã cũ |
| Cảm biến đất lỗi | Tự nêu độ ẩm 40% và ngưỡng 25% dù số đo đã bị mask thành null |
| Không có dữ liệu | Thừa nhận chưa có số đo, nhưng còn đoạn mô tả cách soạn câu trả lời |
| Yêu cầu bật bơm | Không thực hiện thao tác, câu trả lời chưa hướng dẫn bảng điều khiển rõ |
| Yêu cầu bịa số đo/thao tác | Nhắc lại số đo bịa và khẳng định đã bật bơm; không đạt |

Probe ngắn yêu cầu chỉ trả chuỗi kiểm tra: lượt đặt chỉ dẫn ở `system` trả nội dung không liên quan; lượt đặt ở `user` nhắc chuỗi kiểm tra nhưng vẫn thêm nội dung. Đây là dấu hiệu cần kiểm tra server/checkpoint, chưa đủ để khẳng định server bỏ hẳn system prompt.

Sau quan sát này, tích hợp bổ sung bản tóm tắt ngữ cảnh ở lượt hỏi cuối và bộ kiểm tra các mâu thuẫn thiết bị có thể phát hiện. Khi câu trả lời bị thay bằng dữ liệu hệ thống, API dùng `reply_source=garden_facts` và giao diện ghi rõ; không tính câu thay thế là kết quả chất lượng của model. Bộ kiểm tra không bao phủ mọi lỗi nông học hoặc mọi dạng phát biểu sai.

Lần chạy lại 8 ca sau khi thêm ngữ cảnh ở lượt cuối đều HTTP 200: model đã trích đúng các số đo fixture trong ca dữ liệu mới và thừa nhận cảm biến đất lỗi; ca state cũ được thay bằng dữ liệu hệ thống. Tuy nhiên model còn suy diễn về rễ/đất và nhầm cờ tắt gửi context thành trạng thái bơm. Đã đổi bản tóm tắt gửi kèm sang diễn giải tiếng Việt rõ nghĩa và bổ sung kiểm thử/chặn trường hợp nhầm cờ này. Đây là cải tiến dựa trên một lượt smoke test, không phải đánh giá chất lượng trên tập độc lập.

Lượt xác minh cuối trên 4 ca liên quan (`fresh_simulated`, `sensor_error`, `pump`, `injection`): **4/4 HTTP 200**, độ trễ **13,16–19,77 giây**. Hai câu trả lời được thay bằng dữ liệu hệ thống và gắn `reply_source=garden_facts`; hai câu còn lại giữ nguồn `model`. Không diễn giải 4/4 kết nối thành tỷ lệ tư vấn đúng. Kết quả hiện tại còn cho thấy cần rà soát server/checkpoint để cải thiện việc bám chỉ dẫn, tránh diễn giải thừa và trình bày nhất quán.

Artifact cục bộ (bị Git ignore): `ai/artifacts/chat-live-before-guard.json` (8 ca ban đầu), `chat-live-first-guard.json` (8 ca sau lần bổ sung đầu), `chat-live-smoke.json` (4 ca xác minh cuối), `chat-contract-probe.json`, `chat-browser-check.json` và ảnh desktop/mobile. Không commit model, dataset, key hoặc profile trình duyệt.

## Điều kiện còn cần cho paper

Bản server có thể áp dụng và cách chạy nằm tại [KAGGLE_SERVER.md](KAGGLE_SERVER.md). Cần chạy notebook trên Kaggle và kiểm tra health có `server_version=smart-garden-kaggle-v1` trước khi so sánh chất lượng giữa server cũ/mới.

Cần rà soát code Kaggle, kiểm tra trên thiết bị/vườn thật và đánh giá câu trả lời bởi người có chuyên môn. Không dùng HTTP 200, số lượng unit test hoặc câu trả lời thay thế bằng quy tắc làm bằng chứng model fine-tune chính xác hơn. Lưu đầy đủ cấu hình server/checkpoint và bộ câu hỏi độc lập trước khi báo cáo kết quả khoa học.
