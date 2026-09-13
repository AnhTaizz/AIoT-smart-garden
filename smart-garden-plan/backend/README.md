# Backend

Trạng thái: khung development của TASK-000B; chưa có nghiệp vụ Smart Garden.

Backend hiện là một dịch vụ FastAPI tối thiểu chạy bằng Uvicorn. Hai endpoint đã có:

| Endpoint | Ý nghĩa | Kết quả |
| --- | --- | --- |
| `GET /health` | Tiến trình API nhận được request | HTTP 200 và `{"status":"ok"}` |
| `GET /ready` | Mở kết nối mới và chạy `SELECT 1` trên PostgreSQL | HTTP 200 khi sẵn sàng; HTTP 503 khi lỗi kết nối |

`/ready` không trả thông tin kết nối hoặc chi tiết lỗi cho client. Backend lấy `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` và `DB_CONNECT_TIMEOUT_SECONDS` từ môi trường Compose.

## Chạy bằng Docker Compose

Từ thư mục gốc `smart-garden-plan/`:

```bash
cp .env.example .env
docker compose up --build -d
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

Các trách nhiệm về telemetry, command, lịch sử, ảnh và inference mới chỉ là phạm vi dự kiến trong kế hoạch. TASK-000B chưa tạo MQTT subscriber, bảng database, migration, API nghiệp vụ hoặc thuật toán tưới.

Backend không sở hữu một bộ điều khiển tưới tự động chạy song song với ESP32. Payload MQTT, API, schema dữ liệu và quy tắc command vẫn phải được cả nhóm chốt trong G02; không xem các gợi ý trong `docs/INTERFACES.md` là contract đã thống nhất.

Không đặt mật khẩu, token, chuỗi kết nối hoặc thông tin Wi-Fi thật trong Git.
