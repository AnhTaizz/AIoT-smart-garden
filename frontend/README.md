# Frontend ReactJS

Trạng thái ngày 2026-09-29: PR #3 đã merge vào `main`. Frontend React 19 + TypeScript + Vite hiện có implementation cho telemetry/history, device/relay state và pump command lifecycle; `npm test` pass **5/5**, `npm run build` pass và M1 Web/LAN đã được nhóm nghiệm thu trên browser điện thoại. Capacitor/Android là M1.5, hiện TODO/NEXT.

## Chức năng hiện có

- Health/readiness của FastAPI/PostgreSQL.
- Latest telemetry: nhiệt độ, độ ẩm không khí, độ ẩm đất, lỗi sensor, stale và simulated/real badge.
- History REST và sparkline cho nhiệt độ/độ ẩm đất.
- Device mode/boot/relay state do backend trả về.
- Pump ON với thời lượng và pump OFF; theo dõi `pending`, `applied`, `rejected`, `timeout`.
- Chỉ báo thành công sau khi backend trả `applied` từ ACK + state evidence; HTTP `202` chỉ bắt đầu trạng thái chờ.
- Responsive CSS/mobile breakpoint; camera hiện chỉ là placeholder “Chưa triển khai”.

Chưa có UI đổi Manual/Auto, authentication, WebSocket, ảnh/AI thật hoặc Capacitor/Android. Frontend hiện dùng REST polling.

## Kiến trúc web và Android

Đây là codebase frontend duy nhất:

```text
ReactJS source -> Vite production build -> browser/Nginx
                               \-------> Capacitor -> Android WebView/APK
```

Không tạo React Native, Flutter hoặc native Kotlin UI riêng. C sở hữu UI responsive/mobile-first; B chịu trách nhiệm Capacitor, Android toolchain, sync/build và APK. Browser/Android chỉ gọi FastAPI qua REST/WebSocket, không kết nối MQTT trực tiếp và không chứa pump safety logic.

Capacitor chưa được cài/config trong repository. Checklist M1.5 nằm trong [ROADMAP](../docs/ROADMAP.md#m15-android-packaging).

## Chạy cùng Docker Compose

Từ root repository:

```bash
docker compose up --build -d
```

Development mode mở <http://127.0.0.1:5173>. Browser trên điện thoại cùng Wi-Fi/hotspot dùng LAN override rồi mở `http://<IP_LAN_LAPTOP>:5173`:

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

## Networking cho Capacitor Android

Trong điện thoại, `http://localhost:8000` trỏ vào điện thoại, không phải laptop. Bản DEV trên LAN phải cấu hình API bằng giá trị dạng:

```text
VITE_API_BASE_URL=http://<LAPTOP_LAN_IP>:<BACKEND_PORT>
```

Khi WebSocket được implement, dùng cấu hình riêng tương đương như `VITE_WS_BASE_URL`. Không hard-code IP cụ thể vì IP thay đổi theo Wi-Fi/hotspot.

Nếu Android chặn cleartext HTTP, chỉ thêm policy/exception cho DEV local với phạm vi hẹp; production hướng tới HTTPS/WSS. Ưu tiên cài/test bằng USB debugging và `adb` trên điện thoại Android thật. Emulator là optional.

## Điều kiện DONE cho Android

React build pass chưa đủ. Android task chỉ DONE khi Capacitor sync/build pass, APK cài và mở trên điện thoại thật, app gọi được FastAPI trên laptop, và control flow hiển thị đúng ACK/state. Release APK chỉ tạo khi signing/config sẵn sàng; không commit signing key hoặc secret.
