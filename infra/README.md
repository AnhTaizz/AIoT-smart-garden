# Hạ tầng

Trạng thái: có khung Docker Compose cho development; chưa có hạ tầng triển khai production.

`compose.yaml` ở thư mục gốc chạy bốn service:

- `mosquitto`: MQTT broker dùng cấu hình `infra/mosquitto/mosquitto.conf`.
- `postgres`: PostgreSQL với healthcheck và named volume `postgres_data`.
- `backend`: FastAPI với hai endpoint `/health` và `/ready`.
- `frontend`: build React/TypeScript và phục vụ bằng Nginx; `/api` được proxy nội bộ tới backend.

## Cấu hình và khởi động

Từ root repository:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

`.env.example` chỉ chứa giá trị mẫu dành cho development. `.env` bị Git bỏ qua và không được chứa secret dùng thật.

Mặc định chỉ hai dịch vụ cần cho local mobile demo được mở ra LAN tin cậy:

| Service | Cổng mặc định | Ghi chú |
| --- | --- | --- |
| Mosquitto | `1883` | Bind `0.0.0.0`, anonymous, chỉ dùng Wi-Fi/hotspot demo tin cậy |
| PostgreSQL | `5432` | Bind `127.0.0.1`; dữ liệu giữ trong named volume |
| FastAPI | `8000` | Bind `127.0.0.1`; endpoint health/readiness |
| Frontend | `5173` | Bind `0.0.0.0`; dashboard React qua Nginx |

Trên laptop, trình duyệt mở `http://127.0.0.1:5173`. Điện thoại cùng LAN mở `http://<IP_LAN_LAPTOP>:5173`; ESP32 dùng `<IP_LAN_LAPTOP>:1883` làm broker. Chỉ Nginx trong mạng Compose dùng `http://backend:8000`; hostname `backend` không dùng trên điện thoại hoặc ESP32.

`FRONTEND_BIND_ADDRESS` và `MQTT_BIND_ADDRESS` có thể đổi trong `.env`. Chỉ cho phép inbound `5173` và `1883` trên mạng Private; cấu hình anonymous hiện tại không được dùng trên Wi-Fi công cộng hoặc public Internet. Backend vẫn chưa kết nối MQTT; Mosquitto mới là nền tảng cho task tích hợp tiếp theo.

Dừng container nhưng giữ dữ liệu PostgreSQL:

```bash
docker compose down
```

ESP32/ESP32-CAM chạy firmware trên thiết bị, không chạy trong container. `docs/INTERFACES.md` vẫn là bản nháp và TASK-000B không chốt MQTT/API contract.
