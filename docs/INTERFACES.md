# Thỏa thuận giao tiếp — Bản nháp cho G02

Trạng thái: **DRAFT — cả nhóm cần chốt ở G02 trước tích hợp**. Đây là danh sách quyết định để ba mảng làm việc cùng nhau, chưa phải đặc tả kỹ thuật đã triển khai. B chủ trì, A/C cùng kiểm tra. Sau G02 bổ sung payload/API cụ thể và đổi trạng thái thành AGREED kèm ngày và PR.

## Ranh giới xử lý

ESP32 giữ trạng thái tưới, đọc cảm biến, giới hạn chạy bơm và xử lý lỗi cục bộ. Backend kiểm tra yêu cầu, chuyển lệnh, lưu dữ liệu/sự kiện, cung cấp API. Frontend hiển thị trạng thái thiết bị xác nhận. Model chạy trên máy chủ và cung cấp kết quả ảnh; chưa đưa vào vòng điều khiển bơm.

## MQTT đề xuất

| Luồng | Topic dự kiến | Nội dung phải chốt |
| --- | --- | --- |
| Telemetry | garden/node_01/telemetry | device_id, boot_id/sequence nếu khử trùng, thời gian đo, giá trị/đơn vị, sensor_status, mode, relay_state |
| Command | garden/node_01/control | command_id, hành động, tham số, thời hạn; quy tắc kiểm tra tính hợp lệ |
| Xác nhận | garden/node_01/ack | command_id, accepted/rejected/applied, lý do và thời gian |
| Trạng thái | garden/node_01/state | Trạng thái mode/relay/cấu hình thực tế, last_seen hoặc cơ chế online/offline đã chốt |

- Chốt QoS và retained cho từng topic. Không giữ retained lệnh bật bơm để thiết bị chạy lại lệnh cũ khi kết nối.
- Lệnh có ID để nhận biết trùng; nhận lại cùng ID không kéo dài giới hạn chạy. Chốt cửa sổ lưu ID và hành vi qua khởi động lại.
- Chốt cách từ chối lệnh hết hạn và xử lý khi đồng hồ thiết bị chưa đồng bộ. TTL không thay thế giới hạn thời gian chạy cục bộ.
- Backend/UI phân biệt yêu cầu đã gửi, thiết bị chấp nhận và trạng thái được áp dụng. ACK không chứng minh có dòng nước thật.
- Chốt ngưỡng xác định dữ liệu cũ/offline, cách lưu bản tin tới trễ và thứ tự bản tin.

## Dữ liệu và điều khiển

| Nội dung | Quyết định cần điền ở G02 |
| --- | --- |
| Thời gian | Chọn chuẩn UTC, độ chính xác, thời điểm nhận ở server và cách xử lý thời gian đo chưa hợp lệ |
| Đơn vị | Nhiệt độ °C, độ ẩm không khí %, đất là % tương đối sau hiệu chuẩn; giữ ADC phục vụ đánh giá khi cần |
| Sensor lỗi | null/status/error_code theo schema; không tự thay bằng 0 |
| Mode | AUTO/MANUAL, chuyển mode làm gì với bơm đang chạy; STOP ưu tiên ra sao |
| Giới hạn | Thời gian tối đa mỗi nhịp, tổng thời gian/số nhịp, thời gian chờ, điều kiện khóa khi lỗi |
| Cấu hình | Kiểm tra miền giá trị; requested khác applied; trạng thái sau reboot |
| Mực nước | Chỉ thêm nếu nhóm chốt có cảm biến thật; không tạo trường bắt buộc giả |

Ngưỡng tưới và thời lượng là tham số phải kiểm tra trên cây/chậu/bơm thực tế; tài liệu này không gán giá trị mặc định dùng ngay ngoài thực nghiệm.

## API phục vụ frontend — dự kiến

| Nhu cầu | API gợi ý | Điều phải thống nhất |
| --- | --- | --- |
| Dữ liệu mới nhất | GET /devices/{id}/latest | sensor_status, timestamp, stale, mode, relay_state |
| Lịch sử | GET /devices/{id}/telemetry | from/to, giới hạn, thứ tự thời gian |
| Gửi lệnh | POST /devices/{id}/commands | kiểm tra input, command_id, pending; không trả thành công thiết bị ngay |
| Theo dõi lệnh | GET /commands/{command_id} | ack/state, timeout, lỗi, ack tới trễ |
| Cấu hình | GET/PUT /devices/{id}/config | requested/applied; phiên bản cấu hình |
| Upload ảnh | POST /devices/{id}/images | multipart, giới hạn file, metadata và image_id |
| Xem ảnh/kết quả | GET /devices/{id}/images | image_id, captured_at, trạng thái xử lý, model_version, kết quả/lỗi |

Tuần 1 dùng polling đơn giản hoặc cơ chế nhóm quen thuộc; chốt một cách. Chưa cần thêm WebSocket nếu không giải quyết vấn đề thực tế. Phần ảnh được hoàn thiện chi tiết trước tuần 4; thống nhất mã thiết bị và thời gian ngay tuần 1.

## Hợp đồng model — chốt ở tuần 3–4

C bàn giao B: artifact model, preprocessing, danh sách nhãn, inference mẫu, phiên bản dataset/model, dependency, kích thước ảnh và lỗi đầu vào. B trả kết quả gắn image_id và model_version. HSV trả độ phủ xanh riêng; model phân loại trả nhãn/điểm mô hình riêng. Không tự gọi điểm mô hình là xác suất đã hiệu chuẩn.

## Xác nhận

A: chưa xác nhận. B: chưa xác nhận. C: chưa xác nhận. Link PR thống nhất: chưa có.
