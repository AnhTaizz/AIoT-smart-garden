# Frontend

Trạng thái: dashboard cơ bản của TASK-000C; chưa có dữ liệu cảm biến hoặc điều khiển thiết bị.

Frontend dùng React, TypeScript và Vite. Dashboard tiếng Việt hiện có:

- Trạng thái backend lấy từ `GET /health`.
- Trạng thái PostgreSQL lấy từ `GET /ready`.
- Khu vực nhiệt độ, độ ẩm không khí, độ ẩm đất, máy bơm và ảnh cây.
- Thông báo `Chưa có dữ liệu` ở mọi khu vực chưa có API nghiệp vụ.
- Nút bật/tắt bơm bị vô hiệu hóa vì command và giới hạn an toàn chưa được triển khai.

Không có số liệu cảm biến hoặc trạng thái bơm giả trong giao diện.

## Chạy cùng Docker Compose

Từ thư mục gốc `smart-garden-plan/`:

```bash
cp .env.example .env
docker compose up --build -d
```

Mở <http://127.0.0.1:5173>. `FRONTEND_PORT` trong `.env` đổi cổng trình duyệt truy cập.

Frontend gọi URL tương đối `/api`. Nginx trong container proxy đường dẫn này tới `http://backend:8000`, trong đó `backend` là hostname nội bộ Docker và không phải địa chỉ dành cho trình duyệt.

## Chạy development ngoài Docker

Yêu cầu Node.js 22 và npm:

```bash
npm install
npm run dev
```

Vite phục vụ tại <http://127.0.0.1:5173> và proxy `/api` tới backend local tại <http://127.0.0.1:8000>. Có thể đặt `VITE_API_BASE_URL` thành một URL khác khi build, nhưng URL đó phải truy cập được từ trình duyệt và backend cần cấu hình CORS nếu khác origin.

Kiểm tra:

```bash
npm test
npm run build
```

Test hiện có xác nhận khi fetch thất bại, dashboard báo mất kết nối/không thể kiểm tra, không tạo số đo giả và giữ nút điều khiển ở trạng thái disabled.

Telemetry, command, ảnh thật và polling định kỳ vẫn ngoài phạm vi TASK-000C. `docs/INTERFACES.md` tiếp tục là bản nháp.
