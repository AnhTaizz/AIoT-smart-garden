# Frontend ReactJS

Trạng thái ngày 2026-10-06: React 19 + TypeScript + Vite, Capacitor `8.5.2`; regression frontend mới **16/16 PASS**, typecheck và production Web build PASS. **MANUAL DEVICE TEST — User-confirmed on physical Android device (2026-10-06, Asia/Bangkok).** Người dùng xác nhận APK cài/chạy trên Android thật, tắt Wi-Fi và dùng 4G/5G; telemetry/state, pump ON/OFF, Web/App shared state và ACK + state lifecycle đều PASS. Đây là **USER-CONFIRMED MANUAL TEST**, không phải automated test; không suy ra phone browser 4G, network recovery, iOS hoặc phần cứng ESP32 đã được kiểm thử. Xem [báo cáo](../docs/REMOTE_MOBILE_REPORT_2026-10-06.md). iOS architecture/config READY; build/runtime NOT TESTED.

## Chức năng hiện có

- Health/readiness của FastAPI/PostgreSQL.
- Latest telemetry: nhiệt độ, độ ẩm không khí, độ ẩm đất, lỗi sensor, stale và simulated/real badge.
- History REST và sparkline cho nhiệt độ/độ ẩm đất.
- Device mode/boot/relay state do backend trả về.
- Pump ON với thời lượng và pump OFF; theo dõi `pending`, `applied`, `rejected`, `timeout`.
- Chỉ báo thành công sau khi backend trả `applied` từ ACK + state evidence; HTTP `202` chỉ bắt đầu trạng thái chờ.
- Responsive CSS/mobile breakpoint; camera hiện chỉ là placeholder “Chưa triển khai”.

Chưa có UI đổi Manual/Auto, authentication, WebSocket hoặc ảnh/AI thật. Frontend hiện dùng REST polling; Android dùng lại nguyên UI này, không có codebase mobile thứ hai.

## Kiến trúc Web và Mobile App

Đây là codebase frontend duy nhất:

```text
ReactJS source -> Vite Web build (dist) -> browser/Nginx
              \-> mobile build (dist-mobile) -> Capacitor Android/iOS
```

Không tạo React Native, Flutter hoặc native Kotlin UI riêng. C sở hữu UI responsive/mobile-first; B chịu trách nhiệm Capacitor, Android toolchain, sync/build và APK. Browser/Android chỉ gọi FastAPI qua REST/WebSocket, không kết nối MQTT trực tiếp và không chứa pump safety logic.

Capacitor config dùng `appId: com.aiot.smartgarden`, app name `Smart Garden` và `webDir: dist-mobile`. Android platform nằm ở `frontend/android/`; checklist M1.5 nằm trong [ROADMAP](../docs/ROADMAP.md#m15-android-packaging).

## Android debug build

Yêu cầu: JDK 21, Android SDK Platform 36, Build Tools 35.0.0 và Platform Tools. Máy audit dùng command-line SDK persistent tại `%LOCALAPPDATA%\Android\Sdk`; không cần Android Studio hoặc system Gradle. Dùng Gradle Wrapper trong project:

```powershell
npm ci
npm test
$env:VITE_API_URL = (Read-Host "Paste the current BACKEND HTTPS tunnel URL").TrimEnd('/')
npm run android:sync
Set-Location .\android
.\gradlew.bat assembleDebug
```

`android:sync` xác minh backend HTTPS rồi build mobile vào `dist-mobile/` trước khi `cap sync android`; Web build vẫn dùng `dist/`. APK debug được tạo tại `android/app/build/outputs/apk/debug/app-debug.apk`; file APK và build cache được ignore, không commit vào Git. Android Studio là tùy chọn để mở project, không bắt buộc cho command-line build.

Gradle Wrapper (`gradlew` / `gradlew.bat`) tự tạo `logs/java/` ở root repository và chuyển log crash JVM (`hs_err_pid*.log`, `replay_pid*.log`) vào đó, kể cả khi chạy wrapper từ thư mục khác. Thư mục `logs/` đã được Git ignore. Sau khi cập nhật wrapper, chạy `./gradlew --stop` (Linux/macOS) hoặc `.\gradlew.bat --stop` (Windows) một lần trước lần build tiếp theo để daemon cũ nhận cấu hình mới. Cấu hình này áp dụng khi chạy qua wrapper; build trực tiếp từ Android Studio không đi qua script này.

## Remote Web và Capacitor (quyết định 2026-10-06)

Giữ một codebase React + Capacitor cho Web, Android và iOS. User access chính qua Cloudflare Quick Tunnel; ESP32 -> MQTT LAN độc lập. Web dùng `/api` qua frontend tunnel; Capacitor gọi backend tunnel HTTPS trực tiếp bằng `VITE_API_URL` trong local mobile env. Không tạo Expo/React Native. Cách chạy/build/test chính: [REMOTE_DEMO](../docs/REMOTE_DEMO.md).

## Chạy cùng Docker Compose

Từ root repository:

```bash
docker compose up --build -d
```

Development mode mở <http://127.0.0.1:5173>. Remote demo dùng frontend tunnel theo REMOTE_DEMO. **DEPRECATED FOR USER ACCESS**: đoạn LAN override dưới đây chỉ giữ cho demo cũ:

```bash
docker compose -f compose.yaml -f compose.lan.yaml up --build -d
```

Frontend web gọi URL tương đối `/api`. Nginx trong container proxy tới `http://backend:8000`; hostname `backend` chỉ tồn tại trong network Compose.

## Chạy development ngoài Docker

```bash
npm ci
npm run dev
npm test
npm run build
```

Vite development server mặc định phục vụ `127.0.0.1:5173` và proxy `/api` tới <http://127.0.0.1:8000>. Có thể đặt `VITE_API_BASE_URL` ở build time, nhưng URL phải truy cập được từ runtime client và FastAPI cần CORS nếu khác origin.

## Networking cho Capacitor Android/iOS

Trong điện thoại, `localhost` trỏ vào điện thoại, không phải laptop. App chính dùng `VITE_API_URL` bằng URL HTTPS backend tunnel thực tế, ghi trong `.env.mobile.local` (ignored). Ví dụ sau chỉ là **LAN legacy — DEPRECATED FOR USER ACCESS**:

```text
VITE_API_BASE_URL=http://<LAPTOP_LAN_IP>:<FRONTEND_LAN_PORT>/api
```

Đây là URL Nginx/frontend được `compose.lan.yaml` expose; Nginx proxy `/api` tới FastAPI trong Docker. Chỉ trỏ thẳng tới cổng backend nếu cổng đó được expose có chủ đích. Khi WebSocket được implement, dùng cấu hình riêng tương đương như `VITE_WS_BASE_URL`. Không hard-code IP cụ thể vì IP thay đổi theo Wi-Fi/hotspot.

Debug manifest cho phép cleartext HTTP chỉ trong build type `debug` để test DEV LAN; release manifest không bật ngoại lệ này và production vẫn hướng tới HTTPS/WSS. Backend đã cấu hình CORS allow-list qua `CORS_ORIGINS`, mặc định gồm Android `https://localhost` và iOS `capacitor://localhost`; không dùng wildcard. Ưu tiên cài/test bằng USB debugging và `adb` trên điện thoại Android thật. Emulator là optional.

**Mobile App** = ứng dụng Capacitor Android/iOS. **Mobile Browser** = browser/PWA access; repo chưa implement PWA.

## Điều kiện DONE cho Android

React build pass chưa đủ. Android task chỉ DONE khi Capacitor sync/build pass, APK cài và mở trên điện thoại thật, app gọi được FastAPI trên laptop, và control flow hiển thị đúng ACK/state. Release APK chỉ tạo khi signing/config sẵn sàng; không commit signing key hoặc secret.
