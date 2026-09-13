# Người A — Thiết bị và firmware

Họ tên/GitHub username: điền trong [TEAM](../TEAM.md). Task chính: 14. Ước lượng chỉ tính công việc tập trung; review, tích hợp và dự phòng nằm trong phần giờ còn lại mỗi tuần. Tất cả task hiện **Backlog**, chưa có bằng chứng thực hiện.

Đọc [ROADMAP](../ROADMAP.md), [INTERFACES](../INTERFACES.md) và [WORKFLOW](../WORKFLOW.md) trước khi bắt đầu. Các mã phụ thuộc thuộc file của A/B/C tương ứng. Mã M là milestone chung, G là task chung. Có thể làm khung với mock trước; nghiệm thu tích hợp phải dùng đầu ra thật của dependency.

Trước khi có GitHub Issues, cập nhật trạng thái trong từng task dưới đây. Sau khi tạo Issues, điền link vào task và dùng Issue/Project làm nguồn trạng thái; file này giữ phạm vi và tiêu chí, tránh cập nhật hai bảng trạng thái song song.

## Tuần 1 — M1

Mục tiêu chung: Simulator → MQTT → DB → API → React → smartphone LAN và lệnh ngược lại có ACK/state.

### A-W1-01 — Dựng simulator telemetry

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** G02.
- **Đầu ra:** simulator/ và hướng dẫn phát bản tin.
- **Tiêu chí nghiệm thu:** B nhận được 10 bản tin hợp lệ có device_id và sequence; chế độ simulated được ghi rõ.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W1-02 — Simulator nhận command và báo trạng thái

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W1-01, B-W1-01, G02.
- **Đầu ra:** Luồng nhận lệnh, command_id và xác nhận.
- **Tiêu chí nghiệm thu:** Lệnh bật/tắt đổi trạng thái giả; lệnh trùng không khởi động lại bộ đếm; B/C xem được phản hồi.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 2 — M2

Mục tiêu chung: ESP32 thật + sensor + relay/bơm; điện thoại điều khiển bơm qua laptop.

### A-W2-01 — Đọc cảm biến và hiệu chuẩn

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** G03; core hardware đã nhận.
- **Đầu ra:** firmware/; sơ đồ dây; bảng ADC; log lọc.
- **Tiêu chí nghiệm thu:** Đọc AHT20/đất; ghi được lỗi; có tham chiếu khô/ướt và dữ liệu trước/sau lọc; % là thang tương đối.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W2-02 — Tích hợp relay/bơm và MQTT

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W2-01, A-W1-02, B-W2-02.
- **Đầu ra:** Firmware telemetry, command và giới hạn chạy.
- **Tiêu chí nghiệm thu:** Web gửi lệnh tới thiết bị thật; relay đúng cực kích; boot tắt; bơm tự dừng; ghi trạng thái xác nhận.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 3 — M3

Mục tiêu chung: Manual/Auto, safety, reconnect và error handling.

### A-W3-01 — Hoàn thiện logic tưới và lỗi

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W2-02, G02.
- **Đầu ra:** State machine Manual/Auto, hysteresis, tưới theo nhịp.
- **Tiêu chí nghiệm thu:** Thử khô/ẩm, sensor lỗi, mất mạng khi tưới, lệnh trùng, STOP và chuyển mode; giới hạn luôn áp dụng.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W3-02 — Hoàn thiện reconnect và xử lý lỗi thiết bị

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W3-01, A-W2-02, G02.
- **Đầu ra:** Firmware phục hồi Wi-Fi/MQTT; trạng thái offline/reconnect; xử lý sensor/command lỗi.
- **Tiêu chí nghiệm thu:** Thử mất mạng và broker, reconnect không tự bật bơm hoặc chạy lại lệnh cũ; lỗi cảm biến vẫn giữ giới hạn an toàn và được báo rõ.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 4 — M4

Mục tiêu chung: ESP32-CAM → backend → xử lý ảnh; AI baseline có đánh giá ban đầu.

### A-W4-01 — Camera định kỳ và bộ ảnh thực

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W3-02, B-W4-01.
- **Đầu ra:** Lịch chụp, vùng chụp, ảnh gốc có metadata.
- **Tiêu chí nghiệm thu:** Ảnh mới đến backend với timestamp/device_id; thử upload lỗi và phục hồi; giao ảnh cho C.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W4-02 — Baseline độ phủ xanh và hỗ trợ dữ liệu

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W3-02.
- **Đầu ra:** Script HSV; ảnh mask; mô tả giới hạn.
- **Tiêu chí nghiệm thu:** Có ảnh/mask/độ phủ để đối chiếu; thử thay đổi ánh sáng; không gắn độ phủ với chẩn đoán bệnh; giao B/C tích hợp.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 5 — M5

Mục tiêu chung: Full integration IoT, mobile dashboard, camera và AI.

### A-W5-01 — Kiểm tra camera trong hệ thống chung

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W4-01, C-W3-02.
- **Đầu ra:** Log camera và bộ ảnh kiểm thử thực.
- **Tiêu chí nghiệm thu:** Ghi ảnh mờ/tối/lỗi upload; C nhận được bộ ảnh chưa dùng để train/tune; báo thiếu dữ liệu nếu có.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W5-02 — Ổn định thiết bị khi chạy chung

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W3-01, A-W4-01.
- **Đầu ra:** Firmware tích hợp và ghi nhận lỗi đã sửa.
- **Tiêu chí nghiệm thu:** Chụp/gửi ảnh không làm mất giới hạn bơm; ngắt/kết nối lại hoạt động theo thiết kế; cập nhật sơ đồ dây.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 6 — M6

Mục tiêu chung: Testing/hardening; public Internet deployment chỉ optional nếu core đã ổn định.

### A-W6-01 — Thử lỗi và chạy kéo dài có giám sát

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** A-W5-02.
- **Đầu ra:** Biên bản phần cứng theo mẫu review.
- **Tiêu chí nghiệm thu:** Ghi thời lượng/số chu kỳ; thử sensor lỗi, boot, mất mạng lúc tưới; mọi trường hợp bơm dừng theo giới hạn.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W6-02 — Tổng hợp kết quả firmware và lọc

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W6-01, A-W2-01.
- **Đầu ra:** Biểu đồ trước/sau lọc; bảng kiểm thử; phần báo cáo A.
- **Tiêu chí nghiệm thu:** Có điều kiện đo và dữ liệu nguồn; phân tích cả độ trễ lọc và lỗi; không tự tuyên bố tiết kiệm nước.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 7 — M7

Mục tiêu chung: Local mobile demo + repo + báo cáo + slide + video.

### A-W7-01 — Đóng gói mô hình và hướng dẫn thiết bị

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W6-02.
- **Đầu ra:** Hướng dẫn dây/nguồn/nạp/calibration; checklist vật tư.
- **Tiêu chí nghiệm thu:** B làm theo hướng dẫn nạp/khởi động được; cấu hình mẫu không có thông tin đăng nhập thật.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### A-W7-02 — Diễn tập và chốt phần trình bày A

- **Owner:** A. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** A-W7-01, M6.
- **Đầu ra:** Demo phần cứng; câu hỏi phản biện; video chung.
- **Tiêu chí nghiệm thu:** Tham gia hai lượt diễn tập; giải thích thuật toán và hành vi lỗi; xử lý lỗi còn lại trong phạm vi đã chốt.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).
