# Simulator

Trạng thái: publish telemetry bootstrap đã được kiểm tra trong TASK-000E; chưa nhận command.

`simulator.py` phát JSON mô phỏng tới MQTT broker. Mỗi payload và mỗi dòng log đều chỉ rõ đây là dữ liệu mô phỏng. Simulator chỉ hỗ trợ tích hợp phần mềm; không thay thế nghiệm thu cảm biến hoặc phần cứng thật.

## Payload bootstrap

`docs/INTERFACES.md` vẫn là DRAFT, vì vậy payload dưới đây chỉ là đề xuất `bootstrap-telemetry-v0`, chưa phải contract G02 đã thống nhất:

```json
{
  "schema": "bootstrap-telemetry-v0",
  "simulated": true,
  "device_id": "node_01",
  "sequence": 1,
  "measured_at": "2026-09-13T10:00:00.000Z",
  "temperature_c": 27.31,
  "air_humidity_pct": 68.42,
  "soil_moisture_pct": 45.18
}
```

Các số trong ví dụ chỉ minh họa định dạng JSON, không phải kết quả đo. Simulator dùng QoS 0 và `retain=false` như mặc định bootstrap; QoS/retained chính thức vẫn phải chốt ở G02.

## Cấu hình

Tham số CLI được ưu tiên hơn biến môi trường.

| Nội dung | CLI | Biến môi trường | Mặc định |
| --- | --- | --- | --- |
| Broker | `--broker` | `MQTT_BROKER_HOST` | `127.0.0.1` |
| Port | `--port` | `MQTT_BROKER_PORT` | `1883` |
| Username | `--username` | `MQTT_USERNAME` | không có |
| Password | `--password` | `MQTT_PASSWORD` | không có |
| Topic | `--topic` | `MQTT_TOPIC` | `garden/<device_id>/telemetry` |
| Device ID | `--device-id` | `DEVICE_ID` | `node_01` |
| Chu kỳ gửi | `--interval` | `TELEMETRY_INTERVAL_SECONDS` | `2` giây |
| Số bản tin | `--count` | `TELEMETRY_MESSAGE_COUNT` | `0` — gửi liên tục |

`--count 10` gửi đúng 10 bản tin rồi dừng. `--count 0` gửi liên tục và dừng gọn khi nhấn Ctrl+C. Khi broker cần xác thực, nên đặt password bằng biến môi trường để tránh lưu trong lịch sử lệnh.

## Chạy trên Linux/macOS

```bash
cd simulator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py --count 10 --interval 1
```

## Chạy trên Windows PowerShell 5.1

Từ thư mục gốc `smart-garden-plan`:

```powershell
Set-Location .\simulator
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt

$env:MQTT_BROKER_HOST = "127.0.0.1"
$env:MQTT_BROKER_PORT = "1883"
$env:DEVICE_ID = "node_01"
$env:TELEMETRY_INTERVAL_SECONDS = "1"
$env:TELEMETRY_MESSAGE_COUNT = "10"

python .\simulator.py
```

Nếu broker yêu cầu xác thực:

```powershell
$env:MQTT_USERNAME = "<username>"
$env:MQTT_PASSWORD = "<password>"
python .\simulator.py
```

Không đưa username/password thật vào Git hoặc ảnh chụp log.

## Xác nhận đủ 10 bản tin bằng subscriber thật

Khởi động Mosquitto từ thư mục gốc, sau đó mở subscriber trước khi chạy simulator:

```bash
docker compose up -d mosquitto
docker compose exec mosquitto mosquitto_sub \
  -h 127.0.0.1 \
  -t garden/node_01/telemetry \
  -C 10 \
  -v
```

Trong terminal khác:

```bash
cd simulator
python simulator.py --count 10 --interval 1
```

`mosquitto_sub -C 10` chỉ thoát sau khi nhận đủ 10 bản tin. Đối chiếu `sequence` từ 1 đến 10 và xác nhận mọi payload có `simulated: true`. Trên PowerShell 5.1, chạy lệnh subscriber trên một dòng:

```powershell
docker compose exec mosquitto mosquitto_sub -h 127.0.0.1 -t garden/node_01/telemetry -C 10 -v
```

## Kiểm tra không cần broker

```bash
cd simulator
python -m unittest discover -s tests -v
python simulator.py --help
```

TASK-000D chưa nhận command, gửi ACK/state hoặc lưu PostgreSQL. Không dùng simulator để đánh dấu phần cứng thật là đã nghiệm thu.
