# Backend

Chatbot (PR #5): `POST /chat` (cần đăng nhập) kết nối API Kaggle tùy chỉnh, trả `reply/context/prompt_version`. Cấu hình `CHAT_*` chỉ ở backend; xem [hướng dẫn chatbot](../docs/CHATBOT.md). Kiểm thử cô lập bằng `python -m pytest -q tests/test_chat.py tests/test_validation.py`.

Trạng thái: B-W1-01 và B-W1-02 đã merge vào `main` (PR #2); BC-01 thêm CORS cấu hình được và chặn lệnh bơm từ xa (`app/access.py`). Payload MQTT và REST theo mục [Bản đề xuất v1 của Tài (B)](../docs/INTERFACES.md) trong `docs/INTERFACES.md`; mục đó vẫn là **DRAFT**, chưa ai xác nhận.

FastAPI chạy bằng Uvicorn. Khi khởi động, backend:

1. Mở pool PostgreSQL (không chặn: `/health` vẫn trả 200 khi DB chưa sẵn sàng).
2. Chạy migration SQL trong `app/migrations/` (thử lại mỗi 2 giây tới khi DB lên, có advisory lock và bảng `schema_migration`; lỗi migration được ghi log kèm nguyên nhân).
3. Kết nối Mosquitto với `clean_session=true` tường minh, subscribe `garden/+/telemetry` (QoS 0), `garden/+/ack` và `garden/+/state` (QoS 1). Tự kết nối lại khi broker restart.
4. Chạy vòng quét chuyển command quá hạn sang `timeout` mỗi giây.

## Cấu trúc

| File | Vai trò |
| --- | --- |
| `app/main.py` | Lifespan, REST endpoint, thân lỗi chuẩn hóa |
| `app/chat.py` | `POST /chat`: gọi API Kaggle, gắn bản chụp vườn, chặn khẳng định sai về thiết bị |
| `app/http_config.py` | CORS allow-list tường minh (không wildcard, không credentials) |
| `app/auth.py` | Đăng nhập, hash scrypt, phiên Bearer lưu hash trong PostgreSQL, dependency 401/403, CLI tạo hash |
| `app/access.py` | Quyền điều khiển theo role của phiên (`/control-access`) |
| `app/ratelimit.py` | Rate limit sliding window trong bộ nhớ một tiến trình |
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
| `GET /control-access` | `{"commands_allowed": bool, "reason": "forbidden" \| null, "role"}` theo phiên hiện tại; UI dùng để khóa nút bơm |
| `POST /chat` | Tư vấn nông nghiệp; không publish command. `CHAT_API_URL` trống → `503 chat_unavailable` (`reason: not_configured`) |

### Xác thực và phân quyền (BC-02)

Ngoài `GET /health`, `GET /ready` và `POST /auth/login`, mọi endpoint ở bảng trên cần `Authorization: Bearer <access_token>`; thiếu hoặc sai → **401**, tài khoản `viewer` gửi lệnh → **403**. Quyền chỉ dựa trên phiên ở server: một operator đã đăng nhập được gửi lệnh qua HTTPS tunnel (Cloudflare) giống như trong LAN; IP, header proxy và CORS không được xem là bằng chứng xác thực.

- **Tài khoản:** `OPERATOR_USERNAME`, `OPERATOR_PASSWORD_HASH` (scrypt N=2^17, r=8, p=1 từ thư viện chuẩn Python; tạo bằng `python -m app.auth hash-password`), `OPERATOR_ROLE` (`operator` | `viewer`). Không có giá trị mặc định; thiếu/sai → login `503 auth_not_configured`, mọi API bảo vệ `401` (fail closed).
- **Phiên:** token opaque ngẫu nhiên 256 bit. Bảng `auth_session` (migration `004`) chỉ lưu SHA-256 của token, `expires_at`, `revoked_at` và dấu vân tay tài khoản. Đổi username/mật khẩu/role làm mọi phiên cũ hết hiệu lực. `POST /auth/logout` thu hồi ngay.
- **Rate limit** (bộ đếm trong bộ nhớ **một tiến trình Uvicorn**; reset khi restart, không chia sẻ giữa nhiều worker): đăng nhập sai theo username (tên lạ gộp chung một bucket), `/chat` theo tài khoản, `pump_on` theo thiết bị. Vượt → `429` + `Retry-After`. `pump_off` không bao giờ bị giới hạn này.
- **Log:** không ghi mật khẩu, token hay hash; chỉ ghi "Login failed/succeeded".

| Endpoint | Ý nghĩa |
| --- | --- |
| `POST /auth/login` | `{"username","password"}` → `access_token`, `token_type: "bearer"`, `expires_at`, `user {username, role}` |
| `GET /auth/me` | Thông tin phiên hiện tại |
| `POST /auth/logout` | Thu hồi phiên hiện tại |

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
- Bằng chứng thứ hai chỉ chốt `applied` khi xử lý trước `expires_at`; tại hoặc sau hạn, transaction chuyển command sang `timeout` và vẫn giữ bằng chứng muộn. Quy tắc không phụ thuộc sweeper/GET.
- ACK tiến triển đơn điệu: `accepted` lặp không ghi đè một ACK `applied` đã lưu.
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
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,https://localhost,capacitor://localhost` | Danh sách origin cách nhau bằng dấu phẩy; `*` bị từ chối khi khởi động; rỗng = tắt CORS. Web cùng origin qua `/api` không cần thêm. CORS không phải xác thực |
| `CHAT_API_URL`, `CHAT_API_KEY`, `CHAT_TEMPERATURE`, `CHAT_MAX_TOKENS`, `CHAT_TIMEOUT_SECONDS` | Xem `.env.example` | Chỉ ở backend; xem [CHATBOT](../docs/CHATBOT.md) |

## Chạy và kiểm tra

```bash
cp .env.example .env          # lần đầu
docker compose up --build -d
docker compose logs -f backend
```

Chạy simulator (thiết bị mô phỏng đủ hai chiều), đăng nhập rồi đọc lại qua proxy dashboard. Đặt mật khẩu vào biến môi trường trong terminal (không ghi vào lịch sử lệnh hay file commit):

```bash
cd simulator && python -m pip install -r requirements.txt
python simulator.py --device-id node_01 --interval 2
read -rs OPERATOR_PASSWORD   # gõ mật khẩu operator, không hiện ra màn hình
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"username\":\"$OPERATOR_USERNAME\",\"password\":\"$OPERATOR_PASSWORD\"}" \
  http://127.0.0.1:5173/api/auth/login | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5173/api/devices/node_01/telemetry?limit=10"
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5173/api/devices/node_01/state
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"pump_on","duration_seconds":10}' \
  http://127.0.0.1:5173/api/devices/node_01/commands
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5173/api/commands/<command_id>
curl -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5173/api/auth/logout
```

### Test tự động

Chạy E2E từ máy host khi Compose đang hoạt động (runner đọc `.env` và cấu hình event loop tương thích Psycopg trên Windows):

```powershell
.\.venv\Scripts\python.exe backend/tests/run_e2e.py
.\.venv\Scripts\python.exe backend/tests/run_e2e.py --live-chat
```

Chạy từ root repo. Lệnh đầu kiểm tra IoT; lệnh thứ hai gọi Kaggle thật qua Nginx, dùng device ID ngẫu nhiên và telemetry mô phỏng. Các test chat xác nhận dữ liệu từ MQTT/DB đi vào context, tắt context đúng và không publish command; không chấm chất lượng nông học.

Cách gọn nhất trên stack thật (unit + E2E + simulator, không in mật khẩu DB; E2E dùng `device_id` riêng, không điều khiển `node_01`):

```bash
docker compose -f compose.yaml -f compose.test.yaml --profile tests run --build --rm regression-tests
```

E2E cần tài khoản operator của stack: đặt thêm `E2E_OPERATOR_PASSWORD=<mật khẩu gốc>` trong `.env` local (cùng `OPERATOR_USERNAME`/`OPERATOR_PASSWORD_HASH`); service test và `run_e2e.py` đọc từ đó. Stack phải chạy với `CHAT_API_URL` trống để kiểm tra chat chưa cấu hình. `tests/e2e/test_auth_e2e.py` kiểm tra: anonymous → 401, không tạo command, không publish (trực tiếp và qua Nginx); operator → 202 `pending` → `applied` qua ACK+state, kể cả có header tunnel; phiên hết hạn trong PostgreSQL hoặc đã logout → 401; bảng phiên không chứa token gốc; `pump_on` bị 429 nhưng `pump_off` vẫn 202; chat chưa cấu hình → 503 rõ ràng. Unit test: `tests/test_auth.py` (login, token, 401/403, fail closed, rate limit, log), `tests/test_http_config.py` (CORS).

Backend cần Python ≥ 3.11 nên chạy test trong container. Unit test không cần DB:

```bash
docker run --rm -v "$PWD/backend:/src" -w /src python:3.12-slim \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q tests/test_validation.py"
```

E2E cần stack đang chạy, gắn vào mạng Compose:

```bash
docker run --rm --network smart-garden_default -v "$PWD/backend:/src" -w /src \
  -e E2E_API_BASE_URL=http://backend:8000 -e E2E_MQTT_HOST=mosquitto \
  -e E2E_OPERATOR_USERNAME -e E2E_OPERATOR_PASSWORD \
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
- API dùng một tài khoản operator và rate limit trong bộ nhớ (xem [BC-02_REPORT](../docs/BC-02_REPORT.md)). MQTT **chưa** có username/password/ACL; không public MQTT/PostgreSQL.
- Chưa kiểm tra với ESP32 thật; đồng bộ giờ cho ESP32 là đầu việc trước M2 (xem `docs/INTERFACES.md`).
