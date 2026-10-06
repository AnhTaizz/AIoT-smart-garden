# Trạng thái dự án

## Trạng thái Cloudflare + Remote Mobile — 2026-10-06

**MANUAL DEVICE TEST — User-confirmed on physical Android device (2026-10-06, Asia/Bangkok).** Người dùng xác nhận APK cài/chạy trên Android thật, tắt Wi-Fi và dùng 4G/5G; telemetry/state, pump ON/OFF, Web/App shared state và ACK + state lifecycle đều PASS. Đây là **USER-CONFIRMED MANUAL TEST**, không phải automated test; không suy ra phone browser 4G, network recovery, iOS hoặc phần cứng ESP32 đã được kiểm thử. iOS architecture/config READY; build/runtime NOT TESTED. Regression và kết luận đóng phase: [REMOTE_MOBILE_REPORT](REMOTE_MOBILE_REPORT_2026-10-06.md). Firmware/hardware, camera/AI và production deployment còn mở.

**Các mục snapshot, milestone và priority ngày 2026-09-30 bên dưới được giữ như lịch sử; các nhãn Android BLOCKED và hướng phone LAN đã được thay thế bởi evidence/config remote ở trên.** User access hiện hành dùng Cloudflare HTTPS; ESP32 → Mosquitto LAN vẫn hợp lệ.

> Quyết định user ngày 2026-10-06: demo chính qua **Cloudflare Quick Tunnel**; Web/mobile browser dùng Internet, Capacitor Android/iOS gọi HTTPS FastAPI trực tiếp. Giữ MQTT LAN cho ESP32. Giữ React + Capacitor, không tạo Expo. Xem [hướng dẫn remote](REMOTE_DEMO.md) và [báo cáo kiểm chứng](REMOTE_MOBILE_REPORT_2026-10-06.md). Các nghiệm thu M1 LAN/M1.5A phía dưới là lịch sử; không chứng minh runtime 4G/5G hoặc iOS.


Cập nhật: **2026-09-30**. Nguồn trạng thái chi tiết và Definition of Done: [PROJECT ROADMAP](ROADMAP.md).

## Repository snapshot

- Branch: `main`.
- HEAD trước task M1.5A: `e1219cf7afe5f0709897a6b7c619cb03def36d0f`; `origin/main`: `208bf772ae0d7b0399ba6520624944da3792f78b`, local `main` ahead 1 commit tài liệu.
- Working tree trước task M1.5A: sạch.
- PR #2 backend/simulator đã merge ở `cd5e8ee`; PR #3 frontend đã merge ở `208bf77`.
- GitHub CLI không có trên máy audit và trang PR không đọc được qua kết nối web của phiên này; merge status ở trên được xác định từ refs/log local đã đồng bộ với `origin/main`.
- Không có GitHub Actions workflow trong `.github/`; repo chỉ có issue/PR templates, nên không có CI result trong repository để viện dẫn.

## Trạng thái theo workstream

| Workstream | Trạng thái | Kết luận |
| --- | --- | --- |
| Overall | `[~] IN PROGRESS` | Software core đã tiến triển; hardware, Android và camera/AI chưa có |
| Backend | `[x] DONE` cho software M1 | MQTT ingest, PostgreSQL, REST telemetry, command/ACK/state và persistence đã implement/test |
| Simulator | `[x] DONE` | Reference device hai chiều và safety regressions đã test; không thay firmware thật |
| Embedded | `[ ] TODO` | `firmware/` chỉ có README; chưa có bằng chứng ESP32/sensor/relay/bơm |
| ReactJS | `[x] DONE` cho MVP M1 | UI nghiệp vụ, tests/build và phiên E2E qua browser điện thoại trên LAN đã được nhóm nghiệm thu; các màn hình sau M1 còn mở |
| Android/Capacitor — M1.5 | `[!] BLOCKED` | M1.5A packaging và laptop-side Docker/LAN validation đã PASS; không có thiết bị trong `adb devices -l`, nên chưa thể nghiệm thu app trên điện thoại thật |
| Camera/AI | `[ ] TODO` | Chưa có code/dataset/model/image API; UI camera là placeholder |
| Integration | `[x] DONE` cho M1 Web/LAN | Nhóm đã nghiệm thu luồng React → FastAPI → MQTT/Mosquitto → simulator → ACK/state → React trên browser điện thoại qua LAN |

## Những gì đã xác minh DONE

### Backend và dữ liệu

- MQTT subscribe `garden/+/telemetry`, `garden/+/ack`, `garden/+/state`; publish command tới `garden/<id>/control`, QoS 1, không retained.
- Validate và lưu telemetry vào PostgreSQL; payload lỗi được tách vào `rejected_message`; duplicate theo device/boot/sequence bị bỏ qua.
- `GET /devices/{id}/latest`, history, state, command create/get/list.
- Command có `command_id`, `command_sequence`, `expires_at` tuyệt đối và `target_boot_id` cho ON.
- `applied` cần ACK `applied` và state relay phù hợp cùng boot trước deadline; evidence gắn theo command.
- Timeout không hồi sinh; ACK/state muộn được ghi evidence/event; boot cũ không ghi đè state hiện tại.
- 84/84 backend unit + E2E tests pass ngày 2026-09-29 trên Python 3.12/PostgreSQL/Mosquitto thật trong Compose network.

### Simulator tham chiếu

- Telemetry/control/ACK/state v1, clock-unsynced rejection, OFF priority, local timeout, command dedup/order và reboot behavior.
- Mất MQTT lúc ON đặt relay `off`, xóa running command/timer; reconnect phát state `off` và không replay ON trùng trong cùng boot.
- 31/31 simulator tests pass ngày 2026-09-29. Phiên broker thật của PR #2 vẫn được lưu trong [PR2 test handoff](PR2_TEST_HANDOFF_2026-09-26.md).

### ReactJS

- Dashboard lấy health/readiness, latest telemetry, history, device state và recent commands qua REST.
- Hiển thị temperature, air humidity, soil moisture, stale/simulated và sensor error; history sparkline.
- Gửi pump ON/OFF; poll command và chỉ báo thành công khi backend trả `applied`, không dựa vào HTTP `202`.
- Responsive CSS có breakpoint mobile; 5/5 Vitest pass và TypeScript/Vite production build pass ngày 2026-09-29.

### Hạ tầng

- `docker compose config --quiet` pass.
- PostgreSQL, Mosquitto, backend và frontend build/start healthy trong phiên audit; `/health` trả `ok`, `/ready` trả PostgreSQL `up`.
- Base Compose bind localhost; LAN override chỉ expose frontend và MQTT. PostgreSQL/FastAPI không bị expose trực tiếp bởi override hiện tại.

## IN PROGRESS

- M1.5A đã hoàn tất mức packaging tối thiểu: React baseline PASS, Capacitor/Android generated, Gradle Wrapper 8.14.3 + AGP 8.13.0 chạy được trên JDK 21 và debug APK tồn tại.
- Android SDK command-line đã được ổn định tại `%LOCALAPPDATA%\Android\Sdk`; Platform 36, Build Tools 35.0.0 và Platform Tools 37.0.1 hoạt động mà không đổi PATH/JAVA_HOME toàn hệ thống.
- Laptop-side LAN validation PASS: Compose LAN healthy; Nginx `/api` trên IP Wi-Fi runtime trả health, latest/history/state; simulator mới gửi 10 telemetry và dữ liệu đọc lại có `stale=false`.
- Physical-phone integration đang `[!] BLOCKED`: `adb devices -l` không có thiết bị, nên chưa thể install, launch hoặc xác nhận telemetry/control/ACK-state trên UI Android.
- Phần tích hợp ESP32 thật của M2 chưa bắt đầu; backend contract đã sẵn sàng nhưng firmware/hardware chưa có bằng chứng.

## TODO / chưa có bằng chứng

- Firmware ESP32, sensor calibration, relay/bơm, device clock sync, Manual/Auto và hardware safety verification.
- Android Studio nếu nhóm muốn dùng IDE; command-line SDK persistent đã đủ cho Gradle Wrapper build.
- Cài debug APK trên điện thoại thật; REST/control/ACK-state test từ Android app và xác minh CORS cho origin thực tế.
- Release APK/signing chưa thuộc M1.5A; production tiếp tục hướng tới HTTPS/WSS.
- Auth (chưa chốt scope) và WebSocket (chưa implement; frontend hiện polling).
- ESP32-CAM, image API/storage, dataset/model/evaluation và AI UI thật.
- M2–M7, hardening, security, report/demo artifacts.

## Milestone

| Mốc | Trạng thái | Bằng chứng | Thiếu |
| --- | --- | --- | --- |
| M1 — Simulator + React + mobile LAN | `[x] DONE` | G02 AGREED; nhóm đã nghiệm thu E2E React → FastAPI → MQTT/Mosquitto → simulator → ACK/state → React trên browser điện thoại qua LAN | Không phụ thuộc Capacitor |
| M1.5 — Android Packaging & Mobile Integration | `[!] BLOCKED` | M1.5A PASS; SDK persistent; React 5/5, cap sync, Gradle debug build, APK 4.08 MiB và laptop-side Docker/LAN telemetry PASS | Chờ điện thoại thật để install/launch và xác nhận FastAPI LAN, telemetry, pump command, ACK/state trên app |
| M2 — Phần cứng thật | `[ ] TODO` | Không có | ESP32/sensor/relay/bơm + phone control |
| M3 — Manual/Auto an toàn | `[ ] TODO` | Simulator reference không đủ | Firmware/device thật và failure tests |
| M4 — ESP32-CAM/AI baseline | `[ ] TODO` | Không có | Ảnh thật, pipeline, model/evaluation |
| M5 — Tích hợp đầy đủ | `[ ] TODO` | Không có | IoT + React/Android + camera/AI |
| M6 — Hardening | `[ ] TODO` | Không có | Chạy kéo dài, recovery/security/results |
| M7 — Bàn giao | `[ ] TODO` | Không có | APK, demo thật, report/slide/video |

## Việc tiếp theo theo priority

1. B kết nối điện thoại Android thật, bật USB debugging, xác nhận `adb devices -l` trả status `device`, rồi cài APK debug.
2. B+C build với API base URL LAN runtime bằng env/config; ưu tiên `http://<LAPTOP_LAN_IP>:<FRONTEND_LAN_PORT>/api` qua Nginx hiện có, xác minh CORS theo origin thực tế trên phone, không dùng `localhost` hoặc hard-code IP.
3. A chốt G03 rồi triển khai ESP32/sensor/relay với boot-OFF, local timeout, clock sync và reconnect safety.
4. C tiếp tục React mobile-first, Manual/Auto UX khi backend/device hỗ trợ, rồi camera/CV/AI theo dependency.
5. Auth/WebSocket chỉ triển khai khi scope/need được chốt; không coi là điều kiện của M1 hoặc M1.5 nếu chưa nằm trong scope.

## Nhật ký quyết định

- 2026-09-13: chốt local mobile demo bằng browser qua LAN; public Internet optional.
- 2026-09-26: ghi regression backend/simulator của PR #2; thời điểm đó PR chưa merge.
- 2026-09-29: audit lại `main`: PR #2/#3 đã merge; frontend telemetry/control đã tồn tại và pass test/build.
- 2026-09-29: chốt hướng mobile mới là **ReactJS production build + Capacitor + Android APK**, dùng chung frontend; React Native không được chọn. Thêm workstream Android sớm vào lịch, không viết lại lịch sử như thể đã có từ đầu.
- 2026-09-29: A/B/C chính thức chốt G02 là **AGREED** và nghiệm thu **M1 Web/LAN DONE** trên browser điện thoại; Android packaging được tách thành **M1.5 — TODO/NEXT**.
- 2026-09-30: M1.5A đạt mức tối thiểu — Capacitor/Android generated, SDK persistent, sync và debug APK build PASS; Docker/LAN/simulator đã PASS từ laptop. M1.5 tổng thể BLOCKED ON PHYSICAL DEVICE TEST vì chưa có điện thoại trong `adb`.
