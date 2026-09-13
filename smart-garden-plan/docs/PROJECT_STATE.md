# Trạng thái dự án

Cập nhật: 2026-09-13 sau kiểm tra bàn giao bootstrap TASK-000E. Trạng thái dưới đây dựa trên lệnh đã chạy; PASS của từng kiểm tra bootstrap không đồng nghĩa milestone M1 đã hoàn thành.

## Hiện trạng đã biết

- Nhóm: 3 người; thời gian: 7 tuần.
- Vai trò A/B/C: đề xuất, chưa gắn tên.
- Repo URL: `https://github.com/AnhTaizz/AIot-smart-garden.git`; đang ở nhánh `main`, bootstrap chưa commit/push.
- Ngày bắt đầu và hạn bảo vệ: chưa chốt.
- Phần cứng đã mua/đã nhận/đã test: chưa có thông tin xác nhận.
- Đã có bootstrap cho Docker Compose, FastAPI health/readiness, dashboard React và simulator MQTT publish.
- Compose, bốn container, backend, frontend build/test và simulator publish 10 bản tin đã được kiểm tra trong môi trường development; bằng chứng tóm tắt ở `docs/BOOTSTRAP_REPORT.md`.
- PostgreSQL host port `5432` bị lỗi port forwarding trên máy kiểm tra; phiên kiểm tra thành công dùng `POSTGRES_PORT=55432`. Đây là cấu hình local, không đổi cổng nội bộ container.
- Stack development đã được dừng sau kiểm tra bằng `docker compose down`; named volume PostgreSQL được giữ lại.
- Chưa có backend MQTT subscriber, telemetry storage/API/UI hoặc command hai chiều.
- Bộ Markdown phân công đã soạn; vẫn chờ nhóm điền danh tính và chốt G01–G03.

## Kết quả bootstrap hiện tại

| Hạng mục | Trạng thái | Kết quả thực tế |
| --- | --- | --- |
| `docker compose config` | PASS | Parse đủ PostgreSQL, Mosquitto, backend và frontend |
| Build/khởi động Compose | PASS có điều kiện | Bốn container healthy khi dùng PostgreSQL host port `55432` |
| `GET /health` | PASS | HTTP 200 khi PostgreSQL chạy và khi PostgreSQL dừng |
| `GET /ready` | PASS | HTTP 200 khi DB chạy; HTTP 503 khi DB dừng; phục hồi về 200 sau khi DB chạy lại |
| Frontend | PASS | Vitest 1/1, TypeScript + Vite production build, dashboard và proxy `/api` HTTP 200 |
| Simulator unit test | PASS | 3/3 test |
| Simulator → Mosquitto | PASS | Publish hữu hạn 10 bản tin; subscriber thật nhận sequence 1–10 |
| Simulator Ctrl+C | PASS | Tiến trình liên tục ghi nhận Ctrl+C, disconnect và thoát mã 0 |

## Milestone

| Mốc | Tuần | Trạng thái | Bằng chứng | Việc còn thiếu |
| --- | --- | --- | --- | --- |
| M1 — Mô phỏng hai chiều | 1 | Chưa nghiệm thu | Bootstrap report; chưa đủ tiêu chí M1 | Chưa lưu/hiển thị telemetry và chưa có command/ACK hai chiều; G01–G03 chưa chốt |
| M2 — Phần cứng thật | 2 | Chưa nghiệm thu | Chưa có | Thiết bị, hiệu chuẩn và tích hợp |
| M3 — MVP tự tưới | 3 | Chưa nghiệm thu | Chưa có | Logic và thử lỗi; chốt bài toán ML |
| M4 — Camera/ML baseline | 4 | Chưa nghiệm thu | Chưa có | Dataset/model và image pipeline |
| M5 — Tích hợp đủ chức năng | 5 | Chưa nghiệm thu | Chưa có | Demo chung và đóng phạm vi |
| M6 — Sẵn sàng bảo vệ | 6 | Chưa nghiệm thu | Chưa có | Kiểm thử và kết quả |
| M7 — Bàn giao | 7 | Chưa nghiệm thu | Chưa có | Release, báo cáo, slide, video |

## Quyết định đang mở

| Nội dung | Người chủ trì | Hạn tương đối |
| --- | --- | --- |
| Tên/username, người điều phối, giờ rảnh và ngày bắt đầu | Cả nhóm | G01 |
| Repository đích | Chủ dự án | Trước khi push |
| Cây trồng, BOM, người mua và ngày nhận | A | Tuần 1 |
| MQTT/API và quy tắc điều khiển | B cùng A/C | G02 |
| Nhãn, dataset, bài toán ML khả thi | C cùng A/B | Cuối tuần 3 |

## Việc tiếp theo

1. Cả nhóm điền TEAM, chốt G01 và G02; A chủ trì G03. Không đổi `INTERFACES.md` sang AGREED trước khi A/B/C xác nhận payload hợp lệ/lỗi.
2. A: đối chiếu simulator với contract G02, sau đó triển khai nhận command và ACK/state trong A-W1-02; tiếp tục giữ dữ liệu simulator tách khỏi số đo thật.
3. B: triển khai MQTT subscriber, validate/lưu telemetry, migration PostgreSQL và API đọc dữ liệu theo B-W1-01/B-W1-02; xử lý command lifecycle sau khi G02 chốt.
4. C: nối dashboard với API telemetry thật khi B bàn giao; giữ `Chưa có dữ liệu` và nút điều khiển disabled cho tới khi contract/chức năng tương ứng chạy được.
5. Cả nhóm chạy lại luồng `simulator → MQTT → DB → API → UI` và command ngược có ACK, rồi mới hẹn nghiệm thu M1 theo mẫu WEEKLY_REVIEW.

## Nhật ký thay đổi

- 2026-09-13: soạn kế hoạch 7 tuần, 3 task chung và 42 task cá nhân; chưa xác nhận tiến độ triển khai hay hoạt động trên GitHub.
- 2026-09-13: TASK-000E kiểm tra bootstrap trong môi trường development; sửa timeout readiness qua proxy; Compose/backend/frontend/simulator MQTT đạt các kiểm tra riêng. M1 vẫn chưa nghiệm thu vì thiếu telemetry storage/UI và command hai chiều.
