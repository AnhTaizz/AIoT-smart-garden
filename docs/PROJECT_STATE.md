# Trạng thái dự án

Cập nhật: **2026-09-29**. Nguồn trạng thái chi tiết và Definition of Done: [PROJECT ROADMAP](ROADMAP.md).

## Repository snapshot

- Branch: `main`.
- HEAD và `origin/main`: `208bf772ae0d7b0399ba6520624944da3792f78b` — merge PR #3.
- Working tree trước audit: sạch; diff với `main`: không có.
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
| Android/Capacitor — M1.5 | `[ ] TODO / NEXT` | Chưa có Capacitor dependency/config, Android platform hoặc APK |
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

- M1.5 đang là workstream kế tiếp; bước audit môi trường đã xác minh Node/npm, React build và phát hiện JDK 21, nhưng chưa có Android project/Gradle để kiểm tra compatibility.
- Phần tích hợp ESP32 thật của M2 chưa bắt đầu; backend contract đã sẵn sàng nhưng firmware/hardware chưa có bằng chứng.

## TODO / chưa có bằng chứng

- Firmware ESP32, sensor calibration, relay/bơm, device clock sync, Manual/Auto và hardware safety verification.
- Capacitor install/config, Android Studio/SDK/adb/Gradle setup, Android platform, sync/build, debug/release APK và kiểm thử app trên điện thoại Android thật.
- REST/control/ACK-state test từ Android app; cleartext DEV policy; production HTTPS/WSS.
- Auth (chưa chốt scope) và WebSocket (chưa implement; frontend hiện polling).
- ESP32-CAM, image API/storage, dataset/model/evaluation và AI UI thật.
- M2–M7, hardening, security, report/demo artifacts.

## Milestone

| Mốc | Trạng thái | Bằng chứng | Thiếu |
| --- | --- | --- | --- |
| M1 — Simulator + React + mobile LAN | `[x] DONE` | G02 AGREED; nhóm đã nghiệm thu E2E React → FastAPI → MQTT/Mosquitto → simulator → ACK/state → React trên browser điện thoại qua LAN | Không phụ thuộc Capacitor |
| M1.5 — Android Packaging & Mobile Integration | `[ ] TODO / NEXT` | Node/npm và React production build đã verify; JDK 21 đã được phát hiện | Capacitor/Android toolchain, sync/build, cài/chạy và smoke test trên điện thoại thật, APK |
| M2 — Phần cứng thật | `[ ] TODO` | Không có | ESP32/sensor/relay/bơm + phone control |
| M3 — Manual/Auto an toàn | `[ ] TODO` | Simulator reference không đủ | Firmware/device thật và failure tests |
| M4 — ESP32-CAM/AI baseline | `[ ] TODO` | Không có | Ảnh thật, pipeline, model/evaluation |
| M5 — Tích hợp đầy đủ | `[ ] TODO` | Không có | IoT + React/Android + camera/AI |
| M6 — Hardening | `[ ] TODO` | Không có | Chạy kéo dài, recovery/security/results |
| M7 — Bàn giao | `[ ] TODO` | Không có | APK, demo thật, report/slide/video |

## Việc tiếp theo theo priority

1. B triển khai M1.5: cài/config Capacitor, tạo Android platform, verify Android Studio/SDK/adb/JDK/Gradle và cài smoke build lên điện thoại thật.
2. B+C cấu hình API base URL cho Android bằng env/config; kiểm tra `http://<LAPTOP_LAN_IP>:<BACKEND_PORT>`, không dùng `localhost` hoặc hard-code IP.
3. A chốt G03 rồi triển khai ESP32/sensor/relay với boot-OFF, local timeout, clock sync và reconnect safety.
4. C tiếp tục React mobile-first, Manual/Auto UX khi backend/device hỗ trợ, rồi camera/CV/AI theo dependency.
5. Auth/WebSocket chỉ triển khai khi scope/need được chốt; không coi là điều kiện của M1 hoặc M1.5 nếu chưa nằm trong scope.

## Nhật ký quyết định

- 2026-09-13: chốt local mobile demo bằng browser qua LAN; public Internet optional.
- 2026-09-26: ghi regression backend/simulator của PR #2; thời điểm đó PR chưa merge.
- 2026-09-29: audit lại `main`: PR #2/#3 đã merge; frontend telemetry/control đã tồn tại và pass test/build.
- 2026-09-29: chốt hướng mobile mới là **ReactJS production build + Capacitor + Android APK**, dùng chung frontend; React Native không được chọn. Thêm workstream Android sớm vào lịch, không viết lại lịch sử như thể đã có từ đầu.
- 2026-09-29: A/B/C chính thức chốt G02 là **AGREED** và nghiệm thu **M1 Web/LAN DONE** trên browser điện thoại; Android packaging được tách thành **M1.5 — TODO/NEXT**.
