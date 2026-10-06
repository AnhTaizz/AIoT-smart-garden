# Remote demo — Cloudflare + React/Capacitor

User access chính qua Internet/4G/5G. Laptop vẫn chạy services local. ESP32 -> Mosquitto có thể dùng LAN; không tunnel MQTT hoặc PostgreSQL. Browser dùng frontend HTTPS tunnel + `/api`; app Capacitor dùng backend HTTPS tunnel **trực tiếp**.

## Evidence hiện tại — 2026-10-06

**MANUAL DEVICE TEST — User-confirmed on physical Android device (2026-10-06, Asia/Bangkok).** Người dùng xác nhận APK cài/chạy trên Android thật, tắt Wi-Fi và dùng 4G/5G; telemetry/state, pump ON/OFF, Web/App shared state và ACK + state lifecycle đều PASS. Đây là **USER-CONFIRMED MANUAL TEST**, không phải automated test; không suy ra phone browser 4G, network recovery, iOS hoặc phần cứng ESP32 đã được kiểm thử. iOS architecture/config READY; build/runtime NOT TESTED vì môi trường này không có macOS/Xcode/iPhone để nghiệm thu iOS. Testcase hiện có M-01..M-06 được cập nhật trong [báo cáo](REMOTE_MOBILE_REPORT_2026-10-06.md).

**Mobile App** = Capacitor Android/iOS application; **Mobile Browser** = browser/PWA access (PWA chưa implement). Quy trình bên dưới dùng cho lần demo/retest tiếp theo; không phủ nhận evidence đã xác nhận.

## Requirements

Windows PowerShell, Docker Desktop với Compose hỗ trợ `!override`, Node.js 22+, npm. Mobile Android cần JDK 21 và Android SDK Platform 36/Build Tools 35.0.0/Platform Tools. iOS cần macOS/Xcode; Windows không build hoặc nghiệm thu iOS.

Cloudflare Quick Tunnel không cần account/domain/token; URL đổi khi restart. Đây là demo tạm, không production hosting. API chưa có authentication: người biết URL có thể gọi pump endpoints. CORS không phải authorization. Chỉ chạy tunnel trong thời gian demo, Ctrl+C để đóng.

## Terminal 1 — infrastructure + backend + frontend

Chạy từ root repo. Nếu `.env` đã có, giữ nguyên; không copy đè:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -f compose.yaml -f compose.device.yaml config --quiet
docker compose -f compose.yaml -f compose.device.yaml up --build -d
docker compose -f compose.yaml -f compose.device.yaml ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`compose.device.yaml` chỉ mở MQTT LAN; frontend/API/PostgreSQL giữ loopback. Bỏ override nếu chỉ dùng simulator trên laptop. Các port có thể đã được chỉnh trong `.env`; truyền port thực tế vào tunnel scripts.

## Terminal 2 — simulator hoặc ESP32

Simulator (không phải số đo thật):

```powershell
python -m venv simulator/.venv
.\simulator\.venv\Scripts\python.exe -m pip install -r simulator/requirements.txt
.\simulator\.venv\Scripts\python.exe simulator/simulator.py --device-id node_01 --interval 2
```

ESP32 thật dùng IP LAN laptop và MQTT port mặc định 1883 trên mạng thiết bị tin cậy. Chỉ mở firewall MQTT cho mạng đó; phone/user không cần mạng đó. Firmware trong repo hiện chưa implement.

## Terminal 3 — backend tunnel

Cài `cloudflared` theo [Cloudflare downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/). Nếu không có trong PATH, có thể tải binary chính thức vào thư mục ignored `logs/`:

```powershell
New-Item -ItemType Directory -Force logs | Out-Null
Invoke-WebRequest https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile logs/cloudflared-windows-amd64.exe
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-backend-tunnel.ps1 -CloudflaredPath .\logs\cloudflared-windows-amd64.exe
```

Nếu đã cài trong PATH: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-backend-tunnel.ps1`. Execution policy chỉ áp dụng process, không chỉnh policy hệ thống. Nếu mạng chặn QUIC, thêm `-Protocol http2`. Mặc định origin `http://127.0.0.1:8000`; đổi bằng `-Port`.

Copy URL HTTPS backend từ console vào biến local ở terminal kiểm tra/build mobile. Không ghi URL vào source/docs tracked. Ví dụ lệnh dùng URL thực tế người chạy vừa nhận:

```powershell
$backendUrl = (Read-Host "Paste backend HTTPS Quick Tunnel URL").TrimEnd('/')
Invoke-RestMethod "$backendUrl/health"
Invoke-RestMethod "$backendUrl/ready"
```

## Terminal 4 — frontend tunnel

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-frontend-tunnel.ps1 -CloudflaredPath .\logs\cloudflared-windows-amd64.exe
```

Origin mặc định `http://127.0.0.1:5173`. Web mặc định dùng `/api`, Nginx proxy tới FastAPI trong Compose. Không cần đặt public backend URL cho Web cùng origin. Script rewrite HTTP Host về localhost nên Vite development cũng dùng được mà không `allowedHosts=true`.

Vite là lựa chọn development khác, **thay** container frontend trên cùng port:

```powershell
docker compose stop frontend
Set-Location frontend
npm ci
npm run dev
```

Vite proxy `/api` tới backend host loopback 8000; local Web vẫn chạy được. Không dùng Vite dev server như production hosting.

## Cross-origin Web (optional)

Nếu Web phải gọi backend tunnel trực tiếp, đặt `VITE_API_URL` bằng URL HTTPS backend hiện tại trong local env/build environment. `VITE_API_BASE_URL` cũ vẫn được hỗ trợ, ưu tiên thấp hơn `VITE_API_URL`. Trong root `.env`, thêm **đúng frontend origin** vào `CORS_ORIGINS`, giữ Android/iOS origins; recreate backend và rebuild frontend:

```powershell
docker compose -f compose.yaml -f compose.device.yaml up --build -d backend frontend
```

Không wildcard `*` hoặc hard-code random URL. Backend native WebView origins mặc định `https://localhost` (Android) và `capacitor://localhost` (iOS). HTTPS Web không được gọi HTTP API (mixed content). App native không dùng relative `/api`.

## Regression tests

```powershell
Push-Location frontend
npm test
npm run build
Pop-Location
docker compose -f compose.yaml -f compose.device.yaml -f compose.test.yaml --profile tests run --build --rm regression-tests
```

Service test không expose port, lấy DB credentials qua Compose env và chạy toàn bộ backend unit/E2E + simulator safety; E2E dùng device ID riêng, không điều khiển `node_01`. Không `down -v` hoặc xóa dữ liệu demo.

## Manual remote Web / 4G test

1. Chờ `/ready` báo postgres up, chạy simulator và xác nhận state/telemetry có dữ liệu.
2. Giữ hai tunnels chạy; dùng frontend HTTPS URL trên laptop trước.
3. Trên phone tắt Wi-Fi, bật 4G/5G. Mở frontend HTTPS URL. Kiểm tra temperature/humidity/soil moisture, pump/mode và stale/online status.
4. Gửi ON với thời lượng ngắn. HTTP 202 là pending, chưa phải pump ON. Chờ backend `applied` (ACK + state khớp), kiểm tra `/state`; gửi OFF và chờ applied.
5. Thử mất mạng/khôi phục, refresh; không được tự gửi lại POST ON cũ. Simulator phải OFF khi mất MQTT.
6. Thiết bị không ACK phải timeout; rejection phải hiện reason. Không đánh dấu phone PASS chỉ từ curl hoặc tests mock.

## LAN legacy

`compose.lan.yaml` vẫn giữ nguyên frontend+MQTT exposure của demo cũ, **DEPRECATED FOR USER ACCESS**. `ipconfig`/IP LAN laptop chỉ còn cần để cấu hình ESP32 -> MQTT hoặc chạy lại lịch sử LAN, không phải user access chính.

## Mobile

Một codebase React + Capacitor, app native đóng gói assets local; không phải browser shortcut, không dùng `server.url` để mở website. `webDir=dist-mobile`, tách khỏi Web `dist/`. Không tạo Expo project. Poll REST, không có WebSocket/WSS/SSE trong MVP.

### Terminal 5 — Android build / install

Giữ backend và backend tunnel chạy. Từ root repo:

```powershell
Push-Location frontend
npm ci
# Chỉ copy example nếu file local chưa tồn tại; điền HTTPS BACKEND URL trong file đó.
if (-not (Test-Path .env.mobile.local)) { Copy-Item .env.mobile.example .env.mobile.local }
# Hoặc đặt URL cho process hiện tại, không ghi vào source:
$env:VITE_API_URL = (Read-Host "Paste BACKEND HTTPS tunnel URL, NOT frontend URL").TrimEnd('/')
npm test
npm run android:sync
if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk" }
Push-Location android
.\gradlew.bat assembleDebug --no-daemon --max-workers=2
Pop-Location
& "$env:ANDROID_HOME\platform-tools\adb.exe" devices -l
# Khi có đúng một phone đã authorize USB debugging:
& "$env:ANDROID_HOME\platform-tools\adb.exe" install -r android/app/build/outputs/apk/debug/app-debug.apk
& "$env:ANDROID_HOME\platform-tools\adb.exe" shell am start -n com.aiot.smartgarden/.MainActivity
Pop-Location
```

Nếu nhiều devices, thêm `-s` với serial từ `adb devices -l`. Nếu không có device, chỉ ghi build verified; không ghi runtime hoặc 4G PASS. APK debug không phải bản ký phát hành App Store/Play Store.

Mobile builder bắt buộc HTTPS backend origin (không `/api` proxy, credentials hoặc LAN/localhost API); xác minh `/health` và FastAPI OpenAPI command endpoint trước khi ghi output. Copy nhầm frontend tunnel URL sẽ bị từ chối. URL tunnel cần đang hoạt động và DNS đã cập nhật. Native runtime còn từ chối relative API/HTTP/private LAN hosts. Native origin `https://localhost` / `capacitor://localhost` là **assets của app**, không phải laptop backend.

`VITE_API_BASE_URL` vẫn là alias cho cấu hình cũ, nhưng native cần absolute public HTTPS; `VITE_API_URL` ưu tiên cao hơn. Env là build-time: khi backend Quick Tunnel URL đổi, cập nhật local env, chạy lại sync + Gradle build + install. Không chỉ rebuild Web vì output Web tách riêng.

### iOS — cùng React / API

Target `frontend/ios/` đã được tạo bằng Capacitor 8.5.2, dùng Swift Package Manager và iOS deployment target 15.0. `@capacitor/ios`, Android/core/CLI cùng version; không có business logic iOS riêng. Runtime asset origin `capacitor://localhost` có trong backend CORS mặc định; HTTPS API tuân theo ATS mặc định, không thêm arbitrary HTTP exception.

Trên macOS, chuẩn bị Xcode phù hợp Capacitor 8 (tài liệu hiện yêu cầu Xcode 26+), rồi:

```bash
cd frontend
npm ci
# Tạo/điền .env.mobile.local với HTTPS backend URL còn hoạt động.
npm run ios:sync
npx cap open ios
```

Không chạy `ios:add` lại khi target đã có. Trong Xcode chọn signing team của người build và iPhone/simulator, chạy app rồi kiểm tra API/command. Không commit certificate, provisioning profile hoặc team secrets. Windows hiện chỉ xác minh project/config; iOS build/runtime **NOT TESTED**. [Capacitor iOS setup](https://capacitorjs.com/docs/ios).

### Manual Android 4G/5G test

1. Install APK mới với URL backend tunnel đang hoạt động; launch bằng command ở trên.
2. Tắt Wi-Fi trên phone, bật 4G/5G; laptop/tunnel và ESP32 hoặc simulator vẫn online.
3. Xác nhận app hiển thị temperature/humidity/soil, device mode và relay state; không coi sensor null/error là số 0.
4. Gửi ON 5 giây, theo dõi pending -> ACK/state -> applied; đối chiếu state thật/simulator. Gửi OFF, chờ applied. `POST 202` không phải success relay.
5. Cho device không trả lời để thấy timeout; clock-unsynced device phải reject ON với reason. Dùng thiết bị/simulator test riêng, không thay clock/safety của node demo ngoài ý muốn.
6. Mất/khôi phục mạng phone, nhấn Làm mới; chỉ GET status được retry (tối đa 5 lỗi liên tiếp), không tự gửi lại ON. Request HTTP hết thời gian sau 10 giây để UI không treo vô hạn.
7. Lưu kết quả, thời điểm, app version/APK và logs; nếu không chạy trên phone thật thì **NOT TESTED**.

### Quick Tunnel mất kết nối

Đã gặp tunnel hết hiệu lực sau khi laptop đổi/mất mạng: URL cũ không còn DNS hoặc log `Unauthorized: Tunnel not found`. Dừng tunnel lỗi, mở lại script, lấy URL mới; sửa local env và rebuild/reinstall mobile. Không hard-code URL cũ hoặc giả định tunnel tự giữ URL qua restart. Nếu Web dùng `/api`, chỉ cần mở frontend URL mới; Web không cần bake backend tunnel URL.

Tham chiếu: [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [Capacitor](https://capacitorjs.com/docs), [CORS](https://fastapi.tiangolo.com/tutorial/cors/).
