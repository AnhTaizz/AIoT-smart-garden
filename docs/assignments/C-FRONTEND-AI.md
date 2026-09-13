# Người C — Frontend và AI

Họ tên/GitHub username: điền trong [TEAM](../TEAM.md). Task chính: 14. Ước lượng chỉ tính công việc tập trung; review, tích hợp và dự phòng nằm trong phần giờ còn lại mỗi tuần. Tất cả task hiện **Backlog**, chưa có bằng chứng thực hiện.

Đọc [ROADMAP](../ROADMAP.md), [INTERFACES](../INTERFACES.md) và [WORKFLOW](../WORKFLOW.md) trước khi bắt đầu. Các mã phụ thuộc thuộc file của A/B/C tương ứng. Mã M là milestone chung, G là task chung. Có thể làm khung với mock trước; nghiệm thu tích hợp phải dùng đầu ra thật của dependency.

Trước khi có GitHub Issues, cập nhật trạng thái trong từng task dưới đây. Sau khi tạo Issues, điền link vào task và dùng Issue/Project làm nguồn trạng thái; file này giữ phạm vi và tiêu chí, tránh cập nhật hai bảng trạng thái song song.

## Tuần 1 — M1

Mục tiêu chung: React hiển thị telemetry thật, gửi/theo dõi command đúng vòng đời và chạy được trên smartphone qua LAN.

### C-W1-01 — Dựng dashboard tối thiểu và nối API

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** G02, B-W1-02.
- **Đầu ra:** Dashboard dùng latest/history API; nút command; trạng thái `pending/applied/rejected/timeout`.
- **Tiêu chí nghiệm thu:** UI hiển thị telemetry simulator đã đi qua MQTT/PostgreSQL/API; gửi command có `command_id`; chỉ báo thành công khi backend trả trạng thái `applied` từ ACK/state, không dựa vào HTTP 2xx.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog — bootstrap health/readiness UI đã có; telemetry thật và command UI chưa bắt đầu.
- **Issue / PR / bằng chứng:** Frontend test hiện chỉ chứng minh trạng thái mất kết nối và không tạo số liệu giả.

### C-W1-02 — Hoàn thiện responsive và kiểm tra smartphone LAN

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W1-01; stack tích hợp M1; `compose.lan.yaml`.
- **Đầu ra:** Dashboard responsive; checklist IP LAN, hotspot/Wi-Fi, frontend `/api` proxy và trạng thái mất kết nối.
- **Tiêu chí nghiệm thu:** Điện thoại thật cùng LAN mở được dashboard bằng IP laptop, xem telemetry đã lưu và theo dõi command tới kết quả ACK/state; layout và thao tác không yêu cầu desktop.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 2 — M2

Mục tiêu chung: ESP32 thật + sensor + relay/bơm; điện thoại điều khiển bơm qua laptop.

### C-W2-01 — Biểu đồ lịch sử và trạng thái thiết bị

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W1-01, B-W2-01, B-W2-02.
- **Đầu ra:** UI lịch sử, stale/offline, lỗi cảm biến, phản hồi lệnh.
- **Tiêu chí nghiệm thu:** Hiển thị đơn vị/thời gian; sensor lỗi không hiện 0; không báo bật thành công chỉ vì HTTP thành công.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W2-02 — Hoàn thiện UI command và ACK thiết bị thật

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W2-01, A-W2-02, B-W2-02.
- **Đầu ra:** UI gửi lệnh, pending/ACK/rejected/timeout và trạng thái bơm do ESP32 xác nhận.
- **Tiêu chí nghiệm thu:** Điện thoại điều khiển được bơm trong bài test có giám sát; UI không báo thành công chỉ dựa trên HTTP response.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 3 — M3

Mục tiêu chung: Manual/Auto, safety, reconnect và error handling.

### C-W3-01 — UI Auto/Manual, cấu hình và lịch sử tưới

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W2-01, B-W3-01.
- **Đầu ra:** Màn hình mode/cấu hình/lý do tưới.
- **Tiêu chí nghiệm thu:** Hiển thị cấu hình được thiết bị xác nhận; demo cùng A/B đủ chuyển chế độ, lỗi và dừng bơm.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W3-02 — Kiểm tra UX khi reconnect và lỗi an toàn

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W2-02, A-W3-01, A-W3-02, B-W3-02.
- **Đầu ra:** UI offline/stale/reconnect, lỗi sensor/command và hành động dừng rõ ràng.
- **Tiêu chí nghiệm thu:** Smartphone hiển thị đúng khi mất/phục hồi kết nối; không suy đoán relay state; lỗi API/MQTT không vô hiệu hóa khả năng nhận biết trạng thái nguy hiểm.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 4 — M4

Mục tiêu chung: ESP32-CAM → backend → xử lý ảnh; AI baseline có đánh giá ban đầu.

### C-W4-01 — Huấn luyện baseline ML nhỏ

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** M3 đã nghiệm thu, G01, A-W4-01.
- **Đầu ra:** Quyết định nhãn/split, manifest dữ liệu, script huấn luyện/inference, model, cấu hình và seed.
- **Tiêu chí nghiệm thu:** Chạy được pipeline; truy được nguồn/nhãn; chọn model bằng validation; ghi phiên bản dataset và tham số; giữ test cho đánh giá.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W4-02 — Đánh giá baseline và bàn giao B

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W4-01.
- **Đầu ra:** Bảng precision/recall/F1, confusion matrix, lỗi mẫu.
- **Tiêu chí nghiệm thu:** Có số lượng mẫu từng lớp; tách kết quả test công khai và ảnh thực; B chạy được ví dụ inference theo hướng dẫn.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 5 — M5

Mục tiêu chung: Full integration IoT, mobile dashboard, camera và AI.

### C-W5-01 — Tích hợp UI ảnh và kết quả AI

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** B-W4-02, B-W5-01, A-W4-02.
- **Đầu ra:** Ảnh gần nhất, lịch sử, nhãn/độ phủ, trạng thái lỗi.
- **Tiêu chí nghiệm thu:** Kết quả gắn đúng ảnh và phiên bản model; không suy diễn confidence là độ chính xác hay chẩn đoán chắc chắn.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W5-02 — Đánh giá ảnh thật và một đợt cải tiến có giới hạn

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W4-02, A-W5-01.
- **Đầu ra:** Bảng trước/sau; lỗi điển hình; phạm vi sử dụng.
- **Tiêu chí nghiệm thu:** Cải tiến dựa trên validation riêng; không tune trên test; nếu dùng test để sửa thì phải có holdout mới hoặc công khai hạn chế.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 6 — M6

Mục tiêu chung: Testing/hardening; public Internet deployment chỉ optional nếu core đã ổn định.

### C-W6-01 — Kiểm thử UI và toàn luồng người dùng

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 4 giờ.
- **Phụ thuộc:** C-W5-01, B-W5-02.
- **Đầu ra:** Kịch bản dữ liệu cũ, lỗi API, pending, camera lỗi.
- **Tiêu chí nghiệm thu:** Đối chiếu UI với backend/thiết bị; thao tác dừng rõ; lỗi ảnh không làm hỏng giám sát và điều khiển.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W6-02 — Chốt kết quả AI và báo cáo C

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W5-02, C-W6-01.
- **Đầu ra:** Bảng metric cuối, lỗi, dataset/model version, phần báo cáo.
- **Tiêu chí nghiệm thu:** Phân biệt kết quả đo với mục tiêu; nêu ánh sáng/góc chụp/miền dữ liệu; không nói nhận diện mọi bệnh cây.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).

## Tuần 7 — M7

Mục tiêu chung: Local mobile demo + repo + báo cáo + slide + video.

### C-W7-01 — Tổng hợp hình ảnh, slide và kịch bản demo

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W6-02, A-W6-02, B-W6-02.
- **Đầu ra:** Slide chung từ phần A/B/C; kịch bản demo.
- **Tiêu chí nghiệm thu:** Chỉ dùng số liệu có nguồn; mỗi người tự viết lời trình bày phần mình; bố cục/thuật ngữ thống nhất.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

### C-W7-02 — Diễn tập và video dự phòng

- **Owner:** C. **Reviewer:** B. **Ước lượng:** 3 giờ.
- **Phụ thuộc:** C-W7-01, M6.
- **Đầu ra:** Video luồng hoàn chỉnh; kiểm tra UI máy demo.
- **Tiêu chí nghiệm thu:** Tham gia hai lượt diễn tập; video đúng phiên bản; hoàn thiện README frontend/AI và liên kết tài liệu.
- **Bàn giao:** commit/PR, cách chạy/kiểm tra và log/ảnh/video hoặc bảng kết quả liên quan; không chứa thông tin đăng nhập thật.
- **Trạng thái:** Backlog.
- **Issue / PR / bằng chứng:** chưa có.

Cuối tuần: tham gia demo chung, cập nhật phần báo cáo mình sở hữu và ghi vấn đề tuần sau theo [mẫu review](../templates/WEEKLY_REVIEW.md).
