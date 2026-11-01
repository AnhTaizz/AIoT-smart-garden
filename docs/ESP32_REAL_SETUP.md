# Chuyển Smart Garden sang ESP32 thật

Đường chạy: **AHT20/soil → ESP32 → MQTT → backend → AI quyết định → command MQTT →
ESP32 thực thi → ACK/state**. ESP32 không tự đặt ngưỡng hay tự quyết định tưới.
Snapshot giao diện đính kèm không được sửa; source thay đổi nằm trong repository.

## Những phần đã chuyển

- Supervisor cho phép số đo thật khi ID nằm trong `IRRIGATION_REAL_DEVICE_IDS`,
  có cấu hình credential broker, sensor OK, UTC/boot/state hợp lệ.
- `node_01` trong mẫu cấu hình server là ESP32 thật; simulator phải dùng ID khác.
  Dữ liệu simulator dùng chung ID đã được chỉ định thật bị chặn cả trước và sau gọi AI.
- Giao diện đọc `execution_scope` từ server, hiển thị **ESP32 THẬT**, có nút
  **Bật AUTO (ESP32 thật)**; không tự bật AUTO khi mở trang hay khi nhận telemetry.
- JSON quyết định, budget/cooldown/lease, UUID/order/expiry, ACK/state và giới hạn
  60 giây hiện có được giữ nguyên. Không thêm schema MQTT hay migration.

## Cấu hình server

1. Tạo `.env` từ [.env.example](../.env.example) nếu chưa có; giữ
   `IRRIGATION_REAL_DEVICE_IDS=node_01`. Có thể để rỗng để khóa lại AUTO phần cứng.
2. Chuẩn bị Mosquitto private và hai account theo [README firmware](../firmware/README.md#broker-riêng-có-xác-thực):
   backend `garden_backend`, board `esp32_node_01`, password riêng và ACL. Điền
   `MQTT_USERNAME`/`MQTT_PASSWORD` backend vào `.env`; không gửi password vào chat/Git.
3. Khi sẵn sàng vận hành, chủ hệ thống khởi động Docker Desktop và stack:

   ```powershell
   docker compose -f compose.yaml -f compose.lan.yaml -f compose.secure.yaml config --quiet
   docker compose -f compose.yaml -f compose.lan.yaml -f compose.secure.yaml up --build -d
   ```

   Đây là lệnh hướng dẫn, chưa chạy trong phiên coding. Backend restart luôn yêu cầu
   bật AUTO lại. Chỉ dùng LAN riêng có người giám sát; API/dashboard hiện chưa có
   authentication, nên người truy cập được dashboard vẫn có thể yêu cầu lệnh.
   Backend chỉ kiểm tra credential đã cấu hình, không tự chứng minh broker/ACL an toàn.

## Cấu hình ESP32 bằng Arduino IDE

**Rút adapter 5V cấp bơm trước khi kiểm tra.** Nguồn bơm độc lập với USB ESP32.

1. Mở [SmartGarden.ino](../firmware/SmartGarden/SmartGarden.ino), chọn ESP32 Dev Module.
   Library Manager: ArduinoJson 7.4.2, ArduinoMqttClient 0.1.8.
2. Trong file `firmware/SmartGarden/config.local.h` đã ignore, điền Wi-Fi, IP LAN laptop
   làm `GARDEN_MQTT_HOST`, credential account board và NTP host truy cập được.
   `.env` chỉ dành cho server, không được Arduino IDE đọc.
3. Giữ `GARDEN_DRY_RUN=1`, `GARDEN_CONTROL_ENABLED=0` để kiểm tra OFF trước.
   Hai giá trị `GARDEN_SOIL_DRY/WET` phải là số ADC **đo thực tế**; mặc định 0 báo
   lỗi/null và supervisor không tưới. Đọc `soil_adc_raw` để hiệu chuẩn, không dùng
   3200/1400 trong snapshot như số đo đã xác nhận.
4. Bấm Verify để build. Chỉ khi chủ thiết bị cho phép mới Upload, mở Serial Monitor
   115200 và kiểm tra relay OFF, clock đồng bộ, telemetry `simulated:false`,
   `sensor_status` đều OK, state/boot mới trên server. Không chạy simulator cùng ID.
5. Adapter bơm vẫn rút. Sau xác nhận OFF và kiểm tra điện của mạch relay/diode,
   chủ thiết bị mới đặt `GARDEN_DRY_RUN=0`, `GARDEN_CONTROL_ENABLED=1`, Verify và
   Upload lại khi được cho phép. Thử relay ON ngắn/timeout/OFF/disconnect dưới giám sát;
   không coi compile thành công là bằng chứng relay đã nhả đúng.

## Bật AUTO sau kiểm tra phần cứng

1. Chọn đúng `node_01` và kiểm tra giao diện hiện **ESP32 THẬT**. Nếu vẫn hiện simulator,
   kiểm tra biến môi trường backend và recreate container; không sửa nhãn giao diện để bỏ chặn.
2. Điền cây/giai đoạn/giá thể và giới hạn theo thử nghiệm thật. Không tự lấy số ví dụ
   simulator làm ngưỡng an toàn. AUTO không được chạy khi telemetry thiếu/null/stale,
   boot lệch, clock chưa sync, relay chưa OFF hoặc lệnh trước chưa rõ kết quả.
3. Chỉ sau chấp thuận riêng cho bơm thật mới nối adapter. Người vận hành xác nhận đã
   hiệu chuẩn/kiểm tra OFF và đang giám sát, rồi chủ động bấm **Bật AUTO (ESP32 thật)**.
   Giao diện chỉ gửi cấu hình bật; server quyết định có tưới hay không và bao lâu.
4. Theo dõi quyết định → command pending → ACK/state → applied/rejected/timeout.
   **Chuyển MANUAL và gửi STOP** tắt điều phối trước rồi yêu cầu OFF. Timeout API
   không chứng minh bơm đã tắt; timer local và ngắt nguồn tay vẫn cần thiết.

Hai diode là cấu hình người dùng thử thành công, chưa chứng minh an toàn điện lâu dài.
Task watchdog/timer chỉ là bảo vệ phần mềm, không có hard cutoff độc lập; không bật
tưới không giám sát. ACK/state không đo dòng nước, dòng motor hoặc tiếp điểm dính.

## Trạng thái kiểm tra lần chuyển đổi

- Backend: 136 test qua, gồm 27 ca bổ sung cho quyền ESP32 thật, dữ liệu sensor/time
  và pipeline gọi AI rồi kiểm tra lại trước dispatch.
- Frontend: 25 test qua; TypeScript/Vite production build qua.
- Native firmware: 95 kiểm tra qua; giữ nguyên source điều khiển và các chân.
- Docker Engine chưa hoạt động; chưa chạy lại E2E PostgreSQL/MQTT hoặc gọi Qwen thật.
- File cấu hình board cục bộ vẫn dry-run/control disabled, dry/wet bằng 0. Không sửa
  số hiệu chuẩn hoặc credential người dùng. Không nạp, mở serial hay gửi MQTT ON.
