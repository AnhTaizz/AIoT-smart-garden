# Frontend

Một codebase React + TypeScript strict + Vite dùng cho Web (Nginx trong Docker Compose) và app Android (Capacitor). Dashboard tiếng Việt hiện có:

- **Đăng nhập (BC-02):** chưa đăng nhập chỉ thấy form đăng nhập, không gọi API dữ liệu nào. Sau khi đăng nhập, mọi request được bảo vệ (kể cả `/chat`) gửi `Authorization: Bearer <token>`. Token chỉ nằm trong bộ nhớ (`src/auth.ts`), không ghi vào localStorage/sessionStorage/cookie/Capacitor Preferences và không nhúng vào APK; mật khẩu không được lưu. Tải lại trang hoặc mở lại app phải đăng nhập lại. Khi server trả 401, khi đến `expires_at` hoặc khi bấm **Đăng xuất**, app quay về màn hình đăng nhập và dừng polling; lệnh `POST` điều khiển bơm không bao giờ được tự gửi lại. Web và Android dùng cùng logic.

- Trạng thái backend (`GET /health`) và PostgreSQL (`GET /ready`).
- Telemetry mới nhất, lịch sử ngắn (sparkline), nhãn **Dữ liệu mô phỏng / Thiết bị thật**, **Trực tuyến / Dữ liệu cũ (Stale)**; cảm biến lỗi hiển thị `Lỗi cảm biến`, không đổi thành `0`.
- Phân biệt **chưa có dữ liệu** (API trả 404) với **lỗi API** (5xx/mất kết nối): lỗi API hiện cảnh báo `role="alert"` và `Lỗi tải dữ liệu`.
- Trạng thái bơm do thiết bị tự báo; khi state đã cũ hiển thị `Trạng thái cũ: bật/tắt` và cảnh báo thiết bị có thể offline.
- Điều khiển bơm theo vòng đời `pending → applied/rejected/timeout`. HTTP 202 chỉ là `pending`; chỉ báo thành công khi backend `applied` (ACK + state khớp `command_id`). ACK đến sau `timeout` hiển thị `Hết thời gian chờ · ACK đến trễ`, không đổi thành thành công.
- Quyền điều khiển mặc định **khóa**: nút bơm chỉ mở khi backend online và `GET /control-access` trả đúng `{"commands_allowed": true, "reason": null}`. `commands_allowed: false` (tài khoản `viewer`) → "Tài khoản này chỉ có quyền xem"; lỗi mạng, HTTP lỗi, timeout 10 giây hoặc payload lạ → "Không xác minh được quyền điều khiển" (backend vẫn hiển thị online). Đây chỉ là UX; backend tự trả 401/403.
- Polling single-flight: mỗi lần chỉ một lượt tải; tick 5 giây đến giữa lượt đang chạy được xếp hàng một lần; Làm mới hủy lượt cũ bằng `AbortController` nên response cũ không ghi đè dữ liệu mới. Lỗi API (không phải 404) giữ giá trị hợp lệ cuối cùng nhưng gắn nhãn "Chưa cập nhật (lỗi API)"/"Chưa cập nhật: bật/tắt", không hiển thị như realtime.
- Mất mạng khi theo dõi lệnh: chỉ thử lại các request **GET** trạng thái (tối đa 5 lần liên tiếp), không bao giờ tự gửi lại `POST` bật bơm. Mỗi request API (trừ chat) tự hủy sau 10 giây.
- Nút nổi **Trợ lý nông nghiệp**: chat nhiều lượt qua `/chat`, render Markdown an toàn, bật/tắt gửi dữ liệu vườn. Chatbot không có quyền điều khiển bơm. Xem [hướng dẫn chatbot](../docs/CHATBOT.md).

Không có số đo hoặc trạng thái bơm giả trong giao diện.

## Cấu hình API

| Biến (build-time) | Web mặc định | Android |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` (Nginx/Vite proxy cùng origin) | Alias cũ, ưu tiên thấp hơn |
| `VITE_API_URL` | Rỗng. Chỉ đặt khi Web phải gọi backend khác origin (HTTPS) | **Bắt buộc**: origin HTTPS công khai của FastAPI, không có `/api` |

Logic nằm ở `src/apiConfig.ts` và có test. Web HTTPS từ chối API HTTP (mixed content). App native từ chối URL tương đối, HTTP, `localhost`/IP LAN/private và đường dẫn khác `/`. Không đặt credentials/API key vào biến `VITE_*`: mọi giá trị này bị nhúng vào bundle; `CHAT_API_KEY` chỉ nằm ở backend.

## Chạy cùng Docker Compose

Từ root repository:

```bash
cp .env.example .env
docker compose up --build -d
```

Development mode chỉ mở <http://127.0.0.1:5173>. Để điện thoại cùng Wi-Fi/hotspot truy cập và **điều khiển** bơm, chạy `docker compose -f compose.yaml -f compose.lan.yaml up --build -d`, sau đó mở `http://<IP_LAN_LAPTOP>:5173`.

Frontend gọi URL tương đối `/api`. Nginx proxy `/api/` tới `http://backend:8000` (timeout 5 giây) và `/api/chat` riêng (timeout 135 giây), đồng thời chuyển `X-Forwarded-For`/`X-Forwarded-Proto` để backend nhận biết request đi qua tunnel. `backend` là hostname nội bộ Docker, không phải địa chỉ cho trình duyệt.

## Chạy development ngoài Docker

Yêu cầu Node.js 22 và npm:

```bash
npm ci
npm run dev
```

Vite chỉ phục vụ `127.0.0.1:5173` và proxy `/api` tới <http://127.0.0.1:8000>.

Kiểm tra:

```bash
npm test
npm run build
```

## App Android (Capacitor)

`frontend/android` là project Capacitor 8.5.2 (`appId` `com.aiot.smartgarden`), đóng gói assets từ `dist-mobile/` (không dùng `server.url` mở website). iOS chưa thuộc BC-01; scaffold iOS vẫn nằm trên nhánh PR #4.

Yêu cầu: Node.js 22, JDK 21, Android SDK Platform 36 / Build Tools 35, và backend đang có URL HTTPS công khai (ví dụ `scripts/start-backend-tunnel.ps1` với Cloudflare Quick Tunnel).

```bash
cd frontend
npm ci
cp .env.mobile.example .env.mobile.local   # điền VITE_API_URL=https://<backend-tunnel>
npm test
npm run android:sync
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Trên Windows dùng `copy` và `.\gradlew.bat assembleDebug`. `npm run build:mobile` kiểm tra trước khi build: URL phải là HTTPS origin, `/health` trả `{"status":"ok"}` và OpenAPI có `POST /devices/{device_id}/commands`; copy nhầm URL frontend (trả HTML) sẽ bị từ chối. URL tunnel đổi sau mỗi lần khởi động lại, nên phải chạy lại `android:sync` + Gradle + cài APK. `.env.mobile.local`, `dist-mobile/` và file sinh ra trong `android/app/src/main/assets` đều bị Git ignore.

**App Android cần đăng nhập** bằng tài khoản vận hành; sau đó giám sát và điều khiển bơm qua HTTPS giống Web. Không có token nào nhúng trong APK. Origin WebView `https://localhost` là assets của app, không phải laptop; backend cho phép origin này và header `Authorization` qua `CORS_ORIGINS`, nhưng CORS không phải xác thực.

Kiểm thử bắt buộc trên điện thoại thật (chưa thể tự động hóa trong CI): cài APK, tắt Wi-Fi dùng 4G/5G, đăng nhập sai rồi đúng, xác nhận telemetry/state hiển thị, nhãn mô phỏng/thật, stale khi tắt simulator/ESP32, bật bơm 5 giây đi tới `applied` rồi tắt, đăng xuất, mở lại app phải đăng nhập lại, chatbot trả lời hoặc báo lỗi rõ ràng.
