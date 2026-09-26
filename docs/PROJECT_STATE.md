# Trạng thái dự án

Cập nhật: 2026-09-26 trên nhánh `feat/B-W1-backend-telemetry-command`; code được kiểm tra tại `6ba6eb46ca7a06f6f9a258a8900e5edfb1384577`. Trạng thái dưới đây chỉ ghi PASS khi đã có bằng chứng; PASS thành phần không đồng nghĩa milestone M1 đã hoàn thành.

## Hiện trạng đã biết

- Nhóm: 3 người; thời gian: 7 tuần.
- Thành viên và vai trò: Thành (A — Thiết bị & firmware / Embedded), Tài (B — Backend & dữ liệu), Toản (C — Frontend & AI).
- Repo URL: `https://github.com/AnhTaizz/AIoT-smart-garden.git`.
- `origin/main` ở `adbdbd1b3c1b2829661cf53d603392750b6a39f3`; backend/simulator nghiệp vụ và bản đề xuất G02 chỉ có trên [draft PR #2](https://github.com/AnhTaizz/AIoT-smart-garden/pull/2), chưa merge.
- Project đã được chuyển từ thư mục kế hoạch lồng lên root repo; `backend/`, `frontend/`, `firmware/`, `simulator/`, `ai/`, `infra/`, `docs/` và `compose.yaml` nằm trực tiếp ở root.
- Ngày bắt đầu và hạn bảo vệ: chưa chốt.
- Phần cứng đã mua/đã nhận/đã test: chưa có thông tin xác nhận.
- Demo chính: laptop chạy React + FastAPI + Mosquitto + PostgreSQL; điện thoại và ESP32 cùng Wi-Fi/hotspot, truy cập bằng IP LAN laptop.
- Public Internet deployment không bắt buộc; chỉ optional ở tuần 6 sau khi local mobile demo ổn định. Weather API không thuộc core scope.
- Đã có bootstrap cho Docker Compose, FastAPI health/readiness, dashboard React và simulator MQTT publish.
- Compose, bốn container, backend, frontend build/test và simulator publish 10 bản tin đã được kiểm tra trong môi trường development; bằng chứng bootstrap tóm tắt ở `docs/BOOTSTRAP_REPORT.md`.
- PostgreSQL host port `5432` bị lỗi port forwarding trên máy kiểm tra; phiên kiểm tra thành công dùng `POSTGRES_PORT=55432`. Đây là cấu hình local, không đổi cổng nội bộ container.
- Development và LAN Compose đều parse được; trong phiên kiểm tra 2026-09-26, development stack build và bốn container đạt healthy. Đây là trạng thái tại phiên kiểm tra, không phải cam kết stack luôn chạy.
- Backend và simulator trên PR #2 (chờ review/G02): có MQTT subscriber → PostgreSQL, latest/history API và vòng đời command `pending/applied/rejected/timeout`; simulator nhận command, gửi ACK/state, chống lệnh trùng/cũ, tự tắt và fail-safe OFF khi mất MQTT. Đã kiểm tra hai chiều với simulator thật; chưa có UI telemetry/command, smartphone LAN hoặc ESP32 thật.
- Bản ghi lệnh, môi trường và kết quả regression: [PR2_TEST_HANDOFF_2026-09-26](PR2_TEST_HANDOFF_2026-09-26.md).
- Phân công vai trò A/B/C đã gắn tên (Thành, Tài, Toản); tiếp tục chốt GitHub username, lịch và G01–G03.

## Kết quả kiểm tra thành phần hiện tại

| Hạng mục | Trạng thái | Kết quả thực tế |
| --- | --- | --- |
| `docker compose config` | PASS | Parse đủ PostgreSQL, Mosquitto, backend và frontend |
| Root layout và relative link | PASS | Không còn thư mục kế hoạch lồng/tham chiếu đường dẫn cũ; toàn bộ relative link Markdown tồn tại |
| Build/khởi động Compose | PASS có điều kiện | Build từ root repo; bốn container healthy khi dùng PostgreSQL host port `55432` |
| `GET /health` | PASS | HTTP 200 khi PostgreSQL chạy và khi PostgreSQL dừng |
| `GET /ready` | PASS | HTTP 200 khi DB chạy; HTTP 503 khi DB dừng; phục hồi về 200 sau khi DB chạy lại |
| Frontend | PASS | Vitest 1/1, TypeScript + Vite production build, dashboard và proxy `/api` HTTP 200 |
| Development bind | PASS runtime | Base `compose.yaml`: bốn container healthy, cả bốn cổng bind `127.0.0.1` |
| LAN demo override | PASS runtime | `compose.lan.yaml`: bốn container healthy; chỉ dashboard `5173` và MQTT `1883` bind `0.0.0.0`; API/PostgreSQL vẫn ở `127.0.0.1` |
| Smartphone/ESP32 qua LAN thật | CHƯA KIỂM TRA | Chưa có điện thoại/ESP32 và mạng demo trong phiên kiểm tra này |
| Backend unit test | PASS thành phần | 51/51 test validation trên Python 3.12.14; không skip |
| Backend E2E | PASS thành phần | 33/33 test với PostgreSQL, Mosquitto và backend thật; gồm deadline race và ACK order; không skip |
| Simulator unit test | PASS thành phần | 31/31 test cho config, payload, expiry/clock, duplicate, busy, STOP ordering, reboot và disconnect; không skip |
| Simulator ↔ MQTT ↔ backend | PASS thành phần | Simulator thật nhận ON thành `applied/on`; sau khi broker dừng/khởi động lại báo state mới `off`; phát lại chính ON cũ vẫn `off` |
| Simulator Ctrl+C | PASS | Tiến trình liên tục ghi nhận Ctrl+C, disconnect và thoát mã 0 |

## Milestone

| Mốc | Tuần | Trạng thái | Bằng chứng | Việc còn thiếu |
| --- | --- | --- | --- | --- |
| M1 — Simulator và mobile LAN | 1 | Chưa nghiệm thu | Backend/simulator hai chiều đã có [bằng chứng thành phần](PR2_TEST_HANDOFF_2026-09-26.md) trên PR #2 chưa merge | Chưa có React telemetry/command, smartphone LAN thật; G01–G02 chưa chốt |
| M2 — Phần cứng thật | 2 | Chưa nghiệm thu | Chưa có | ESP32/sensor/relay/bơm thật và điều khiển từ điện thoại |
| M3 — Manual/Auto an toàn | 3 | Chưa nghiệm thu | Chưa có | Logic tưới, safety, reconnect và error handling |
| M4 — ESP32-CAM/AI baseline | 4 | Chưa nghiệm thu | Chưa có | Ảnh thật, dataset/model và image pipeline; chỉ bắt đầu tích hợp sau core IoT |
| M5 — Tích hợp đầy đủ | 5 | Chưa nghiệm thu | Chưa có | IoT + mobile dashboard + camera/AI và đóng phạm vi |
| M6 — Testing/hardening | 6 | Chưa nghiệm thu | Chưa có | Kiểm thử, kết quả; cloud deploy là optional |
| M7 — Bàn giao | 7 | Chưa nghiệm thu | Chưa có | Local mobile demo, repo, báo cáo, slide và video |

### Checklist M1 theo bằng chứng hiện tại

| Điều kiện bắt buộc | Trạng thái thực tế |
| --- | --- |
| Simulator telemetry → MQTT → backend subscriber → PostgreSQL | PASS thành phần — 10 bản tin simulator lưu đúng `node_01`/sequence 1–10 (chưa merge) |
| Latest REST API | PASS thành phần — `GET /devices/{id}/latest` đọc PostgreSQL, có `stale` (chưa merge) |
| History REST API | PASS thành phần — `GET /devices/{id}/telemetry` (chưa merge) |
| React hiển thị telemetry thật từ API | CHƯA CÓ — dashboard hiện chỉ có trạng thái health/readiness |
| Smartphone mở dashboard qua LAN | CHƯA KIỂM TRA trên điện thoại thật |
| Command có `command_id` | PASS thành phần — `POST /devices/{id}/commands` publish lên `garden/<id>/control` (chưa merge) |
| Simulator nhận MQTT command | PASS thành phần — simulator thật nhận ON từ backend (chưa merge) |
| Simulator gửi ACK và state | PASS thành phần — ON thành `applied`, state tự về OFF sau thời lượng (chưa merge) |
| Backend phân biệt `pending/applied/rejected/timeout` | PASS thành phần — backend unit 51/51, E2E thật 33/33 và phiên simulator thật (chưa merge) |
| UI không báo thành công chỉ vì HTTP 2xx | CHƯA CÓ luồng command để nghiệm thu |

Vì chưa chứng minh đủ hai chiều xuyên qua React và smartphone trong cùng một phiên end-to-end, M1 giữ trạng thái **Chưa nghiệm thu**. Các mục PASS phía trên chỉ là bằng chứng thành phần.

## Quyết định đang mở

| Nội dung | Người chủ trì | Hạn tương đối |
| --- | --- | --- |
| Tên/username, người điều phối, giờ rảnh và ngày bắt đầu | Cả nhóm | G01 |
| Cây trồng, BOM, người mua và ngày nhận | Thành (A) | Tuần 1 |
| MQTT/API và quy tắc điều khiển | Tài (B) cùng Thành/Toản | G02 |
| Wi-Fi/hotspot demo, IP LAN ổn định và firewall private | Cả nhóm | Trước nghiệm thu M1 |
| Nhãn, dataset, bài toán ML khả thi | Toản (C) cùng Thành/Tài | Cuối tuần 3 |

## Việc tiếp theo

Trước khi nghiệm thu M1, cả nhóm hoàn thiện thông tin còn thiếu trong `docs/TEAM.md` và xác nhận G02 trong `INTERFACES.md`; Thành (A) tiếp tục chủ trì G03 song song.

**Task coding tiếp theo:** C-W1 — Toản dùng nhánh PR #2 (không dùng `main` cũ) để review REST G02 và nối UI telemetry/command vào API đã có theo checklist trong [C-FRONTEND-AI](assignments/C-FRONTEND-AI.md). Song song, Thành review quy tắc thiết bị/simulator. Khi ba người chốt G02, chạy phiên end-to-end M1 đầy đủ với UI và smartphone qua LAN.

## Nhật ký thay đổi

- 2026-09-13: soạn kế hoạch 7 tuần, 3 task chung và 42 task cá nhân; chưa xác nhận tiến độ triển khai hay hoạt động trên GitHub.
- 2026-09-13: TASK-000E kiểm tra bootstrap trong môi trường development; sửa timeout readiness qua proxy; Compose/backend/frontend/simulator MQTT đạt các kiểm tra riêng. M1 vẫn chưa nghiệm thu vì thiếu telemetry storage/UI và command hai chiều.
- 2026-09-13: chuyển project lên root repo và chốt LOCAL MOBILE DEMO; public Internet deployment thành optional, Weather API ngoài core scope, AI đứng sau luồng IoT end-to-end. Không thay đổi trạng thái nghiệm thu M1–M7.
- 2026-09-13: tách LAN demo sang `compose.lan.yaml`; development mode trở lại localhost-only. Chưa nâng trạng thái milestone vì chưa kiểm tra smartphone/ESP32 thật.
- 2026-09-13: thống nhất checklist M1 hai chiều từ simulator tới smartphone và ngược lại; toàn bộ tiêu chí M1 vẫn chưa nghiệm thu theo bằng chứng hiện có.
- 2026-09-18: cập nhật phân công nhân sự chính thức: Thành (A — Thiết bị & firmware / Embedded), Tài (B — Backend & dữ liệu), Toản (C — Frontend & AI) trên toàn bộ tài liệu dự án.
- 2026-09-18: Tài hoàn thành phần code B-W1-01/B-W1-02 (MQTT subscriber, migration, latest/history API, command lifecycle) trên nhánh riêng; unit + e2e test PASS trong development. M1 vẫn chưa nghiệm thu: chờ review, G02, simulator nhận command, UI và smartphone.
- 2026-09-25: hoàn thiện bản đề xuất G02 cho hạn tuyệt đối, bằng chứng ACK+state, boot đích và thứ tự STOP; thêm simulator hai chiều. Unit backend 51/51, simulator 29/29, E2E backend 26/26 và một phiên simulator thật hai chiều PASS. G02 vẫn DRAFT; M1 vẫn chưa nghiệm thu vì thiếu UI, smartphone và xác nhận nhóm.
- 2026-09-26: kiểm tra lại code PR #2 tại `6ba6eb46`: backend unit 51/51, simulator 31/31, E2E thật 33/33, không có test skip. Ba regression về disconnect, bằng chứng sau hạn và ACK accepted đến sau applied đều PASS; phiên broker thật xác nhận reconnect/duplicate ON giữ relay `off`. G02 vẫn DRAFT và M1 vẫn chưa nghiệm thu; bàn giao tiếp cho Toản làm C-W1.
