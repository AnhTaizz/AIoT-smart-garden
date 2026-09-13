# Báo cáo dựng khung dự án — TASK-000A đến TASK-000E

Ngày thực hiện: 2026-09-13.

## Phạm vi

TASK-000A chỉ dựng cấu trúc repository và mô tả ranh giới các thành phần. Không triển khai nghiệp vụ, dependency, database schema, MQTT payload, API, firmware, giao diện, model AI hoặc hạ tầng chạy được.

## Hiện trạng trước thay đổi

- Git working tree sạch khi bắt đầu TASK-000A; không có thay đổi người dùng cần ghép hoặc bảo toàn.
- Không tìm thấy `AGENTS.md` trong cây repository.
- Repository mới có bộ kế hoạch Markdown và template GitHub; chưa có mã nguồn hay kết quả chạy được xác nhận.
- `docs/INTERFACES.md` đang ở trạng thái DRAFT, chưa được A/B/C xác nhận.
- G01–G03 và các milestone M1–M7 chưa được nghiệm thu theo `docs/PROJECT_STATE.md`.

## Thay đổi đã thực hiện

- Tạo `backend/README.md`: phạm vi FastAPI, MQTT, PostgreSQL, API và vòng đời command.
- Tạo `frontend/README.md`: phạm vi dashboard React và cách thể hiện trạng thái thiết bị.
- Tạo `simulator/README.md`: phạm vi mô phỏng telemetry, command và ACK/state cho M1.
- Tạo `firmware/README.md`: phạm vi ESP32, cảm biến, relay/bơm và an toàn cục bộ.
- Tạo `ai/README.md`: phạm vi dữ liệu, baseline ML/HSV, đánh giá và bàn giao inference.
- Tạo `infra/README.md`: phạm vi Mosquitto, PostgreSQL và hướng container hóa sau này.
- Tạo `.gitignore` cho secret cục bộ, môi trường Python/Node, kết quả build ESP32, dữ liệu runtime và artifact AI lớn.

Các thư mục được đặt dưới `smart-garden-plan/`, cùng cấp với `docs/` hiện hữu. Không di chuyển hoặc tạo lại tài liệu và template đã có.

## Kiến trúc được giữ nguyên

Luồng dự kiến vẫn là:

```text
ESP32/simulator -> Mosquitto -> FastAPI -> PostgreSQL -> React
ESP32/simulator <- Mosquitto <- FastAPI <- React
ESP32-CAM -> backend -> xử lý ảnh/AI -> backend/frontend (phase sau)
```

ESP32 sở hữu trạng thái tưới, giới hạn chạy bơm và xử lý lỗi cục bộ. Backend kiểm tra/chuyển lệnh, lưu dữ liệu và cung cấp API. Frontend hiển thị ACK và trạng thái thiết bị thực tế. AI chưa điều khiển bơm.

## Quyết định còn mở

- G01: danh tính A/B/C, người điều phối, ngày bắt đầu, hạn bảo vệ, cây trồng và phạm vi AI.
- G02: schema MQTT/API, ví dụ payload hợp lệ/lỗi, QoS/retained, TTL, khử trùng, thời gian, stale/offline, vòng đời command và cách frontend cập nhật dữ liệu.
- G03: BOM, nguồn điện, relay/bơm, dây/ống, lịch mua và kết quả kiểm tra phần cứng thật.
- Cách tổ chức mã nguồn cụ thể trong từng module, phiên bản dependency và công cụ build.
- Thiết kế database, lưu file ảnh, xác thực/phân quyền và cấu hình triển khai.
- Bài toán ML, nguồn dữ liệu, nhãn, split và định dạng artifact.

`docs/INTERFACES.md` vẫn giữ nguyên trạng thái DRAFT. TASK-000A không đánh dấu G01–G03, task cá nhân hoặc milestone nào là hoàn thành.

## Xác minh

- Đã kiểm tra lại cây thư mục và nội dung các README mới.
- Không có mã thực thi nên không chạy build hoặc test ứng dụng.
- Không commit, push hoặc merge thay đổi.

## TASK-000B — Docker Compose và backend health/readiness

### Hiện trạng trước thay đổi

- Git chỉ có các file untracked do TASK-000A tạo; chúng được giữ nguyên và bổ sung, không xóa hoặc ghi đè ngoài phạm vi.
- Không có backend, container hoặc dependency chạy được trước TASK-000B.
- `docs/INTERFACES.md` vẫn là DRAFT và các milestone chưa được nghiệm thu.

### Thay đổi đã thực hiện

- Thêm `compose.yaml` cho Mosquitto, PostgreSQL và FastAPI; cả ba cổng host chỉ bind localhost.
- Thêm named volume cho dữ liệu PostgreSQL và dữ liệu persistence của Mosquitto.
- Thêm `.env.example` với giá trị development mẫu; `.env` tiếp tục bị Git bỏ qua.
- Thêm cấu hình Mosquitto anonymous dành riêng cho development local.
- Thêm image backend Python 3.12, dependency FastAPI/Uvicorn/Psycopg và mã API tối thiểu.
- Thêm `GET /health`, chỉ phản ánh tiến trình API.
- Thêm `GET /ready`, mở kết nối PostgreSQL và chạy `SELECT 1`; lỗi kết nối trả HTTP 503 mà không lộ thông tin cấu hình.
- Cập nhật hướng dẫn chạy trong README gốc, backend và infra.

### Ngoài phạm vi và quyết định còn mở

- Chưa có MQTT subscriber hoặc kết nối backend–Mosquitto.
- Chưa có schema, migration, telemetry storage, command, ảnh/AI hoặc thuật toán tưới.
- Mosquitto chưa có xác thực và chưa mở ra LAN; cấu hình hiện tại chỉ dùng development local.
- MQTT/API contract, QoS, retained, TTL và các nội dung G02 vẫn chưa được chốt.
- Không cập nhật trạng thái G01–G03 hoặc M1–M7.

### Trạng thái xác minh TASK-000B

- Kiểm tra cú pháp Python: **ĐẠT** bằng `compile()` của Python 3.
- Kiểm tra cấu trúc YAML tĩnh: **ĐẠT** bằng PyYAML; xác nhận đủ ba service, có `postgres_data` và các cổng đều bind `127.0.0.1`. Đây không thay thế `docker compose config`.
- Rà mẫu private key, AWS access key và PostgreSQL URL chứa mật khẩu trong file ngoài Markdown: không phát hiện kết quả khớp. Giá trị mật khẩu trong `.env.example` là placeholder development, không phải secret thật.
- Import/chạy backend trực tiếp trên host: **CHƯA KIỂM TRA** vì môi trường host chưa cài FastAPI.
- `docker compose config`: **CHƯA KIỂM TRA**.
- Khởi động ba service: **CHƯA KIỂM TRA**.
- `GET /health`: **CHƯA KIỂM TRA**.
- `GET /ready` khi PostgreSQL hoạt động/lỗi/phục hồi: **CHƯA KIỂM TRA**.

Lý do: Docker CLI trong WSL2 báo chưa khả dụng và yêu cầu bật Docker Desktop WSL integration; gọi trực tiếp executable Docker phía Windows cũng không kết nối được engine. Trạng thái trên phải được cập nhật chỉ sau khi có kết quả lệnh thực tế. Không commit, push hoặc merge trong TASK-000B.

## TASK-000C — Frontend React và TypeScript

### Hiện trạng trước thay đổi

- Giữ nguyên toàn bộ thay đổi untracked của TASK-000A/TASK-000B và phần README đã sửa; không phát hiện thay đổi mới ngoài kết quả các task trước.
- `frontend/` chỉ có README mô tả phạm vi, chưa có ứng dụng.
- Node.js/npm không chạy được trong WSL hiện tại; Docker vẫn chưa khả dụng.

### Thay đổi đã thực hiện

- Thêm ứng dụng React + TypeScript + Vite và cấu hình build/kiểm thử.
- Thêm dashboard tiếng Việt hiển thị trạng thái backend từ `/health` và PostgreSQL từ `/ready`.
- Thêm khu vực nhiệt độ, độ ẩm không khí, độ ẩm đất, máy bơm và ảnh cây; tất cả dữ liệu chưa có đều ghi `Chưa có dữ liệu`.
- Giữ nút bật/tắt bơm disabled và không thêm số đo hoặc trạng thái thiết bị giả.
- Thêm test cho tình huống mất kết nối API, dữ liệu rỗng và nút điều khiển chưa khả dụng.
- Thêm Dockerfile multi-stage, Nginx phục vụ frontend và proxy `/api` tới hostname nội bộ `backend:8000`.
- Bổ sung service `frontend` vào Compose, bind cổng mặc định `127.0.0.1:5173`.
- Bổ sung `FRONTEND_PORT` và `VITE_API_BASE_URL` vào `.env.example`.
- Cập nhật README gốc, frontend và infra với cách chạy và phân biệt URL trình duyệt với hostname Docker.

### Ngoài phạm vi

- Chưa có API telemetry, command hoặc ảnh, nên frontend không polling hay hiển thị các dữ liệu đó.
- Chưa có hành động bật/tắt bơm và không gửi request command.
- Chưa thay đổi MQTT/API contract hoặc trạng thái DRAFT của `docs/INTERFACES.md`.
- Không cập nhật G01–G03 hoặc M1–M7.

### Trạng thái xác minh TASK-000C

- Kiểm tra tĩnh source/config: **ĐẠT**. `package.json` là JSON hợp lệ; Compose parse được bằng PyYAML và có đủ bốn service; frontend bind localhost; `/api` proxy tới `backend:8000`; các khu vực dữ liệu rỗng và nút disabled có trong source; không phát hiện khoảng trắng cuối dòng.
- Rà mẫu private key, AWS access key và PostgreSQL URL chứa mật khẩu trong file ngoài Markdown: không phát hiện kết quả khớp.
- `npm test`: **CHƯA KIỂM TRA**.
- `npm run build`: **CHƯA KIỂM TRA**.
- `docker compose config` với frontend: **CHƯA KIỂM TRA**.
- Khởi động dashboard và gọi `/health`, `/ready` qua proxy: **CHƯA KIỂM TRA**.
- Trạng thái mất kết nối trong trình duyệt/test runner: **CHƯA KIỂM TRA**.

Lý do: WSL hiện không có Node.js; lệnh npm phía Windows không dùng được trong distro và báo môi trường WSL không được hỗ trợ. Docker CLI vẫn yêu cầu bật Docker Desktop WSL integration. Vì vậy chưa cài dependency, chưa sinh `package-lock.json`, chưa thể chạy TypeScript compiler, Vitest, Vite build hoặc container.

Các mục chỉ được đổi sang ĐẠT sau khi lệnh tương ứng chạy thành công. Không commit, push hoặc merge trong TASK-000C.

## TASK-000D — Simulator phát MQTT telemetry

### Hiện trạng trước thay đổi

- Giữ nguyên các thay đổi từ TASK-000A đến TASK-000C; không phát hiện thay đổi mới ngoài phạm vi các task trước.
- Đã đọc lại `docs/INTERFACES.md`: tài liệu vẫn là DRAFT, chưa có schema telemetry được A/B/C xác nhận.
- Host có Python 3 nhưng chưa cài `paho-mqtt`; không có Mosquitto client và Docker vẫn chưa khả dụng trong WSL.

### Thay đổi đã thực hiện

- Thêm simulator Python dùng Paho MQTT để publish telemetry, mặc định tới `garden/<device_id>/telemetry`.
- Cho phép cấu hình broker, port, username/password, topic, `device_id`, interval và số bản tin bằng CLI hoặc biến môi trường; CLI được ưu tiên.
- Hỗ trợ `--count 0` để gửi liên tục tới Ctrl+C và `--count N` để gửi hữu hạn đúng N bản tin.
- Log rõ tiến trình, payload, tổng số đã gửi và dừng kết nối/network loop trong khối `finally`.
- Thêm payload đề xuất `bootstrap-telemetry-v0` với `simulated: true`, sequence, thời gian UTC và ba giá trị nhiệt độ/độ ẩm; không sửa `docs/INTERFACES.md`.
- Thêm unit test cho payload JSON, cấu hình môi trường và ưu tiên CLI.
- Bổ sung hướng dẫn Linux/macOS, Windows PowerShell 5.1 và quy trình dùng `mosquitto_sub -C 10` để xác nhận đủ 10 bản tin.

### Ngoài phạm vi

- Chưa subscribe command, chưa gửi ACK/state và chưa lưu PostgreSQL.
- QoS 0 và `retain=false` chỉ là mặc định bootstrap của simulator, không phải quyết định G02.
- Không cập nhật trạng thái G02 hoặc các milestone.

### Trạng thái xác minh TASK-000D

- Kiểm tra cú pháp Python: **ĐẠT**.
- Unit test không cần broker: **ĐẠT**, 3/3 test.
- `python simulator.py --help`: **ĐẠT**.
- Kết nối simulator tới Mosquitto: **CHƯA KIỂM TRA**.
- Gửi hữu hạn 10 bản tin: **CHƯA KIỂM TRA**.
- Subscriber thực nhận đủ 10 bản tin và sequence 1–10: **CHƯA KIỂM TRA**.
- Dừng bằng Ctrl+C khi đang kết nối broker: **CHƯA KIỂM TRA**.

Lý do phần MQTT chưa kiểm tra: host chưa có `paho-mqtt` hoặc Mosquitto client, còn Docker CLI trong WSL vẫn yêu cầu bật Docker Desktop WSL integration. Không báo PASS cho luồng MQTT khi chưa có subscriber làm bằng chứng. Không commit, push hoặc merge trong TASK-000D.

## TASK-000E — Kiểm tra và bàn giao bootstrap

Kết quả TASK-000E là trạng thái kiểm tra hiện tại và thay thế các mục CHƯA KIỂM TRA lịch sử trong TASK-000B–000D khi cùng hạng mục đã được chạy lại thành công.

### Môi trường và phần đã chạy

- Docker Engine `29.4.3`, Docker Compose `v5.1.3` qua Docker Desktop/WSL2.
- `docker compose config` với `.env.example`.
- Build image backend Python 3.12 và frontend Node 22/Nginx.
- Vitest, TypeScript compiler và Vite production build trong stage build frontend.
- Bốn container PostgreSQL, Mosquitto, backend và frontend.
- `/health`, `/ready`, dashboard và proxy `/api` bằng request localhost.
- Thử dừng/khởi động lại PostgreSQL chỉ trong stack development.
- Simulator và Paho MQTT trong container dùng một lần; subscriber là `mosquitto_sub` trong container broker development.
- Unit test simulator bằng Python host.
- Sau kiểm tra, chạy `docker compose down` không kèm `-v`; container/network đã được gỡ và hai named volume, gồm `smart-garden_postgres_data`, vẫn còn.

Host vẫn chưa có Node.js/npm Linux và thiếu Python `pip`/`venv`; các đường chạy trực tiếp ngoài Docker chưa được kiểm tra. Lệnh PowerShell 5.1 đã được rà cú pháp tài liệu nhưng chưa chạy trên máy Windows PowerShell 5.1 thật.

### Lỗi phát hiện và sửa trong phạm vi bootstrap

- Lần `docker compose up` đầu tiên FAIL vì Docker Desktop không forward được PostgreSQL host port `5432`. Không thay cổng container; lần kiểm tra thành công dùng file env tạm với `POSTGRES_PORT=55432`. README đã hướng dẫn đổi cổng local khi bị chiếm.
- Khi PostgreSQL dừng, backend trực tiếp trả 503 nhưng Nginx ban đầu trả 504 vì readiness kéo dài hơn proxy timeout. Đã giới hạn toàn bộ kết nối/query PostgreSQL bằng timeout bất đồng bộ; kiểm tra lại cho kết quả 503 sau khoảng 2 giây ở cả backend trực tiếp và proxy.
- Chuẩn hóa `/ready` luôn trả `JSONResponse` để FastAPI không phải suy luận response model từ kiểu union.
- Thêm `npm test` vào stage build frontend để image không build thành công khi test trạng thái mất kết nối thất bại.

### Ma trận kết quả

| Hạng mục | Trạng thái | Bằng chứng quan sát |
| --- | --- | --- |
| Compose config | PASS | Nhận đủ bốn service: postgres, backend, frontend, mosquitto |
| Compose với port mặc định trên máy kiểm tra | FAIL môi trường | Docker Desktop lỗi forward `127.0.0.1:5432` |
| Compose với `POSTGRES_PORT=55432` | PASS | Bốn container cùng ở trạng thái healthy |
| Backend `/health` | PASS | HTTP 200, `{"status":"ok"}` khi DB chạy và khi DB dừng |
| Backend `/ready` bình thường | PASS | HTTP 200, PostgreSQL `up` |
| Backend `/ready` khi DB dừng | PASS | HTTP 503, PostgreSQL `down` trong khoảng 2 giây |
| Readiness phục hồi | PASS | Trở lại HTTP 200 sau khi PostgreSQL khởi động và healthy |
| Dashboard/frontend proxy | PASS | Trang `/`, `/api/health`, `/api/ready` đều HTTP 200 khi stack bình thường |
| Frontend test | PASS | Vitest 1/1; tình huống mất kết nối, không có số liệu giả, nút bơm disabled |
| Frontend production build | PASS | TypeScript và Vite build thành công; 30 module được transform |
| Simulator unit test | PASS | 3/3 test |
| Simulator gửi hữu hạn | PASS | Log gửi đúng 10/10 và dừng gọn |
| Subscriber MQTT thật | PASS | `mosquitto_sub -C 10` nhận đủ payload sequence 1–10, đều `simulated: true` |
| Simulator Ctrl+C | PASS | Nhận Ctrl+C, log dừng gọn, disconnect và thoát mã 0 |
| Dừng môi trường và giữ volume | PASS | Compose không còn container; named volume PostgreSQL vẫn tồn tại sau `docker compose down` |
| Host Node/npm, pip/venv | CHƯA KIỂM TRA runtime | Toolchain Linux chưa được cài trên host |
| PowerShell 5.1 | CHƯA KIỂM TRA runtime | Chưa có phiên Windows PowerShell 5.1 trong môi trường kiểm tra |

Các cảnh báo readiness khi PostgreSQL bị dừng và log shutdown database là kết quả mong đợi của phép thử lỗi development, không phải lỗi production được che giấu.

### Giới hạn và giả định còn mở

- `docs/INTERFACES.md` vẫn là DRAFT; payload `bootstrap-telemetry-v0`, QoS 0 và anonymous MQTT chưa phải quyết định G02.
- `.env.example` chỉ dùng development; cần đổi credential và chính sách broker trước môi trường khác.
- Host port có thể phải đổi theo máy thành viên. Hostname `backend`, `postgres`, `mosquitto` chỉ dùng trong mạng Compose.
- Chưa có backend MQTT subscriber, schema/migration nghiệp vụ, telemetry storage/API/UI, command, ACK/state hoặc firmware thật.
- Chưa kiểm tra phần cứng, camera hay AI.

### Việc tiếp theo theo vai trò

- A: cùng B/C chốt G02, giữ simulator tương thích contract đã chốt, rồi làm nhận command và ACK/state; A chủ trì BOM/phần cứng G03.
- B: thêm MQTT subscriber, validate/lưu telemetry, migration và API đọc dữ liệu; sau đó triển khai vòng đời command đúng contract.
- C: nối dashboard vào telemetry API thật và chỉ bật điều khiển sau khi command/ACK đã chạy; tiếp tục chuẩn bị bài toán/dữ liệu AI theo roadmap.
- Cả nhóm: điền TEAM/G01, tạo Issues tuần 1 và nghiệm thu lại toàn luồng. M1 **CHƯA ĐẠT/CHƯA NGHIỆM THU** vì chưa có `MQTT → DB → API → UI` và command hai chiều.

Không commit, push hoặc merge trong TASK-000E.
