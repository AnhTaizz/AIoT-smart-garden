# Simulator

Trạng thái: đã triển khai hai chiều theo bản đề xuất `v1` trong
[`docs/INTERFACES.md`](../docs/INTERFACES.md), nhưng G02 vẫn là **DRAFT** chờ
Thành, Tài và Toản xác nhận. Simulator là thiết bị tham chiếu cho M1, không thay
thế kiểm thử ESP32, cảm biến, relay hoặc bơm thật.

`simulator.py` dùng cùng bốn topic với thiết bị:

| Topic | Hướng | QoS | Retained |
| --- | --- | --- | --- |
| `garden/<id>/telemetry` | simulator → backend | 0 | không |
| `garden/<id>/control` | backend → simulator | 1 | không |
| `garden/<id>/ack` | simulator → backend | 1 | không |
| `garden/<id>/state` | simulator → backend | 1 | không |

MQTT dùng clean session. Mỗi lần chạy có `boot_id` mới, phát state ngay sau khi
kết nối, telemetry luôn có `simulated: true`, rồi nhận command và trả ACK/state.

## Telemetry v1

```json
{
  "schema": "telemetry-v1",
  "simulated": true,
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "sequence": 1,
  "clock_synced": true,
  "measured_at": "2026-09-25T09:10:00.000Z",
  "uptime_ms": 1250,
  "temperature_c": 27.31,
  "air_humidity_pct": 68.42,
  "soil_moisture_pct": 45.18,
  "sensor_status": {"aht20": "ok", "soil": "ok"}
}
```

Các số chỉ minh họa định dạng, không phải kết quả đo. `--sensor-error` đặt giá
trị cảm biến tương ứng thành `null` cùng trạng thái `error`. `--clock-unsynced`
đặt các timestamp thiết bị thành `null` và làm `pump_on` bị từ chối bằng
`clock_unsynced`; `pump_off` vẫn được áp dụng.

## Xử lý command

Logic thuần nằm ở `device.py` để có thể unit test. Simulator:

- giữ nguyên `command_id`, kiểm tra `target_boot_id` và `expires_at` trước ON;
- từ chối ON cũ hơn mốc STOP bằng `command_sequence`;
- không chạy lại hoặc kéo dài bộ đếm khi nhận trùng `command_id`;
- trả `busy` cho ON khác khi bơm đang chạy;
- ưu tiên OFF kể cả khi clock chưa đồng bộ, lệnh đã hết hạn hoặc qua reboot;
- tự chuyển relay về `off` khi hết `duration_seconds` và phát state mới.
- tắt relay và hủy timer ngay khi mất MQTT; reconnect phát state `off` nhưng
  giữ mốc thứ tự/bộ nhớ command của boot để ON trùng không chạy lại.

`applied` ở đây chỉ mô phỏng output relay, không chứng minh có nước chảy.

## Cấu hình

CLI ưu tiên hơn biến môi trường.

| Nội dung | CLI | Biến môi trường | Mặc định |
| --- | --- | --- | --- |
| Broker | `--broker` | `MQTT_BROKER_HOST` | `127.0.0.1` |
| Port | `--port` | `MQTT_BROKER_PORT` | `1883` |
| Username | `--username` | `MQTT_USERNAME` | không có |
| Password | `--password` | `MQTT_PASSWORD` | không có |
| Device ID | `--device-id` | `DEVICE_ID` | `node_01` |
| Boot ID cố định để test | `--boot-id` | `BOOT_ID` | sinh mới |
| Chu kỳ telemetry | `--interval` | `TELEMETRY_INTERVAL_SECONDS` | `2` giây |
| Số telemetry | `--count` | `TELEMETRY_MESSAGE_COUNT` | `0` — liên tục |
| Heartbeat state | `--state-heartbeat` | `STATE_HEARTBEAT_SECONDS` | `10` giây |
| Giới hạn bơm cục bộ | `--pump-max-seconds` | `PUMP_MAX_SECONDS` | `60` giây |
| Đồng hồ | `--clock-unsynced` | `CLOCK_SYNCED` | dùng UTC của máy chạy |
| Lỗi cảm biến | `--sensor-error` | `SENSOR_ERROR` | `none` |

Không đưa username/password thật vào source hoặc ảnh chụp log.

## Chạy

Linux/macOS:

```bash
cd simulator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py --count 10 --interval 1
```

Windows PowerShell 5.1, từ root repository:

```powershell
Set-Location .\simulator
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
python .\simulator.py --count 10 --interval 1
```

Simulator phải kết nối cùng broker với backend và dùng một `device_id` không
đồng thời được ESP32 thật sử dụng. Với `--count 0`, nhấn Ctrl+C để dừng gọn;
nếu relay đang `on`, simulator phát state `off` trước khi thoát.

## Kiểm tra

Không cần broker:

```bash
cd simulator
python -m unittest discover -s tests -v
python simulator.py --help
```

Kiểm tra tích hợp cần stack Compose đang chạy. Sau khi simulator đã phát state,
gửi `POST /devices/<id>/commands`, poll `GET /commands/<command_id>`, rồi kiểm
tra `GET /devices/<id>/state` và telemetry history. Kết quả thành phần không
được dùng để ghi M1 PASS khi UI và smartphone LAN thật chưa được kiểm tra.
