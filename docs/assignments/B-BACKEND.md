# Tài — Backend, integration và mobile packaging

Phụ trách: **Tài** (B). GitHub username: điền trong [TEAM](../TEAM.md). Reviewer mặc định: **Toản** (C); phối hợp **Thành** (A) cho giao tiếp thiết bị. Ngoài 14 task backend ban đầu, B sở hữu workstream mới Capacitor/Android ở cuối file. Task giữ `[ ] TODO` nếu bên dưới không ghi trạng thái/bằng chứng khác.

Đọc [ROADMAP](../ROADMAP.md), [INTERFACES](../INTERFACES.md) và [WORKFLOW](../WORKFLOW.md) trước khi bắt đầu. Các mã phụ thuộc thuộc file của Thành, Tài, Toản (A/B/C) tương ứng. Mã M là milestone chung, G là task chung. Có thể làm khung với mock trước; nghiệm thu tích hợp phải dùng đầu ra thật của dependency.

Trước khi có GitHub Issues, cập nhật trạng thái trong từng task dưới đây. Sau khi tạo Issues, điền link vào task và dùng Issue/Project làm nguồn trạng thái; file này giữ phạm vi và tiêu chí, tránh cập nhật hai bảng trạng thái song song.

## Tuần 1 — M1

Mục tiêu chung: backend nối đủ MQTT subscriber → PostgreSQL → REST API và FastAPI → MQTT command → ACK/state với trạng thái vòng đời rõ ràng.

### B-W1-01 — Nhận và lưu telemetry từ MQTT

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** G02, A-W1-01; broker/PostgreSQL bootstrap đã có.
- **Đầu ra:** Backend MQTT subscriber; migration/bảng telemetry; validate và lưu PostgreSQL.
- **Tiêu chí nghiệm thu:** Ít nhất 10 telemetry hợp lệ từ simulator được lưu và truy vấn lại đúng `device_id`/sequence; JSON lỗi không làm dừng subscriber và không được lưu như dữ liệu hợp lệ.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** `[x] DONE` cho implementation/test; G02 đã AGREED.
- **Issue / PR / bằng chứng:** PR #2 đã merge vào `main`. Audit 2026-09-29: full backend suite 84/84 pass, gồm telemetry hợp lệ lưu/truy vấn, payload lỗi bị từ chối và subscriber tiếp tục. Cách chạy: [backend README](../../backend/README.md); lịch sử: [PR2 test handoff](../PR2_TEST_HANDOFF_2026-09-26.md).

### B-W1-02 — REST telemetry và vòng đời command

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W1-01, A-W1-02, G02.
- **Đầu ra:** Latest/history API đọc PostgreSQL; API tạo/theo dõi command; MQTT publish control và consume ACK/state.
- **Tiêu chí nghiệm thu:** Latest/history trả telemetry đã lưu; command có `command_id`; backend phân biệt `pending`, `applied`, `rejected`, `timeout`; HTTP 2xx tạo command không được coi là thiết bị đã áp dụng.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** `[x] DONE` cho backend software contract và M1 Web/LAN; tích hợp ESP32 thật thuộc M2.
- **Issue / PR / bằng chứng:** PR #2 đã merge. Audit 2026-09-29: backend full suite 84/84 pass, gồm deadline race, ACK order, boot binding, persistence và evidence ACK+state. Xem [bản ghi kiểm thử và bàn giao](../PR2_TEST_HANDOFF_2026-09-26.md). Nhóm đã nghiệm thu M1 qua React trên browser điện thoại; chưa kiểm tra ESP32 thật.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## M1.5 — Android Packaging & Mobile Integration

**Trạng thái milestone: `[ ] TODO / NEXT`.** Workstream này được thêm ngày 2026-09-29 sau quyết định dùng **ReactJS + Capacitor**, không phải React Native. B chịu trách nhiệm toolchain/packaging/integration; C tiếp tục sở hữu React UI. Checklist đầy đủ và thứ tự nằm trong [ROADMAP](../ROADMAP.md#m15-android-packaging).

### B-MOB-01 — Environment và Android skeleton (ưu tiên tuần 1–2)

- **Đầu ra:** Capacitor config, Android platform/Gradle wrapper, hướng dẫn Android Studio/SDK/adb/JDK.
- **Tiêu chí nghiệm thu:** `npm` build React pass; Capacitor sync pass; Android project mở/build được; không chứa secret hoặc IP laptop hard-code.
- **Trạng thái:** `[~] IN PROGRESS` ở mức audit môi trường: Node/npm và React build đã verify; JDK 21 được tìm thấy nhưng compatibility chưa verify; Android Studio/SDK/adb và Android project chưa có.

### B-MOB-02 — Physical phone + backend integration (ưu tiên tuần 2–3)

- **Đầu ra:** Test build cài trên điện thoại Android thật; cấu hình REST/WebSocket base URL; log LAN integration.
- **Tiêu chí nghiệm thu:** App mở được, gọi FastAPI trên laptop qua `http://<LAPTOP_LAN_IP>:<BACKEND_PORT>`, thực hiện REST; khi có WebSocket/auth thì kiểm tra tương ứng. `localhost` trên điện thoại không được dùng làm laptop backend.
- **Trạng thái:** `[ ] TODO`.

### B-MOB-03 — Control flow và APK (ưu tiên tuần 4–7)

- **Đầu ra:** Android app hiển thị telemetry/state và command result; app name/icon/splash nếu cần; debug APK và release APK khi sẵn sàng.
- **Tiêu chí nghiệm thu:** Pump intent đi `React/Capacitor → FastAPI → MQTT → simulator` qua Docker/LAN cho M1.5, UI chỉ báo Applied sau ACK+state; final demo pass trên điện thoại thật. Khi ESP32 M2 sẵn sàng, chạy lại cùng contract với thiết bị thật. Cleartext chỉ giới hạn cho DEV, production hướng tới HTTPS/WSS; signing secret không commit.
- **Trạng thái:** `[ ] TODO`.

## Tuần 2 — M2

Mục tiêu chung: ESP32 thật + sensor + relay/bơm; điện thoại điều khiển bơm qua laptop.

### B-W2-01 — Chuẩn hóa dữ liệu và trạng thái thiết bị

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W1-01, A-W2-01.
- **Đầu ra:** Schema/migration; thời điểm nhận; xử lý dữ liệu lỗi.
- **Tiêu chí nghiệm thu:** Phân biệt sensor lỗi với giá trị 0; nhận dữ liệu thật; có last_seen và quy tắc stale; không đếm lặp telemetry nếu đã chốt khử trùng.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** `[~] IN PROGRESS` — schema, sensor error/null, receive time, stale và dedup đã có/test; dữ liệu ESP32 thật chưa có.
- **Issue / PR / bằng chứng:** `backend/app/migrations/`, `backend/app/schemas.py`, `backend/app/repository.py`; backend 84/84 pass ngày 2026-09-29.

### B-W2-02 — Hoàn thiện vòng đời command và tích hợp thật

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W1-02, G02.
- **Đầu ra:** `command_id`, `expires_at` tuyệt đối, `target_boot_id`, ACK/state evidence và lịch sử.
- **Tiêu chí nghiệm thu:** Timeout không tự ghi thành công; xử lý ack trễ; không replay lệnh bật đã hết hạn; Thành (A) dùng được contract với thiết bị thật.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** `[~] IN PROGRESS` — lifecycle/late evidence/replay protection đã có với simulator và G02 đã AGREED; thiếu tích hợp ESP32 thật.
- **Issue / PR / bằng chứng:** Backend E2E 33/33 trong tổng 84 tests; simulator 31/31 ngày 2026-09-29.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 3 — M3

Mục tiêu chung: Manual/Auto, safety, reconnect và error handling.

### B-W3-01 — API mode/cấu hình và nhật ký tưới

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W2-02, A-W3-01.
- **Đầu ra:** Cấu hình được kiểm tra; lịch sử lý do tưới.
- **Tiêu chí nghiệm thu:** ESP32 xác nhận cấu hình đã áp dụng; UI phân biệt requested/applied; backend không tự điều khiển tưới song song.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### B-W3-02 — Kiểm tra phục hồi và hỗ trợ MVP

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W3-01, C-W3-01.
- **Đầu ra:** Kịch bản restart/mất mạng và log tích hợp.
- **Tiêu chí nghiệm thu:** M3 được chạy cùng Thành (A) và Toản (C); bản tin lỗi không chặn hệ thống; cập nhật mô hình DB và tài liệu API.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 4 — M4

Mục tiêu chung: ESP32-CAM → backend → xử lý ảnh; AI baseline có đánh giá ban đầu.

### B-W4-01 — API nhận/lưu ảnh và danh sách ảnh

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W2-01, G02.
- **Đầu ra:** Image endpoint, metadata và trạng thái xử lý.
- **Tiêu chí nghiệm thu:** Kiểm tra file/kích thước theo cấu hình; ảnh lỗi không làm dừng dịch vụ; Thành (A) upload được và Toản (C) đọc danh sách.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### B-W4-02 — Hỗ trợ giao diện ảnh và giao tiếp inference

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W4-01, C-W3-02.
- **Đầu ra:** Khung UI ảnh theo thiết kế C; giao tiếp model.
- **Tiêu chí nghiệm thu:** Toản (C) review khung UI; chốt input/output, nhãn, version và lỗi inference; chạy được mock trước khi có model.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 5 — M5

Mục tiêu chung: Full integration IoT, mobile dashboard, camera và AI.

### B-W5-01 — Đóng gói và tích hợp model baseline

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W4-01, B-W4-02.
- **Đầu ra:** Module/service inference; cấu hình model; kết quả trong DB.
- **Tiêu chí nghiệm thu:** Dùng artifact Toản (C) bàn giao; lưu version; timeout/lỗi được ghi; yêu cầu ảnh không chặn API điều khiển trong kịch bản thử.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### B-W5-02 — Ổn định dịch vụ và cấu hình triển khai

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W5-01, C-W5-01.
- **Đầu ra:** Hướng dẫn chạy chung; log; quyền truy cập cơ bản.
- **Tiêu chí nghiệm thu:** Khởi động được hệ thống chung; không commit secret; có tài khoản/cấu hình mẫu; Toản (C) nhận kết quả ảnh và lịch sử.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 6 — M6

Mục tiêu chung: Testing/hardening; public Internet deployment chỉ optional nếu core đã ổn định.

### B-W6-01 — Đo truyền dữ liệu và độ trễ lệnh

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W5-02.
- **Đầu ra:** Bảng gửi/nhận; command latency; log kiểm thử.
- **Tiêu chí nghiệm thu:** Có số mẫu, điều kiện mạng, cách đo; tách thời gian backend gửi→ack khỏi độ trễ toàn hành trình; ghi lỗi/timeout.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### B-W6-02 — Kiểm tra phục hồi và hoàn thiện báo cáo của Tài (B)

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W6-01.
- **Đầu ra:** Kết quả restart broker/backend; hướng dẫn chạy; phần báo cáo.
- **Tiêu chí nghiệm thu:** Có bằng chứng phục hồi và khoảng dữ liệu thiếu nếu có; không tự ghi không mất dữ liệu khi chưa đo.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 7 — M7

Mục tiêu chung: Local mobile demo + repo + báo cáo + slide + video.

### B-W7-01 — Kiểm tra khởi động từ đầu và chốt cấu hình

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W6-02.
- **Đầu ra:** README chạy app thật, mẫu env và phiên bản phụ thuộc.
- **Tiêu chí nghiệm thu:** Một người khác chạy được từ hướng dẫn; vị trí model/dữ liệu rõ; mã nguồn ứng dụng được commit theo quy trình.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### B-W7-02 — Đóng gói bản bàn giao và diễn tập

- **Owner:** Tài. **Reviewer:** Toản. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** B-W7-01, M6.
- **Đầu ra:** Phiên bản release dự kiến; tài liệu của Tài (B); demo chung.
- **Tiêu chí nghiệm thu:** Hai lượt diễn tập; xác định commit dùng demo; liên kết artifact có thật; cập nhật PROJECT_STATE theo kết quả.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).
