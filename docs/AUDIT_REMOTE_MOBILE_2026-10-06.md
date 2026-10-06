# Phase 0 — Audit trước khi chuyển Cloudflare / Expo

> Báo cáo này giữ snapshot Phase 0 trước khi user chấp nhận audit. Quyết định tiếp theo đã đổi sang **KEEP CAPACITOR**, không tạo Expo; Phase 1/2 được tiếp tục theo [báo cáo mới](REMOTE_MOBILE_REPORT_2026-10-06.md). Những dòng chờ xác nhận và dự kiến Expo dưới đây là lịch sử tại thời điểm audit.

Ngày audit: 2026-10-06 (Asia/Bangkok). Nguồn sự thật: working tree hiện tại, không chỉ README hoặc HEAD.

**Trạng thái: Phase 0 hoàn tất; Phase 1/2 chưa bắt đầu, chờ xác nhận theo mục 5 của `task.txt`.** Có Capacitor/Android đã được triển khai và thay đổi quan trọng chưa commit. Yêu cầu xác nhận đã được gửi trong chat: giữ Capacitor làm legacy, bảo toàn working tree, triển khai Cloudflare rồi tạo client Expo riêng.

## 1. Initial repository state

- Branch: `main`.
- HEAD: `e1219cf7afe5f0709897a6b7c619cb03def36d0f`.
- Remote: `https://github.com/AnhTaizz/AIot-smart-garden.git`.
- Trước task: 67 tracked files đang modified. Khi bỏ khác biệt CRLF/LF, 10 file có thay đổi nội dung: `.env.example`, `README.md`, `docs/INTERFACES.md`, `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, `docs/assignments/B-BACKEND.md`, `docs/assignments/C-FRONTEND-AI.md`, `frontend/README.md`, `frontend/package.json`, `frontend/package-lock.json`.
- `.gitignore` trước task chỉ khác CRLF/LF; trong task này đã thêm `/task.txt`, giữ nguyên các rule và kiểu xuống dòng cũ.
- `frontend/android/` và `frontend/capacitor.config.ts` đang untracked; đó là implementation đã có, không phải file mới do task Cloudflare/Expo tạo.
- Các sửa Gradle Wrapper/log từ lượt trước đã tồn tại lúc audit và được giữ nguyên.
- Không commit, push, merge, reset hoặc staging.

## 2. Architecture before

```text
Browser cùng LAN / Capacitor Android WebView
             -> React
             -> /api (Nginx hoặc Vite proxy)
             -> FastAPI -> Mosquitto -> simulator
                              ^            |
                              |-- ACK/state|
FastAPI -> PostgreSQL
ESP32 thật: firmware chưa triển khai.
```

Base Compose bind các cổng host vào loopback. `compose.lan.yaml` expose cả frontend và MQTT trên `0.0.0.0`. Snapshot container thực tế đang dùng LAN override: frontend `0.0.0.0:5173`, Mosquitto `0.0.0.0:1883`; backend `127.0.0.1:8000`, PostgreSQL `127.0.0.1:55432`. Cả bốn container healthy khi kiểm tra. Không coi đó là bằng chứng phone/ESP32 thật đã hoạt động.

## 3. Current frontend stack

React `19.1.1`, TypeScript `5.8.3`, Vite `7.1.2`, Vitest `3.2.4`. UI có health/readiness, latest telemetry/history, device state, pump ON/OFF và command lifecycle. REST polling; không có MQTT client ở browser.

## 4. Current backend stack

FastAPI `0.116.1`, Uvicorn `0.35.0`, psycopg `3.2.9`, psycopg-pool `3.2.6`, paho-mqtt `2.1.0`; PostgreSQL 16 và Mosquitto 2.0 trong Compose. Backend làm migrations, ingest MQTT, lưu telemetry/ACK/state và quét timeout.

## 5. Current mobile implementation — khác giả định trong task

- Có Capacitor `8.5.2`, `frontend/capacitor.config.ts`, generated Android project và Gradle Wrapper.
- `MainActivity` chỉ extends `BridgeActivity`: app hiện đóng gói React trong WebView, không phải client React Native riêng.
- APK `frontend/android/app/build/outputs/apk/debug/app-debug.apk` tồn tại; không build lại APK trong audit này. Chỉ sự tồn tại không chứng minh APK hoạt động trên phone.
- Không có `mobile/`, Expo, React Native, Flutter hoặc iOS project.
- Không tìm thấy PWA manifest/service worker trong source hiện có.
- Debug Android manifest cho phép cleartext HTTP; tài liệu đang hướng dẫn URL LAN của Nginx.
- Roadmap/tài liệu đã chọn Capacitor và nói không dùng React Native. Yêu cầu mới chọn client cross-platform riêng sẽ thay đổi quyết định đó; cần ghi lại quyết định mới và giữ lịch sử nghiệm thu cũ.

## 6. Current API routing

`frontend/src/api.ts` đọc `VITE_API_BASE_URL`, mặc định `/api`; bỏ trailing slash, không hard-code LAN IP. Vite proxy `/api` tới `http://127.0.0.1:8000`, Nginx proxy `/api/` tới `http://backend:8000/` trong network Docker.

API thực tế: `GET /health`, `/ready`, `/devices/{id}/latest`, `/devices/{id}/telemetry`, `/devices/{id}/state`, `/devices/{id}/commands`, `/commands/{command_id}` và `POST /devices/{id}/commands`.

`POST` thành công trả **202**, trạng thái pending; backend chưa xác nhận relay đã đổi. Web hiện đọc trạng thái cuối từ API. `VITE_API_URL` chưa có; nếu thêm tên mới phải giữ compatibility với `VITE_API_BASE_URL` hiện có và Docker build args.

Backend có thể public độc lập qua cổng loopback 8000 cho tunnel trên host. Web có thể tiếp tục dùng `/api` qua tunnel frontend để tránh đổi URL mỗi lần Quick Tunnel restart; native app sau này dùng HTTPS URL tunnel backend, không dùng URL frontend.

## 7. Current WebSocket / CORS / proxy behavior

Không có endpoint WebSocket hoặc client WebSocket. README nhắc REST/WebSocket như mục tiêu, không phải implementation. Không tạo realtime backend mới chỉ để phục vụ mobile MVP; polling là lựa chọn phù hợp.

Không có CORSMiddleware hoặc CORS origins configurable. Cross-origin browser gọi backend public riêng sẽ cần allow-list cấu hình qua environment; native app không chịu browser CORS. Không có TrustedHost middleware hoặc cấu hình forwarded headers riêng trong source. Dockerfile chạy Uvicorn bind `0.0.0.0:8000`; host publishing vẫn loopback. Nginx hiện gửi Host/X-Real-IP nhưng chưa có forwarded proto config cho public HTTPS.

## 8. Current MQTT flow / safety

Backend subscribe `garden/+/telemetry`, `garden/+/ack`, `garden/+/state`; publish `garden/<id>/control` với QoS 1 và `retain=False`.

Source hiện giữ command UUID, monotonic sequence, `expires_at`, `target_boot_id` cho ON, timeout, ACK và state evidence. `applied` yêu cầu ACK applied + state relay khớp cùng boot, trước deadline; timeout không hồi sinh khi evidence muộn tới. Simulator có clock-unsynced rejection, OFF priority, duplicate/order rejection, local timer, reboot-OFF và disconnect-OFF/reconnect không replay ON.

State schema có MANUAL/AUTO. Simulator hiện báo MANUAL và backend không có endpoint đổi mode; không diễn giải đó thành Auto watering đã implement. `firmware/` chỉ có README, nên chưa có bằng chứng safety trên ESP32 thật.

Trong task này chưa sửa backend, simulator, firmware, database hoặc topic/ACK/state contract.

## 9. LAN-only assumptions / remaining IP references

Giả định phone cùng Wi-Fi vẫn nằm ở README, frontend/README, infra/README, roadmap, project state và assignments. `.env.example` hiện hướng dẫn Capacitor dùng URL LAN của Nginx.

Không tìm thấy địa chỉ LAN cá nhân hard-code trong application source được audit. `<IP_LAN_LAPTOP>` / `<LAPTOP_LAN_IP>` là placeholder tài liệu; `127.0.0.1` / localhost là local development, proxy target, healthcheck hoặc backend test; `backend` / `mosquitto` là Docker DNS. `10.0.26200.0` trong báo cáo PR2 là phiên bản Windows, không phải LAN IP.

Phân loại khi sửa Phase 1:

- Smartphone -> LAN frontend: deprecated for user access, không còn đường demo chính.
- ESP32 -> MQTT LAN: giữ đường kết nối và cổng 1883 trong mạng thiết bị; không tunnel broker.
- Localhost -> Web/API: giữ cho development và tunnel origin trên laptop.
- Báo cáo nghiệm thu M1/PR2 cũ: giữ lịch sử, bổ sung ngữ cảnh khi cần; không sửa lịch sử thành nghiệm thu Internet.
- `compose.lan.yaml`: không xóa vì MQTT LAN còn cần; tách phần device MQTT khỏi user LAN access nếu triển khai được duyệt.

Full scan 587 matches: `logs/audits/phase0-network-mobile-scan-2026-10-06.txt` (ignored). Git snapshot: `logs/audits/phase0-git-status-2026-10-06.txt` (ignored).

## 10. Existing tests / audit validation

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend regressions | PASS | Windows `npm test`: 5/5 Vitest tests |
| Frontend production build | PASS | Windows `npm run build`: tsc + Vite thành công |
| Simulator device safety | PASS | `python3 -m unittest discover -s tests -p test_device.py -v`: 23/23 |
| Backend health | PASS | HTTP 200, `{"status":"ok"}` trong running container |
| Backend readiness | PASS | HTTP 200, postgres up trong running container |
| Infrastructure | PASS | 4 containers healthy; đọc trạng thái không restart stack |
| `task.txt` ignore | PASS | `git check-ignore -v task.txt`: `.gitignore:58:/task.txt`; không tracked |
| Backend unit + E2E | NOT TESTED | Linux host thiếu pytest/dependencies; running backend cũng chưa có pytest. Chưa cài hoặc dựng test environment trong Phase 0 |
| Simulator callback/integration unit tests | NOT TESTED | Host thiếu paho-mqtt; 8 tests còn lại chưa chạy |
| Public frontend/backend tunnel | NOT TESTED | Chưa tạo tunnel trong Phase 0 |
| Phone 4G/5G / command end-to-end | NOT TESTED | Không có bằng chứng từ thiết bị vật lý |
| Android runtime / new APK build | NOT TESTED | APK có sẵn; chưa build lại hoặc install/launch |
| iOS runtime/build | NOT TESTED | Không có iOS client hiện tại |

Các số 84/84 backend và 31/31 simulator trong tài liệu là kết quả lịch sử, không được coi là PASS mới của phiên này. Phase 1 P1-01..P1-10 và Phase 2 M-01..M-10 chưa được nghiệm thu; baseline ở trên không thay thế tests sau từng phase.

## 11. Files changed in this task

| File | Change | Reason |
| --- | --- | --- |
| `.gitignore` | Thêm `/task.txt`; giữ các rule hiện có | Yêu cầu trực tiếp của user; file hướng dẫn local không vào Git |
| `docs/AUDIT_REMOTE_MOBILE_2026-10-06.md` | Báo cáo Phase 0 | Ghi nguồn sự thật, khác biệt với prompt, baseline và phạm vi cần duyệt |

Frontend build cập nhật output trong `frontend/dist/` đã ignored. Không chỉnh source frontend/backend hoặc phần mobile hiện có trong task này.

## 12. Files dự kiến thay đổi sau xác nhận

Phase 1: `.env.example`, `compose.yaml`, `compose.lan.yaml` và có thể một override device MQTT riêng; backend `app/config.py`, `app/main.py`, CORS tests, `README.md` và env example; frontend `src/api.ts`, `src/vite-env.d.ts`, `vite.config.ts`, `Dockerfile`, env example và `README.md`; `scripts/start-backend-tunnel.ps1`, `scripts/start-frontend-tunnel.ps1`; README gốc, infra README, docs/INTERFACES, PROJECT_STATE, ROADMAP và assignments liên quan.

Giữ `/api` cho Web cùng origin; thêm/configure public backend URL và CORS cho direct API access; Quick Tunnel URL chỉ ở local env/runtime, không source; không public PostgreSQL/MQTT. Kiểm tra Phase 1 gate trước tạo mobile.

Phase 2: `mobile/` với Expo/React Native/TypeScript một codebase Android+iOS, env-driven networking layer, polling, telemetry/state/control và lifecycle pending/applied/rejected/timeout theo API hiện có; tests phù hợp, README chạy/test 4G/5G. Giữ Capacitor hiện có dưới nhãn legacy, không xóa hoặc rewrite khi chưa cần.

Danh sách là dự kiến, không phải bằng chứng đã implement. Chưa có environment variables mới ngoài các biến hiện có; không tạo local secret hoặc hard-code tunnel URL.

## 13. Risks / gate / next action

- Working tree chứa implementation Capacitor và thay đổi nội dung chưa commit; bảo toàn toàn bộ, không lấy HEAD đè lại.
- Mobile MVP mới khác quyết định Capacitor hiện tại. Xác nhận được yêu cầu theo câu trong mục 5 task: “Không cần chờ tôi trả lời trừ khi phát hiện ... working tree có thay đổi quan trọng chưa commit ... có mobile app đã được viết sẵn mà prompt chưa biết”.
- API hiện chưa có authentication; khi chạy public tunnel, người biết URL có thể gọi command endpoints. CORS không phải authorization. Ghi rõ phạm vi demo và chỉ tunnel HTTP Web/API được user yêu cầu; không thêm authentication redesign trong task này.
- Quick Tunnel URL đổi khi restart; Web same-origin `/api` giảm cấu hình lại, mobile/direct Web cần cập nhật local env và khởi động lại theo hướng dẫn.
- Không mở MQTT 1883 hoặc PostgreSQL ra Internet, không thay database schema hoặc các guarantee safety.
- Không có firmware ESP32 thật, điện thoại 4G/5G hoặc iOS evidence trong audit. Các bước cần thiết bị vẫn phải báo NOT TESTED nếu không thực hiện được.
- Không chuyển Phase 2 nếu Phase 1 code/config/local runtime/regressions không qua gate.

**Chờ user xác nhận tiếp tục Phase 1/2 với Capacitor legacy hoặc dừng sau audit. Không đánh dấu toàn bộ task DONE.** Báo cáo cuối 19 phần và lệnh Windows cho architecture mới sẽ được hoàn tất sau implementation; chưa đưa lệnh tunnel/Expo chưa kiểm chứng như kết quả đã xong.
