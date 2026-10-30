# BC-01 — Tích hợp B/C: Mobile + Chatbot

Ngày: 2026-10-30. Nhánh: `feat/bc-01-mobile-chat-integration`, tạo từ `main` tại `13e1ac0` (merge PR #5). Người thực hiện: Claude Code theo yêu cầu của Tài (B). Firmware không bị sửa; G02/G03 không bị đổi trạng thái.

## 1. Audit repository (kiểm chứng bằng Git/GitHub)

| Hạng mục | Trạng thái kiểm chứng |
| --- | --- |
| `main` | `13e1ac0`; đã merge PR #1, #2 (backend/simulator), #3 (dashboard), #5 (chatbot Qwen3) |
| PR #4 `feat/remote-mobile-cloudflare` | Mở, chưa merge. Merge-base với `main` là `208bf77` (PR #3). 4 commit riêng: `e1219cf` (docs G02 AGREED, M1 nghiệm thu), `d7a5804` (Cloudflare/CORS/Capacitor), `30c805a` (test), `e4b4221` (docs Android 4G) |
| File trùng giữa PR #4 và PR #5 | `.env.example`, `README.md`, `backend/README.md`, `backend/app/config.py`, `backend/app/main.py`, `compose.yaml`, `frontend/README.md`, `frontend/nginx.conf`, `frontend/package*.json`, `frontend/src/App.tsx`, `frontend/src/api.ts` |
| Firmware | Chỉ có trên `feat/A-W1-esp32-firmware` (`a052b49`, Wokwi), chưa vào `main` |
| `docs/PROJECT_STATE.md` trên `main` | Đã cũ (2026-09-26, còn ghi PR #2 chưa merge); đã cập nhật trong BC-01 |

### Phân loại chức năng

| Phân loại | Chức năng |
| --- | --- |
| **Đã hoàn thiện (mức thành phần, có test)** | MQTT ingest → PostgreSQL; `latest`/`telemetry`/`state`/`commands` REST; vòng đời `pending/applied/rejected/timeout` có late ACK; simulator hai chiều có fail-safe; dashboard React telemetry/lịch sử/điều khiển bơm; chatbot backend `/chat` + UI Markdown; Compose dev/LAN |
| **Đã code nhưng chưa tích hợp (trước BC-01)** | Capacitor Android, cấu hình API HTTPS cho native, CORS, timeout 10 giây cho request, retry giới hạn chỉ cho GET trạng thái lệnh, script Cloudflare tunnel, `compose.device.yaml`, `compose.test.yaml` (đều trên PR #4). Scaffold iOS (PR #4). Firmware ESP32 (nhánh của A) |
| **Chưa triển khai** | Xác thực API/MQTT; chế độ AUTO và API cấu hình (M3); ESP32-CAM/ảnh/AI inference (M4); WebSocket (đang polling REST); PWA |
| **Đang lỗi / rủi ro phát hiện** | (1) Dashboard coi mọi lỗi API của latest/state/history là "Chưa có dữ liệu"; (2) PR #4 cho phép điều khiển bơm qua Quick Tunnel công khai khi API chưa có xác thực; (3) `CHAT_API_URL` mặc định là một URL ngrok free cố định trong `config.py`/`compose.yaml`, chết khi phiên Kaggle tắt (chat trả `503 chat_unavailable`); (4) nhãn lịch sử lệnh gọi `timeout` là "Hết hạn", dễ nhầm với reason `expired`; (5) PR #4 đổi tài liệu sang "G02 AGREED / M1 đã nghiệm thu" trong khi `main` vẫn DRAFT |

(1), (2), (4) được sửa trong BC-01. (3), (5) cần nhóm quyết định, xem mục 6.

## 2. Những gì đã tích hợp

Cherry-pick hai commit code/test của PR #4 (giữ tác giả gốc), giải quyết conflict để **giữ cả** chatbot và mobile:

- `backend/app/config.py`: giữ toàn bộ `CHAT_*` và thêm `cors_origins`; `main.py` giữ `include_router(chat_router)` và thêm `configure_cors`; `compose.yaml` truyền cả `CHAT_*` và `CORS_ORIGINS`.
- `frontend/src/api.ts`: các request thường dùng `apiFetch` (timeout 10 giây, không retry POST); `sendChat` giữ timeout 145 giây riêng. `resolveApiBaseUrl` giữ Web `/api`, bắt buộc HTTPS công khai cho native.
- `package.json`/`package-lock.json`: thêm `@capacitor/core`, `@capacitor/android`, `@capacitor/cli` 8.5.2 bên cạnh `react-markdown`. Lockfile sinh lại bằng `npm install`.
- Dockerfile frontend dùng `npm ci` + lockfile; `.dockerignore` loại `android/`.

Không đưa vào: commit tài liệu `e1219cf`/`e4b4221` (trạng thái G02/M1 cần cả nhóm xác nhận), scaffold iOS và `@capacitor/ios` (ngoài phạm vi Android, chưa build được ở đây), comment đánh dấu LAN demo là "DEPRECATED" (trái với mục tiêu LOCAL MOBILE DEMO).

Thay đổi riêng của BC-01:

| Thay đổi | File |
| --- | --- |
| Chặn lệnh bơm từ tunnel/Internet: `POST /devices/{id}/commands` → `403 remote_control_disabled` trước khi chạm DB/MQTT; `GET /control-access` cho UI | `backend/app/access.py`, `backend/app/main.py` |
| UI khóa nút bơm kèm giải thích khi `commands_allowed: false` | `frontend/src/App.tsx`, `frontend/src/api.ts` |
| Phân biệt lỗi API với chưa có dữ liệu; state cũ hiển thị "Trạng thái cũ" + cảnh báo offline; nhãn "Hết thời gian chờ · ACK đến trễ"; thông báo applied nêu rõ ACK + state | `frontend/src/App.tsx` |
| Nginx `/api/chat` chuyển `X-Forwarded-*` như `/api/` | `frontend/nginx.conf` |
| Test unit/E2E mới | `backend/tests/test_access.py`, `backend/tests/e2e/test_remote_access_e2e.py`, `frontend/src/App.test.tsx`, `compose.test.yaml`, `backend/tests/run_e2e.py` |
| Tài liệu | `README.md`, `backend/README.md`, `frontend/README.md`, `docs/INTERFACES.md` (bổ sung đề xuất, vẫn DRAFT), `docs/PROJECT_STATE.md`, `.env.example`, `compose.lan.yaml` |

Hành vi khác PR #4: PR #4 ghi nhận người dùng đã bật/tắt bơm từ app Android qua 4G. Trên nhánh BC-01, đường đó **cố ý bị chặn** cho tới BC-02. App Android hiện chỉ giám sát; điều khiển từ điện thoại dùng LAN demo.

## 3. Kiểm chứng giao tiếp B/C (phiên thật 2026-10-30)

Môi trường: Linux container, Docker 29.9.2, stack Compose thật (Nginx/React, FastAPI, Mosquitto 2.0, PostgreSQL 16), simulator `node_01` thật, Chromium headless qua Playwright. Không phải điện thoại thật.

| Luồng | Kết quả quan sát |
| --- | --- |
| MQTT → Backend → PostgreSQL → REST → React | PASS: UI hiển thị số đo simulator, nhãn "Dữ liệu mô phỏng", "Trực tuyến", sparkline |
| React → REST → MQTT → Simulator → ACK/state → React | PASS: `POST` 202 `pending` → UI "Đang đợi ACK" → `applied`, `device_ack=applied`, `confirmed_relay_state=on`, cùng `command_id` từ POST tới UI; `pump_off` → applied, relay tắt |
| Rejected | PASS: simulator `--clock-unsynced` → UI "Thiết bị từ chối lệnh: Thiết bị chưa đồng bộ giờ UTC", không có thông báo thành công |
| Timeout | PASS: dừng simulator → UI pending rồi "Quá thời hạn phản hồi (timeout)", lịch sử ghi "Hết thời gian chờ"; không gửi lại lệnh |
| Online → offline/stale | PASS: sau ~30 giây không có state, pump card hiển thị "Trạng thái cũ: tắt" + cảnh báo; API `latest.stale=true` |
| React → FastAPI → Chatbot API → React | PASS **với engine STUB**: `ai/kaggle_server.py` thật chạy engine trả lời cố định (không phải Qwen3) → `/api/chat` 200, `context.status=included`, cảnh báo dữ liệu mô phỏng, Markdown hiển thị. Đây chỉ là kiểm tra đường truyền/contract, không đánh giá model |
| Chatbot qua URL ngrok mặc định | KHÔNG CHẠY ĐƯỢC: proxy của môi trường chặn `*.ngrok-free.dev` (403). Backend trả đúng `503 chat_unavailable`, UI hiện lỗi |
| Mobile (viewport 390×844) qua tunnel | PASS mô phỏng: trình duyệt gửi header Cloudflare (`Cf-Connecting-Ip`, `Cf-Ray`) qua Nginx → telemetry/state vẫn hiển thị, hai nút bơm disabled kèm giải thích, `fetch` POST thủ công → `403 remote_control_disabled` |

## 4. Kết quả kiểm thử tự động

| Kiểm thử | Lệnh | Kết quả |
| --- | --- | --- |
| Baseline `main` trước khi sửa | unit + simulator + frontend + E2E | Backend unit 96/96; simulator 31/31; frontend 18/18 + build; E2E 33 pass, 2 skip (live Kaggle) |
| Compose config | `docker compose config` (base, `+lan`, `+device`, `+test --profile tests`) | Tất cả parse được; LAN: chỉ 5173/1883 bind `0.0.0.0`, API/PostgreSQL `127.0.0.1` |
| Backend unit + E2E thật | `docker compose -f compose.yaml -f compose.test.yaml --profile tests run --build --rm regression-tests` | **163 pass, 2 skip** (2 test live Kaggle cần `E2E_CHAT_LIVE=1`). Gồm 125 unit (có `test_access.py` 22, `test_http_config.py` 7, `test_chat.py`) và 38 E2E (có 5 E2E chặn từ xa, 1 qua Nginx) |
| Simulator | cùng service trên | 31/31 OK |
| Frontend | `npm test`, `npm run build` | 35/35 test, TypeScript + Vite build OK (image Docker frontend cũng chạy `npm test` khi build) |
| `build:mobile` | URL rỗng / HTTP / `/api` / URL trả HTML / HTTPS tới FastAPI | 4 trường hợp sai bị từ chối đúng thông báo; HTTPS tới FastAPI (forwarder TLS cục bộ, chứng chỉ tự ký) build `dist-mobile` OK |
| `npx cap sync android` | | OK; file sinh ra bị Git ignore |
| `./gradlew assembleDebug` | | **KHÔNG CHẠY ĐƯỢC**: `dl.google.com` (Android Gradle Plugin/AndroidX/SDK) bị proxy chặn 403; không có Android SDK |

Ghi chú môi trường: để build image trong container này phải tạo tạm base image `python:3.12-slim`/`node:22-alpine` có CA của proxy. Đây chỉ là cấu hình máy kiểm tra, không commit.

## 5. Cần người dùng kiểm tra trên thiết bị thật

1. Build APK trên máy có Android SDK theo [frontend/README](../frontend/README.md#app-android-capacitor), cài lên Android thật, dùng 4G/5G qua backend tunnel: telemetry/state hiển thị, nhãn mô phỏng/thật, stale khi tắt simulator, nút bơm khóa kèm giải thích, chatbot trả lời hoặc báo lỗi rõ.
2. Điện thoại cùng Wi-Fi/hotspot mở `http://<IP_LAN_LAPTOP>:5173` (`compose.lan.yaml`): bật bơm 5 giây → pending → applied, tắt bơm → applied. Đây là phần M1 còn thiếu.
3. Web qua frontend tunnel trên điện thoại: chỉ đọc, nút bơm khóa.
4. Chatbot với phiên Kaggle Qwen3 thật: `backend/tests/run_e2e.py --live-chat`.

## 6. Blocker, technical debt và rủi ro

- **Blocker:** chưa có Android SDK/Google Maven trong môi trường này nên APK chưa được build lại sau khi tích hợp; Kaggle/ngrok không truy cập được từ đây.
- **Cần nhóm quyết định:** PR #4 ghi G02 AGREED và M1 Web/LAN đã nghiệm thu (2026-09-29) nhưng chưa merge; `main` vẫn DRAFT. BC-01 không tự đổi. Nếu nhóm đã xác nhận thật, cần một PR tài liệu riêng có xác nhận của Thành/Tài/Toản.
- **Rủi ro bảo mật:** rào chắn tunnel dựa vào việc proxy tự khai báo header. Port-forward thẳng từ router không bị nhận diện. API đọc dữ liệu và `/chat` vẫn mở cho ai biết URL tunnel; `/chat` có thể làm tốn tài nguyên Kaggle. MQTT anonymous.
- **Technical debt:** `CHAT_API_URL` mặc định là URL ngrok cố định trong code/compose, nên để rỗng và báo "chưa cấu hình"; URL Quick Tunnel đổi sau mỗi lần khởi động lại nên phải build lại APK; `CORS_ORIGINS` đọc lúc import module; iOS scaffold còn ở PR #4; polling REST thay vì WebSocket; script tunnel chỉ có PowerShell.
- **PR #4:** sau khi BC-01 được review, PR #4 nên đóng hoặc thu gọn chỉ còn phần tài liệu cần nhóm quyết định, tránh merge đè lên chatbot.

## 7. Đề xuất BC-02

1. Xác thực API cho thao tác điều khiển: token thiết bị/người dùng phía backend (ví dụ đăng nhập đơn giản + session/token ngắn hạn, hoặc Cloudflare Access trước tunnel), rate limit `/chat` và `POST /commands`; chỉ sau đó mới cho phép lệnh từ xa, có test E2E qua tunnel.
2. Bỏ URL ngrok mặc định; thêm `/chat` health/config rõ ràng trên dashboard.
3. Cấu hình URL backend cho app lúc chạy (không phải build lại APK khi tunnel đổi), hoặc dùng named tunnel ổn định.
4. MQTT username/password và ACL theo `device_id` trước khi ESP32 thật (phối hợp A).
5. Chạy phiên M1 đầy đủ trên smartphone LAN và ghi bằng chứng; Android 4G read-only theo mục 5.
