# AIoT Smart Garden — Project Roadmap

## Trạng thái Cloudflare + Remote Mobile — 2026-10-06

**MANUAL DEVICE TEST — User-confirmed on physical Android device (2026-10-06, Asia/Bangkok).** Người dùng xác nhận APK cài/chạy trên Android thật, tắt Wi-Fi và dùng 4G/5G; telemetry/state, pump ON/OFF, Web/App shared state và ACK + state lifecycle đều PASS. Đây là **USER-CONFIRMED MANUAL TEST**, không phải automated test; không suy ra phone browser 4G, network recovery, iOS hoặc phần cứng ESP32 đã được kiểm thử. iOS architecture/config READY; build/runtime NOT TESTED. Regression và kết luận đóng phase: [REMOTE_MOBILE_REPORT](REMOTE_MOBILE_REPORT_2026-10-06.md). Firmware/hardware, camera/AI và production deployment còn mở.

**Các mục snapshot, milestone và priority ngày 2026-09-30 bên dưới được giữ như lịch sử; các nhãn Android BLOCKED và hướng phone LAN đã được thay thế bởi evidence/config remote ở trên.** User access hiện hành dùng Cloudflare HTTPS; ESP32 → Mosquitto LAN vẫn hợp lệ.

> Quyết định user ngày 2026-10-06: demo chính qua **Cloudflare Quick Tunnel**; Web/mobile browser dùng Internet, Capacitor Android/iOS gọi HTTPS FastAPI trực tiếp. Giữ MQTT LAN cho ESP32. Giữ React + Capacitor, không tạo Expo. Xem [hướng dẫn remote](REMOTE_DEMO.md) và [báo cáo kiểm chứng](REMOTE_MOBILE_REPORT_2026-10-06.md). Các nghiệm thu M1 LAN/M1.5A phía dưới là lịch sử; không chứng minh runtime 4G/5G hoặc iOS.


Cập nhật theo implementation M1.5A ngày **2026-09-30**, bắt đầu tại `main` / `e1219cf7afe5f0709897a6b7c619cb03def36d0f`. Đây là source of truth cho trạng thái và kế hoạch hiện hành. Các báo cáo bootstrap/PR có ngày trong tên là bằng chứng lịch sử, không thay thế trạng thái ở file này.

## 1. Quy ước trạng thái

- `[x] DONE`: có implementation/artifact trong repository và đã có kiểm tra phù hợp.
- `[~] IN PROGRESS`: đã có một phần code/design nhưng thiếu verification hoặc điều kiện nghiệm thu.
- `[ ] TODO`: chưa tìm thấy bằng chứng triển khai.
- `[!] BLOCKED`: có phụ thuộc cụ thể đang ngăn công việc tiếp tục.

Không nâng milestone chỉ từ tên branch, tài liệu thiết kế, HTTP `202`, test mock, simulator hoặc một component chạy riêng.

## 2. Current Status

**Overall: IN PROGRESS**

| Workstream | Trạng thái | Bằng chứng hiện có | Còn thiếu để nghiệm thu |
| --- | --- | --- | --- |
| Architecture & control contract | `[x] DONE` | G02 đã được A/B/C chính thức thống nhất; contract được implement trong backend/simulator và có 84 backend + 31 simulator tests pass ngày 2026-09-29 | Việc triển khai contract trên ESP32 thật thuộc M2, không làm G02 trở lại DRAFT |
| Backend core | `[x] DONE` cho phạm vi software M1 | PR #2 đã merge; MQTT ingest, PostgreSQL migrations, latest/history REST, command/ACK/state persistence và validation có trong `backend/` | Auth, WebSocket, API mode/AUTO, image/AI API và real-device integration chưa có |
| Reference simulator | `[x] DONE` | Bốn topic v1; chống replay/trùng; OFF ưu tiên; fail-safe khi mất MQTT; 31/31 unit tests pass | Không thay thế firmware/phần cứng thật |
| Embedded / hardware | `[ ] TODO` | `firmware/` chỉ có README | Firmware ESP32, sensor, relay/bơm, clock sync, reconnect và test phần cứng thật |
| ReactJS web | `[x] DONE` cho MVP M1 | PR #3 đã merge; telemetry/history, device state, pump command lifecycle, responsive CSS; 5/5 tests, production build và M1 browser/LAN E2E đã được nghiệm thu | Mode control, auth, WebSocket và camera/AI thật là phạm vi sau M1 |
| M1.5 — Android Packaging & Mobile Integration | `[!] BLOCKED` | M1.5A PASS: Capacitor 8.5.2, persistent SDK, Android platform, cap sync, Gradle debug build, APK 4.08 MiB; Docker/LAN telemetry PASS từ laptop | Chờ physical phone để install/launch và xác nhận FastAPI LAN, telemetry, command, ACK/state trên app |
| Camera / AI | `[ ] TODO` | `ai/` và camera UI mới là mô tả/placeholder | ESP32-CAM, image API, dataset, baseline, evaluation và UI kết quả |
| End-to-end integration | `[x] DONE` cho M1 Web/LAN | Nhóm đã nghiệm thu React → FastAPI → MQTT/Mosquitto → simulator → ACK/state → React trên browser điện thoại qua LAN | M1.5 Android app và M2+ phần cứng vẫn chưa làm |

### Bằng chứng audit mới nhất

- Git: PR #2 và PR #3 đã có merge commit trên `main`; `HEAD == origin/main == 208bf77` tại thời điểm audit.
- Backend: `python -m pytest -v tests` trong network Compose — **84 passed**, không skip; cảnh báo duy nhất là test container không ghi được pytest cache vào bind mount.
- Simulator: `python -m unittest discover -s tests -v` — **31 passed**.
- Frontend: `npm test` — **5 passed**; `npm run build` — PASS.
- Compose: build/start PASS; PostgreSQL, Mosquitto, backend và frontend đều healthy; `/health` và `/ready` trả trạng thái hợp lệ. Phiên M1.5 ngày 2026-09-30 còn xác minh Nginx `/api` qua IP Wi-Fi runtime, simulator gửi 10 telemetry và latest/history/state đều đọc lại được từ laptop.
- M1 đã được nhóm nghiệm thu trên browser điện thoại qua LAN; debug APK đã build nhưng chưa có bằng chứng **app Android/Capacitor** chạy trên điện thoại thật, ESP32 thật, relay/bơm thật hoặc ESP32-CAM.

## 3. Architecture Decision

Kiến trúc mục tiêu hiện hành:

```text
ESP32 / ESP32-CAM
        |
        | MQTT: telemetry / control / ack / state
        v
Eclipse Mosquitto
        |
        v
FastAPI Backend ---- PostgreSQL
        |
        +---- REST API / WebSocket (WebSocket chưa implement)
                    |
                    +---- ReactJS web (browser)
                    |
                    +---- cùng ReactJS production build
                          -> Capacitor
                          -> Android native container / WebView
                          -> APK
```

Quyết định:

- Dùng **một ReactJS codebase**, responsive/mobile-first, cho browser và Android.
- Android app là ReactJS production build được đóng gói bằng **Capacitor**; không tạo frontend React Native, Flutter hoặc native Kotlin UI riêng.
- React Native là phương án cũ/được cân nhắc, **không phải công nghệ mobile được chọn**.
- Browser và Android app đều gọi FastAPI qua REST/WebSocket; frontend không kết nối MQTT trực tiếp.
- Hiện frontend dùng REST + polling. WebSocket là TODO, không được mô tả là đã có.
- ESP32 sở hữu cuối cùng Manual/Auto, relay, giới hạn bơm, local timeout và fail-safe. Backend validate/lưu/chuyển lệnh và evidence. Frontend gửi intent/hiển thị trạng thái. AI chỉ cảnh báo/phân tích, không sở hữu relay.

### Mobile networking

- Trong app trên điện thoại, `http://localhost:8000` trỏ vào chính điện thoại, **không** trỏ vào FastAPI trên laptop.
- Khi test LAN: điện thoại và laptop ở cùng Wi-Fi/hotspot; với Compose hiện tại app ưu tiên `http://<LAPTOP_LAN_IP>:<FRONTEND_LAN_PORT>/api` qua Nginx proxy. Chỉ dùng cổng FastAPI trực tiếp nếu nó được expose có chủ đích. Không hard-code một IP laptop vào source/docs như giá trị cố định.
- REST base URL hiện hỗ trợ `VITE_API_BASE_URL`. Khi WebSocket được triển khai, thêm cấu hình tương đương như `VITE_WS_BASE_URL` thay vì hard-code.
- Nếu Android chặn cleartext HTTP, chỉ cho phép cleartext trong cấu hình **DEV/local LAN** có phạm vi hẹp. Production hướng tới HTTPS/WSS và không tắt security toàn cục.

## 4. Current Control Contract

Các topic đã được implement và test với simulator:

| Topic | Hướng | QoS | Retained |
| --- | --- | --- | --- |
| `garden/<id>/telemetry` | ESP32/simulator → backend | 0 | không |
| `garden/<id>/control` | backend → ESP32/simulator | 1 | không |
| `garden/<id>/ack` | ESP32/simulator → backend | 1 | không |
| `garden/<id>/state` | ESP32/simulator → backend | 1 | không |

- `[x]` Backend phát lệnh không retained; command có `expires_at` tuyệt đối và `command_sequence` bền qua restart.
- `[x]` `pump_on` cần `target_boot_id`; thiết bị tham chiếu từ chối ON khi `clock_unsynced`, hết hạn, sai boot, cũ/trùng hoặc đang bận.
- `[x]` `pump_off` được ưu tiên và bỏ qua boot/clock/expiry/busy sau khi envelope hợp lệ.
- `[x]` Backend chỉ chốt `applied` khi có ACK `applied` **và** state phù hợp, cùng command/boot, trước deadline; evidence lưu theo command.
- `[x]` Timeout không được hồi sinh bởi ACK/state muộn; reconnect không replay retained ON; simulator giữ memory trong cùng boot để ON trùng không chạy lại.
- `[x]` Simulator tắt relay và hủy timer khi mất MQTT; reconnect phát state `off`.
- `[ ]` Chưa có firmware ESP32 để xác nhận các hành vi trên phần cứng thật. Vì vậy các dòng DONE ở đây chỉ áp dụng cho backend/simulator reference.

Chi tiết payload, validation và REST nằm trong [INTERFACES](INTERFACES.md). G02 hiện là **AGREED** theo xác nhận chính thức của A/B/C ngày 2026-09-29; thay đổi contract sau mốc này phải được thống nhất và cập nhật đồng bộ producer/consumer.

## 5. Phase / Workstreams

### Phase 0 — Architecture & Contract

- `[x]` Chọn Mosquitto → FastAPI → PostgreSQL → ReactJS.
- `[x]` Chọn một ReactJS codebase + Capacitor cho Android; loại React Native khỏi current plan.
- `[x]` G02 MQTT/REST contract đã được A/B/C thống nhất, implement và test.
- `[ ]` Chốt G01: cây trồng, ngày bắt đầu, deadline, người điều phối và phạm vi auth.
- `[ ]` Chốt G03: BOM, GPIO, cực relay, nguồn, ngưỡng và giới hạn bơm thật.

### Phase 1 — Backend Core & Reference Device

- `[x]` MQTT telemetry ingest, validation, rejected-message isolation và dedup.
- `[x]` PostgreSQL persistence/migrations cho telemetry, command, event, state, boot và sequence.
- `[x]` Latest/history REST API.
- `[x]` Command create/get/list và vòng đời `pending/applied/rejected/timeout`.
- `[x]` ACK/state evidence, deadline race, reboot/old-boot và ordering tests.
- `[x]` Simulator hai chiều và fail-safe disconnect/replay regression.
- `[ ]` Auth/backend security nếu nhóm đưa auth vào MVP.
- `[ ]` WebSocket realtime; hiện tại dùng polling.

### Phase 2 — Embedded Integration

- `[ ]` Firmware ESP32 đọc AHT20 và cảm biến ẩm đất; calibration/error reporting.
- `[ ]` MQTT telemetry/control/ACK/state trên ESP32 theo G02.
- `[ ]` Relay/bơm: boot OFF, local maximum duration, watchdog/fail-safe.
- `[ ]` Đồng bộ giờ đáng tin cậy để kiểm tra `expires_at`; khi chưa sync phải reject ON nhưng vẫn cho OFF.
- `[ ]` Manual/Auto, hysteresis/tưới theo nhịp và safety lock trên ESP32.
- `[ ]` Test mất Wi-Fi/MQTT khi đang ON, reconnect và replay ON cũ trên phần cứng thật.

### Phase 3 — ReactJS Frontend

- `[x]` React/TypeScript/Vite production build và test harness.
- `[x]` Dashboard nhiệt độ, ẩm không khí, ẩm đất, pump/device/backend/database status cho MVP M1; code/test và browser/LAN E2E đã nghiệm thu.
- `[x]` History dạng sparkline từ REST history cho MVP M1; browser điện thoại qua LAN đã được nghiệm thu.
- `[x]` Pump ON/OFF và `pending/applied/rejected/timeout` với simulator cho M1; kiểm tra ESP32 thật thuộc M2.
- `[ ]` UI chuyển Manual/Auto; hiện chỉ hiển thị mode do device state báo.
- `[ ]` Login/authentication chỉ thêm nếu G01 xác nhận auth nằm trong scope.
- `[ ]` Camera/AI page thật; hiện chỉ là placeholder “Chưa triển khai”.
- `[ ]` WebSocket realtime; hiện polling 5 giây và command polling 1 giây.
- `[x]` Responsive/mobile browser verification cho M1 trên điện thoại thật qua LAN.
- `[ ]` Accessibility review chuyên biệt ngoài tiêu chí M1 tối thiểu.

<a id="m15-android-packaging"></a>

### Phase 4 / M1.5 — Android Packaging & Mobile Integration

**Trạng thái: `[!] BLOCKED ON PHYSICAL DEVICE TEST`.** M1.5A packaging, SDK persistent và laptop-side Docker/LAN telemetry validation đã PASS; `adb devices -l` vẫn không có thiết bị nên chưa thể nghiệm thu app Android. M1 Web/LAN đã DONE và không phụ thuộc Capacitor. M1.5 có thể nghiệm thu control flow bằng simulator qua Docker/LAN; không phải chờ ESP32 thật của M2.

- `[x]` Verify Node/npm environment — audit: Node `v24.13.0`, npm `11.6.2`.
- `[x]` Verify current ReactJS frontend setup — 5 tests và production build pass.
- `[x]` Install/configure Capacitor 8.5.2 trong frontend hiện tại; `webDir: dist`, app ID `com.aiot.smartgarden`, app name `Smart Garden`.
- `[x]` Add Android platform tại `frontend/android/`.
- `[ ]` Verify Android Studio — không tìm thấy trong audit machine.
- `[x]` Verify Android SDK — command-line SDK persistent tại `%LOCALAPPDATA%\Android\Sdk`, gồm Platform 36 + Build Tools 35.0.0; Gradle Wrapper build PASS. Android Studio vẫn optional/chưa cài.
- `[x]` Verify Platform Tools / `adb` — 37.0.1 chạy được; không có connected device.
- `[x]` Verify compatible JDK — JDK 21.0.8 chạy Gradle build PASS.
- `[x]` Verify Gradle/Android toolchain — AGP 8.13.0 + Gradle Wrapper 8.14.3; không cần system Gradle.
- `[x]` Build a minimal React app successfully — app hiện tại đã production-build thành công, vượt mức smoke test tối thiểu.
- `[x]` Sync React build into Capacitor bằng `npm run android:sync`.
- `[ ]` Open Android project trong Android Studio — IDE chưa cài; không chặn command-line build.
- `[!]` Verify USB debugging / `adb` và cài test build trên **điện thoại Android thật** — không có thiết bị kết nối.
- `[ ]` Verify app can reach FastAPI qua IP LAN/config và Nginx `/api` proxy; laptop-side LAN endpoint đã PASS nhưng chưa có bằng chứng từ app trên điện thoại.
- `[ ]` Verify REST requests.
- `[ ]` Verify WebSocket realtime sau khi backend/frontend có WebSocket.
- `[ ]` Verify authentication nếu auth được đưa vào scope.
- `[ ]` Verify pump control flow từ Android qua backend → MQTT → device.
- `[ ]` Verify command ACK/state hiển thị đúng trên Android.
- `[ ]` Verify telemetry/history, pump state và device/connection status hiển thị đúng trên Android.
- `[~]` Configure app name/icon — app name `Smart Garden` đã có; icon hiện là asset mặc định của generated project.
- `[ ]` Configure splash screen nếu cần.
- `[x]` Generate debug APK — `android/app/build/outputs/apk/debug/app-debug.apk`, 4.08 MiB; artifact được ignore. Build-time LAN URL được sync vào asset nhưng không hard-code vào source/Git.
- `[ ]` Generate release APK khi release configuration/signing đã sẵn sàng; không commit secret/signing key.
- `[ ]` Final demo trên điện thoại thật.

Emulator là optional. Ưu tiên điện thoại thật để tránh tải đồng thời IDE + Docker + backend/database/MQTT + emulator trên máy dev.

### Phase 5 — Camera / AI

- `[ ]` ESP32-CAM capture/upload và metadata.
- `[ ]` Backend image storage/list/latest API.
- `[ ]` Chốt dataset/labels/split và baseline phù hợp.
- `[ ]` Evaluation có metric, model/dataset version và failure examples.
- `[ ]` React/Capacitor hiển thị ảnh gần nhất và AI result/cảnh báo.
- `[ ]` Xác minh inference không chặn telemetry/command; AI không bật relay trực tiếp.

### Phase 6 — End-to-End Integration

- `[x]` Một phiên M1 đầy đủ đã được nhóm nghiệm thu: simulator → MQTT → DB → API → React trên browser điện thoại qua LAN và chiều command quay về ACK/state.
- `[ ]` Một phiên M2 với ESP32/sensor/relay/bơm thật.
- `[ ]` Mất MQTT khi ON, replay cũ, timeout, reboot và STOP được kiểm tra trên thiết bị thật.
- `[ ]` React/Capacitor Android → REST/WebSocket → FastAPI → MQTT → ESP32.
- `[ ]` Camera/AI tích hợp mà không ảnh hưởng control path.

### Phase 7 — Demo / Report / Final Hardening

- `[ ]` Chạy kéo dài có số liệu, test failure/recovery và ghi giới hạn.
- `[ ]` Security/config review; production dùng HTTPS/WSS và broker/API auth nếu deploy ngoài LAN tin cậy.
- `[ ]` Debug/release APK artifact và version được ghi lại.
- `[ ]` README khởi động lại từ máy sạch; slide, report, video và hai lượt diễn tập.

## 6. Kế hoạch 7 tuần đã cập nhật

Tuần là mốc tương đối từ ngày nhóm bắt đầu; chưa có ngày lịch được xác nhận. Capacitor là thay đổi phạm vi được thêm ngày 2026-09-29, không được viết lại như thể đã nằm trong kế hoạch ban đầu.

| Tuần | Trọng tâm | Trạng thái audit | Kế hoạch / điều kiện ra |
| --- | --- | --- | --- |
| 1 | Software M1: backend, simulator, React | `[x]` | G02 AGREED; backend/simulator và React đã merge; M1 Web/LAN E2E trên browser điện thoại đã được nhóm nghiệm thu. |
| 2 | ESP32 thật + Android skeleton | `[~]` | Android skeleton/debug APK đã build; A vẫn cần đưa telemetry/control lên ESP32, B cần cài APK và test LAN trên điện thoại thật, C giữ UI responsive. |
| 3 | Manual/Auto + safety + mobile integration | `[ ]` | A hoàn thiện device state machine/fail-safe; B nối Android tới backend; C thêm mode/control UX. Test disconnect/replay/STOP trên phần cứng. |
| 4 | Camera/AI baseline + Android integration | `[ ]` | Debug APK đã build sớm ở M1.5A; còn cài/mở/gọi REST trên phone, image API, dữ liệu ảnh và camera/AI UI. |
| 5 | Full integration | `[ ]` | React MVP sync vào Capacitor; Android control/ACK-state; camera/AI tích hợp; đóng phạm vi. |
| 6 | Hardening | `[ ]` | Test kéo dài, network failures, dependency/security audit, Android physical-device regression; release APK chỉ khi cấu hình sẵn sàng. |
| 7 | Bàn giao | `[ ]` | Demo trên smartphone/ESP32 thật, README, report, slide, video, artifact/version và phương án hotspot dự phòng. |

Đường găng:

```text
G02/backend contract ổn định
        +--> ReactJS MVP --------------------+
        +--> Capacitor environment smoke test |
                                             v
                                   Capacitor sync/build
                                             |
                                             v
                                  Physical Android test
                                             |
                                             v
                         E2E command + ACK/state + safety
```

## 7. Ownership và công việc tiếp theo của A/B/C

### A — Thành — Embedded / Hardware

- Sở hữu ESP32, sensor, relay/bơm, firmware, MQTT device, reconnect/watchdog/fail-safe, local Manual/Auto, calibration và hardware integration.
- Ưu tiên tiếp theo: chốt G03 → tạo firmware skeleton → sensor/calibration → MQTT v1 → relay boot-OFF/local timeout → test disconnect/replay trên phần cứng thật.
- Không chuyển quyền safety/relay sang backend, frontend hoặc AI.

### B — Tài — Backend + Integration + Mobile Packaging

- Sở hữu Mosquitto/FastAPI/PostgreSQL, telemetry, command/ACK/state, REST/WebSocket, backend security nếu có, Docker/deployment, API contract, Capacitor/Android toolchain, sync/build và APK.
- Ưu tiên tiếp theo: kết nối điện thoại thật → cài debug APK → launch → cấu hình LAN API/CORS tối thiểu → kiểm tra telemetry → control/ACK-state.
- B không mặc định sở hữu toàn bộ UI design; dùng ReactJS do C phát triển.

### C — Toản — Frontend + Camera/AI

- Sở hữu ReactJS responsive/mobile-first, dashboard/history/control UX, camera page, application-side ESP32-CAM integration phù hợp, CV/AI pipeline và hiển thị AI result.
- Ưu tiên tiếp theo: tiếp tục UI responsive/mobile-first → bổ sung Manual/Auto khi backend/device hỗ trợ → phối hợp B kiểm tra cùng React build trong M1.5 → chuẩn bị camera/CV/AI sau core IoT.
- C duy trì một codebase ReactJS để B đóng gói bằng Capacitor; không tạo frontend mobile riêng.

## 8. Definition of Done

- **Code:** implemented; test/lint/build phù hợp pass; không phá contract; PR/merge theo workflow nếu task yêu cầu.
- **Backend endpoint:** chạy được; validation và error contract rõ; có test hợp lý; persistence đúng nếu endpoint liên quan dữ liệu.
- **MQTT integration:** publish/subscribe đúng topic/QoS/retained; failure/reconnect path được test khi liên quan.
- **Frontend:** component/page hoạt động với API; có loading/empty/error tối thiểu; responsive nếu thuộc scope; không suy luận device state từ HTTP request.
- **Android:** production web build + Capacitor sync/build thành công; APK cài/mở được trên điện thoại thật; gọi backend LAN được; control chỉ PASS sau ACK/state.
- **Hardware:** compile không đủ; cần bằng chứng ESP32/sensor/relay/bơm thật và safety test khi hardware có sẵn.
- **Documentation/design:** link/contract nhất quán với implementation; historical decisions được ghi là historical.
- **Milestone:** mọi điều kiện bắt buộc phải được chứng minh trong cùng phiên bản/phiên test; component PASS không tự nâng milestone.

## 9. Findings / TODO chưa được che giấu

- G02 đã AGREED và M1 Web/LAN đã DONE theo xác nhận chính thức của nhóm; hai mục này không còn là blocker.
- `firmware/` và `ai/` chưa có implementation.
- Auth và WebSocket chưa tồn tại; frontend hiện polling REST.
- Capacitor/Android project và debug APK đã có; physical-device install/launch/API/control chưa có bằng chứng vì không có thiết bị `adb`.
- Command-line SDK đã persistent tại `%LOCALAPPDATA%\Android\Sdk`; Android Studio chưa cài nhưng không chặn Gradle Wrapper build. PATH/JAVA_HOME toàn hệ thống không bị thay đổi.
- Sau khi thêm Capacitor, npm báo 6 dependency vulnerabilities (4 moderate, 1 high, 1 critical); cần `npm audit`/triage có kiểm soát, không tự dùng `--force` làm thay đổi dependency ngoài task.
- Broker anonymous chỉ phù hợp development/LAN tin cậy; production/public deployment chưa được harden.
