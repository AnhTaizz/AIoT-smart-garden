# AI

Theo yêu cầu mới, đã có [vòng điều phối tưới AI trên simulator](../docs/AI_IRRIGATION.md) trong backend, tách khỏi chatbot. Chỉ các quyết định JSON hợp lệ vượt qua kiểm tra mới được chuyển thành command; dữ liệu thiết bị thật hiện bị chặn.

Nhánh `finetuneAI` đã bổ sung chatbot tư vấn nông nghiệp qua API model **ToanPhamAIEngi/Qwen3-8B-Vietnam-MultiDomainEdu** trên Kaggle. Xem [hướng dẫn chatbot](../docs/CHATBOT.md) để cấu hình endpoint, system prompt và đánh giá cho paper. Chatbot chỉ tư vấn, đọc dữ liệu vườn khi được chọn; không điều khiển bơm.

Đã chuẩn bị [notebook server Kaggle](Smart_Garden_Kaggle_Server.ipynb) dùng đầy đủ chat template và chỉ decode token mới sinh. Xem [cách áp dụng vào Kaggle](../docs/KAGGLE_SERVER.md); notebook chưa được triển khai vào tài khoản Kaggle của chủ dự án. Kiểm thử adapter bằng `python -m pytest -q ai/tests/test_kaggle_server.py` từ root.

ESP32-CAM, xử lý ảnh (HSV) và baseline ML trên ảnh đã được nhóm **loại khỏi phạm vi** ngày 2026-11-02 do không đủ thời gian.

Không commit dataset hoặc model dung lượng lớn; cần lưu vị trí, phiên bản và cách lấy artifact sau khi nhóm thống nhất.

