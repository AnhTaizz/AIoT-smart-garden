# AI và xử lý ảnh

Nhánh `finetuneAI` đã bổ sung chatbot tư vấn nông nghiệp qua API model **ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu** trên Kaggle. Xem [hướng dẫn chatbot](../docs/CHATBOT.md) để cấu hình endpoint, system prompt và đánh giá cho paper. Chatbot chỉ tư vấn, đọc dữ liệu vườn khi được chọn; không điều khiển bơm.

Đã chuẩn bị [notebook server Kaggle](Smart_Garden_Kaggle_Server.ipynb) dùng đầy đủ chat template và chỉ decode token mới sinh. Xem [cách áp dụng vào Kaggle](../docs/KAGGLE_SERVER.md); notebook chưa được triển khai vào tài khoản Kaggle của chủ dự án. Kiểm thử adapter bằng `python -m pytest -q ai/tests/test_kaggle_server.py` từ root.

Camera và xử lý ảnh vẫn chưa triển khai; đây là phần bổ sung sau IoT cốt lõi.

Thư mục này sẽ chứa tài liệu dữ liệu, mã huấn luyện/đánh giá, inference mẫu và baseline xử lý ảnh. Trách nhiệm dự kiến:

- Quản lý manifest, nguồn/quyền sử dụng dữ liệu, quy tắc gán nhãn và split train/validation/test.
- Huấn luyện và đánh giá một baseline ML nhỏ sau khi bài toán và nhãn được chốt.
- Bàn giao preprocessing, danh sách nhãn, model version, dependency và ví dụ inference cho backend.
- Giữ kết quả độ phủ xanh HSV tách biệt với kết quả mô hình ML.

AI chỉ cung cấp thông tin hoặc cảnh báo và chưa tham gia trực tiếp vào vòng điều khiển bơm. Không commit dataset hoặc model dung lượng lớn; cần lưu vị trí, phiên bản và cách lấy artifact sau khi nhóm thống nhất.

