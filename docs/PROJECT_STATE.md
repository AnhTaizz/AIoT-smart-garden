# Trạng thái dự án

Cập nhật: 2026-09-13 trên nhánh `chore/local-mobile-demo-plan`, sau khi chuyển project lên root repo và chốt hướng LOCAL MOBILE DEMO. Trạng thái dưới đây chỉ ghi PASS khi đã có bằng chứng; PASS của bootstrap không đồng nghĩa milestone M1 đã hoàn thành.

## Hiện trạng đã biết

- Nhóm: 3 người; thời gian: 7 tuần.
- Vai trò A/B/C: đề xuất, chưa gắn tên.
- Repo URL: `https://github.com/AnhTaizz/AIoT-smart-garden.git`.
- Bootstrap đã có trên `origin/main` tại commit `b6d182f`; thay đổi định hướng/migration hiện ở nhánh `chore/local-mobile-demo-plan`.
- Project đã được chuyển từ thư mục kế hoạch lồng lên root repo; `backend/`, `frontend/`, `firmware/`, `simulator/`, `ai/`, `infra/`, `docs/` và `compose.yaml` nằm trực tiếp ở root.
- Ngày bắt đầu và hạn bảo vệ: chưa chốt.
- Phần cứng đã mua/đã nhận/đã test: chưa có thông tin xác nhận.
- Demo chính: laptop chạy React + FastAPI + Mosquitto + PostgreSQL; điện thoại và ESP32 cùng Wi-Fi/hotspot, truy cập bằng IP LAN laptop.
- Public Internet deployment không bắt buộc; chỉ optional ở tuần 6 sau khi local mobile demo ổn định. Weather API không thuộc core scope.
- Đã có bootstrap cho Docker Compose, FastAPI health/readiness, dashboard React và simulator MQTT publish.
- Compose, bốn container, backend, frontend build/test và simulator publish 10 bản tin đã được kiểm tra trong môi trường development; bằng chứng bootstrap tóm tắt ở `docs/BOOTSTRAP_REPORT.md`.
- PostgreSQL host port `5432` bị lỗi port forwarding trên máy kiểm tra; phiên kiểm tra thành công dùng `POSTGRES_PORT=55432`. Đây là cấu hình local, không đổi cổng nội bộ container.
- Sau migration, Compose đã build/chạy lại từ root repo; bốn container healthy và health/readiness trực tiếp lẫn qua proxy đều PASS. Stack sau đó được dừng bằng `docker compose stop`, nên container vẫn còn để mở lại trong Docker Desktop và named volume vẫn được giữ.
- Chưa có backend MQTT subscriber, telemetry storage/API/UI hoặc command hai chiều.
- Bộ Markdown phân công đã soạn; vẫn chờ nhóm điền danh tính và chốt G01–G03.

## Kết quả bootstrap hiện tại

| Hạng mục | Trạng thái | Kết quả thực tế |
| --- | --- | --- |
| `docker compose config` | PASS | Parse đủ PostgreSQL, Mosquitto, backend và frontend |
| Root layout và relative link | PASS | Không còn thư mục kế hoạch lồng/tham chiếu đường dẫn cũ; toàn bộ relative link Markdown tồn tại |
| Build/khởi động Compose | PASS có điều kiện | Build từ root repo; bốn container healthy khi dùng PostgreSQL host port `55432` |
| `GET /health` | PASS | HTTP 200 khi PostgreSQL chạy và khi PostgreSQL dừng |
| `GET /ready` | PASS | HTTP 200 khi DB chạy; HTTP 503 khi DB dừng; phục hồi về 200 sau khi DB chạy lại |
| Frontend | PASS | Vitest 1/1, TypeScript + Vite production build, dashboard và proxy `/api` HTTP 200 |
| Bind local mobile | PASS cấu hình | Dashboard `5173` và MQTT `1883` bind `0.0.0.0`; API `8000` và PostgreSQL chỉ bind `127.0.0.1` |
| Smartphone/ESP32 qua LAN thật | CHƯA KIỂM TRA | Chưa có điện thoại/ESP32 và mạng demo trong phiên kiểm tra này |
| Simulator unit test | PASS | 3/3 test |
| Simulator → Mosquitto | PASS | Publish hữu hạn 10 bản tin; subscriber thật nhận sequence 1–10 |
| Simulator Ctrl+C | PASS | Tiến trình liên tục ghi nhận Ctrl+C, disconnect và thoát mã 0 |

## Milestone

| Mốc | Tuần | Trạng thái | Bằng chứng | Việc còn thiếu |
| --- | --- | --- | --- | --- |
| M1 — Simulator và mobile LAN | 1 | Chưa nghiệm thu | Bootstrap report chỉ chứng minh từng phần | Chưa có MQTT → DB → API → React, smartphone LAN và command/ACK end-to-end; G01–G02 chưa chốt |
| M2 — Phần cứng thật | 2 | Chưa nghiệm thu | Chưa có | ESP32/sensor/relay/bơm thật và điều khiển từ điện thoại |
| M3 — Manual/Auto an toàn | 3 | Chưa nghiệm thu | Chưa có | Logic tưới, safety, reconnect và error handling |
| M4 — ESP32-CAM/AI baseline | 4 | Chưa nghiệm thu | Chưa có | Ảnh thật, dataset/model và image pipeline; chỉ bắt đầu tích hợp sau core IoT |
| M5 — Tích hợp đầy đủ | 5 | Chưa nghiệm thu | Chưa có | IoT + mobile dashboard + camera/AI và đóng phạm vi |
| M6 — Testing/hardening | 6 | Chưa nghiệm thu | Chưa có | Kiểm thử, kết quả; cloud deploy là optional |
| M7 — Bàn giao | 7 | Chưa nghiệm thu | Chưa có | Local mobile demo, repo, báo cáo, slide và video |

## Quyết định đang mở

| Nội dung | Người chủ trì | Hạn tương đối |
| --- | --- | --- |
| Tên/username, người điều phối, giờ rảnh và ngày bắt đầu | Cả nhóm | G01 |
| Cây trồng, BOM, người mua và ngày nhận | A | Tuần 1 |
| MQTT/API và quy tắc điều khiển | B cùng A/C | G02 |
| Wi-Fi/hotspot demo, IP LAN ổn định và firewall private | Cả nhóm | Trước nghiệm thu M1 |
| Nhãn, dataset, bài toán ML khả thi | C cùng A/B | Cuối tuần 3 |

## Việc tiếp theo

1. Cả nhóm điền TEAM, chốt G01/G02 và Wi-Fi hoặc hotspot dùng cho demo; A chủ trì G03. Không đổi `INTERFACES.md` sang AGREED trước khi A/B/C xác nhận payload hợp lệ/lỗi.
2. B: triển khai MQTT subscriber, validate/lưu telemetry, migration PostgreSQL, API đọc dữ liệu và command lifecycle theo G02.
3. C: nối dashboard với telemetry API thật, kiểm tra bằng IP LAN trên smartphone; giữ `Chưa có dữ liệu` và nút điều khiển disabled tới khi chức năng tương ứng chạy được.
4. A: đối chiếu simulator với contract G02, bổ sung mô phỏng command/ACK cho M1; sau đó chuyển sang ESP32/sensor/relay thật ở M2.
5. Cả nhóm nghiệm thu `simulator → MQTT → DB → API → React → smartphone LAN` và command ngược có ACK trước khi bắt đầu tích hợp AI.

## Nhật ký thay đổi

- 2026-09-13: soạn kế hoạch 7 tuần, 3 task chung và 42 task cá nhân; chưa xác nhận tiến độ triển khai hay hoạt động trên GitHub.
- 2026-09-13: TASK-000E kiểm tra bootstrap trong môi trường development; sửa timeout readiness qua proxy; Compose/backend/frontend/simulator MQTT đạt các kiểm tra riêng. M1 vẫn chưa nghiệm thu vì thiếu telemetry storage/UI và command hai chiều.
- 2026-09-13: chuyển project lên root repo và chốt LOCAL MOBILE DEMO; public Internet deployment thành optional, Weather API ngoài core scope, AI đứng sau luồng IoT end-to-end. Không thay đổi trạng thái nghiệm thu M1–M7.
