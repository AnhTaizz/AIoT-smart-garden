# ESP32 Smart Garden — MQTT v1

Firmware Arduino IDE cho **ESP32 Dev Module** (DevKit V1), một node.
ESP32 chỉ đo, kiểm tra/thực thi command và bảo vệ cục bộ. Không có ngưỡng tưới,
hysteresis hay quyết định AI trên ESP32. Giao thức giữ nguyên
[G02 v1](../docs/INTERFACES.md), vẫn DRAFT; không tự xác nhận G02/M2.
Xem [báo cáo tích hợp](../docs/FIRMWARE_INTEGRATION.md) để biết khoảng trống AI Server.

| Phần | Source |
| --- | --- |
| GPIO, Wi-Fi, MQTT, I2C, SNTP, safety task, watchdog | [SmartGarden.cpp](SmartGarden/SmartGarden.cpp) |
| Kiểm tra lệnh, bộ đếm, guard đầu ra, ADC/AHT20 decode | [garden.h](SmartGarden/garden.h) |
| Telemetry/state dùng chung cho board và test | [payloads.h](SmartGarden/payloads.h) |
| Chân và mặc định khóa điều khiển | [config.h](SmartGarden/config.h) |
| Mẫu cấu hình cục bộ | [config.local.example.h](SmartGarden/config.local.example.h) |
| Sketch mở trong Arduino IDE | [SmartGarden.ino](SmartGarden/SmartGarden.ino) |
| Test C++ không có GPIO/MQTT | [test_runtime.cpp](tests/test_runtime.cpp) |

## Chân và nguồn thật

- AHT20: 3V3/GND, SDA21/SCL22, địa chỉ 0x38. Đọc trực tiếp I2C có timeout,
  cờ calibrated/busy và CRC-8 AHT20; không dùng vòng chờ BUSY vô hạn.
- Soil Capacitive v1.2: 3V3/GND/AOUT34, ADC1 12-bit, attenuation 11dB.
- CW-020: VCC rail USB 5V, GND chung ESP32; GPIO26 qua **hai diode nối tiếp**,
  đầu có vạch/cathode hướng GPIO26, theo cấu hình người dùng đã thử.
- Bơm: adapter 5V/5A riêng (+) → COM, NO → dây đỏ; dây đen → adapter (−).
  Không lấy điện bơm từ ESP32. Không có sơ đồ Wokwi trong repository hiện tại.

Hai diode đã hoạt động theo người dùng nhưng chưa được đo dòng injection,
transient hoặc xác minh mạch IN. Không coi đây là bộ chuyển mức đã chứng minh an toàn.
Không nối trực tiếp IN về GPIO26: HIGH 3.3V đã từng không nhả relay.

## Cấu hình và Verify trong Arduino IDE

1. Mở [SmartGarden.ino](SmartGarden/SmartGarden.ino) bằng Arduino IDE.
   Giữ các file `.cpp`/`.h` đi kèm trong cùng thư mục `SmartGarden`.
2. Boards Manager: cài **esp32 by Espressif Systems**, chọn **ESP32 Dev Module**.
   Phiên chuyển đổi này kiểm tra bằng core **3.3.12** đã cài trên máy người dùng.
3. Library Manager: cài **ArduinoJson 7.4.2** và **ArduinoMqttClient 0.1.8**.
   WiFi, Wire, SNTP và FreeRTOS có sẵn trong ESP32 core. AHT20 được đọc trực tiếp,
   không cần cài thêm Adafruit AHTX0 cho sketch này.
4. Copy [config.local.example.h](SmartGarden/config.local.example.h) thành
   `config.local.h` **trong cùng thư mục sketch**, chỉ khi chưa có cấu hình cục bộ.
   File cục bộ đã được Git ignore. Điền Wi-Fi, IP LAN broker riêng, account/password
   của board, NTP host và kết quả hiệu chuẩn đo thật.
5. Giữ `GARDEN_DRY_RUN=1`, `GARDEN_CONTROL_ENABLED=0`; bấm **Verify (✓)** để biên dịch.
   Verify không cần board/cổng COM và không nạp firmware.

[.env.example](../.env.example) dành cho server/Docker; Arduino IDE không đọc `.env`.
Backend dùng account `garden_backend`; board dùng account riêng `esp32_node_01`.
Mẫu broker xác thực/ACL nằm trong [compose.secure.yaml](../compose.secure.yaml).
Không dùng broker public, không chạy simulator cùng `node_01` với board thật.

Mặc định không có SSID/broker/secret/NTP, `GARDEN_DRY_RUN=1` và điều khiển bị khóa.
Dry-run từ chối ON hợp lệ bằng `safety_lock`; GPIO luôn OFF, không báo `applied/on`
giả. Sensor thật vẫn báo `simulated:false`. Test host không phát MQTT.
Chỉ chủ thiết bị mới chuyển `GARDEN_DRY_RUN=0` **và** `GARDEN_CONTROL_ENABLED=1`
sau khi được phép kiểm tra phần cứng, cấu hình broker riêng và đồng bộ giờ.
Cấu trúc sketch theo [quy định Arduino](https://docs.arduino.cc/arduino-cli/sketch-specification/).
SNTP host phải truy cập được qua mạng demo: có thể là dịch vụ NTP LAN trên laptop,
hoặc NTP Internet khi mạng có Internet. Firmware không tự cài NTP server.
Chỉ đặt `clock_synced:true` sau callback SNTP. Khi chưa đồng bộ: timestamp `null`,
ON → `clock_unsynced`, OFF vẫn được thực thi. SNTP/TCP không có bảo đảm chống
giả mạo trên mạng thù địch; cấu hình này dành cho LAN riêng tin cậy, chưa có TLS.

## Hiệu chuẩn và lỗi cảm biến

`GARDEN_SOIL_DRY/WET=0` nghĩa là **chưa hiệu chuẩn**: phần trăm `null`, soil `error`.
Xem `soil_adc_raw` trên serial, đo nhiều mẫu ở trạng thái khô và ướt phù hợp
giá thể/probe thực tế (không nhúng phần điện tử); điền hai endpoint đo được.
Không lấy 3200/1400 của snapshot làm kết quả đo thật. Phần trăm là thang tương đối.
ADC sát rail (≤15 hoặc ≥4080), endpoint không hợp lệ hoặc cách nhau <100 count
đều là lỗi; mẫu hợp lệ lấy trung bình 8 lần, quy đổi rồi giới hạn 0..100.
ADC có thể trôi vào vùng hợp lệ khi đứt dây; phần mềm không bảo đảm phát hiện
mọi trường hợp probe rút/disconnect. Không thêm trường MQTT raw mới; raw chỉ log serial.
AHT20 không đáp ứng, BUSY quá hạn, CRC sai hoặc ngoài miền → cả hai giá trị `null`.

## Hành vi MQTT và bảo vệ

Bốn topic `garden/<id>/{telemetry,control,ack,state}`; telemetry QoS0 mỗi 5 giây,
control/ACK/state QoS1, không retained, clean session đặt tường minh. State ngay
khi connect, sau command, khi dừng và heartbeat 10 giây. Boot ID ngẫu nhiên mới
mỗi lần khởi động, state/telemetry sequence mới; không khôi phục ON sau reboot.

Lệnh kiểm tra UUID/envelope/type/độ dài/params, boot đích, SNTP, expiry tuyệt đối,
thứ tự, duplicate, busy và safety lock. Parser chấp nhận UTC `Z` do backend phát
(giây hoặc 1..9 chữ số phần lẻ), kiểm tra ngày hợp lệ; không chấp nhận timezone
khác `Z`. ON chỉ **1..60 giây**; API hiện vẫn cho phép 120 nhưng board từ chối >60
bằng `invalid_duration`. OFF bỏ qua boot/clock/expiry/order/busy, vẫn cần envelope
hợp lệ. Retained ON bị `safety_lock` ngay cả khi chưa hết hạn.

Cache RAM giữ nguyên ACK của **128 ID đầu mỗi boot**, kể cả timestamp, qua reconnect.
Khi đầy, khóa mọi ON mới tới reboot để không evict và vô tình chạy lại ON cũ;
OFF vẫn hoạt động. ACK cho ID mới sau khi cache đầy không được lưu, nên timestamp
có thể khác khi gửi lại. Đây là giới hạn RAM cần nhóm xác nhận trước vận hành dài hạn;
không phải lưu dedup vô hạn. ID cũ trong cache không bị mất. `order_mark` không lùi.

Đầu ra OFF được nạp latch trước `pinMode`. Safety task ưu tiên cao chạy mỗi 10ms,
giữ timer riêng với phép trừ unsigned qua overflow. Nó tắt khi Wi-Fi mất,
hết thời lượng hoặc vòng MQTT không quay lại trong 500ms. MQTT mất kết nối được
tắt ngay khi thư viện phát hiện; đứt mạng âm thầm cần thời gian keepalive (2 giây
và timeout phản hồi của thư viện), không thể phát hiện vật lý tức thì. Callback
chỉ xếp hàng tối đa 8 payload để tránh xử lý lệnh lồng trong lúc chờ PUBACK;
queue đầy cũng tắt/ngắt phiên. Reconnect luôn OFF, xóa queue nhưng giữ dedup/order.
Task watchdog 3 giây là lớp bổ sung khi luồng chính treo. Những timer/task này
chưa được đo latency trên board; scheduler/SoC vẫn có thể hỏng. Không có bộ ngắt
nguồn phần cứng độc lập, không bảo đảm OFF khi brownout/boot hoặc relay dính tiếp điểm.

Mode `MANUAL` giữ nguyên tương thích v1: chưa có lệnh cấu hình AUTO trong contract.
Server có thể quyết định rồi dùng API command hiện có; firmware không tự suy luận mode.
Theo G02, lỗi AHT20/soil không chặn lệnh MANUAL. [Supervisor AI hiện có](../docs/AI_IRRIGATION.md)
kiểm tra dữ liệu null/stale/simulated nhưng chỉ cho phép simulator; số đo
`simulated:false` của ESP32 thật vẫn bị chặn, chưa bật AUTO trên phần cứng.

## Kiểm thử host (tùy chọn, không cần khi dùng nút Verify)

Test C++ độc lập cần compiler g++ trên máy tính và thư viện ArduinoJson đã cài.
Không dùng compiler Xtensa của ESP32 để chạy chương trình host.
Trong PowerShell, từ root repository:

```powershell
./firmware/tests/run.ps1 -Compiler 'C:/duong-dan-gcc/bin/g++.exe' -ArduinoJsonPath 'C:/duong-dan-sketchbook/libraries/ArduinoJson'
```

Lấy Sketchbook location tại **File → Preferences** trong Arduino IDE; nếu dùng
OneDrive, đường dẫn có thể khác `Documents/Arduino`. Tham số `-Compiler` có thể
bỏ qua khi g++ đã ở PATH. Test dùng source core/guard/payload thật, không network/GPIO.
Output nằm trong `firmware/build` và không được commit.

Linux/macOS, thay đường dẫn ArduinoJson bằng thư viện đã cài:

```sh
mkdir -p firmware/build
g++ -std=c++17 -Wall -Wextra -Ifirmware/SmartGarden -I/path/to/ArduinoJson/src firmware/tests/test_runtime.cpp -o firmware/build/native-tests
firmware/build/native-tests
```
## Broker riêng có xác thực

Chỉ chủ hệ thống thực hiện các bước vận hành sau khi sẵn sàng; phiên coding
không chạy broker hoặc gửi lệnh ON. Từ root, tạo thư mục `secrets/mosquitto`.
Dùng `mosquitto_passwd` tương tác (không đưa password lên dòng lệnh):

```powershell
New-Item -ItemType Directory -Force secrets/mosquitto
docker run --rm -it -v "${PWD}/secrets/mosquitto:/mosquitto/secrets" eclipse-mosquitto:2.0 mosquitto_passwd -c /mosquitto/secrets/passwords garden_backend
docker run --rm -it -v "${PWD}/secrets/mosquitto:/mosquitto/secrets" eclipse-mosquitto:2.0 mosquitto_passwd /mosquitto/secrets/passwords esp32_node_01
```

`-c` chỉ dùng lần đầu, tránh ghi đè password file đã có. Đặt `MQTT_USERNAME=garden_backend`
và password tương ứng trong `.env`; board dùng account `esp32_node_01` riêng.
ACL cấm board publish control và cấm anonymous. Giữ đúng username mẫu, hoặc sửa
ACL đồng bộ khi đổi tên. Kiểm tra file password đọc được bởi UID Mosquitto trong container.

```powershell
docker compose -f compose.yaml -f compose.lan.yaml -f compose.secure.yaml config --quiet
docker compose -f compose.yaml -f compose.lan.yaml -f compose.secure.yaml up --build -d
```

Override thay đúng mount config của broker, giữ volume dữ liệu. Chỉ mở firewall
Private network cho IP/thiết bị cần dùng. API/dashboard hiện chưa có authentication;
người truy cập dashboard trong LAN vẫn có thể yêu cầu lệnh. Xác thực broker không
thay thế xác thực API; chưa triển khai public Internet/unattended watering.

## Nạp và kiểm tra thủ công — chỉ khi chủ thiết bị cho phép

**Bước 1: rút adapter 5V cấp cho bơm**, kiểm tra COM/NO, giữ các đầu nối khô/cách điện.
Không coi rút nguồn USB ESP32 là đã cắt nguồn bơm.

1. Giữ dry-run và control disabled; chỉ nối USB khi chủ thiết bị cho phép.
2. Sau khi được cho phép nạp: chọn **Tools → Board → ESP32 Dev Module**, chọn đúng
   cổng tại **Tools → Port**, bấm **Upload (→)** rồi mở **Serial Monitor**, 115200 baud.
   Các thao tác nạp/serial này chỉ là hướng dẫn, chưa được thực hiện trong phiên coding.
3. Kiểm tra relay không hút khi boot/reset, telemetry `simulated:false`, sensor error/null
   đúng; kiểm tra SNTP và hiệu chuẩn ADC; backend nhận state OFF/boot mới, ACK/state
   được chấp nhận. Không dùng cùng ID với simulator. Dry-run ON hợp lệ phải `safety_lock`.
4. Với adapter bơm **vẫn rút**, chỉ sau chấp thuận của chủ thiết bị mới đặt
   `GARDEN_DRY_RUN=0` và `GARDEN_CONTROL_ENABLED=1`, Verify và Upload lại trong IDE.
5. Chỉ sau khi được cho phép thử lệnh: kiểm tra OFF trước; ON ngắn 1–2 giây chỉ
   quan sát relay; duplicate không kéo dài, OFF ưu tiên, sai boot/expired/>60 bị từ chối.
   Ngắt Wi-Fi/MQTT khi relay đang ON, reconnect OFF; reset có boot mới và không replay.
   Kiểm tra rút cảm biến, trạng thái lỗi, phục hồi và thời gian OFF đo được.
6. Chỉ nối lại adapter và thử bơm thật khi có chấp thuận riêng, có người giám sát,
   nguồn cắt tay sẵn sàng, sau xác minh điện của mạch diode/relay. Chưa cho phép tưới
   không giám sát. Bơm quảng cáo 3–5V không nên chạy dài ở 5V theo người bán.

ACK/state chỉ chứng minh firmware báo đầu ra relay, không chứng minh tiếp điểm
đã nhả hoặc nước chảy. Không có cảm biến lưu lượng, dòng, mực nước hay hard cutoff.

