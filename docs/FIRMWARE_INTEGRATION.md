# Kiểm tra repository và tích hợp ESP32 — 2026-11-01

**Cập nhật chuyển ESP32 thật:** supervisor đã có quyền AUTO theo device ID và
giao diện đã phân biệt `real_device`/`simulator_only`. Xem
[quy trình cấu hình và kết quả test](ESP32_REAL_SETUP.md). Các nhận định về việc
chỉ cho simulator bên dưới là lịch sử trước thay đổi này. Chưa bật AUTO, nạp board
hay thử bơm thật; cấu hình/hiệu chuẩn và nghiệm thu vẫn cần hoàn tất.

**Cập nhật sau merge main `0b039d6`:** repository đã có
[supervisor AI tưới](AI_IRRIGATION.md), API cấu hình và migration `004_irrigation.sql`.
Supervisor hiện chỉ cho simulator, chặn số đo `simulated:false`, giữ MQTT v1 và
không yêu cầu AUTO cục bộ trên ESP32. Các nhận định "chưa có AI quyết định tưới"
ở phần kiểm tra ban đầu bên dưới là lịch sử trước merge; không còn mô tả code hiện tại.
Vòng AUTO cho phần cứng thật vẫn chưa được bật hoặc nghiệm thu. Merge này không
gỡ giới hạn simulator, không bật AUTO và không điều khiển phần cứng.
Kiểm tra lại sau merge: backend **109 passed**, frontend **20 passed** và production
build qua, native firmware **95 kiểm tra qua**; editor không báo lỗi. Không chạy
lại E2E PostgreSQL/MQTT hoặc gọi model Kaggle thật trong phiên merge này.

**Cập nhật theo yêu cầu dùng Arduino IDE:** đã bỏ cấu hình PlatformIO khỏi project;
entrypoint hiện là [SmartGarden.ino](../firmware/SmartGarden/SmartGarden.ino).
Watchdog hỗ trợ ESP32 core 3.x đã cài trên máy. Các lệnh build PlatformIO phía dưới
chỉ là bằng chứng lịch sử của phiên triển khai trước, không còn là hướng dẫn chạy.
Cách Verify/Upload và cấu hình mới nằm trong [README firmware](../firmware/README.md).
Không gỡ cài đặt công cụ toàn máy hoặc các Python environment đang dùng chung.

## Kiểm thử sau chuyển đổi Arduino IDE

- Đã bỏ cấu hình và cache PlatformIO trong project; source/header nằm cùng sketch
  `firmware/SmartGarden`, không cần PlatformIO để build hay chạy test host.
- Compile thành công bằng Arduino CLI **1.5.1 đi kèm Arduino IDE**, board
  `esp32:esp32:esp32` (**ESP32 Dev Module**), ESP32 core **3.3.12** đang có trên máy.
  Flash 983681/1310720 byte (75%), RAM tĩnh 50100/327680 byte (15%).
- Lệnh đã chạy: `arduino-cli compile --fqbn esp32:esp32:esp32 --libraries firmware/build/libraries --build-path firmware/build/arduino-dry-run firmware/SmartGarden`.
  Hai thư viện phiên bản đã ghim được đặt trong thư mục build tạm đã ignore để
  kiểm tra; khi dùng GUI, cài chúng bằng Library Manager theo README.
- Chạy lại native tests: **95 kiểm tra qua** sau khi chuyển đường dẫn header.
  Test nhận compiler g++ và đường dẫn ArduinoJson qua tham số, không tự tìm PlatformIO.
- Watchdog có nhánh API cho core 2.x/3.x và kiểm tra lỗi khởi tạo. Bản Arduino IDE
  lần này được kiểm tra với core 3.3.12; không tuyên bố đã build mọi phiên bản core.
- Editor không báo lỗi. Chỉ compile/test, không upload, không mở serial hay gửi ON.
- `.env.example` đã chú thích rõ là cấu hình server/Docker; cấu hình board nằm ở
  `firmware/SmartGarden/config.local.h` đã ignore. Dry-run vẫn bật mặc định.

## Kiến trúc và bằng chứng

Đã đọc [AGENTS](../AGENTS.md), [AGENT_TASK](../AGENT_TASK.md), README root/module,
[INTERFACES](INTERFACES.md), PROJECT_STATE, ROADMAP, phân công embedded; đối chiếu
backend main/config/schemas/ingest/MQTT/repository/migrations, simulator/device/tests,
frontend App/API/tests, AI server/chat adapter/tests, Compose và Mosquitto.
Không có source firmware, config, PlatformIO, diagram Wokwi hoặc decision model
trước thay đổi này: thư mục firmware chỉ có README. Snapshot trong hội thoại không
phải file hiện hữu của checkout. Git ban đầu chỉ có hai file hướng dẫn untracked;
không sửa/xóa chúng và không thay đổi phần cứng.

```text
AHT20 + ADC34 → ESP32 → telemetry-v1 → Mosquitto → FastAPI → PostgreSQL
                                                              ↓ REST
                                                        React / điện thoại

AI quyết định tưới (CHƯA CÓ implementation/contract)
             → API command đã có → PostgreSQL cấp sequence/boot/expiry
             → MQTT command-v1 → ESP32 kiểm tra → relay GPIO26
             ← ACK + state ← ESP32 (timeout/OFF/mất mạng cục bộ)

React → FastAPI chat → Kaggle Qwen3 hiện tại: chỉ tư vấn, không phát command
```

Người dùng xác nhận AHT20, soil, CW-020 qua hai diode và bơm chạy thật thành công.
Đó là bằng chứng phần cứng người dùng báo, không phải chứng nhận điện hoặc chứng
minh firmware mới đã chạy end-to-end. PROJECT_STATE cũ là bản ghi lịch sử tháng 9;
không cập nhật milestone PASS thay cho nghiệm thu mới.

## Khoảng trống và cách xử lý

| Phát hiện trước sửa | Xử lý / phần còn thiếu |
| --- | --- |
| Chưa có firmware thực tế trong repo | Thêm Arduino IDE, core testable, driver và cấu hình |
| README firmware cũ yêu cầu hysteresis/Auto tại ESP32 | Bỏ định hướng đó khỏi hướng dẫn firmware mới; mọi quyết định tưới ở server |
| Backend/simulator đã có G02 v1, ACK + state độc lập | Giữ topic/schema/reason/correlation; không đổi SQL hoặc REST |
| Contract G02 còn DRAFT | Giữ trạng thái, không tự xác nhận AGREED |
| API cho phép 120 giây | Không thay contract; board từ chối >60 bằng invalid_duration |
| Chưa hiệu chuẩn probe | Mặc định error/null, log raw cho người dùng đo, không coi placeholder là số thật |
| MQTT anonymous, Compose chưa truyền credential backend | Thêm override xác thực và ACL riêng; base development giữ nguyên |
| Chưa có giờ ESP32 tin cậy | SNTP cấu hình rõ ràng; chưa sync thì ON bị chặn, timestamp null |
| AHT20 thư viện có vòng chờ BUSY vô hạn khi bus lỗi | Đọc I2C có timeout, status và CRC; lỗi không thay bằng số 0 |
| Publish QoS1 có thể poll callback lồng nhau | Callback chỉ enqueue; xử lý command tuần tự bên ngoài poll |
| Không có API/model quyết định tưới | Chưa thể hoàn tất vòng AI tự động; cần source/contract thực của chủ dự án |
| API/dashboard chưa auth; TCP MQTT/SNTP chưa mã hóa/xác thực thời gian | Chỉ LAN riêng tin cậy; không public hoặc tưới không giám sát |

## Phạm vi triển khai

Kế hoạch đã báo trước khi sửa: tạo firmware với đúng chân, giữ MQTT v1, mặc định
khóa đầu ra; tách logic để test trên host; thêm timeout/disconnect/clock/calibration;
build cả hai môi trường, regression và tài liệu vận hành an toàn.

Các file mới/chỉnh:

- [SmartGarden.ino](../firmware/SmartGarden/SmartGarden.ino): sketch Arduino IDE; ArduinoJson 7.4.2 và ArduinoMqttClient 0.1.8 hỗ trợ publish QoS1.
- [SmartGarden.cpp](../firmware/SmartGarden/SmartGarden.cpp): Wi-Fi/MQTT clean reconnect, SNTP, AHT20/ADC,
  GPIO26 active-low, latch OFF trước output, safety task và task watchdog.
- [garden.h](../firmware/SmartGarden/garden.h): parser, strict UTC/calendar/type/ID,
  dedup/order/boot/expiry/busy/OFF, elapsed unsigned, guard đầu ra và decode sensor.
- [payloads.h](../firmware/SmartGarden/payloads.h): state/telemetry v1 dùng chung trong test.
- [config.h](../firmware/SmartGarden/config.h), [mẫu cục bộ](../firmware/SmartGarden/config.local.example.h):
  đúng chân 21/22/34/26, không secret, dry-run và control disabled mặc định.
- [test_runtime.cpp](../firmware/tests/test_runtime.cpp), [run.ps1](../firmware/tests/run.ps1):
  kiểm thử native cùng source, không GPIO/MQTT, xuất fixture để validator backend đọc.
- [compose.secure.yaml](../compose.secure.yaml), [broker config](../infra/mosquitto/mosquitto.secure.conf),
  [ACL](../infra/mosquitto/control.acl), [.env.example](../.env.example), [.gitignore](../.gitignore):
  option broker riêng với hai account/ACL, ignore config cục bộ.
- [README firmware](../firmware/README.md): cấu hình, hiệu chuẩn, build, upload chỉ
  dưới dạng hướng dẫn và test thủ công bắt đầu bằng **rút adapter bơm**.

Firmware không phát ON khi flash/connect/telemetry. Dry-run không tạo relay ON giả;
lệnh ON hợp lệ bị safety_lock, số đo sensor vật lý vẫn simulated:false. ACK/state
giữ command_id và sequence; boot ID mới mỗi reboot. OFF khi chưa có giờ vẫn áp dụng.

Giới hạn dedup hữu hạn: giữ 128 ACK đầu mỗi boot, không evict; khi đầy khóa ON mới
tới reboot, OFF vẫn dùng được. Các ID mới sau khi đầy không được cache (ACK timestamp
có thể khác khi retry). Không tuyên bố hỗ trợ dedup vô hạn. Parser UTC nhận đúng
dạng Z backend đang phát, chưa hỗ trợ offset ISO khác. Cả hai điểm cần ghi rõ khi
nhóm chốt G02 cho vận hành dài hạn.

## Kiểm thử phần mềm trước chuyển đổi Arduino IDE

Các lệnh đã dùng (Windows, interpreter hiện có tại
`C:/Users/ADMIN/.platformio/penv/Scripts/python.exe`; `pio` cũng ở thư mục Scripts):

| Lệnh / kiểm tra | Kết quả |
| --- | --- |
| `pio run -d firmware -e esp32_dry_run -e esp32_real` | Build cả hai cấu hình ESP32; không upload |
| `./firmware/tests/run.ps1` | 95 kiểm tra C++ qua, gồm guard thật dùng trên ESP32 |
| `native-tests.exe --fixtures` → backend Pydantic | 4 fixture ACK/state/telemetry được validator thật chấp nhận |
| `python -m pytest -q tests/test_validation.py tests/test_chat.py` tại backend | 96 passed |
| `python -m unittest discover -s tests -v` tại simulator | 31 passed |
| `python -m pytest -q ai/tests` từ root | 15 passed |
| `npm ci --no-audit --no-fund`, `npm test`, `npm run build` tại frontend | 18 passed; TypeScript/Vite build qua |
| `docker compose --env-file .env.example config --quiet` | Qua |
| LAN + secure override config với password placeholder chỉ để parse | Qua; không tạo credential thật |
| Editor diagnostics | Không có lỗi |
| `docker info` | Không kết nối được Docker Desktop Linux Engine |

Test C++ bao gồm startup OFF, ON/OFF, 60 giây và >60, timer overflow, deadline bằng
hiện tại, ngày không hợp lệ, JSON hỏng/trailing bytes/null/action thiếu/sai kiểu,
wrong device/boot, duplicate ACK nguyên bản, superseded/busy, OFF bỏ qua clock/boot/expiry,
reboot, mất MQTT/Wi-Fi, guard không được ON ở dry-run, lease mạng quá hạn, retained
ON, cache đầy, AHT20 CRC/decode, ADC lỗi/chưa hiệu chuẩn và sensor error/null payload.
Đây là test logic; chưa giả lập toàn bộ FreeRTOS/scheduler/Wi-Fi/I2C vật lý.

Không chạy E2E Mosquitto–PostgreSQL–API vì Docker Engine không hoạt động. Không gọi
Kaggle thật, không phát MQTT ON, không mở serial/nạp/reset board, không cấp điện bơm.
Các test frontend/backend dùng mock trong process; không điều khiển node_01 thật.
Có một warning deprecation từ Starlette/AnyIO trong test, không có test thất bại.

## Việc cần có để đóng vòng AI và nghiệm thu

1. Source/contract của AI irrigation: model/artifact/version, input/preprocessing,
   output quyết định và thời lượng, quy tắc freshness/error/cooldown, quyền bật Auto.
   Repository hiện chỉ có Qwen3 chat completion tư vấn và đã chủ đích cấm điều khiển bơm.
   Không lấy ngôn ngữ tự do chatbot làm lệnh vật lý.
2. Khi có quyết định đã được validate ở server, dùng API `POST /devices/{id}/commands`
   hiện có, không để model tự cấp command_id/sequence/target_boot_id. Backend đã
   quản lý các trường đó, lưu pending và đối chiếu ACK + state để xác nhận applied.
3. Khởi động stack test cô lập, dùng device_id riêng; kiểm tra MQTT QoS1, ingest,
   PostgreSQL/REST và command lifecycle với fixture/runtime trước thử board thật.
4. Người dùng hiệu chuẩn probe và kiểm tra board theo README, **adapter bơm rút trước**.
   Đo thời gian OFF khi timeout/disconnect/reset. Chỉ flash và thử ON sau chấp thuận riêng.
5. Xác minh mạch hai diode và giới hạn điện của module/GPIO, dòng khởi động/stall bơm,
   cách điện chống nước, nguồn cắt tay và bảo vệ nguồn độc lập cho dùng lâu dài.

Safety task 10ms, lease mạng 500ms và watchdog 3 giây là bảo vệ phần mềm, không phải
cam kết cắt điện độc lập ở đúng 60 giây. Không thể đo được relay/contact/water flow
từ GPIO output; relay dính hoặc brownout cần biện pháp phần cứng. Chưa nghiệm thu
tích hợp AI–ESP32 thật và chưa cho phép vận hành không giám sát.
