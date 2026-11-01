# Frontend ReactJS

Một codebase React + TypeScript strict + Vite dùng cho Web (Nginx trong Docker Compose) và app Capacitor Android/iOS; không có codebase mobile thứ hai.

Bằng chứng thiết bị gần nhất: ngày 2026-10-06 (bản **trước** BC-01/BC-02), **MANUAL DEVICE TEST — User-confirmed on physical Android device**: APK cài/chạy trên Android thật qua 4G/5G; telemetry/state, pump ON/OFF, Web/App shared state và ACK + state lifecycle PASS ([báo cáo](../docs/REMOTE_MOBILE_REPORT_2026-10-06.md)). Đây là kiểm tra thủ công do người dùng xác nhận, không phải automated test, và **chưa** được lặp lại với bản có đăng nhập BC-02. iOS architecture/config READY; build/runtime NOT TESTED.

Dashboard tiếng Việt hiện có:

- **Đăng nhập (BC-02):** chưa đăng nhập chỉ thấy form đăng nhập, không gọi API dữ liệu nào. Sau khi đăng nhập, mọi request được bảo vệ (kể cả `/chat`) gửi `Authorization: Bearer <token>`. Token chỉ nằm trong bộ nhớ (`src/auth.ts`), không ghi vào localStorage/sessionStorage/cookie/Capacitor Preferences và không nhúng vào APK; mật khẩu không được lưu. Tải lại trang hoặc mở lại app phải đăng nhập lại. Khi server trả 401 hoặc khi đến `expires_at`, app quay về màn hình đăng nhập và dừng polling; lệnh `POST` điều khiển bơm không bao giờ được tự gửi lại. **Đăng xuất (BC-02.1):** nút bơm khóa ngay; app gửi `POST /auth/logout` một lần. Chỉ khi server trả 200/401 mới báo "Máy chủ đã xác nhận". Nếu mất mạng, timeout hoặc 5xx, app vẫn xóa token khỏi thiết bị nhưng cảnh báo rõ phiên ở máy chủ **có thể vẫn dùng được tới giờ hết hạn**. Web và Android dùng cùng logic.

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

| Biến (build-time) | Web mặc định | Capacitor Android/iOS |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` (Nginx/Vite proxy cùng origin) | Alias cũ, ưu tiên thấp hơn |
| `VITE_API_URL` | Rỗng. Chỉ đặt khi Web phải gọi backend khác origin (HTTPS) | **Bắt buộc**: origin HTTPS công khai của FastAPI, không có `/api`. Demo cố định: `https://garden-api.anhtaizz.id.vn` |

Logic nằm ở `src/apiConfig.ts` và có test. Web HTTPS từ chối API HTTP (mixed content). App native từ chối URL tương đối, HTTP, `localhost`/IP LAN/private và đường dẫn khác `/`. Không đặt credentials/API key vào biến `VITE_*`: mọi giá trị này bị nhúng vào bundle; `CHAT_API_KEY` chỉ nằm ở backend.

## Kiến trúc Web và Mobile App

Đây là codebase frontend duy nhất:

```text
ReactJS source -> Vite Web build (dist) -> browser/Nginx
              \-> mobile build (dist-mobile) -> Capacitor Android/iOS
```

Không tạo React Native, Flutter hoặc native Kotlin UI riêng. C sở hữu UI responsive/mobile-first; B chịu trách nhiệm Capacitor, Android toolchain, sync/build và APK. Browser/Android chỉ gọi FastAPI qua REST/WebSocket, không kết nối MQTT trực tiếp và không chứa pump safety logic.

Capacitor config dùng `appId: com.aiot.smartgarden`, app name `Smart Garden` và `webDir: dist-mobile`. Android platform nằm ở `frontend/android/`; checklist M1.5 nằm trong [ROADMAP](../docs/ROADMAP.md#m15-android-packaging).

## Truy cập từ xa (Cloudflare Named Tunnel)

User access chính qua Named Tunnel `garden-local`; ESP32 -> MQTT LAN độc lập. Web mở `https://garden.anhtaizz.id.vn` (hoặc apex `https://anhtaizz.id.vn` khi đã thêm route) và gọi `/api` cùng origin qua Nginx; Capacitor gọi `https://garden-api.anhtaizz.id.vn` trực tiếp bằng `VITE_API_URL`. Quick Tunnel chỉ còn là phương án dự phòng. Cách chạy/build/test chính: [REMOTE_DEMO](../docs/REMOTE_DEMO.md).


## Chạy cùng Docker Compose

Từ root repository:

```bash
docker compose up --build -d
```

Development mode chỉ mở <http://127.0.0.1:5173>. Truy cập từ xa dùng domain cố định theo [REMOTE_DEMO](../docs/REMOTE_DEMO.md). **LAN legacy — DEPRECATED FOR USER ACCESS:** override dưới đây chỉ giữ cho demo cũ trên hotspot tin cậy; trang chạy HTTP nên mật khẩu và Bearer token đi dạng rõ trong mạng đó:

```bash
docker compose -f compose.yaml -f compose.lan.yaml up --build -d
```

Frontend gọi URL tương đối `/api`. Nginx proxy `/api/` tới `http://backend:8000` (timeout 5 giây) và `/api/chat` riêng (timeout 135 giây), đồng thời chuyển `X-Forwarded-For`/`X-Forwarded-Proto` chỉ để log/chẩn đoán; backend **không** dùng header hoặc IP để quyết định quyền. `backend` là hostname nội bộ Docker, không phải địa chỉ cho trình duyệt.

## Chạy development ngoài Docker

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

`frontend/android` là project Capacitor 8.5.2 (`appId` `com.aiot.smartgarden`), đóng gói assets từ `dist-mobile/` (không dùng `server.url` mở website). Scaffold iOS (`frontend/ios`, scheme `capacitor://localhost`) đi cùng bản tích hợp; build/runtime iOS NOT TESTED và cần macOS/Xcode.

Yêu cầu: Node.js 22, JDK 21, Android SDK Platform 36 / Build Tools 35, và backend đang có URL HTTPS công khai (`https://garden-api.anhtaizz.id.vn` qua Named Tunnel; dự phòng `scripts/start-backend-tunnel.ps1` với Quick Tunnel).

```bash
cd frontend
npm ci
cp .env.mobile.example .env.mobile.local   # VITE_API_URL=https://garden-api.anhtaizz.id.vn
npm test
npm run android:sync
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Trên Windows dùng `copy` và `.\gradlew.bat assembleDebug`. `npm run build:mobile` kiểm tra trước khi build: URL phải là HTTPS origin, `/health` trả `{"status":"ok"}` và OpenAPI có `POST /devices/{device_id}/commands`; copy nhầm URL frontend (trả HTML) sẽ bị từ chối. Với domain cố định không cần build lại APK khi restart laptop; chỉ khi dùng Quick Tunnel dự phòng (URL đổi mỗi lần) mới phải chạy lại `android:sync` + Gradle + cài APK. `.env.mobile.local`, `dist-mobile/` và file sinh ra trong `android/app/src/main/assets` đều bị Git ignore.

**App Android cần đăng nhập** bằng tài khoản vận hành; sau đó giám sát và điều khiển bơm qua HTTPS giống Web. Không có token nào nhúng trong APK. Origin WebView `https://localhost` là assets của app, không phải laptop; backend cho phép origin này và header `Authorization` qua `CORS_ORIGINS`, nhưng CORS không phải xác thực.

Kiểm thử bắt buộc trên điện thoại thật (chưa thể tự động hóa trong CI): cài APK, tắt Wi-Fi dùng 4G/5G, đăng nhập sai rồi đúng, xác nhận telemetry/state hiển thị, nhãn mô phỏng/thật, stale khi tắt simulator/ESP32, bật bơm 5 giây đi tới `applied` rồi tắt, đăng xuất, mở lại app phải đăng nhập lại, chatbot trả lời hoặc báo lỗi rõ ràng.

Gradle Wrapper (`gradlew` / `gradlew.bat`) tự tạo `logs/java/` ở root repository và chuyển log crash JVM (`hs_err_pid*.log`, `replay_pid*.log`) vào đó, kể cả khi chạy wrapper từ thư mục khác. Thư mục `logs/` đã được Git ignore. Sau khi cập nhật wrapper, chạy `./gradlew --stop` (Linux/macOS) hoặc `.\gradlew.bat --stop` (Windows) một lần trước lần build tiếp theo để daemon cũ nhận cấu hình mới. Cấu hình này áp dụng khi chạy qua wrapper; build trực tiếp từ Android Studio không đi qua script này.

## Networking cho Capacitor Android/iOS

Trong điện thoại, `localhost` trỏ vào điện thoại, không phải laptop; vì vậy app luôn dùng `VITE_API_URL` HTTPS công khai trong `.env.mobile.local` (ignored), không dùng IP LAN.

Debug manifest cho phép cleartext HTTP chỉ trong build type `debug` để test DEV LAN; release manifest không bật ngoại lệ này và production vẫn hướng tới HTTPS/WSS. Backend đã cấu hình CORS allow-list qua `CORS_ORIGINS`, mặc định gồm Android `https://localhost` và iOS `capacitor://localhost`; không dùng wildcard. Ưu tiên cài/test bằng USB debugging và `adb` trên điện thoại Android thật. Emulator là optional.

**Mobile App** = ứng dụng Capacitor Android/iOS. **Mobile Browser** = browser/PWA access; repo chưa implement PWA.

## Điều kiện DONE cho Android

React build pass chưa đủ. Android task chỉ DONE khi Capacitor sync/build pass, APK cài và mở trên điện thoại thật, app gọi được FastAPI trên laptop, và control flow hiển thị đúng ACK/state. Release APK chỉ tạo khi signing/config sẵn sàng; không commit signing key hoặc secret.
