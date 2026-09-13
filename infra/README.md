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

Base `compose.yaml` là development mode và chỉ bind localhost:

| Service | Cổng mặc định | Ghi chú |
| --- | --- | --- |
| Mosquitto | `1883` | Bind `127.0.0.1`; anonymous development |
| PostgreSQL | `5432` | Bind `127.0.0.1`; dữ liệu giữ trong named volume |
| FastAPI | `8000` | Bind `127.0.0.1`; endpoint health/readiness |
| Frontend | `5173` | Bind `127.0.0.1`; dashboard React qua Nginx |

LAN demo dùng `compose.lan.yaml` để thay riêng port publishing của frontend và Mosquitto:

```bash
docker compose -f compose.yaml -f compose.lan.yaml up --build -d
```

Khi đó điện thoại cùng LAN mở `http://<IP_LAN_LAPTOP>:5173`; ESP32 dùng `<IP_LAN_LAPTOP>:1883` làm broker. FastAPI và PostgreSQL vẫn bind localhost; Nginx gọi `http://backend:8000` trong mạng Compose và proxy `/api` cho điện thoại.

Không hardcode IP laptop trong Compose hoặc frontend. Chỉ cho phép inbound `5173` và `1883` trên mạng Private; cấu hình anonymous hiện tại không được dùng trên Wi-Fi công cộng hoặc public Internet. Backend vẫn chưa kết nối MQTT; Mosquitto mới là nền tảng cho task tích hợp tiếp theo.

Dừng container nhưng giữ dữ liệu PostgreSQL:

```bash
docker compose down
```

ESP32/ESP32-CAM chạy firmware trên thiết bị, không chạy trong container. `docs/INTERFACES.md` vẫn là bản nháp và TASK-000B không chốt MQTT/API contract.
