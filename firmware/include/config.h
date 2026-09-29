#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// CẤU HÌNH HỆ THỐNG SMART GARDEN FIRMWARE (ESP32)
// ============================================================================

// 1. Cấu hình Wi-Fi
// Mặc định hỗ trợ Wokwi-GUEST. Đổi lại Wi-Fi của bạn khi chạy mạch thật.
#define WIFI_SSID             "Wokwi-GUEST"
#define WIFI_PASSWORD         ""

// 2. Cấu hình MQTT Broker
// Cung cấp IP LAN của máy tính chạy Mosquitto khi demo (ví dụ "192.168.1.15")
// Hoặc Public Broker nếu test độc lập: "broker.emqx.io"
#define MQTT_BROKER_HOST      "192.168.1.100"
#define MQTT_BROKER_PORT      1883
#define MQTT_USERNAME         ""
#define MQTT_PASSWORD         ""

// 3. Định danh trạm (Device ID)
#define DEVICE_ID             "node_01"
#define IS_SIMULATED          false

// 4. Cấu hình Chân cắm phần cứng (GPIO Pins)
#define PIN_I2C_SDA           21    // I2C SDA cho AHT20
#define PIN_I2C_SCL           22    // I2C SCL cho AHT20
#define PIN_SOIL_ADC          34    // Analog ADC đọc cảm biến độ ẩm đất
#define PIN_RELAY             26    // Digital điều khiển Relay máy bơm

// Cực kích Relay: LOW (Active LOW) hoặc HIGH (Active HIGH)
#define RELAY_ACTIVE_LEVEL    LOW

// 5. Hiệu chuẩn Cảm biến độ ẩm đất
#define SOIL_ADC_DRY          3200
#define SOIL_ADC_WET          1400

// 6. Ngưỡng An toàn Cục bộ của Máy bơm (Hardware Watchdog)
#define PUMP_MAX_SECONDS      60

// 7. Chu kỳ phát bản tin
#define TELEMETRY_INTERVAL_MS 10000   // 10 giây
#define STATE_HEARTBEAT_MS    15000   // 15 giây
#define NTP_SERVER            "pool.ntp.org"

#endif // CONFIG_H
