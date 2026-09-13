# Smart Garden — Kế hoạch triển khai 7 tuần

Bộ tài liệu phân công và quản lý công việc cho nhóm 3 người. Phiên bản kế hoạch: 2026-09-13. Đây là kế hoạch triển khai, chưa có mã nguồn ứng dụng hoặc kết quả thực nghiệm được xác nhận.

## Bắt đầu từ đâu?

1. Đọc [phân công nhóm](docs/TEAM.md), điền tên/GitHub username cho A, B, C và thống nhất người điều phối.
2. Chốt G01–G03 ở [kế hoạch 7 tuần](docs/ROADMAP.md): phạm vi, giao tiếp và phần cứng.
3. Mỗi người mở file của mình: [A — Thiết bị](docs/assignments/A-EMBEDDED.md), [B — Backend](docs/assignments/B-BACKEND.md), [C — Frontend và AI](docs/assignments/C-FRONTEND-AI.md).
4. Dùng [quy trình làm việc](docs/WORKFLOW.md) để chuyển task tuần 1 thành GitHub Issues, nhận người phụ trách và kiểm tra.
5. Theo dõi mốc chung trong [trạng thái dự án](docs/PROJECT_STATE.md). Không đánh dấu hoàn thành khi chưa demo được.

## Phạm vi sản phẩm

Một khu vực trồng thử nghiệm, ESP32, cảm biến đất Capacitive v1.2, AHT20, relay/bơm, ESP32-CAM. Luồng chính: cảm biến → ESP32 → MQTT/Mosquitto → FastAPI → PostgreSQL → React. Lệnh điều khiển đi ngược về ESP32. Camera gửi ảnh tới backend để xử lý trên máy chủ.

Mục tiêu bắt buộc: giám sát, lưu lịch sử, điều khiển Manual/Auto, tưới có giới hạn, xử lý lỗi cơ bản. Phần nâng cao: camera và một bài toán ML nhỏ có đánh giá; độ phủ xanh bằng HSV là baseline xử lý ảnh, không được gọi là mô hình ML đã huấn luyện. Weather API, nhiều khu vực trồng và tối ưu nâng cao nằm ngoài phạm vi mặc định.

## Các tài liệu

| Tài liệu | Mục đích |
| --- | --- |
| [TEAM](docs/TEAM.md) | Ai chịu trách nhiệm, phối hợp và bàn giao gì |
| [ROADMAP](docs/ROADMAP.md) | Phase, milestone, lịch 7 tuần và task chung |
| [A-EMBEDDED](docs/assignments/A-EMBEDDED.md) | 14 task của người A |
| [B-BACKEND](docs/assignments/B-BACKEND.md) | 14 task của người B |
| [C-FRONTEND-AI](docs/assignments/C-FRONTEND-AI.md) | 14 task của người C |
| [INTERFACES](docs/INTERFACES.md) | Những thỏa thuận giao tiếp cần chốt trước tích hợp |
| [WORKFLOW](docs/WORKFLOW.md) | Task, review, Git, GitHub và xử lý chậm tiến độ |
| [PROJECT_STATE](docs/PROJECT_STATE.md) | Trạng thái thực tế và việc tiếp theo |
| [WEEKLY_REVIEW](docs/templates/WEEKLY_REVIEW.md) | Mẫu nghiệm thu tuần và ghi kết quả |

Hai mẫu GitHub đi kèm: `.github/ISSUE_TEMPLATE/task.md` và `.github/pull_request_template.md`.

## Cách đưa bộ tài liệu vào repository

Repo mới: đặt nội dung thư mục này tại gốc repo. Repo đã có tài liệu: dùng nhánh riêng, đối chiếu và ghép nội dung; không ghi đè README hay kế hoạch đang dùng mà chưa xem khác biệt. Hướng dẫn cụ thể nằm trong WORKFLOW.

Không có repo đích hoặc tên thành viên được xác nhận khi soạn bộ file. Chưa tạo GitHub Issues, commit hoặc push từ bộ tài liệu này.

## Cơ sở lập kế hoạch

- `IOT.pdf`: đề án kỹ thuật vườn thông minh do người dùng cung cấp; tham khảo kiến trúc, cảm biến, lọc, tưới theo nhịp và ảnh định kỳ.
- `Tài Liệu Bài Giảng & Quy Định BTL IoT.pdf`: bản ghi chú bài giảng do người dùng cung cấp; dùng định hướng hệ thống IoT và tự xây dựng frontend/backend kèm AI/ML hoặc bảo mật. Đây là bản ghi chú, không bảo đảm điểm số.
- Thời hạn 7 tuần và nhóm 3 người do chủ dự án xác định. Các ước lượng giờ, milestone và tiêu chí thử nghiệm là đề xuất của kế hoạch, không phải quy định của giảng viên.

Các PDF gốc không được đính kèm vào gói này. Giá linh kiện, tính năng dịch vụ và số liệu hiệu năng chưa được xác minh mới trong bộ kế hoạch.
