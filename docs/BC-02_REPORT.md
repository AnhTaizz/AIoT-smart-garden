# BC-02 — Xác thực API và điều khiển bơm từ xa

Ngày: 2026-10-30. Nhánh: `feat/bc-02-api-authentication`. Người thực hiện: Claude Code theo yêu cầu của Tài (B). Firmware, MQTT G02 và trạng thái G02/M1 không bị thay đổi.

## 1. Điều kiện bắt đầu và blocker

- `origin/main` vẫn ở `13e1ac0`. PR #6 (BC-01) **chưa merge** (Draft, mở). Theo yêu cầu, nhánh BC-02 **không** tạo từ `main` cũ mà là **stacked branch** trên đầu nhánh BC-01 (`57f78b6`). Draft PR của BC-02 đặt base là `feat/bc-01-mobile-chat-integration` để diff chỉ còn phần BC-02. Khi PR #6 merge, đổi base của PR BC-02 sang `main` (GitHub tự đổi nếu nhánh BC-01 bị xóa sau merge).
- Không có PR/commit nào khác trên `main` cần rebase.

## 2. Audit và lựa chọn thiết kế

Dependency backend hiện có: FastAPI, Pydantic, psycopg/psycopg-pool, paho-mqtt, httpx, Uvicorn. **Không có** `argon2-cffi`, `passlib`, `PyJWT` hay Redis.

| Vấn đề | Lựa chọn | Lý do |
| --- | --- | --- |
| Hash mật khẩu | **scrypt** (`hashlib.scrypt`, thư viện chuẩn) N=2^17, r=8, p=1, salt 16 byte, so sánh `hmac.compare_digest` | Memory-hard, nằm trong danh sách OWASP chấp nhận; không thêm dependency native (CLAUDE.md: không thêm dependency nếu thư viện hiện có đáp ứng). Argon2id cần `argon2-cffi`. Đo trong image backend: ~1,5 giây/lần trên máy kiểm tra, chạy trong thread nên không chặn event loop |
| Định dạng hash | `scrypt:<log2N>:<r>:<p>:<salt>:<hash>` (base64 URL-safe) | Không có `$` nên Compose không nội suy nhầm trong `.env`; tham số nằm trong chuỗi để tăng chi phí sau này |
| Token | Opaque ngẫu nhiên 256 bit (`secrets.token_urlsafe(32)`), Bearer | Thu hồi được ngay (logout), không cần signing secret; JWT sẽ cần secret và danh sách thu hồi riêng |
| Lưu phiên | PostgreSQL `auth_session` (migration `004`): SHA-256 của token, username, role, `credential_id`, `expires_at`, `revoked_at` | Đủ cho hết hạn + thu hồi; không cần Redis. Đọc bảng không lấy lại được token |
| Tài khoản | Một operator qua env `OPERATOR_USERNAME`/`OPERATOR_PASSWORD_HASH`/`OPERATOR_ROLE` | Đúng phạm vi demo; không có đăng ký công khai |
| Phân quyền | Role `operator` (xem + điều khiển) hoặc `viewer` (chỉ xem → 403 khi gửi lệnh) | Tối thiểu để có 401/403 rõ ràng, không phải RBAC |
| Đổi tài khoản | `credential_id` = SHA-256(username, hash, role); phiên chỉ hợp lệ khi khớp | Đổi mật khẩu/role làm mọi phiên cũ mất hiệu lực |
| Rate limit | Sliding window trong bộ nhớ một tiến trình | Đúng với Compose hiện tại (1 tiến trình Uvicorn); không cần Redis |

## 3. Triển khai

### Backend

- `app/auth.py`: hash/verify scrypt, `credential_id`, dependency `require_session` (401 `auth_required` / `invalid_session`, header `WWW-Authenticate: Bearer`) và `require_operator` (403 `forbidden`), endpoint `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, CLI `python -m app.auth hash-password` (nhập mật khẩu qua `getpass`, chỉ in hash).
- `app/access.py`: `GET /control-access` theo role của phiên. Bỏ hoàn toàn rào chắn IP/header của BC-01; operator đã xác thực được gửi lệnh qua tunnel.
- `app/main.py`: mọi endpoint dữ liệu/lịch sử/lệnh/state cần phiên; `POST /devices/{id}/commands` cần operator. Public: `/health`, `/ready`, `/auth/login` (và `/docs`, `/openapi.json` mặc định của FastAPI, không chứa dữ liệu vườn).
- `app/chat.py`: `/chat` cần phiên, giới hạn theo tài khoản; `CHAT_API_URL` trống → `503 chat_unavailable` (`reason: not_configured`), không gọi ra ngoài.
- `app/config.py`, `compose.yaml`, `.env.example`: bỏ URL ngrok cố định; thêm biến tài khoản, TTL và rate limit. Không có mật khẩu/hash/token nào trong repo.
- `app/http_config.py`: CORS cho phép header `Authorization`; vẫn không wildcard, không credentials cookie.
- **Không đổi:** `schemas.py`, `mqtt_bridge.py`, `ingest.py`, migration 001–003, simulator, firmware. Vòng đời command G02 giữ nguyên: 202 chỉ là `pending`; `applied` cần ACK + state khớp; `target_boot_id`, `command_sequence`, `expires_at` giữ nguyên; không replay ON; không tự retry ON.

Thứ tự kiểm tra lệnh: 401 → 403 → 422 thời lượng → 503 broker → 429 `pump_on` → tạo command + publish. Request bị chặn trước đó không tạo bản ghi và không publish.

| Giới hạn (mặc định, cấu hình qua env) | Khóa | Vượt → |
| --- | --- | --- |
| Đăng nhập sai: 5 lần / 300 giây | Username đúng; mọi username lạ gộp một bucket | `429 login_rate_limited` + `Retry-After` (kể cả khi lần sau nhập đúng) |
| `/chat`: 5 lượt / 60 giây | Tài khoản | `429 chat_request_rate_limited` + `Retry-After` |
| `pump_on`: 6 lượt / 60 giây | `device_id` | `429 command_rate_limited` + `Retry-After` |
| `pump_off` | — | **Không bao giờ bị giới hạn** để luôn dừng được bơm |

### Frontend (Web + Capacitor Android, cùng code)

- `src/auth.ts`: phiên trong bộ nhớ. Không dùng localStorage/sessionStorage/cookie/Capacitor Preferences; không token nào trong bundle (đã grep `dist/` và `dist-mobile/`: 0 tham chiếu storage).
- `src/LoginScreen.tsx`: form đăng nhập; thông báo rõ cho sai mật khẩu, bị khóa (kèm số giây), backend chưa cấu hình, mất mạng. Xóa mật khẩu khỏi state ngay sau khi gửi.
- `src/App.tsx`: chưa có phiên → chỉ màn hình đăng nhập, không gọi API dữ liệu. Dashboard được key theo token; 401 cho token hiện tại, đến `expires_at` hoặc Đăng xuất → về màn hình đăng nhập, dashboard unmount nên polling dừng. 401 của token cũ đến muộn bị bỏ qua.
- `src/api.ts`: gắn `Authorization` cho mọi request được bảo vệ (kể cả `/chat`), không retry `POST`. Giữ nguyên toàn bộ BC-01.1: fail-closed, single-flight polling, nhãn stale/chưa cập nhật, trạng thái lệnh không lùi.
- Header mobile: không tràn ngang ở 360/390 px (đã đo `scrollWidth`).

## 4. Threat model ngắn

| Mối đe dọa | Biện pháp | Còn lại |
| --- | --- | --- |
| Người lạ biết URL tunnel đọc dữ liệu/bật bơm | Mọi API dữ liệu/lệnh/chat cần Bearer; server kiểm tra từng request | Ai có mật khẩu operator có toàn quyền (một tài khoản dùng chung) |
| Đoán mật khẩu | scrypt chậm + 5 lần sai/5 phút → 429 | Kẻ biết username có thể cố ý khóa operator 5 phút (DoS lockout); đếm trong bộ nhớ, reset khi restart |
| Lộ bảng phiên/DB | Chỉ lưu SHA-256 token; mật khẩu chỉ ở dạng scrypt trong env | Ai đọc được `.env` có hash để brute force offline (chậm nhờ scrypt) |
| Token bị lộ (log, máy) | Không log token/mật khẩu; token trong bộ nhớ; hết hạn 8 giờ; logout thu hồi; đổi mật khẩu thu hồi tất cả | Token bị đánh cắp trong thời hạn vẫn dùng được tới khi logout/hết hạn |
| Giả mạo header IP/Cloudflare | Không dùng header/IP/CORS cho quyết định | — |
| Spam lệnh bật bơm | 429 `pump_on` theo thiết bị; firmware giữ giới hạn bơm cục bộ | `pump_off` không giới hạn (cố ý) |
| Lạm dụng Kaggle | `/chat` cần đăng nhập + 5 lượt/phút/tài khoản | Không có quota tổng |
| AI tự bật bơm | `/chat` không có đường publish command; test xác nhận không publish | — |
| MQTT trong LAN | Ngoài phạm vi BC-02 | MQTT vẫn anonymous; ai trong LAN/hotspot publish được lên topic điều khiển. Cần task riêng với Thành (A) |
| Tấn công qua HTTP thuần | Tunnel/Android dùng HTTPS; native từ chối HTTP | LAN demo vẫn HTTP: mật khẩu/token đi dạng rõ trong Wi-Fi/hotspot. Chỉ dùng hotspot tin cậy |

## 5. Kiểm thử

### Đã chạy thật

| Kiểm thử | Môi trường | Kết quả |
| --- | --- | --- |
| Compose config base, `+lan`, `+device`, `+test --profile tests` | Docker 29.9.2 | Parse OK; không còn URL ngrok trong config |
| Backend unit (gồm 53 test auth mới) | Python 3.12 trong container và 3.13 host | **156/156** |
| Backend E2E (PostgreSQL 16, Mosquitto 2.0, FastAPI, Nginx thật) | `docker compose -f compose.yaml -f compose.test.yaml --profile tests run --build --rm regression-tests` | **47 pass**, 2 skip (live Kaggle cần `E2E_CHAT_LIVE=1`). Tổng **203 pass** |
| Simulator | cùng service | 31/31 |
| E2E auth chính | như trên | Anonymous → 401 (kể cả token giả, header tunnel), không tạo command, không publish (trực tiếp và qua Nginx); anonymous không đọc được latest/telemetry/state/commands/control-access/chat; operator → 202 `pending` → `applied` (ACK + state, đúng `target_boot_id`/`command_sequence`/`expires_at`) trực tiếp, qua Nginx, có và không có header tunnel; phiên hết hạn trong PostgreSQL → 401; logout → 401; bảng phiên không chứa token gốc; `pump_on` tới 429 nhưng `pump_off` vẫn 202; chat chưa cấu hình → 503 `not_configured`, không có ngrok |
| Frontend unit | Vitest | **67/67** (14 test mới cho đăng nhập/đăng xuất/401/hết hạn/viewer/token cũ) |
| Kiểm tra đột biến frontend | Cố ý bỏ header Authorization, bỏ xử lý 401, bỏ hẹn giờ hết hạn, bỏ màn hình đăng nhập | Mỗi đột biến làm 1–13 test fail; code đã khôi phục |
| TypeScript + Vite build | | OK |
| `build:mobile` + `cap sync android` | HTTPS forwarder cục bộ (chứng chỉ tự ký) tới FastAPI | OK; bundle không chứa token/storage |
| Phiên trình duyệt thật (Chromium headless) + simulator `node_01` (dữ liệu **mô phỏng**) | Stack Compose thật | Anonymous: chỉ form đăng nhập, 0 request dữ liệu; sai mật khẩu → thông báo; operator → bật bơm 5 giây → `applied`, `ĐANG BẬT` → tắt `applied`; chat → "chưa được cấu hình CHAT_API_URL"; đăng xuất → token cũ bị 401; viewport 390 px với header Cloudflare → đăng nhập, bật/tắt bơm `applied`; hết hạn phiên trong DB → UI về màn hình đăng nhập |

### Chưa chạy được (không tính là PASS)

- **Build APK / Android thật / 4G:** môi trường kiểm tra chặn `dl.google.com` (Android Gradle Plugin/SDK). Chưa cài app trên điện thoại.
- **Cloudflare Quick Tunnel thật:** đường tunnel chỉ được mô phỏng bằng header Cloudflare qua Nginx; chưa chạy `cloudflared`.
- **Kaggle Qwen3 thật:** endpoint ngrok bị proxy môi trường chặn; chỉ kiểm tra trạng thái chưa cấu hình.
- **ESP32 thật:** không thuộc BC-02; MQTT không đổi.
- Đa tiến trình/đa replica: không áp dụng (rate limit trong bộ nhớ).

## 6. Cách demo

1. `cp .env.example .env` (lần đầu). Tạo hash: `docker compose run --rm --no-deps backend python -m app.auth hash-password`; đặt `OPERATOR_USERNAME` và `OPERATOR_PASSWORD_HASH` trong `.env`. Đặt `CHAT_API_URL` nếu phiên Kaggle đang chạy.
2. `docker compose up --build -d`, chạy simulator `python simulator/simulator.py --device-id node_01 --interval 2` (hoặc ESP32 thật qua `compose.device.yaml`).
3. Web local: mở <http://127.0.0.1:5173>, đăng nhập, bật bơm 5 giây, chờ `applied`, tắt bơm, đăng xuất.
4. Từ xa: chạy `scripts/start-frontend-tunnel.ps1` (Web) và/hoặc `scripts/start-backend-tunnel.ps1` (Android), build APK với URL backend tunnel theo [frontend/README](../frontend/README.md#app-android-capacitor), đăng nhập trên điện thoại.
5. Regression: đặt thêm `E2E_OPERATOR_PASSWORD` trong `.env` local rồi chạy service `regression-tests`.

## 7. Kết luận: bật điều khiển bơm từ xa?

**Có thể bật ở mức demo**, với điều kiện: dùng mật khẩu mạnh riêng cho buổi demo, chỉ mở tunnel trong thời gian demo, không public cổng MQTT/PostgreSQL, và hotspot/LAN tin cậy (MQTT vẫn anonymous, LAN vẫn HTTP). Authentication, authorization và rate limit đã được kiểm chứng bằng unit + E2E thật; điều khiển qua header tunnel đi đúng vòng đời G02.

**Chưa phù hợp cho triển khai thật/công khai lâu dài** vì: một tài khoản dùng chung, lockout có thể bị lạm dụng, rate limit không bền qua restart, MQTT chưa có xác thực/ACL, chưa kiểm tra APK/điện thoại/tunnel thật.

## 8. Đề xuất tiếp theo

1. Chạy kiểm tra thiết bị thật: APK trên Android qua 4G với tunnel thật; smartphone LAN cho M1.
2. MQTT username/password + ACL theo `device_id` (phối hợp Thành, A).
3. Lockout theo IP tin cậy (Cloudflare Access/WAF) hoặc tăng dần thời gian khóa; lưu bộ đếm vào PostgreSQL nếu chạy nhiều tiến trình.
4. Lưu phiên bền trên Android bằng kho bảo mật (Android Keystore) nếu cần, thay vì đăng nhập lại mỗi lần mở app.
5. HTTPS cho LAN demo hoặc chỉ cho phép đăng nhập qua tunnel HTTPS.
