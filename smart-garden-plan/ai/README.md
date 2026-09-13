# AI và xử lý ảnh

Trạng thái: chưa triển khai; camera/AI là phần bổ sung sau IoT cốt lõi.

Thư mục này sẽ chứa tài liệu dữ liệu, mã huấn luyện/đánh giá, inference mẫu và baseline xử lý ảnh. Trách nhiệm dự kiến:

- Quản lý manifest, nguồn/quyền sử dụng dữ liệu, quy tắc gán nhãn và split train/validation/test.
- Huấn luyện và đánh giá một baseline ML nhỏ sau khi bài toán và nhãn được chốt.
- Bàn giao preprocessing, danh sách nhãn, model version, dependency và ví dụ inference cho backend.
- Giữ kết quả độ phủ xanh HSV tách biệt với kết quả mô hình ML.

AI chỉ cung cấp thông tin hoặc cảnh báo và chưa tham gia trực tiếp vào vòng điều khiển bơm. Không commit dataset hoặc model dung lượng lớn; cần lưu vị trí, phiên bản và cách lấy artifact sau khi nhóm thống nhất.

