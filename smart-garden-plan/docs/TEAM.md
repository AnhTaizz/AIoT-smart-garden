# Phân công nhóm 3 người

## Điền thông tin trước khi bắt đầu

| Vai trò | Họ tên | GitHub username | Thời gian cam kết/tuần |
| --- | --- | --- | --- |
| A — Thiết bị và firmware | Chưa điền | Chưa điền | Dự kiến 10–12 giờ |
| B — Backend và dữ liệu | Chưa điền | Chưa điền | Dự kiến 10–12 giờ |
| C — Frontend và AI | Chưa điền | Chưa điền | Dự kiến 10–12 giờ |

Người điều phối: chưa chọn. Ngày bắt đầu tuần 1: chưa chốt. Hạn bảo vệ: chưa chốt. Tài có thể nhận B nếu nhóm thống nhất; đây chưa phải phân công theo tên được xác nhận.

## Trách nhiệm chính

| Người | Sở hữu kỹ thuật | Bàn giao cuối kỳ | Người kiểm tra mặc định |
| --- | --- | --- | --- |
| A | Simulator, ESP32, cảm biến, relay/bơm, logic tưới cục bộ, camera | Firmware, sơ đồ nối dây, hiệu chuẩn, log và kiểm thử thiết bị | B |
| B | Mosquitto, FastAPI, PostgreSQL, telemetry, command, API, triển khai dịch vụ AI | Backend, schema, hướng dẫn khởi động, log truyền dữ liệu và lệnh | C; phối hợp A cho giao tiếp thiết bị |
| C | Dashboard React, dữ liệu/nhãn ảnh, huấn luyện và đánh giá ML | Frontend, pipeline ML, bảng đánh giá và kết quả ảnh trên UI | B; phối hợp A cho dữ liệu camera |

Mỗi người viết và trình bày phần mình thực hiện. Người điều phối tổng hợp tiến độ, điều chỉnh ưu tiên và thống nhất tài liệu; không làm thay báo cáo của cả nhóm.

## Phối hợp theo phase

- Tuần 1: A tạo simulator, B dựng dịch vụ, C dựng UI; cả ba chốt giao tiếp trong G02.
- Tuần 2–3: A có nhiều việc phần cứng. B hỗ trợ log và phiên tích hợp; C ghi nhận demo và chuẩn bị dữ liệu ảnh. Không để A tự kiểm tra toàn bộ mạch.
- Tuần 4: C tập trung mô hình và đánh giá. A phụ trách ảnh thực, vùng chụp và baseline HSV; B xây API ảnh và hỗ trợ khung hiển thị ảnh trên React theo thống nhất với C.
- Tuần 5: B đóng gói inference; C tập trung đánh giá và tích hợp UI; A thử camera trong điều kiện thực và hỗ trợ bộ ảnh kiểm thử.
- Tuần 6–7: mỗi người kiểm thử phần mình sở hữu, kiểm tra chéo và diễn tập luồng chung.

## Quyền quyết định và ranh giới

- A quyết định chi tiết firmware trong giao tiếp đã chốt. ESP32 sở hữu trạng thái tưới, giới hạn thời gian và hành vi khi lỗi.
- B quyết định triển khai backend trong giao tiếp đã chốt. Backend không chạy thêm một bộ logic tự tưới độc lập gây xung đột với ESP32.
- C quyết định UI và cách huấn luyện trong phạm vi nhãn/dataset đã thống nhất. AI cung cấp thông tin/cảnh báo, chưa điều khiển bơm trực tiếp.
- Đổi MQTT schema/API phải có người gửi và người nhận cùng kiểm tra; cập nhật INTERFACES trước hoặc cùng PR.
- Đổi phạm vi, deadline hay tiêu chí nghiệm thu: cả nhóm chốt và ghi PROJECT_STATE. Thay đổi cam kết với thầy cần cập nhật với thầy.

## Cân đối sức làm

Mỗi người có 2 task chính/tuần, tổng 6–8 giờ ước lượng. Phần còn lại trong 10–12 giờ dành review, tích hợp, học bổ sung và xử lý lỗi. Đây là ước lượng ban đầu; kiểm tra lại sau tuần 1. Nếu một task vượt 4 giờ, tách thành các issue nhỏ hơn, giữ mã task cha.

Vướng quá một buổi: báo nguyên nhân, cách đã thử, người cần hỗ trợ. Người điều phối chuyển hỗ trợ trước khi dời milestone. Mọi thay đổi owner phải được cả người giao và người nhận xác nhận trên task.
