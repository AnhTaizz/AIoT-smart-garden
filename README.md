# Smart Garden — Kế hoạch triển khai 7 tuần

Bộ tài liệu phân công và quản lý công việc cho nhóm 3 người. Phiên bản kế hoạch: 2026-09-13. Repository hiện có khung hạ tầng development, hai endpoint kiểm tra sức khỏe của backend và dashboard React cơ bản; chưa có chức năng IoT nghiệp vụ hoàn chỉnh.

Demo chính được chốt là **LOCAL MOBILE DEMO**: laptop chạy React, FastAPI, Mosquitto và PostgreSQL; điện thoại và ESP32 kết nối cùng Wi-Fi hoặc hotspot với laptop. Điện thoại mở dashboard bằng địa chỉ IP LAN của laptop. Public Internet deployment không bắt buộc và chỉ thực hiện ở tuần 6 nếu core đã ổn định, còn đủ thời gian kiểm thử.

## Bắt đầu từ đâu?

1. Đọc [phân công nhóm](docs/TEAM.md), điền tên/GitHub username cho A, B, C và thống nhất người điều phối.
2. Chốt G01–G03 ở [kế hoạch 7 tuần](docs/ROADMAP.md): phạm vi, giao tiếp và phần cứng.
3. Mỗi người mở file của mình: [A — Thiết bị](docs/assignments/A-EMBEDDED.md), [B — Backend](docs/assignments/B-BACKEND.md), [C — Frontend và AI](docs/assignments/C-FRONTEND-AI.md).
4. Dùng [quy trình làm việc](docs/WORKFLOW.md) để chuyển task tuần 1 thành GitHub Issues, nhận người phụ trách và kiểm tra.
5. Theo dõi mốc chung trong [trạng thái dự án](docs/PROJECT_STATE.md). Không đánh dấu hoàn thành khi chưa demo được.

## Phạm vi sản phẩm

Một khu vực trồng thử nghiệm, ESP32, cảm biến đất Capacitive v1.2, AHT20, relay/bơm, ESP32-CAM. Luồng chính: cảm biến → ESP32 → MQTT/Mosquitto → FastAPI → PostgreSQL → React. Lệnh điều khiển đi ngược về ESP32 và phải có ACK/state để giao diện không suy đoán trạng thái thiết bị. Camera gửi ảnh tới backend để xử lý trên laptop.

Mục tiêu bắt buộc: giám sát, lưu lịch sử, điều khiển Manual/Auto từ laptop hoặc điện thoại, tưới có giới hạn và xử lý lỗi cơ bản. Phải hoàn thành luồng IoT end-to-end trước khi tích hợp AI. ESP32-CAM và một bài toán AI baseline nhỏ có đánh giá bắt đầu ở tuần 4; độ phủ xanh bằng HSV là baseline xử lý ảnh, không được gọi là mô hình ML đã huấn luyện. Weather API, nhiều khu vực trồng và tối ưu nâng cao không thuộc core scope.

## Kiến trúc demo local mobile

```text
Điện thoại ──HTTP qua Wi-Fi/hotspot──> IP LAN laptop:5173
                                            │
                                            ▼
                                      React / Nginx
                                            │ /api
                                            ▼
ESP32 ──MQTT qua Wi-Fi/hotspot──> Mosquitto → FastAPI → PostgreSQL
                                            │
                                            └── command → ESP32 → ACK/state
```

React/Nginx, FastAPI, Mosquitto và PostgreSQL đều chạy trên laptop bằng Docker Compose. Điện thoại chỉ cần truy cập dashboard; frontend proxy API trong mạng Docker. ESP32 dùng IP LAN của laptop làm địa chỉ MQTT broker. Không dùng hostname Docker như `frontend`, `backend` hoặc `mosquitto` trên điện thoại/ESP32.

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

## Điều kiện cài đặt

Để chạy toàn bộ bootstrap cần:

- Docker Engine hoặc Docker Desktop đang hoạt động và có Docker Compose hỗ trợ YAML tag `!override` (Compose 2.24.4 trở lên).
- Các cổng mặc định `1883`, `5432`, `8000`, `5173` chưa bị ứng dụng khác sử dụng; có thể đổi trong `.env`.
- Python 3.10 trở lên và pip nếu chạy simulator trực tiếp trên host.
- Node.js 22 và npm chỉ khi phát triển frontend ngoài Docker; build Compose đã chứa Node trong image.
- Wi-Fi hoặc hotspot cho phép laptop, điện thoại và ESP32 nhìn thấy nhau; firewall của laptop cho phép inbound TCP `5173` và `1883` trên mạng riêng khi demo.

Trên Windows dùng Docker Desktop với WSL2 integration nếu chạy lệnh từ WSL. Tất cả cấu hình hiện tại chỉ dành cho development local, không dùng làm cấu hình production.

## Cấu hình và khởi động

Linux/macOS/WSL, từ thư mục chứa file này:

```bash
test -f .env || cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Windows PowerShell 5.1:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config
docker compose up --build -d
docker compose ps
```

Không dùng `cp`, `curl` alias hoặc toán tử `&&` trong các lệnh PowerShell 5.1 ở tài liệu này. `.env.example` chứa giá trị mẫu; thay đổi `.env` cục bộ khi cổng bị chiếm, ví dụ `POSTGRES_PORT=55432`. Không đưa secret thật vào Git.

Lệnh Compose mặc định ở trên là **development mode**: cả bốn cổng chỉ bind `127.0.0.1`, nên máy khác trong LAN không truy cập được.

## Địa chỉ truy cập

| Thành phần | Development mode | LAN demo mode |
| --- | --- | --- |
| Dashboard | <http://127.0.0.1:5173> | `http://<IP_LAN_LAPTOP>:5173` |
| Backend health/readiness | `http://127.0.0.1:8000/health`, `/ready` | Không expose trực tiếp; điện thoại dùng `/api/health`, `/api/ready` qua dashboard |
| Mosquitto | `127.0.0.1:1883` | `<IP_LAN_LAPTOP>:1883` |
| PostgreSQL | `127.0.0.1:5432` | Vẫn chỉ `127.0.0.1`; không expose ra LAN |

Trình duyệt gọi API qua đường dẫn tương đối `/api`; Nginx trong container frontend mới dùng hostname Docker `backend:8000`. Hostname `backend` chỉ phân giải trong mạng Compose, không phải địa chỉ nhập vào trình duyệt.

## Chạy demo trên điện thoại

1. Cho laptop, điện thoại và ESP32 vào cùng một Wi-Fi/hotspot. Nên dùng hotspot riêng của nhóm thay vì mạng công cộng có client isolation.
2. Tìm IP LAN của laptop:
   - Windows PowerShell 5.1: chạy `ipconfig`, tìm `IPv4 Address` của adapter Wi-Fi đang dùng.
   - Linux: chạy `hostname -I` và chọn địa chỉ của mạng Wi-Fi/hotspot.
   - macOS: chạy `ipconfig getifaddr en0` nếu Wi-Fi là interface `en0`.
3. Khởi động LAN demo từ root repository:

   ```powershell
   docker compose -f compose.yaml -f compose.lan.yaml config
   docker compose -f compose.yaml -f compose.lan.yaml up --build -d
   docker compose -f compose.yaml -f compose.lan.yaml ps
   ```

4. Xác nhận cột `PORTS`: frontend phải có `0.0.0.0:5173`, Mosquitto có `0.0.0.0:1883`, còn backend/PostgreSQL là `127.0.0.1`.
5. Nếu Windows Firewall hỏi, chỉ cho phép Docker/dashboard và MQTT trên **Private networks**.
6. Trên điện thoại mở `http://<IP_LAN_LAPTOP>:<FRONTEND_PORT>`, mặc định là `http://<IP_LAN_LAPTOP>:5173`.
7. Cấu hình ESP32 dùng `<IP_LAN_LAPTOP>` làm MQTT broker và `MQTT_PORT` làm cổng, mặc định `1883`.

`compose.lan.yaml` chỉ thay port publishing của frontend và Mosquitto; frontend vẫn proxy `/api` tới FastAPI qua mạng Docker. File không chứa IP laptop, vì IP có thể đổi theo Wi-Fi/hotspot. Mosquitto hiện cho phép anonymous cho development/local demo tin cậy; tuyệt đối không dùng cấu hình này trên Wi-Fi công cộng hoặc public Internet. Nếu điện thoại không mở được dashboard, kiểm tra hai thiết bị có cùng subnet, client isolation và firewall trước khi sửa code.

Kiểm tra backend trên Linux/macOS/WSL:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

PowerShell 5.1:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/ready
```

`/health` chỉ xác nhận tiến trình API hoạt động. `/ready` thực hiện `SELECT 1` trên PostgreSQL và trả HTTP 503 khi database không kết nối được.

## Xem log

Các lệnh sau dùng giống nhau trên Bash và PowerShell 5.1:

```text
docker compose logs --tail=100
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
docker compose logs -f mosquitto
```

Nhấn Ctrl+C để ngừng theo dõi log; thao tác này không dừng container.

## Phát telemetry mô phỏng

Sau khi Mosquitto hoạt động, chạy simulator từ terminal khác:

```bash
cd simulator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py --count 10 --interval 1
```

PowerShell 5.1:

```powershell
Set-Location .\simulator
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
python .\simulator.py --count 10 --interval 1
```

Payload luôn có `simulated: true` và schema `bootstrap-telemetry-v0`. Đây là đề xuất bootstrap trong khi `INTERFACES.md` còn DRAFT, không phải số đo thật hoặc contract G02 đã chốt. Cách cấu hình broker/xác thực/topic và lệnh subscriber xác nhận 10 bản tin nằm trong `simulator/README.md`.

## Dừng môi trường

Bash hoặc PowerShell 5.1, development mode:

```text
docker compose down
```

LAN demo mode:

```text
docker compose -f compose.yaml -f compose.lan.yaml down
```

Lệnh trên giữ named volume PostgreSQL. Không dùng `docker compose down -v` nếu muốn giữ dữ liệu local.

Chi tiết từng phần nằm trong `backend/README.md`, `frontend/README.md`, `simulator/README.md` và `infra/README.md`. Quy trình branch/commit/PR nằm trong `docs/WORKFLOW.md`.

## Cơ sở lập kế hoạch

- `IOT.pdf`: đề án kỹ thuật vườn thông minh do người dùng cung cấp; tham khảo kiến trúc, cảm biến, lọc, tưới theo nhịp và ảnh định kỳ.
- `Tài Liệu Bài Giảng & Quy Định BTL IoT.pdf`: bản ghi chú bài giảng do người dùng cung cấp; dùng định hướng hệ thống IoT và tự xây dựng frontend/backend kèm AI/ML hoặc bảo mật. Đây là bản ghi chú, không bảo đảm điểm số.
- Thời hạn 7 tuần và nhóm 3 người do chủ dự án xác định. Các ước lượng giờ, milestone và tiêu chí thử nghiệm là đề xuất của kế hoạch, không phải quy định của giảng viên.

Các PDF gốc không được đính kèm vào gói này. Giá linh kiện, tính năng dịch vụ và số liệu hiệu năng chưa được xác minh mới trong bộ kế hoạch.
