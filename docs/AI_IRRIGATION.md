# Điều phối tưới AI — ESP32 thật và simulator

Backend tự đánh giá theo chu kỳ, không cần mở chat: đọc telemetry/state và lịch sử → gọi AI → validate quyết định JSON → kiểm tra điều kiện → dự trù ngân sách → gửi command MQTT → theo dõi ACK/state.

**ESP32 thật được cấp quyền theo device ID.** Đặt `IRRIGATION_REAL_DEVICE_IDS=node_01`
trong cấu hình server và dùng MQTT riêng có tài khoản/mật khẩu. Mẫu `.env.example`
đã trỏ `node_01` tới ESP32 thật; nếu không cấu hình biến này, backend mặc định vẫn
khóa AUTO cho thiết bị thật. ID đã được cấp quyền thật sẽ từ chối dữ liệu simulator
cùng ID. Xem [quy trình chuyển sang ESP32 thật](ESP32_REAL_SETUP.md).

[Firmware Arduino IDE](../firmware/README.md) vẫn OFF/dry-run mặc định. AUTO là chế độ
điều phối backend; thiết bị báo mode MANUAL và giữ timer cục bộ. Thiết bị có AUTO
riêng bị chặn để tránh hai bộ quyết định cạnh tranh. Hỗ trợ trong source chưa phải
nghiệm thu tích hợp trên board thật, hiệu chuẩn cảm biến hoặc lưu lượng bơm.

## Cách dùng

1. Với ESP32 thật, làm theo [hướng dẫn riêng](ESP32_REAL_SETUP.md), dùng broker riêng
   có xác thực; không dùng cấu hình broker anonymous để tưới thật.
2. Với simulator, chọn ID riêng không nằm trong `IRRIGATION_REAL_DEVICE_IDS`, ví dụ
   `sim_01`; không chạy simulator cùng ID với ESP32 thật. Base Compose chỉ dành cho
   development; build và khởi động stack khi sẵn sàng để áp dụng migration.
3. Điền bảng **Điều phối tưới AI** trên dashboard: cây, giai đoạn, giá thể, giới hạn ẩm ngừng tưới, nhịp tưới tối đa, thời gian nghỉ, ngân sách AUTO/24 giờ và chu kỳ đánh giá.
4. Ví dụ chỉ cho phần mềm mô phỏng: ghi cây/giai đoạn/giá thể là mô phỏng; ngừng từ 80%, nhịp 2 giây, nghỉ 300 giây, ngân sách 10 giây/24h, đánh giá mỗi 60 giây. Đây không phải cấu hình khuyến nghị cho cây thật.
5. Phạm vi thiết bị do server xác nhận. Với ESP32 thật, giao diện yêu cầu xác nhận
   đã hiệu chuẩn/kiểm tra OFF và đang giám sát trước khi bật AUTO. Dùng MANUAL/STOP
   để hủy điều phối và yêu cầu dừng; không cần xác nhận bật để gửi STOP.

## Quy tắc

- AI phải trả `{"water":true,"duration_seconds":1,"reason":"Lý do"}` hoặc `{"water":false,"duration_seconds":0,"reason":"Lý do"}`. Không chuyển lời văn tư vấn của model thành lệnh; không có thuật toán thay AI khi model lỗi (lỗi vẫn tắt AUTO).
- Prompt `irrigation-decision-v4`: cuối lượt user là một dòng sự thật tất định do server tạo ("Độ ẩm đất hiện tại X%, thấp hơn/không thấp hơn ngưỡng ngừng tưới Y%; max_pulse_seconds=N.") và schema JSON **không có lý do mẫu**. v3 có ví dụ `"reason":"Đất đủ ẩm"` và model Qwen chép nguyên ví dụ đó nên lượt nào cũng `no_water`. Probe model thật 2026-11-01: 30,8% và 26% → tưới, 36% → không tưới; model thường chọn đúng `max_pulse_seconds`, nên đặt nhịp tối đa nhỏ khi demo.
- **Luật ngưỡng** (tùy chọn, `policy.force_water_below_pct`, phải ≤ `moisture_stop_pct`; để trống/`null` là tắt): khi độ ẩm đất **dưới** ngưỡng này, server đề xuất tưới `min(10, max_pulse_seconds)` giây **không gọi AI**. Quyết định ghi `observation.decision_source = "rule"`, lý do bắt đầu bằng `Luật ngưỡng:` và dashboard hiển thị nhãn "Luật ngưỡng", không trình bày như AI quyết định. Mọi kiểm tra phía sau (lease, dữ liệu mới, boot, lệnh trước, nghỉ, ngân sách, nhịp tối đa, ACK/state) giống hệt nhánh AI. Ngưỡng cụ thể do người vận hành đặt, không phải khuyến nghị nông học.
- Chỉ chạy khi cảm biến OK, dữ liệu mới, clock đồng bộ, boot khớp và relay OFF. Kiểm tra lại sau khi AI trả lời; số đo AI dùng đã hết hạn thì bỏ quyết định.
- Với ESP32 thật: đúng ID được cấp quyền, số đo `simulated:false`, state cùng device ID,
  cấu hình credential MQTT và thời gian `measured_at`/`reported_at` hợp lệ, cách giờ
  server không quá ngưỡng stale. NaN/Infinity/giá trị ngoài miền đều chặn. Dữ liệu
  đổi sang simulator hoặc lỗi cảm biến trong lúc chờ AI không được phát ON.
- Giới hạn ẩm là quyền phủ quyết. Nghỉ tối thiểu 300 giây, nhịp tối đa 60 giây và chịu thêm giới hạn command/thiết bị, ngân sách AUTO tối đa 600 giây trong cửa sổ 24 giờ.
- Dự trù thời lượng và mốc nghỉ được commit trước publish; lỗi gửi vẫn tiêu ngân sách, không tự phát lại ON. Lệnh pending/timeout/rejected chặn lần tiếp; lỗi AI/API/thực thi tắt AUTO.
- Lệnh tay ON/OFF đều tắt AUTO và tăng revision. MANUAL từ bảng cấu hình cũng gửi STOP. Không suy ra bơm đã dừng chỉ từ HTTP; phải đọc ACK/state. Nếu MQTT down, việc dừng phụ thuộc giới hạn thiết bị.
- Backend restart yêu cầu bật AUTO lại. Khóa thiết bị tuần tự hóa thao tác tay và AUTO; lease DB chống hai worker đánh giá/gửi cùng lượt. Khởi động worker mới có thể hủy AUTO đang chạy; demo dùng một backend worker.
- Model trong `/chat` chỉ tư vấn. Lệnh rõ ràng "bật bơm N giây"/"tắt bơm" trong chat được parser tất định chuyển thành lệnh tay (chỉ `operator`, cùng đường nút bấm, tắt AUTO); xem [CHATBOT](CHATBOT.md#lệnh-bơm-trong-chat). Chưa coi checkpoint Kaggle là đạt chất lượng tưới chỉ vì HTTP 200.
- Dự báo thời tiết (W3; schema `GET /weather` AGREED 2026-11-01, cách dùng trong AUTO vẫn thử nghiệm): observation gửi model có thêm `weather`. Khi dự báo Open-Meteo **fresh** là tóm tắt mưa 6 giờ tới (`kind: "forecast"`, xác suất cao nhất theo giờ, tổng mm, khung giờ, `fetched_at`); ngược lại chỉ `{status, reason}`. Prompt v2 yêu cầu model coi đây là dự báo tham khảo, chỉ dùng để cân nhắc **không tưới/hoãn** khi sắp mưa, không bao giờ dùng để tưới hoặc tưới lâu hơn. Đây là chỉ dẫn mềm cho model: các chặn phía server (soil, stale, boot, relay, nghỉ, ngân sách, ACK) **không đọc** weather và không đổi; weather tắt/lỗi không chặn đánh giá. Ngưỡng "mưa đáng kể" chưa được nhóm chốt nên không có quy tắc cứng; chưa thử với Qwen thật trên simulator.

## API và dữ liệu

Từ bản tích hợp BC-02, `GET` cần phiên đăng nhập và `PUT` cần role `operator` (anonymous `401`, viewer `403`); dashboard gửi Bearer token qua `apiFetch`. Bật AUTO khi chưa cấu hình `CHAT_API_URL` trả `503 chat_unavailable` (`reason: not_configured`).
`GET /devices/{id}/irrigation` trả profile và 20 quyết định gần nhất, gồm command status/ACK/relay xác nhận và `decision_source` (`rule`, `ai`, hoặc `null` với bản ghi trước v4 = AI).
Trường `execution_scope` hiện có thêm giá trị `real_device` khi ID nằm trong cấu hình
thiết bị thật; còn lại là `simulator_only`. Đây là mở rộng enum của response REST;
frontend đã cập nhật tương ứng và không cho bật nếu phạm vi chưa được xác nhận.
`PUT` giữ nguyên body `{enabled, policy}`; `policy` có thêm trường tùy chọn `force_water_below_pct` (cộng thêm, policy cũ vẫn hợp lệ). Không thêm trường MQTT hoặc bảng DB.
Tắt lưu chế độ trước rồi yêu cầu STOP.

Migration `004_irrigation.sql` thêm profile/lease và nhật ký quyết định. Số `004` trùng với `004_auth_sessions.sql` của BC-02; runner lưu theo tên file nên cả hai đều chạy (thứ tự tên: auth trước, irrigation sau, không phụ thuộc nhau). Không đổi tên file đã chia sẻ; migration mới tiếp theo dùng `005_`. Nhật ký lưu snapshot, policy, prompt version, phản hồi model tối đa 4.000 ký tự, đề xuất, lý do chặn, ngân sách và command ID. `sent` không có nghĩa `applied`; ACK cũng không chứng minh có nước chảy. Ngân sách chỉ tính AUTO; ON bằng tay vẫn cập nhật mốc nghỉ nếu đã có profile.

MQTT command/ACK/state, GPIO và migration hiện có được giữ nguyên. Thông số cây,
hiệu chuẩn probe và lưu lượng bơm thật phải được người vận hành đo/kiểm tra trước
khi bật AUTO. Không tự điền ngưỡng nông học hay coi preset simulator là khuyến nghị.

## Kiểm thử

Bản tích hợp `integration/smart-garden-unified-20261101` (2026-11-01): backend unit + E2E 239 pass, 2 skip (live Kaggle); gồm 8 ca supervisor và các ca mới anonymous 401 / viewer 403 / AUTO không có `CHAT_API_URL` → 503. Số liệu dưới đây là của PR #9 trên `main` trước BC-02.

Bản mở hỗ trợ ESP32 thật được kiểm tra bằng test trong process với dữ liệu và AI,
storage, command I/O giả lập có kiểm soát; không gửi MQTT hoặc cấp điện bơm thật.
Bao gồm kiểm tra nguồn dữ liệu đổi khi chờ AI, sensor lỗi, reboot, STOP trong khi
chờ AI, AI JSON sai, thời lượng vượt giới hạn và credential MQTT bị bỏ.
E2E Docker/board thật chưa chạy trong phiên này vì Docker Engine không hoạt động.
Kết quả simulator dưới đây là bằng chứng lịch sử của bản trước.

Kết quả 2026-11-01: backend unit 109/109, frontend 20/20 và build thành công; E2E 41/41 với PostgreSQL/MQTT thật (33 ca cũ và 8 ca supervisor). Ca AUTO xác nhận ON → ACK/state, không tưới, JSON sai, cooldown, vượt giới hạn, STOP trong lúc chờ AI, timeout lệnh và lease hết hạn. Model trong các ca supervisor là giả lập có kiểm soát. Kiểm tra trực tiếp API Kaggle hiện nhận lỗi HTTP; chưa xác minh quyết định từ Qwen thật ở phiên này. AUTO vẫn tắt mặc định.

Từ `backend/`: `python -m pytest -q tests/test_irrigation.py tests/test_chat.py tests/test_validation.py`.

Từ root, khi Compose đang chạy: `python backend/tests/run_e2e.py -k supervisor`. Các ca supervisor dùng phản hồi AI giả định có nhãn rõ, với PostgreSQL/MQTT/ACK thật; đây là kiểm thử luồng, không phải metric Qwen hay nghiệm thu bơm thật. Nếu Kaggle không trả JSON hợp lệ, hệ thống không gửi ON và tắt AUTO; cần sửa/đánh giá inference rồi chủ động bật lại.
