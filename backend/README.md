# Backend

Trạng thái: B-W1-01 (MQTT → PostgreSQL) và B-W1-02 (REST telemetry + vòng đời command) đã triển khai, chờ Toản (C) review và tích hợp với simulator nhận command (A-W1-02). Payload MQTT/API đang theo bản **đề xuất** trong [INTERFACES](../docs/INTERFACES.md#đề-xuất-triển-khai-của-tài-b--chờ-g02); chưa phải contract AGREED.

FastAPI chạy bằng Uvicorn. Khi khởi động, backend:

1. Mở pool PostgreSQL (không chặn: `/health` vẫn trả 200 khi DB chưa sẵn sàng).
2. Chạy migration SQL trong `app/migrations/` (thử lại mỗi 2 giây tới khi DB lên; có advisory lock và bảng `schema_migration`).
3. Kết nối Mosquitto, subscribe `garden/+/telemetry` (QoS 0), `garden/+/ack` và `garden/+/state` (QoS 1). Tự kết nối lại khi broker restart.
4. Chạy vòng quét chuyển command quá hạn sang `timeout` mỗi giây.

## Cấu trúc

| File | Vai trò |
| --- | --- |
| `app/main.py` | Lifespan, REST endpoint, xử lý lỗi DB → 503 |
| `app/mqtt_bridge.py` | paho-mqtt chạy thread riêng, chuyển bản tin vào `asyncio.Queue` |
| `app/ingest.py` | Validate bản tin MQTT, lưu dữ liệu hợp lệ, ghi bản tin lỗi |
| `app/schemas.py` | Pydantic model cho telemetry/ACK/state/command |
| `app/repository.py` | Toàn bộ SQL, gồm máy trạng thái command |
| `app/migrations/*.sql` | Bảng `telemetry`, `rejected_message`, `command`, `command_event`, `device_state` |

## Endpoint

Qua dashboard dùng tiền tố `/api` (Nginx/Vite proxy); gọi trực tiếp FastAPI thì bỏ `/api`.

| Endpoint | Ý nghĩa |
| --- | --- |
| `GET /health` | Tiến trình API sống: 200 `{"status":"ok"}` |
| `GET /ready` | Chạy `SELECT 1` trên PostgreSQL: 200 hoặc 503 |
| `GET /devices/{id}/latest` | Telemetry mới nhất đã lưu (theo thời điểm server nhận), kèm `stale` (quá `TELEMETRY_STALE_SECONDS`); 404 nếu chưa có |
| `GET /devices/{id}/telemetry?from=&to=&limit=100&order=asc` | `limit` bản ghi mới nhất (1–1000) có `measured_at` trong [from, to]; `order` chỉ đổi thứ tự trả về. `from`/`to` phải có múi giờ |
| `POST /devices/{id}/commands` | Body `{"action":"pump_on","duration_seconds":10}` hoặc `{"action":"pump_off"}`. Trả **202** với `status: "pending"` — chỉ nghĩa là backend đã lưu và publish |
| `GET /commands/{command_id}` | `pending` / `applied` / `rejected` / `timeout`, kèm `device_ack`, `reason`, `state_confirmed_at`, `late_ack` |
| `GET /devices/{id}/commands?limit=20` | Lịch sử command mới nhất |
| `GET /devices/{id}/state` | State thiết bị tự báo gần nhất; 404 nếu chưa có |

`device_id` chỉ gồm `A–Z a–z 0–9 _ -`, tối đa 64 ký tự. DB lỗi → 503 `database_unavailable`; MQTT mất kết nối khi tạo command → 503 `mqtt_unavailable` (không tạo command).

### Vòng đời command

```text
POST → pending ──ACK accepted──▶ pending (device_ack = accepted)
          │──ACK applied──▶ applied
          │──ACK rejected─▶ rejected (giữ reason)
          └──quá expires_at─▶ timeout ──ACK tới trễ──▶ vẫn timeout, ghi late_ack
```

- Chỉ ACK có cùng `command_id` **và** cùng `device_id` với command mới đổi trạng thái; ACK từ thiết bị khác bị ghi vào `rejected_message` (`ack_device_mismatch`).
- ACK đến sau `expires_at` luôn bị coi là trễ, kể cả khi vòng quét chưa chạy; `timeout` không bao giờ tự thành `applied`.
- State có `last_command_id` khớp chỉ đặt `state_confirmed_at`; không thay thế ACK.
- Mọi ACK/state được lưu vào `command_event` để truy vết.
- Command publish QoS 1, **không retained**, nên thiết bị kết nối lại không nhận lại lệnh cũ.

### Bản tin lỗi

JSON hỏng, sai kiểu (chuỗi thay số, bool thay số, NaN), ngoài miền (độ ẩm > 100, nhiệt độ ngoài −40…85), thiếu trường, thời gian không có múi giờ, hoặc `device_id` khác topic → ghi vào bảng `rejected_message` (lý do + tối đa 4096 ký tự gốc), log WARNING, **không** vào `telemetry`, và subscriber tiếp tục chạy. Giá trị cảm biến `null` được giữ là `null`, không đổi thành 0.

## Cấu hình

| Biến | Mặc định | Ghi chú |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_CONNECT_TIMEOUT_SECONDS` | Compose cung cấp | Không đặt thông tin thật trong Git |
| `MQTT_HOST`, `MQTT_PORT` | `mosquitto`, `1883` | `MQTT_USERNAME`/`MQTT_PASSWORD` nếu broker yêu cầu |
| `COMMAND_TIMEOUT_SECONDS` | 15 | Hạn nhận ACK cuối; giá trị nháp chờ G02 |
| `COMMAND_MAX_DURATION_SECONDS` | 120 | Chỉ là kiểm tra input ở backend; ESP32 vẫn giữ giới hạn bơm riêng |
| `TELEMETRY_STALE_SECONDS` | 30 | Ngưỡng `stale` cho `/latest` |

## Chạy và kiểm tra

```bash
cp .env.example .env          # lần đầu
docker compose up --build -d
docker compose logs -f backend
```

Phát 10 bản tin mô phỏng rồi đọc lại qua proxy dashboard:

```bash
cd simulator && python -m pip install -r requirements.txt
python simulator.py --count 10 --interval 0.5
curl "http://127.0.0.1:5173/api/devices/node_01/telemetry?limit=10"
curl http://127.0.0.1:5173/api/devices/node_01/latest
```

Thử command bằng tay (dùng `mosquitto_pub` thay thiết bị khi simulator chưa nhận command):

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"action":"pump_on","duration_seconds":10}' \
  http://127.0.0.1:5173/api/devices/node_01/commands
docker compose exec mosquitto mosquitto_pub -q 1 -t garden/node_01/ack \
  -m '{"command_id":"<ID>","device_id":"node_01","status":"applied"}'
curl http://127.0.0.1:5173/api/commands/<ID>
```

### Test tự động

Unit test (validate payload, không cần DB) và e2e test (MQTT + API + PostgreSQL thật; tự bỏ qua nếu thiếu `E2E_API_BASE_URL`). Backend cần Python ≥ 3.11, nên chạy trong container, gắn vào mạng Compose khi stack đang chạy:

```bash
docker run --rm --network smart-garden_default -v "$PWD/backend:/src" -w /src \
  -e E2E_API_BASE_URL=http://backend:8000 -e E2E_MQTT_HOST=mosquitto \
  -e DB_HOST=postgres -e DB_PORT=5432 -e DB_NAME=smart_garden \
  -e DB_USER=smart_garden -e DB_PASSWORD=<POSTGRES_PASSWORD trong .env> \
  python:3.12-slim sh -c "pip install -q -r requirements-dev.txt && python -m pytest -v tests"
```

Trên Git Bash (Windows) thêm `MSYS_NO_PATHCONV=1` trước lệnh và dùng `$(pwd -W)/backend`. E2E dùng `device_id` ngẫu nhiên `e2e_xxxxxxxx`, không lẫn dữ liệu demo `node_01`.

## Ranh giới và hạn chế đã biết

- Backend không chạy logic tự tưới song song với ESP32; chỉ chuyển lệnh và lưu kết quả.
- Chưa khử trùng telemetry (simulator reset sequence mỗi lần chạy); để B-W2-01 sau khi G02 chốt `boot_id`/sequence.
- Bản tin đến khi PostgreSQL đang down bị log lỗi và bỏ qua (không buffer lâu dài); command khi DB down trả 503 và không được publish.
- MQTT subscriber dùng clean session: ACK/state gửi lúc backend tắt sẽ mất; command khi đó sẽ về `timeout`.
- Chưa có xác thực API/MQTT (chỉ dùng trong mạng LAN tin cậy, xem `compose.lan.yaml`).
