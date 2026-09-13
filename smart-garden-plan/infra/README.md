# Hạ tầng

Trạng thái: có khung Docker Compose cho development; chưa có hạ tầng triển khai production.

`compose.yaml` ở thư mục gốc chạy bốn service:

- `mosquitto`: MQTT broker dùng cấu hình `infra/mosquitto/mosquitto.conf`.
- `postgres`: PostgreSQL với healthcheck và named volume `postgres_data`.
- `backend`: FastAPI với hai endpoint `/health` và `/ready`.
- `frontend`: build React/TypeScript và phục vụ bằng Nginx; `/api` được proxy nội bộ tới backend.

## Cấu hình và khởi động

Từ thư mục gốc `smart-garden-plan/`:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

`.env.example` chỉ chứa giá trị mẫu dành cho development. `.env` bị Git bỏ qua và không được chứa secret dùng thật.

Các cổng host mặc định chỉ bind vào `127.0.0.1`:

| Service | Cổng mặc định | Ghi chú |
| --- | --- | --- |
| Mosquitto | `1883` | Anonymous, chỉ dùng local development |
| PostgreSQL | `5432` | Dữ liệu giữ trong named volume |
| FastAPI | `8000` | Endpoint health/readiness |
| Frontend | `5173` | Dashboard React qua Nginx |

Trình duyệt mở `http://127.0.0.1:5173` và gọi `/api`. Chỉ Nginx trong mạng Compose dùng `http://backend:8000`; hostname `backend` không được đưa ra làm địa chỉ truy cập của trình duyệt.

Vì broker không mở ra LAN, ESP32 vật lý chưa thể kết nối từ máy khác. Backend của TASK-000B cũng chưa kết nối MQTT; Mosquitto mới là nền tảng cho simulator và task tích hợp sau.

Dừng container nhưng giữ dữ liệu PostgreSQL:

```bash
docker compose down
```

ESP32/ESP32-CAM chạy firmware trên thiết bị, không chạy trong container. `docs/INTERFACES.md` vẫn là bản nháp và TASK-000B không chốt MQTT/API contract.
