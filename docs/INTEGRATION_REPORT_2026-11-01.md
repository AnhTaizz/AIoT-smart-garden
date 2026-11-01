# Báo cáo hợp nhất nhánh — 2026-11-01

Nhánh: `integration/smart-garden-unified-20261101`, tạo từ `origin/main` `13e1ac0`, sau đó merge `origin/main` mới `0b039d6` (PR #9). Người thực hiện: Claude Code theo yêu cầu của Tài (B). Không merge vào `main`, không force-push, không xóa nhánh cũ.

**Kiểm thử: NOT TESTED.** Theo yêu cầu của chủ dự án trong phiên này, toàn bộ regression/E2E để sau khi E2E ổn định. Không có mục nào dưới đây là PASS mới.

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

## 6. Bảo mật — vấn đề mở

1. **NGHIÊM TRỌNG — stack đang chạy là bản trước BC-02.** Container backend build 2026-10-06; OpenAPI công khai không có `/auth`; `GET /devices/node_01/latest` trả 200 cho người lạ qua `garden-api`. Theo tài liệu PR #4, `POST /devices/{id}/commands` cũng không cần xác thực. Hiện không có thiết bị online (telemetry cuối 2026-10-06, `simulated: true`), nên chưa có rủi ro bơm vật lý, nhưng **không kết nối ESP32 bật điều khiển** cho tới khi deploy bản này.
2. **Blocker deploy:** `.env` chưa có `OPERATOR_USERNAME`/`OPERATOR_PASSWORD_HASH`. Bản BC-02 sẽ từ chối mọi đăng nhập (fail closed) cho tới khi chủ dự án tự tạo hash.
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
