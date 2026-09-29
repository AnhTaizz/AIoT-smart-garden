# Phân công nhóm 3 người

## Điền thông tin trước khi bắt đầu

| Vai trò | Họ tên | GitHub username | Thời gian cam kết/tuần |
| --- | --- | --- | --- |
| A — Thiết bị và firmware (Embedded) | Thành | Chưa điền | Dự kiến 10–12 giờ |
| B — Backend, integration và mobile packaging | Tài | Chưa điền | Dự kiến 10–12 giờ |
| C — Frontend và AI (Frontend-AI) | Toản | Chưa điền | Dự kiến 10–12 giờ |

Người điều phối: chưa chọn. Ngày bắt đầu tuần 1: chưa chốt. Hạn bảo vệ: chưa chốt. Đã xác nhận phân công vai trò: Thành phụ trách A (Embedded), Tài phụ trách B (Backend), Toản phụ trách C (Frontend-AI).

## Trách nhiệm chính

| Người | Sở hữu kỹ thuật | Bàn giao cuối kỳ | Người kiểm tra mặc định |
| --- | --- | --- | --- |
| Thành (A) | ESP32, sensor, relay/bơm, firmware, MQTT device, reconnect/watchdog/fail-safe, Manual/Auto cục bộ, calibration và hardware integration | Firmware, sơ đồ nối dây, hiệu chuẩn, log và kiểm thử thiết bị thật | Tài (B) |
| Tài (B) | Mosquitto, FastAPI, PostgreSQL, telemetry, command/ACK/state, REST/WebSocket, backend security/deployment, API contract; Capacitor, Android toolchain, sync/build và APK | Backend/schema, hướng dẫn chạy, log tích hợp; Android project và APK khi đạt DoD | Toản (C); phối hợp Thành (A) cho giao tiếp thiết bị |
| Toản (C) | ReactJS responsive/mobile-first, dashboard/history/control UX, camera page, dữ liệu/nhãn ảnh, CV/AI và hiển thị kết quả | Một frontend ReactJS dùng cho web và Capacitor; pipeline/đánh giá AI | Tài (B); phối hợp Thành (A) cho dữ liệu camera |

Mỗi người viết và trình bày phần mình thực hiện. Người điều phối tổng hợp tiến độ, điều chỉnh ưu tiên và thống nhất tài liệu; không làm thay báo cáo của cả nhóm.

## Phối hợp theo phase

- Tuần 1: G02 đã AGREED; backend/simulator/React đã merge và M1 Web/LAN đã được nghiệm thu trên browser điện thoại. Tài chuyển sang M1.5 để smoke-test môi trường Capacitor và dựng Android packaging.
- Tuần 2–3: Thành tập trung phần cứng. Tài hỗ trợ log/tích hợp và dựng Capacitor/Android platform; Toản giữ React mobile-first và kiểm tra trên điện thoại thật. Không để Thành tự kiểm tra toàn bộ mạch.
- Tuần 4: Toản tập trung mô hình và đánh giá. Thành phụ trách ảnh thực, vùng chụp và baseline HSV; Tài xây API ảnh và hỗ trợ khung hiển thị ảnh trên React theo thống nhất với Toản.
- Tuần 5: Tài đóng gói inference; Toản tập trung đánh giá và tích hợp UI; Thành thử camera trong điều kiện thực và hỗ trợ bộ ảnh kiểm thử.
- Tuần 6–7: mỗi người kiểm thử phần mình sở hữu, kiểm tra chéo và diễn tập luồng chung.

## Quyền quyết định và ranh giới

- Thành quyết định chi tiết firmware trong giao tiếp đã chốt. ESP32 sở hữu trạng thái tưới, giới hạn thời gian và hành vi khi lỗi.
- Tài quyết định triển khai backend trong giao tiếp đã chốt. Backend không chạy thêm một bộ logic tự tưới độc lập gây xung đột với ESP32.
- Toản quyết định UI và cách huấn luyện trong phạm vi nhãn/dataset đã thống nhất. AI cung cấp thông tin/cảnh báo, chưa điều khiển bơm trực tiếp.
- ReactJS của Toản là codebase frontend duy nhất. Tài đóng gói codebase đó bằng Capacitor và chịu trách nhiệm toolchain/APK; không tạo React Native, Flutter hoặc native Kotlin UI song song.
- Đổi MQTT schema/API phải có người gửi và người nhận cùng kiểm tra; cập nhật INTERFACES trước hoặc cùng PR.
- Đổi phạm vi, deadline hay tiêu chí nghiệm thu: cả nhóm chốt và ghi PROJECT_STATE. Thay đổi cam kết với thầy cần cập nhật với thầy.

## Cân đối sức làm

Mỗi người có 2 task chính/tuần, tổng 6–8 giờ ước lượng. Phần còn lại trong 10–12 giờ dành review, tích hợp, học bổ sung và xử lý lỗi. Đây là ước lượng ban đầu; kiểm tra lại sau tuần 1. Nếu một task vượt 4 giờ, tách thành các issue nhỏ hơn, giữ mã task cha.

Vướng quá một buổi: báo nguyên nhân, cách đã thử, người cần hỗ trợ. Người điều phối chuyển hỗ trợ trước khi dời milestone. Mọi thay đổi owner phải được cả người giao và người nhận xác nhận trên task.
