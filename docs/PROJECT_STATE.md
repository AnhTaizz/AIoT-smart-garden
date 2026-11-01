# Trạng thái dự án

## Trạng thái hợp nhất — 2026-11-01

Nhánh `integration/smart-garden-unified-20261101` gom BC-01, BC-02, W3 (docs), firmware Arduino IDE, phần còn thiếu của PR #4 (G02 AGREED docs, REMOTE_DEMO, iOS) và PR #9 (supervisor tưới AI cho simulator, nay cần đăng nhập). Chi tiết, conflict và việc cần làm: [INTEGRATION_REPORT_2026-11-01](INTEGRATION_REPORT_2026-11-01.md).

- **Kiểm thử bản tích hợp: NOT TESTED** (để sau E2E theo yêu cầu chủ dự án). Số liệu test trong các mục khác là của từng nhánh trước khi hợp nhất.
- **Stack demo đang chạy là bản trước BC-02**: API công khai qua `garden-api.anhtaizz.id.vn` chưa có xác thực. Chưa redeploy vì `.env` chưa có tài khoản operator.
- Domain: `garden` và `garden-api` hoạt động qua Named Tunnel `garden-local`; apex chưa có route; TOEIC trả 502 từ trước, không thuộc phạm vi.
- Kiến trúc Auto **chưa chốt** (ESP32 / server / supervisor PR #9); xem [INTERFACES](INTERFACES.md#ranh-giới-xử-lý). Weather W3 chưa có code.
- Firmware: Arduino IDE dry-run mặc định, chưa nghiệm thu board; nhánh PlatformIO A-W1 chưa hợp nhất.

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
- 2026-10-30: BC-01 trên `feat/bc-01-mobile-chat-integration`: audit lại repo (PR #2/#3/#5 đã merge, PR #4 còn mở), tích hợp phần code Capacitor Android/CORS/API HTTPS của PR #4 vào `main` mới nhất mà giữ chatbot, chặn lệnh bơm qua tunnel/Internet và sửa UI để phân biệt lỗi API/chưa có dữ liệu/state cũ. Backend unit 125/125, E2E thật 38 pass (2 live Kaggle skip), simulator 31/31, frontend 35/35 + build. APK, smartphone thật và Kaggle thật chưa kiểm tra. G02 vẫn DRAFT trên `main`; M1 vẫn chưa nghiệm thu.
- 2026-10-30: BC-01.1 trên cùng nhánh: UI khóa điều khiển khi chưa xác minh được quyền (fail closed), polling single-flight + hủy request cũ, giữ số đo cũ khi lỗi API nhưng gắn nhãn chưa cập nhật, rào chắn remote dùng danh sách mạng local tường minh. Backend unit 129/129, E2E thật 38 pass (2 live Kaggle skip), simulator 31/31, frontend 53/53 + build, phiên UI thật cho online/denied/unknown/pending/applied/rejected/timeout/stale/offline. APK, smartphone thật và Kaggle thật vẫn chưa kiểm tra; M1 vẫn chưa nghiệm thu.
- 2026-10-30: BC-02 trên `feat/bc-02-api-authentication` (stacked trên BC-01 vì PR #6 chưa merge): xác thực operator và phiên Bearer lưu hash trong PostgreSQL, bảo vệ toàn bộ API dữ liệu/lệnh/chat, điều khiển từ xa cho operator đã đăng nhập, rate limit, bỏ URL ngrok mặc định, màn hình đăng nhập Web/Android. Backend unit 156/156, E2E thật 47 pass (2 live Kaggle skip), simulator 31/31, frontend 67/67 + build + mobile bundle + cap sync, phiên trình duyệt thật. APK, điện thoại, tunnel Cloudflare thật và Kaggle thật chưa kiểm tra. G02 vẫn DRAFT; M1 vẫn chưa nghiệm thu.
- 2026-10-30: BC-02.1 trên cùng nhánh PR #7: chặn đăng nhập song song vượt giới hạn/chạy scrypt không giới hạn (ghi nhận trước khi hash, tối đa 2 phép hash đồng thời, `429 login_busy`), đăng xuất chỉ báo "đã thu hồi" khi server xác nhận, thêm test an toàn lệnh. Backend unit 167/167, E2E thật 48 pass (2 live Kaggle skip), simulator 31/31, frontend 73/73 + build + mobile bundle + cap sync. APK, điện thoại, tunnel thật, Kaggle thật chưa kiểm tra. G02 vẫn DRAFT; M1 vẫn chưa nghiệm thu.

> Ghi chú hợp nhất 2026-11-01: các dòng BC-01/BC-02 dưới đây được viết trên base `origin/main` chưa có commit `e1219cf`, nên ghi "G02 vẫn DRAFT; M1 chưa nghiệm thu". Trạng thái đúng theo xác nhận của nhóm là G02 AGREED và M1 Web/LAN DONE từ 2026-09-29; số liệu test trong từng dòng vẫn giữ nguyên như bản ghi lịch sử.

### Thay đổi phạm vi W3 chờ A/C review — 2026-10-31

Chủ dự án yêu cầu tích hợp dự báo thời tiết để hỗ trợ **hoãn tưới Auto** trong M3, không thay kế hoạch 14 task/người. Đã lập tài liệu [W3_WEATHER_LOCAL_EXECUTION_PLAN](W3_WEATHER_LOCAL_EXECUTION_PLAN.md) và cập nhật ROADMAP/assignments A+B+C/INTERFACES ở một Draft PR tài liệu riêng. Đây là **quyết định mở rộng phạm vi do chủ dự án yêu cầu**, nhưng contract A/C vẫn **DRAFT**, chưa có code Weather API, chưa có firmware Auto Weather, chưa có E2E Weather. Không đổi trạng thái G02 hoặc M1–M7.

Thực thi chuyển sang Claude Code trên máy local. Bước đầu tiên bắt buộc là **audit read-only**: git status/branch/HEAD/PR #6/#7, dirty worktree, công cụ Docker/Python/Node/Android SDK/adb và thiết bị; sau đó mới xác minh test baseline. Local tốt hơn về khả năng test APK/thiết bị nhưng **không tự động đồng nghĩa đã test**.

Snapshot GitHub đã kiểm tra 2026-10-31: main `13e1ac0`, PR #6 Draft head `57f78b6`, PR #7 Draft stacked head `1a3db7b`. Theo báo cáo PR #7: 215 backend pass, 2 Kaggle skip; 31 simulator; 73 frontend; build/sync OK. Chưa có chứng cứ APK/điện thoại/Cloudflare tunnel/Kaggle/ESP32 thật ở BC-02.1. Không rebase/merge/force push hoặc cập nhật mốc nghiệm thu khi chưa kiểm tra lại bằng chứng.
- 2026-11-01: hợp nhất các nhánh trên `integration/smart-garden-unified-20261101`, chuẩn hóa domain `anhtaizz.id.vn`, gắn xác thực cho API irrigation của PR #9. Chưa chạy test; không đổi trạng thái milestone.
