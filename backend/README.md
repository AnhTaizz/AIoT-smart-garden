# Backend

Trạng thái: B-W1-01 và B-W1-02 đã triển khai theo bản đề xuất v1 cho G02, chờ Toản (C) review và chờ nhóm chốt contract. Payload MQTT và REST theo mục [Bản đề xuất v1 của Tài (B)](../docs/INTERFACES.md) trong `docs/INTERFACES.md`; mục đó vẫn là **DRAFT**, chưa ai xác nhận.

FastAPI chạy bằng Uvicorn. Khi khởi động, backend:

1. Mở pool PostgreSQL (không chặn: `/health` vẫn trả 200 khi DB chưa sẵn sàng).
2. Chạy migration SQL trong `app/migrations/` (thử lại mỗi 2 giây tới khi DB lên, có advisory lock và bảng `schema_migration`; lỗi migration được ghi log kèm nguyên nhân).
3. Kết nối Mosquitto với `clean_session=true` tường minh, subscribe `garden/+/telemetry` (QoS 0), `garden/+/ack` và `garden/+/state` (QoS 1). Tự kết nối lại khi broker restart.
4. Chạy vòng quét chuyển command quá hạn sang `timeout` mỗi giây.

## Cấu trúc

| File | Vai trò |
| --- | --- |
| `app/main.py` | Lifespan, REST endpoint, thân lỗi chuẩn hóa |
| `app/mqtt_bridge.py` | paho-mqtt chạy thread riêng, chuyển bản tin vào `asyncio.Queue` |
| `app/ingest.py` | Validate bản tin MQTT, lưu dữ liệu hợp lệ, ghi bản tin lỗi |
| `app/schemas.py` | Pydantic model cho telemetry/ACK/state/command v1 |
| `app/repository.py` | Toàn bộ SQL: dedup telemetry, bằng chứng theo command, boot, thứ tự |
| `app/migrations/*.sql` | `telemetry`, `rejected_message`, `command`, `command_event`, `device_state`, `device_boot`, `device_command_counter` |

## Endpoint

Qua dashboard dùng tiền tố `/api` (Nginx/Vite proxy); gọi trực tiếp FastAPI thì bỏ `/api`.

| Endpoint | Ý nghĩa |
| --- | --- |
| `GET /health` | Tiến trình API sống: 200 `{"status":"ok"}` |
| `GET /ready` | Chạy `SELECT 1` trên PostgreSQL: 200 hoặc 503 |
| `GET /devices/{id}/latest` | Telemetry mới nhất đã lưu (theo `received_at`), kèm `stale`; 404 `no_telemetry` nếu chưa có |
| `GET /devices/{id}/telemetry?from=&to=&limit=100&order=asc` | `limit` bản ghi mới nhất (1–1000) theo `received_at`; `count == limit` chỉ nghĩa **có thể** còn dữ liệu cũ hơn |
| `POST /devices/{id}/commands` | `{"action":"pump_on","duration_seconds":10}` hoặc `{"action":"pump_off"}`. Trả **202** `pending`; `pump_on` cần backend đã biết `boot_id`, nếu chưa thì 409 `device_boot_unknown` |
| `GET /commands/{command_id}` | `pending`/`applied`/`rejected`/`timeout` kèm `device_ack`, `reason`, bằng chứng state và `late_ack` |
| `GET /devices/{id}/commands?limit=20` | `{device_id, count, items}` sắp theo `command_sequence` giảm dần |
| `GET /devices/{id}/state` | State thiết bị tự báo gần nhất kèm `boot_id`, `state_sequence`, `stale`; 404 `no_state` |

Mọi lỗi dùng chung một dạng, kể cả 422:

```json
{"detail": {"code": "no_telemetry", "message": "Thiết bị chưa có telemetry nào được lưu."}}
```

`device_id` và `boot_id` chỉ gồm `A-Z a-z 0-9 _ -`, tối đa 64 ký tự.

### Vòng đời command

`applied` cần **hai** bằng chứng: ACK `applied` và một state có `last_command_id` trùng, cùng boot, và `relay_state` khớp hành động (`on` cho `pump_on`, `off` cho `pump_off`).

```text
POST → pending ──ACK accepted──▶ pending
          │──ACK applied + state khớp──▶ applied
          │──ACK rejected─────────────▶ rejected (giữ reason)
          │──state mới boot_id────────▶ timeout (backend:device_rebooted)
          └──quá expires_at───────────▶ timeout ──bằng chứng muộn──▶ vẫn timeout, giữ late_ack/state_confirmed_*
```

- Bằng chứng lưu theo từng command (`state_confirmed_at`, `confirmed_relay_state`, `confirmed_state_sequence`, `confirmed_boot_id`), tách khỏi state mới nhất của thiết bị. Lệnh ON 5 giây vẫn `applied` sau khi bơm tự tắt, còn `/state` hiển thị `off`.
- Chỉ nhận state `off` mà chưa có bằng chứng `on` thì `pump_on` **không** được coi là `applied`.
- `command_sequence` cấp nguyên tử trên bảng `device_command_counter` nên không lùi khi backend restart; thiết bị dùng nó làm mốc thứ tự để một ON cũ không chạy sau một OFF mới hơn.
- `pump_on` mang `target_boot_id`; ACK/state từ boot khác bị ghi nhận là cũ và không đổi trạng thái. `pump_off` không gắn boot nên vẫn dùng được sau reboot.
- State của boot đã bị thay thế không làm state hiện tại quay lại boot cũ; state có `state_sequence` nhỏ hơn bị bỏ qua khi cập nhật state hiện tại.
- `applied` chỉ xác nhận thiết bị báo đã đóng/ngắt relay, **không** chứng minh có nước chảy.
- Command publish QoS 1, không retained; broker không giữ lệnh cho thiết bị offline.

### Bản tin lỗi và bản tin trùng

JSON hỏng, sai kiểu, ngoài miền, thiếu trường, `measured_at` lệch với `clock_synced`, `sensor_status` không khớp giá trị `null`, hoặc `device_id` khác topic → ghi vào `rejected_message` kèm lý do, log WARNING, **không** vào `telemetry`, subscriber vẫn chạy.

Telemetry trùng `device_id` + `boot_id` + `sequence` bị **bỏ qua im lặng**: đó là bản gửi lại, không phải dữ liệu lỗi, nên không vào `rejected_message`.

## Cấu hình

| Biến | Mặc định | Ghi chú |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_CONNECT_TIMEOUT_SECONDS` | Compose cung cấp | Không đặt thông tin thật trong Git |
| `MQTT_HOST`, `MQTT_PORT` | `mosquitto`, `1883` | `MQTT_USERNAME`/`MQTT_PASSWORD` nếu broker yêu cầu |
| `COMMAND_TIMEOUT_SECONDS` | 15 | Hạn nhận đủ bằng chứng; giá trị nháp chờ G02 |
| `COMMAND_MAX_DURATION_SECONDS` | 120 | Chỉ kiểm tra input; thiết bị vẫn giữ giới hạn bơm riêng |
| `TELEMETRY_STALE_SECONDS` | 30 | Ngưỡng `stale` cho `/latest` và `/state` |

## Chạy và kiểm tra

```bash
cp .env.example .env          # lần đầu
docker compose up --build -d
docker compose logs -f backend
```

Chạy simulator (thiết bị mô phỏng đủ hai chiều) rồi đọc lại qua proxy dashboard:

```bash
cd simulator && python -m pip install -r requirements.txt
python simulator.py --device-id node_01 --interval 2
curl "http://127.0.0.1:5173/api/devices/node_01/telemetry?limit=10"
curl http://127.0.0.1:5173/api/devices/node_01/state
curl -X POST -H "Content-Type: application/json" \
  -d '{"action":"pump_on","duration_seconds":10}' \
  http://127.0.0.1:5173/api/devices/node_01/commands
curl http://127.0.0.1:5173/api/commands/<command_id>
```

### Test tự động

Backend cần Python ≥ 3.11 nên chạy test trong container. Unit test không cần DB:

```bash
docker run --rm -v "$PWD/backend:/src" -w /src python:3.12-slim \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q tests/test_validation.py"
```

E2E cần stack đang chạy, gắn vào mạng Compose:

```bash
docker run --rm --network smart-garden_default -v "$PWD/backend:/src" -w /src \
  -e E2E_API_BASE_URL=http://backend:8000 -e E2E_MQTT_HOST=mosquitto \
  -e DB_HOST=postgres -e DB_PORT=5432 -e DB_NAME=smart_garden \
  -e DB_USER=smart_garden -e DB_PASSWORD=<POSTGRES_PASSWORD trong .env> \
  python:3.12-slim sh -c "pip install -q -r requirements-dev.txt && python -m pytest -v tests/e2e"
```

Trên Git Bash (Windows) thêm `MSYS_NO_PATHCONV=1` và dùng `$(pwd -W)/backend`. E2E dùng `device_id` ngẫu nhiên `e2e_xxxxxxxx` nên không lẫn dữ liệu demo `node_01`. `tests/e2e/test_backend_e2e.py` là nghiệm thu B-W1; `tests/e2e/test_g02_contract.py` là các quy tắc G02 (bằng chứng state, boot/reboot, thứ tự command, dedup, thân lỗi).

## Ranh giới và hạn chế đã biết

- Backend không chạy logic tự tưới song song với ESP32; chỉ kiểm tra, chuyển lệnh và lưu kết quả.
- Bản tin đến khi PostgreSQL đang down bị log lỗi và bỏ qua (không buffer lâu dài); command khi DB down trả 503 và không được publish.
- MQTT subscriber dùng clean session: ACK/state gửi lúc backend tắt sẽ mất, command khi đó về `timeout`.
- Backend học `boot_id` từ state nên một state của boot chưa từng thấy luôn được coi là boot mới; không có thứ tự tuyệt đối giữa hai boot chưa biết.
- Chưa có xác thực API/MQTT (chỉ dùng trong LAN tin cậy, xem `compose.lan.yaml`).
- Chưa kiểm tra với ESP32 thật; đồng bộ giờ cho ESP32 là đầu việc trước M2 (xem `docs/INTERFACES.md`).
