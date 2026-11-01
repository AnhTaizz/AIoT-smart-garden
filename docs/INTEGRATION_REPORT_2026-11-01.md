# Báo cáo hợp nhất nhánh — 2026-11-01

Nhánh: `integration/smart-garden-unified-20261101`, tạo từ `origin/main` `13e1ac0`, sau đó merge `origin/main` mới `0b039d6` (PR #9). Người thực hiện: Claude Code theo yêu cầu của Tài (B). Không merge vào `main`, không force-push, không xóa nhánh cũ.

**Kiểm thử:** regression phần mềm đã chạy ngày 2026-11-01 (§5b). Điện thoại thật, ESP32 thật, iOS và Kaggle thật vẫn **NOT TESTED**.

## 1. Nhánh và PR đã kiểm tra

| Nhánh / PR | Head | Quan hệ với `main` | Quyết định |
| --- | --- | --- | --- |
| PR #6 `feat/bc-01-mobile-chat-integration` | `57f78b6` | Stack tuyến tính trên `13e1ac0`; chứa bản rebase PR #4 (`6802b96`, `3660f87`) | **Hợp nhất** (cùng BC-02) |
| PR #7 `feat/bc-02-api-authentication` | `1a3db7b` | Stack trên BC-01 | **Hợp nhất** |
| PR #8 `docs/w3-weather-local-validation-20261031` | `79764e0` | Stack trên BC-02, 7 commit chỉ docs | **Hợp nhất** (chỉ 7 commit docs; BC-01/BC-02 không bị đưa lại) |
| `feat/esp32-arduino-mqtt` (Thành) | `90ac105` | 1 commit trên `13e1ac0` | **Hợp nhất** firmware Arduino IDE + `compose.secure.yaml` |
| PR #4 `feat/remote-mobile-cloudflare` | `e4b4221` | Base `208bf77`; code đã được rebase vào BC-01 | **Hợp nhất phần còn thiếu**: `e1219cf` (G02 AGREED/M1 docs), `e4b4221` (REMOTE_DEMO, bằng chứng 4G), iOS scaffold |
| PR #9 `finetuneAI` (Toản) | `43785ba` | Đã merge vào `main` (`0b039d6`) | **Hợp nhất** + gắn xác thực BC-02 cho endpoint irrigation |
| `feat/A-W1-esp32-firmware` | `a052b49` | Base `cd5e8ee` cũ, PlatformIO | **Không hợp nhất** (xem §3) |
| `feat/B-W1-…`, `feat/C-W1-…`, `chore/local-mobile-demo-plan` | — | Đã nằm trong `main` (PR #1–#3) | Không cần |

Local: nhánh `feat/remote-mobile-cloudflare` có 3 commit chưa push (merge `main` vào nhánh); local `main` ở `e1219cf` lệch `origin/main`. Không sửa hai nhánh này.

## 2. Ma trận chức năng

| Chức năng | Trước tích hợp | Sau tích hợp |
| --- | --- | --- |
| Backend/simulator G02, dashboard, chatbot Qwen3 | Có trên `main` | Giữ nguyên |
| Capacitor Android, API HTTPS, CORS | PR #4 + rebase trong BC-01 (trùng lặp) | Một bản (BC-01) |
| iOS scaffold `frontend/ios`, `@capacitor/ios` | Chỉ PR #4 | Có |
| Đăng nhập operator/viewer, rate limit, logout | Chỉ BC-02 | Có |
| G02 AGREED, M1 Web/LAN DONE, Android 4G PASS (docs) | Chỉ PR #4 (BC/W3 ghi nhầm "DRAFT" vì base thiếu `e1219cf`) | Có, ghi rõ 4G PASS là bản trước BC-02 |
| Firmware Arduino IDE (dry-run mặc định) + broker auth/ACL tùy chọn | Chỉ nhánh ESP32 | Có, chưa nghiệm thu board |
| Firmware PlatformIO A-W1 | Nhánh riêng | Không hợp nhất |
| Supervisor tưới AI (simulator) | `main` (PR #9), API không auth | Có, API cần đăng nhập |
| Weather W3 | Chỉ kế hoạch/contract PROPOSED | Chỉ docs; chưa có code |
| Domain cố định `anhtaizz.id.vn` | Chưa có trong repo | Docs + `compose.tunnel.yaml` tùy chọn |

## 3. Conflict và cách giải quyết

- **Code PR #4 ↔ BC-01/BC-02:** merge 3-way với base `208bf77` có thể đưa lại dòng mà BC-02 cố ý bỏ (rào chắn IP/header của BC-01). Mọi file code lấy phía integration; chỉ thêm iOS và `@capacitor/ios` (lockfile chèn đúng một entry, `npm ci` thành công). Đối chiếu: so với tip W3, delta code chỉ còn firmware/broker ESP32 + iOS.
- **Docs PR #4 ↔ BC/W3:** README/PROJECT_STATE/ROADMAP lấy cấu trúc mới của PR #4 (có bằng chứng nghiệm thu), thêm BC-01/BC-02/W3/firmware và ghi chú vì sao các dòng BC ghi "G02 DRAFT".
- **PR #9 ↔ BC-02:** `create_command` giữ `OperatorDep` chạy trước khóa thiết bị; `GET/PUT /devices/{id}/irrigation` gắn `SessionDep`/`OperatorDep`; frontend dùng `apiFetch`; test E2E in-process truyền `Session` operator.
- **Migration trùng số:** `004_auth_sessions.sql` (BC-02) và `004_irrigation.sql` (PR #9). Runner lưu theo tên file nên cả hai chạy; không đổi tên file đã chia sẻ. Migration tiếp theo: `005_`.
- **Firmware Arduino IDE ↔ PlatformIO:** không kết hợp. A-W1 hard-code pin/cực relay/ngưỡng ADC/IP LAN trong `config.h` được commit và có Auto/hysteresis trên ESP32; nhánh Arduino IDE tách `config.local.h` (ignored), dry-run/control-disabled mặc định, có native test. Hai hướng đối nghịch về Auto. Nhóm (Thành) quyết định hướng nào giữ lại.
- **Kiến trúc Auto — CHƯA CHỐT:** CLAUDE.md/W3 (ESP32 sở hữu Auto) ↔ `AGENTS.md` (server quyết định) ↔ PR #9 (supervisor backend, simulator-only). Đã ghi bảng so sánh trong [INTERFACES](INTERFACES.md#ranh-giới-xử-lý), ghi chú trong CLAUDE.md và AGENTS.md. Trạng thái an toàn: firmware không có Auto, supervisor chặn `simulated: false`, Weather chưa có code.

## 4. File thay đổi chính (ngoài nội dung các nhánh)

`backend/app/irrigation.py`, `backend/app/main.py`, `backend/tests/e2e/test_irrigation_e2e.py`, `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/package.json`, `frontend/package-lock.json`, `compose.tunnel.yaml` (mới), `.env.example`, `frontend/.env.mobile.example`, `.gitignore`, `docs/REMOTE_DEMO.md`, `docs/INTERFACES.md`, `docs/AI_IRRIGATION.md`, `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, `README.md`, `frontend/README.md`, `backend/README.md`, `CLAUDE.md`, `AGENTS.md`.

## 5. Domain (kiểm tra bằng GET ngày 2026-11-01, trước mọi thay đổi)

| Hostname | Kết quả | Ghi chú |
| --- | --- | --- |
| `garden.anhtaizz.id.vn` | `/`, `/api/health`, `/api/ready` → 200 | Connector `garden-local` (Docker, remotely-managed) → `http://frontend:80` |
| `garden-api.anhtaizz.id.vn` | `/health`, `/ready` → 200 | → `http://backend:8000` |
| `anhtaizz.id.vn` (apex) | Không có bản ghi DNS | Cần thêm route trên Dashboard: [REMOTE_DEMO](REMOTE_DEMO.md#thêm-apex-anhtaizzidvn-thao-tác-dashboard) |
| `toeic.anhtaizz.id.vn` | **502** ngay từ trước khi thao tác | Không thuộc phạm vi; không đụng tới. Chủ TOEIC cần kiểm tra origin/Windows Service |

Không có quyền Cloudflare API trong phiên này; không tạo tunnel, không sửa route/DNS, không restart connector nào.

## 5a. Deploy lên stack demo — 2026-11-01 (sau khi chủ dự án đồng ý)

- Tạo tài khoản operator `admin` (hash scrypt trong `.env`; `.env` cũ sao lưu ở `.env.bak`, cả hai bị Git ignore). Mật khẩu chỉ đưa cho chủ dự án, không ghi vào repo.
- Build frontend lần đầu fail vì `npm test` trong Dockerfile: 3 test polling của `App.test.tsx` bắt nhầm interval 5 giây của `IrrigationPanel`. Đã mock panel trong file test đó (panel có test riêng). Vitest **75/75 PASS**.
- `up --build -d` (không `-v`): migration `004_auth_sessions`, `004_irrigation` được áp dụng; bốn container healthy; connector `garden-local` vẫn nối được.
- Kiểm tra qua domain thật: `garden` `/`, `/api/health`, `/api/ready` và `garden-api` `/health`, `/ready` → 200; anonymous `latest`, `irrigation`, `POST commands` → **401**; đăng nhập `admin` → operator, `latest` 200, `control-access` cho phép; logout → token cũ 401. Không gửi lệnh bơm.
- Simulator `node_01` (dữ liệu **mô phỏng**) chạy nền để dashboard có telemetry; qua domain, operator thấy `simulated: true`, `stale: false`.

## 5b. Regression bản tích hợp — 2026-11-01

Backend/simulator chạy trên stack Compose **tách biệt** (`-p sg-regression`, port 18000/15173/11883/15432, DB và tài khoản test riêng trong env file tạm), không đụng stack demo hay volume `smart-garden`.

| Kiểm thử | Kết quả |
| --- | --- |
| `docker compose config` base, `+device`, `+lan`, `+test --profile tests`, `+secure`, `+tunnel` (placeholder chỉ để parse) | **PASS** 7/7 |
| Backend unit + E2E (PostgreSQL 16, Mosquitto 2.0, FastAPI, Nginx thật) | **239 PASS**, 2 SKIP (live Kaggle, cần `E2E_CHAT_LIVE=1`), 0 FAIL |
| Simulator unittest | **PASS** 31/31 |
| Frontend Vitest + TypeScript/Vite build | **PASS** 75/75, build OK |
| Firmware native (`firmware/tests/run.ps1`, g++ 12.1 mingw64, ArduinoJson 7.4.2 tải vào `firmware/build/` ignored) | **PASS** 95 checks; không compile Arduino/ESP32, không flash |
| `build:mobile` + `cap sync android` + `gradlew assembleDebug` với `VITE_API_URL=https://garden-api.anhtaizz.id.vn` | **PASS**; APK `frontend/android/app/build/outputs/apk/debug/app-debug.apk` (4,3 MB, không commit); bundle chứa `garden-api`, không tham chiếu storage/Quick Tunnel |
| Cài APK / điện thoại 4G | **NOT TESTED** (`adb devices -l` trống) |

Lần chạy đầu: 226 pass, 10 fail, đều do ghép PR #9 với BC-02, đã sửa:
- Byte NUL lọt vào `test_irrigation_e2e.py` khi merge (lỗi ghi file), gây lỗi collection.
- 3 test auth: `create_command` giờ gọi khóa irrigation, mà `FakePool` của unit test không có DB → fixture `api` thay `irrigation.device_lock` bằng bản no-op (khóa thật đã có E2E cover).
- 7 test supervisor: BC-02 bỏ URL Kaggle mặc định nên `chat_api_url` rỗng → E2E đặt URL cho model giả lập. Hành vi sản phẩm: `PUT /irrigation` bật AUTO khi chưa có `CHAT_API_URL` giờ trả `503 chat_unavailable/not_configured` thay vì nhận rồi lỗi ở chu kỳ sau. Thêm unit test: anonymous 401, viewer 403, AUTO không có model 503; không publish lệnh nào.

## 5c. Đồng bộ PR #10 (`main` `5b1c110`) — 2026-11-01

Thành merge PR #10 vào `main` sau khi nhánh integration được tạo. Ngoài firmware (`90ac105`, đã có), PR #10 thêm `f356fde`: supervisor AI được điều khiển **ESP32 thật** khi device ID nằm trong `IRRIGATION_REAL_DEVICE_IDS` **và** broker có credential, với telemetry/state thật, còn mới, trong miền hợp lệ.

- Merge `1a59036`: conflict ở `config.py`, `compose.yaml` và docs. Giữ toàn bộ kiểm tra thiết bị thật của `f356fde` cộng auth/503 của integration; `CHAT_API_URL` mặc định vẫn rỗng (BC-02). Mẫu `.env.example` đổi `IRRIGATION_REAL_DEVICE_IDS=node_01` thành rỗng để copy template không cấp quyền tưới thật; `ESP32_REAL_SETUP.md` cập nhật theo.
- 3 test mới của PR #10 fail trên BC-02 (gọi `get_profile` không có phiên; model giả lập không có URL) → sửa test, không đổi code sản phẩm.
- Regression trên stack tách biệt: backend **266 PASS**, 2 SKIP (live Kaggle); simulator **31/31**; frontend **80/80** + build; firmware native **95 checks**.
- Deploy demo: `.env` không đặt `IRRIGATION_REAL_DEVICE_IDS` → `GET /devices/node_01/irrigation` trả `execution_scope: simulator_only`; anonymous 401; admin đăng nhập được; simulator vẫn gửi dữ liệu.
- Kiến trúc: `main` nay theo hướng **server quyết định tưới**, trái với CLAUDE.md §3. Nhóm cần ghi quyết định chính thức rồi sửa CLAUDE.md/W3; tài liệu đã nêu rõ mâu thuẫn, không tự chọn.

## 5d. Hợp nhất lần 2 — Weather W3 (nhánh `integration/smart-garden-unified-20261101-v2`)

Sau khi PR #11 merge vào `main` (`d7ffd3e`), chỉ còn 3 nhánh có commit ngoài `main`:

| Nhánh | Quyết định | Lý do |
| --- | --- | --- |
| `feat/w3-weather` (`879b464..c75d2f4`, 6 commit) | **Hợp nhất** (merge sạch, `8f4d92a`) | `GET /weather` chỉ đọc, cần đăng nhập, URL Open-Meteo cố định, `WEATHER_ENABLED=false` mặc định; Weather Card; dự báo làm context tham khảo cho chatbot và model tưới (prompt `irrigation-decision-v2`), các guard của supervisor không đọc weather và prompt cấm dùng weather làm lý do tưới |
| `feat/A-W1-esp32-firmware` (PlatformIO) | Không hợp nhất | Bản firmware thay thế, đối nghịch với firmware Arduino IDE trên `main` mà board thật đang chạy; hard-code pin/ngưỡng; có Auto trên ESP32 xung đột với AUTO phía server đang dùng. Thành đã chủ động chuyển sang Arduino IDE |
| local `feat/remote-mobile-cloudflare` (`d1d6351`, chưa push) | Không hợp nhất | Merge thủ công ngày 27/10 giữa PR #4 và chatbot; phần code đã được thay bằng BC-01/BC-02 trên `main` |

Regression (stack tách biệt `sg-regression`): backend unit + E2E **309 PASS**, 2 SKIP (live Kaggle); simulator **31/31**; frontend **86/86** + build; firmware native **95 checks**. Cây mã của nhánh v2 trùng với `feat/w3-weather` đang chạy trên demo (commit cuối chỉ sửa docs/docstring), nên không deploy lại.

Vận hành demo cùng ngày (ngoài repo, `.env` bị ignore): bật broker xác thực `compose.secure.yaml` và `IRRIGATION_REAL_DEVICE_IDS=node_01` để supervisor có thể chạy AUTO cho ESP32 thật khi người vận hành bật. AUTO chưa được bật.

## 6. Bảo mật — vấn đề mở

1. **Đã xử lý ở §5a (2026-11-01).** Trước khi deploy, stack đang chạy là bản trước BC-02. Container backend build 2026-10-06; OpenAPI công khai không có `/auth`; `GET /devices/node_01/latest` trả 200 cho người lạ qua `garden-api`. Theo tài liệu PR #4, `POST /devices/{id}/commands` cũng không cần xác thực. Hiện không có thiết bị online (telemetry cuối 2026-10-06, `simulated: true`), nên chưa có rủi ro bơm vật lý, nhưng **không kết nối ESP32 bật điều khiển** cho tới khi deploy bản này.
2. **Đã xử lý ở §5a.** Trước đó `.env` chưa có `OPERATOR_USERNAME`/`OPERATOR_PASSWORD_HASH`. Bản BC-02 sẽ từ chối mọi đăng nhập (fail closed) cho tới khi chủ dự án tự tạo hash.
3. Mosquitto đang bind `0.0.0.0:1883` anonymous (`compose.device.yaml`). `compose.secure.yaml` có auth/ACL nhưng simulator chưa hỗ trợ credential.
4. Connector `garden-local` nhận token qua command line (`docker inspect` thấy được) và được nối tay vào network Compose; `docker compose down` sẽ làm domain 502. `compose.tunnel.yaml` là phương án thay thế, chưa áp dụng.
5. Supervisor PR #9 gửi telemetry/policy tới `CHAT_API_URL` (Kaggle/ngrok); dữ liệu vườn rời khỏi laptop khi AUTO bật.

## 7. Firmware / Weather — vấn đề mở

- Firmware Arduino IDE chưa compile/flash trong phiên này (không có `arduino-cli`); chưa nghiệm thu board, relay qua hai diode chưa được kiểm chứng điện.
- Board từ chối ON `>60` giây trong khi API cho phép 120 → UI thấy `rejected invalid_duration`; nhóm nên chốt một giới hạn.
- Weather W3: chưa có code/test. Không báo PASS.

## 8. Việc người dùng cần làm trước khi merge `main`

1. Review Draft PR của nhánh integration; quyết định kiến trúc Auto (§3) và hướng firmware.
2. Tạo hash operator: `docker compose run --rm --no-deps backend python -m app.auth hash-password`; đặt `OPERATOR_USERNAME`, `OPERATOR_PASSWORD_HASH`, `E2E_OPERATOR_PASSWORD` trong `.env`.
3. Chạy regression theo CLAUDE.md §6: Compose config, backend unit + E2E (`compose.test.yaml`, project name riêng để không đè stack demo), frontend `npm test`/`npm run build`, simulator, firmware `firmware/tests/run.ps1`.
4. Deploy lên stack demo: `docker compose -f compose.yaml -f compose.device.yaml up --build -d` (migration `004_auth_sessions`, `004_irrigation` chỉ thêm bảng). Kiểm tra từ xa: anonymous `GET garden-api…/devices/node_01/latest` phải là **401**.
5. Thêm route apex trên Dashboard nếu muốn; kiểm tra `https://anhtaizz.id.vn/api/health`.
6. Build APK với `.env.mobile.local` = `https://garden-api.anhtaizz.id.vn`; thử trên điện thoại qua 4G: đăng nhập, telemetry, ON 5 giây → `applied`, OFF, đăng xuất.
7. Sau khi PR integration được merge, có thể đóng PR #4/#6/#7/#8 (nội dung đã được kế thừa; ngoại lệ: PR #4 chỉ được kế thừa phần code qua rebase BC-01 cộng phần docs/iOS ở merge `7643875`).
