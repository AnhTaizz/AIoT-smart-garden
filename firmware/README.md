# Firmware ESP32 — Smart Garden

Firmware chính thức chạy trên bo mạch vi điều khiển **ESP32 DevKit V1** (và tương thích mô phỏng trên **Wokwi**). Firmware tuân thủ đầy đủ hợp đồng giao tiếp G02 ([docs/INTERFACES.md](../docs/INTERFACES.md)) và các quy tắc an toàn phần cứng tối cao.

---

## 1. Sơ đồ nối dây phần cứng (Wiring Pinout)

| Linh kiện | Chân linh kiện | Chân ESP32 GPIO | Ghi chú |
| :--- | :--- | :--- | :--- |
| **AHT20** (Cảm biến vi khí hậu) | `VIN` | `3V3` | Nguồn cấp 3.3V |
| | `GND` | `GND` | Nối đất |
| | `SDA` | `GPIO 21` | Giao tiếp I2C SDA |
| | `SCL` | `GPIO 22` | Giao tiếp I2C SCL |
| **Cảm biến độ ẩm đất điện dung v1.2** | `VCC` | `3V3` | Cấp 3.3V |
| | `GND` | `GND` | Nối đất |
| | `AOUT` (Signal) | `GPIO 34` | ADC1 Channel 6 (Analog Input) |
| **Module Relay 1 kênh** | `VCC` | `5V` (hoặc `VIN`) | Nguồn nuôi cuộn hút relay |
| | `GND` | `GND` | Nối đất |
| | `IN` (Control) | `GPIO 26` | Tín hiệu kích hoạt (Active LOW mặc định) |
| **Máy bơm nước mini** | `Cực dương (+)` | Tiếp điểm `NO` Relay | Tiếp điểm thường mở (Normally Open) |
| | `Cực âm (-)` | `GND` nguồn ngoài | Nguồn bơm cách ly |

---

## 2. Các cơ chế an toàn tích hợp (Hardware Safety Invariants)

1. **Relay mặc định TẮT khi Boot:** Ngay dòng đầu tiên của `setup()`, chân điều khiển relay lập tức kéo về mức ngắt để tránh tình trạng kích nhầm bơm khi chip khởi động.
2. **Hardware Watchdog / Timer cục bộ:** Bơm đếm lùi thời gian bằng `millis()` cục bộ trong `loop()`. Hết thời gian (`duration_seconds`), relay **tự động ngắt 100% độc lập**, không phụ thuộc vào việc có mạng hay backend có gửi lệnh tắt hay không.
3. **Fail-Safe khi mất kết nối MQTT:** Nếu mất kết nối Wi-Fi hoặc broker Mosquitto bị ngắt, ESP32 lập tức cưỡng chế **TẮT BƠM NGAY LẬP TỨC** để tránh sự cố tràn nước ngoài ý muốn.
4. **Idempotency & Replay Attack Protection:** Bộ nhớ đệm lưu danh sách `command_id` gần nhất trong RAM. Nếu nhận lại lệnh ON cũ (do broker gửi lại hoặc mạng chập chờn), ESP32 chỉ gửi lại đúng ACK cũ, **không bao giờ chạy lại bơm hay kéo dài thời gian tưới**.
5. **Kiểm tra Boot Đích (`target_boot_id`):** Lệnh bật bơm chỉ được thực thi nếu `target_boot_id` khớp với `boot_id` hiện tại của phiên chạy. Nếu ESP32 vừa reset, lệnh ON từ phiên cũ sẽ bị từ chối với lý do `boot_mismatch`.
6. **Báo lỗi cảm biến đúng chuẩn:** Cảm biến hỏng sẽ trả giá trị `null` và `sensor_status: "error"`, **tuyệt đối không biến lỗi thành số 0**.

---

## 3. Cấu hình trước khi nạp

Mở file `firmware/include/config.h` (được tạo từ `include/config.h.example`) để sửa thông tin:
* `WIFI_SSID` & `WIFI_PASSWORD`: Tên và mật khẩu Wi-Fi (trên Wokwi dùng `"Wokwi-GUEST"` và `""`).
* `MQTT_BROKER_HOST`: Địa chỉ IP LAN của máy tính chạy Docker Mosquitto (ví dụ: `"192.168.1.15"`).
* `DEVICE_ID`: Mặc định là `"node_01"`.
* `SOIL_ADC_DRY` & `SOIL_ADC_WET`: Hiệu chuẩn ADC khi đất khô và khi nhúng nước.

---

## 4. Cách Build và Nạp Firmware

### Cách A: Dùng PlatformIO (Khuyên dùng)
1. Mở thư mục dự án trong VS Code đã cài extension **PlatformIO IDE**.
2. Kết nối board ESP32 vào cổng USB máy tính.
3. Nhấn biểu tượng **Build** (✓) hoặc chạy lệnh terminal:
   ```bash
   pio run
   ```
4. Nhấn biểu tượng **Upload** (→) để nạp code vào ESP32:
   ```bash
   pio run --target upload
   ```
5. Mở Serial Monitor với tốc độ baud `115200` để xem log hoạt động:
   ```bash
   pio device monitor -b 115200
   ```

### Cách B: Dùng Arduino IDE
1. Cài đặt board ESP32: *Tools -> Board -> Boards Manager -> tìm "esp32" by Espressif Systems*.
2. Cài đặt các thư viện từ Library Manager:
   * `ArduinoJson` (phiên bản 7.x)
   * `PubSubClient` (bởi Nick O'Leary)
   * `Adafruit AHTX0` (bởi Adafruit)
3. Mở file `firmware/src/main.cpp` (có thể đổi tên thư mục thành `firmware.ino`), chọn board **ESP32 Dev Module** và cổng COM, rồi bấm **Upload**.

---

## 5. Chạy mô phỏng trên Wokwi (Không cần phần cứng)

Dự án đã tích hợp sẵn sơ đồ mạch Wokwi trong [diagram.json](diagram.json):
1. Truy cập [https://wokwi.com](https://wokwi.com) -> Chọn **ESP32**.
2. Chuyển sang tab **diagram.json** và dán nội dung từ file [firmware/diagram.json](diagram.json).
3. Chuyển sang tab code chính và dán nội dung [firmware/src/main.cpp](src/main.cpp).
4. Bấm nút **Play (▶️)** để bắt đầu mô phỏng:
   * ESP32 sẽ tự động kết nối mạng ảo `Wokwi-GUEST`.
   * Vặn thanh trượt biến trở (Potentiometer) để thay đổi độ ẩm đất.
   * Khi nhận lệnh Bật bơm từ Dashboard/MQTT, Relay trên Wokwi sẽ nhảy và đèn LED màu xanh sẽ sáng lên!
