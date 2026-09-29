/**
 * Smart Garden — ESP32 Firmware
 * 
 * Triển khai đầy đủ hợp đồng G02 (docs/INTERFACES.md) và các nguyên tắc an toàn:
 * - Khởi tạo ngẫu nhiên boot_id mỗi lần khởi động.
 * - Relay mặc định OFF khi boot và ngắt an toàn cục bộ.
 * - Tự động tắt bơm theo thời gian cục bộ (Hardware watchdog bằng millis()).
 * - Tự động tắt bơm ngay lập tức khi mất kết nối MQTT.
 * - Kiểm tra Idempotent (chống trùng lặp command_id), không gia hạn lệnh cũ.
 * - Kiểm tra hạn tuyệt đối expires_at, target_boot_id, order_mark.
 * - Đọc cảm biến AHT20 (I2C) và cảm biến độ ẩm đất (ADC). Báo lỗi bằng null, không thay bằng 0.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_AHTX0.h>
#include <time.h>
#include "config.h"

// ============================================================================
// ĐỊNH NGHĨA TRẠNG THÁI & HẰNG SỐ
// ============================================================================
#define RELAY_ON              1
#define RELAY_OFF             0
#define COMMAND_CACHE_SIZE    10

// Cấu trúc lưu lịch sử lệnh để xử lý idempotent (lệnh trùng lặp)
struct CachedCommand {
    char commandId[40];
    char status[16];          // "applied" hoặc "rejected"
    char reason[32];          // Mã lý do từ chối nếu rejected
    bool exists;
};

// ============================================================================
// BIẾN TOÀN CỤC CỦA THIẾT BỊ
// ============================================================================
char bootId[32];
uint32_t orderMark = 0;
uint32_t stateSequence = 0;
uint32_t telemetrySequence = 0;

int relayState = RELAY_OFF;
uint32_t pumpStopMillis = 0;
char currentRunningCommandId[40] = "";

char lastAppliedCommandId[40] = "";
int32_t lastAppliedCommandSequence = -1;

CachedCommand commandCache[COMMAND_CACHE_SIZE];
int commandCacheIndex = 0;

unsigned long lastTelemetryMillis = 0;
unsigned long lastHeartbeatMillis = 0;
unsigned long lastWiFiCheckMillis = 0;

// Đối tượng phần cứng & mạng
WiFiClient espClient;
PubSubClient mqttClient(espClient);
Adafruit_AHTX0 aht;
bool aht20Available = false;

// Topic MQTT
char topicTelemetry[80];
char topicControl[80];
char topicAck[80];
char topicState[80];

// ============================================================================
// HÀM TIỆN ÍCH THỜI GIAN & ĐỊNH DANH
// ============================================================================

void generateBootId() {
    uint32_t randVal = esp_random();
    snprintf(bootId, sizeof(bootId), "boot_%08x", randVal);
}

bool isClockSynced() {
    time_t now = time(nullptr);
    struct tm timeinfo;
    gmtime_r(&now, &timeinfo);
    // Năm tính từ 1900, nếu > 2025 tức là SNTP đã cập nhật giờ UTC hợp lệ
    return (timeinfo.tm_year + 1900) >= 2025;
}

void getIsoUtcString(char* buffer, size_t maxLen) {
    time_t now = time(nullptr);
    struct tm timeinfo;
    gmtime_r(&now, &timeinfo);
    strftime(buffer, maxLen, "%Y-%m-%dT%H:%M:%S.000Z", &timeinfo);
}

// Chuyển đổi chuỗi ISO 8601 ("2026-09-29T10:00:00.000Z") thành time_t để so sánh hạn
time_t parseIsoUtc(const char* isoStr) {
    if (!isoStr || strlen(isoStr) < 19) return 0;
    struct tm tmInfo;
    memset(&tmInfo, 0, sizeof(tmInfo));
    
    int year, month, day, hour, min, sec;
    if (sscanf(isoStr, "%d-%d-%dT%d:%d:%d", &year, &month, &day, &hour, &min, &sec) >= 6) {
        tmInfo.tm_year = year - 1900;
        tmInfo.tm_mon = month - 1;
        tmInfo.tm_mday = day;
        tmInfo.tm_hour = hour;
        tmInfo.tm_min = min;
        tmInfo.tm_sec = sec;
        return mktime(&tmInfo);
    }
    return 0;
}

// ============================================================================
// ĐIỀU KHIỂN RELAY AN TOÀN
// ============================================================================

void setRelay(int targetState) {
    relayState = targetState;
    if (targetState == RELAY_ON) {
        digitalWrite(PIN_RELAY, RELAY_ACTIVE_LEVEL);
    } else {
        digitalWrite(PIN_RELAY, RELAY_ACTIVE_LEVEL == LOW ? HIGH : LOW);
    }
}

// ============================================================================
// QUẢN LÝ CACHE LỆNH (IDEMPOTENCY)
// ============================================================================

CachedCommand* findCachedCommand(const char* cmdId) {
    for (int i = 0; i < COMMAND_CACHE_SIZE; i++) {
        if (commandCache[i].exists && strcmp(commandCache[i].commandId, cmdId) == 0) {
            return &commandCache[i];
        }
    }
    return nullptr;
}

void recordCommandDecision(const char* cmdId, const char* status, const char* reason) {
    CachedCommand* item = &commandCache[commandCacheIndex];
    strncpy(item->commandId, cmdId, sizeof(item->commandId) - 1);
    strncpy(item->status, status, sizeof(item->status) - 1);
    if (reason) {
        strncpy(item->reason, reason, sizeof(item->reason) - 1);
    } else {
        item->reason[0] = '\0';
    }
    item->exists = true;
    commandCacheIndex = (commandCacheIndex + 1) % COMMAND_CACHE_SIZE;
}

// ============================================================================
// PHÁT BẢN TIN MQTT (ACK & STATE & TELEMETRY)
// ============================================================================

void sendAck(const char* cmdId, const char* status, const char* reason = nullptr) {
    JsonDocument doc;
    doc["schema"] = "ack-v1";
    doc["command_id"] = cmdId;
    doc["device_id"] = DEVICE_ID;
    doc["boot_id"] = bootId;
    doc["status"] = status;

    if (reason && strlen(reason) > 0) {
        doc["reason"] = reason;
    } else {
        doc["reason"] = nullptr;
    }

    bool clockSynced = isClockSynced();
    doc["clock_synced"] = clockSynced;
    if (clockSynced) {
        char timeStr[32];
        getIsoUtcString(timeStr, sizeof(timeStr));
        doc["acked_at"] = timeStr;
    } else {
        doc["acked_at"] = nullptr;
    }

    char buffer[384];
    size_t len = serializeJson(doc, buffer, sizeof(buffer));
    mqttClient.publish(topicAck, buffer, len);
    Serial.printf("[MQTT ACK] id=%s status=%s reason=%s\n", cmdId, status, reason ? reason : "none");
}

void sendState(const char* currentRelay, const char* lastCmdId, int32_t lastCmdSeq) {
    stateSequence++;
    JsonDocument doc;
    doc["schema"] = "state-v1";
    doc["device_id"] = DEVICE_ID;
    doc["boot_id"] = bootId;
    doc["state_sequence"] = stateSequence;
    doc["mode"] = "MANUAL";
    doc["relay_state"] = currentRelay;

    if (lastCmdId && strlen(lastCmdId) > 0 && lastCmdSeq >= 0) {
        doc["last_command_id"] = lastCmdId;
        doc["last_command_sequence"] = lastCmdSeq;
    } else {
        doc["last_command_id"] = nullptr;
        doc["last_command_sequence"] = nullptr;
    }

    bool clockSynced = isClockSynced();
    doc["clock_synced"] = clockSynced;
    if (clockSynced) {
        char timeStr[32];
        getIsoUtcString(timeStr, sizeof(timeStr));
        doc["reported_at"] = timeStr;
    } else {
        doc["reported_at"] = nullptr;
    }
    doc["uptime_ms"] = millis();

    char buffer[450];
    size_t len = serializeJson(doc, buffer, sizeof(buffer));
    mqttClient.publish(topicState, buffer, len);
    Serial.printf("[MQTT STATE] seq=%d relay=%s last_cmd=%s\n", stateSequence, currentRelay, lastCmdId ? lastCmdId : "null");
}

void sendTelemetry() {
    telemetrySequence++;
    JsonDocument doc;
    doc["schema"] = "telemetry-v1";
    doc["simulated"] = IS_SIMULATED;
    doc["device_id"] = DEVICE_ID;
    doc["boot_id"] = bootId;
    doc["sequence"] = telemetrySequence;

    bool clockSynced = isClockSynced();
    doc["clock_synced"] = clockSynced;
    if (clockSynced) {
        char timeStr[32];
        getIsoUtcString(timeStr, sizeof(timeStr));
        doc["measured_at"] = timeStr;
    } else {
        doc["measured_at"] = nullptr;
    }
    doc["uptime_ms"] = millis();

    // 1. Đọc cảm biến AHT20
    bool ahtSuccess = false;
    float tempC = 0.0f;
    float humidityPct = 0.0f;

    if (aht20Available) {
        sensors_event_t humidity, temp;
        if (aht.getEvent(&humidity, &temp) && !isnan(temp.temperature) && !isnan(humidity.relative_humidity)) {
            tempC = temp.temperature;
            humidityPct = humidity.relative_humidity;
            ahtSuccess = true;
        }
    }

    // 2. Đọc cảm biến độ ẩm đất (Analog ADC)
    int soilRaw = 0;
    // Lấy trung bình 8 lần đọc để giảm nhiễu ADC trên ESP32
    for (int i = 0; i < 8; i++) {
        soilRaw += analogRead(PIN_SOIL_ADC);
        delayMicroseconds(50);
    }
    soilRaw /= 8;

    // Kiểm tra cảm biến hợp lệ hay hở mạch
    bool soilSuccess = (soilRaw >= 100 && soilRaw <= 4050);
    float soilPct = 0.0f;
    if (soilSuccess) {
        // Cảm biến điện dung: ADC cao khi khô, ADC thấp khi ẩm
        soilPct = (float)(SOIL_ADC_DRY - soilRaw) / (float)(SOIL_ADC_DRY - SOIL_ADC_WET) * 100.0f;
        if (soilPct < 0.0f) soilPct = 0.0f;
        if (soilPct > 100.0f) soilPct = 100.0f;
    }

    // Gán dữ liệu đo và kiểm tra hợp đồng G02 (Lỗi dùng null, không dùng 0)
    JsonObject sensorStatus = doc["sensor_status"].to<JsonObject>();
    if (ahtSuccess) {
        doc["temperature_c"] = round(tempC * 10.0f) / 10.0f;
        doc["air_humidity_pct"] = round(humidityPct * 10.0f) / 10.0f;
        sensorStatus["aht20"] = "ok";
    } else {
        doc["temperature_c"] = nullptr;
        doc["air_humidity_pct"] = nullptr;
        sensorStatus["aht20"] = "error";
    }

    if (soilSuccess) {
        doc["soil_moisture_pct"] = round(soilPct * 10.0f) / 10.0f;
        sensorStatus["soil"] = "ok";
    } else {
        doc["soil_moisture_pct"] = nullptr;
        sensorStatus["soil"] = "error";
    }

    char buffer[512];
    size_t len = serializeJson(doc, buffer, sizeof(buffer));
    mqttClient.publish(topicTelemetry, buffer, len);
    Serial.printf("[MQTT TELEMETRY] #%d Temp=%.1f Hum=%.1f Soil=%.1f\n", 
                  telemetrySequence, 
                  ahtSuccess ? tempC : -99.0, 
                  ahtSuccess ? humidityPct : -99.0, 
                  soilSuccess ? soilPct : -99.0);
}

// ============================================================================
// XỬ LÝ LỆNH NHẬN ĐƯỢC TỪ MQTT CONTROL (G02 STATE MACHINE)
// ============================================================================

void handleIncomingCommand(char* topic, byte* payload, unsigned int length) {
    if (length == 0 || length > 1024) return;

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) {
        Serial.println(F("[COMMAND] JSON parse error -> Bỏ qua"));
        return;
    }

    // 1. Kiểm tra envelope cơ bản
    const char* schema = doc["schema"];
    const char* cmdId = doc["command_id"];
    const char* devId = doc["device_id"];
    const char* action = doc["action"];

    if (!schema || strcmp(schema, "command-v1") != 0 || !cmdId || strlen(cmdId) < 10) {
        Serial.println(F("[COMMAND] Envelope không hợp lệ -> Bỏ qua"));
        return;
    }

    // 2. Kiểm tra device_id: nếu không phải của trạm này thì bỏ qua không ACK
    if (!devId || strcmp(devId, DEVICE_ID) != 0) {
        Serial.printf("[COMMAND] Lệch device_id (%s != %s) -> Bỏ qua\n", devId ? devId : "null", DEVICE_ID);
        return;
    }

    // 3. Kiểm tra Idempotent (trùng command_id trong cùng một boot)
    CachedCommand* cached = findCachedCommand(cmdId);
    if (cached != nullptr) {
        Serial.printf("[COMMAND] Trùng command_id=%s -> Gửi lại ACK cũ, không chạy lại\n", cmdId);
        sendAck(cached->commandId, cached->status, cached->reason[0] != '\0' ? cached->reason : nullptr);
        return;
    }

    uint32_t cmdSeq = doc["command_sequence"] | 0;

    // 4. XỬ LÝ ACTION: PUMP_OFF (Tắt bơm khẩn cấp)
    // pump_off bỏ qua kiểm tra boot, đồng hồ, hạn hay bận; tắt bơm luôn an toàn hơn để bơm chạy
    if (strcmp(action, "pump_off") == 0) {
        setRelay(RELAY_OFF);
        pumpStopMillis = 0;
        currentRunningCommandId[0] = '\0';

        if (cmdSeq > orderMark) orderMark = cmdSeq;
        strncpy(lastAppliedCommandId, cmdId, sizeof(lastAppliedCommandId) - 1);
        lastAppliedCommandSequence = cmdSeq;

        recordCommandDecision(cmdId, "applied", nullptr);
        sendAck(cmdId, "applied");
        sendState("off", lastAppliedCommandId, lastAppliedCommandSequence);
        Serial.printf("[COMMAND APPLIED] Tắt bơm thành công cmdId=%s seq=%d\n", cmdId, cmdSeq);
        return;
    }

    // 5. XỬ LÝ ACTION: PUMP_ON (Bật bơm có thời lượng và kiểm tra an toàn)
    if (strcmp(action, "pump_on") == 0) {
        int durationSeconds = doc["params"]["duration_seconds"] | 0;

        // 5.1. Kiểm tra duration hợp lệ
        if (durationSeconds <= 0 || durationSeconds > PUMP_MAX_SECONDS) {
            recordCommandDecision(cmdId, "rejected", "invalid_duration");
            sendAck(cmdId, "rejected", "invalid_duration");
            Serial.printf("[COMMAND REJECTED] invalid_duration: %d (max %d)\n", durationSeconds, PUMP_MAX_SECONDS);
            return;
        }

        // 5.2. Kiểm tra target_boot_id
        const char* targetBoot = doc["target_boot_id"];
        if (!targetBoot || strcmp(targetBoot, bootId) != 0) {
            recordCommandDecision(cmdId, "rejected", "boot_mismatch");
            sendAck(cmdId, "rejected", "boot_mismatch");
            Serial.printf("[COMMAND REJECTED] boot_mismatch (%s != %s)\n", targetBoot ? targetBoot : "null", bootId);
            return;
        }

        // 5.3. Kiểm tra đồng bộ giờ UTC
        bool clockSynced = isClockSynced();
        if (!clockSynced) {
            recordCommandDecision(cmdId, "rejected", "clock_unsynced");
            sendAck(cmdId, "rejected", "clock_unsynced");
            Serial.println(F("[COMMAND REJECTED] clock_unsynced"));
            return;
        }

        // 5.4. Kiểm tra hạn tuyệt đối (expires_at)
        const char* expiresAtStr = doc["expires_at"];
        time_t expiresAt = parseIsoUtc(expiresAtStr);
        time_t now = time(nullptr);
        if (expiresAt > 0 && now > expiresAt) {
            recordCommandDecision(cmdId, "rejected", "expired");
            sendAck(cmdId, "rejected", "expired");
            Serial.printf("[COMMAND REJECTED] expired (now=%ld > expires=%ld)\n", (long)now, (long)expiresAt);
            return;
        }

        // 5.5. Kiểm tra thứ tự lệnh (chống lệnh phát trước OFF nhưng đến sau OFF)
        if (cmdSeq <= orderMark) {
            recordCommandDecision(cmdId, "rejected", "superseded");
            sendAck(cmdId, "rejected", "superseded");
            Serial.printf("[COMMAND REJECTED] superseded (cmdSeq=%d <= orderMark=%d)\n", cmdSeq, orderMark);
            return;
        }

        // 5.6. Kiểm tra trạng thái bận
        if (relayState == RELAY_ON) {
            recordCommandDecision(cmdId, "rejected", "busy");
            sendAck(cmdId, "rejected", "busy");
            Serial.println(F("[COMMAND REJECTED] busy (Bơm đang chạy lệnh khác)"));
            return;
        }

        // 5.7. THỰC THI BẬT BƠM
        setRelay(RELAY_ON);
        pumpStopMillis = millis() + ((uint32_t)durationSeconds * 1000UL);
        strncpy(currentRunningCommandId, cmdId, sizeof(currentRunningCommandId) - 1);

        if (cmdSeq > orderMark) orderMark = cmdSeq;
        strncpy(lastAppliedCommandId, cmdId, sizeof(lastAppliedCommandId) - 1);
        lastAppliedCommandSequence = cmdSeq;

        recordCommandDecision(cmdId, "applied", nullptr);
        sendAck(cmdId, "applied");
        sendState("on", lastAppliedCommandId, lastAppliedCommandSequence);
        Serial.printf("[COMMAND APPLIED] BẬT BƠM trong %d giây! cmdId=%s seq=%d\n", durationSeconds, cmdId, cmdSeq);
        return;
    }

    // 6. Action không hỗ trợ
    recordCommandDecision(cmdId, "rejected", "unsupported_action");
    sendAck(cmdId, "rejected", "unsupported_action");
    Serial.printf("[COMMAND REJECTED] unsupported_action: %s\n", action ? action : "null");
}

// ============================================================================
// KẾT NỐI WI-FI & MQTT CLIENT
// ============================================================================

void setupWiFi() {
    Serial.printf("\n[WIFI] Đang kết nối tới SSID: %s ...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Đã kết nối! IP: %s\n", WiFi.localIP().toString().c_str());
        configTime(0, 0, NTP_SERVER);
    } else {
        Serial.println(F("\n[WIFI] Chưa kết nối được Wi-Fi. Sẽ thử lại trong vòng lặp loop."));
    }
}

void reconnectMQTT() {
    if (WiFi.status() != WL_CONNECTED) return;
    if (mqttClient.connected()) return;

    Serial.printf("[MQTT] Đang kết nối broker %s:%d ...\n", MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    
    // Tạo Client ID ngẫu nhiên có chứa device_id
    char clientId[64];
    snprintf(clientId, sizeof(clientId), "%s_%04x", DEVICE_ID, (uint16_t)esp_random());

    // clean_session = true theo hợp đồng G02
    bool connected = false;
    if (strlen(MQTT_USERNAME) > 0) {
        connected = mqttClient.connect(clientId, MQTT_USERNAME, MQTT_PASSWORD, nullptr, 0, false, nullptr, true);
    } else {
        connected = mqttClient.connect(clientId, nullptr, nullptr, nullptr, 0, false, nullptr, true);
    }

    if (connected) {
        Serial.println(F("[MQTT] Kết nối thành công!"));
        // Subscribe topic control
        mqttClient.subscribe(topicControl, 1);
        Serial.printf("[MQTT] Đã subscribe: %s\n", topicControl);

        // Gửi state ban đầu (Relay OFF)
        sendState(relayState == RELAY_ON ? "on" : "off", 
                  lastAppliedCommandId[0] != '\0' ? lastAppliedCommandId : nullptr, 
                  lastAppliedCommandSequence);
    } else {
        Serial.printf("[MQTT] Kết nối thất bại, rc=%d. Sẽ thử lại sau.\n", mqttClient.state());
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.printf("\n[MQTT INCOMING] Topic: %s (len=%u)\n", topic, length);
    handleIncomingCommand(topic, payload, length);
}

// ============================================================================
// ARDUINO SETUP & LOOP
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println(F("\n======================================================="));
    Serial.println(F("🌱 SMART GARDEN FIRMWARE (ESP32) — CONTRACT G02"));
    Serial.println(F("======================================================="));

    // 1. AN TOÀN PHẦN CỨNG: Cấu hình Relay và đảm bảo BƠM TẮT KHI KHỞI ĐỘNG
    pinMode(PIN_RELAY, OUTPUT);
    setRelay(RELAY_OFF);

    // 2. Khởi tạo boot_id ngẫu nhiên duy nhất cho phiên chạy này
    generateBootId();
    Serial.printf("[BOOT] Khởi tạo phiên trạm: boot_id = %s\n", bootId);

    // 3. Khởi tạo Topics theo device_id
    snprintf(topicTelemetry, sizeof(topicTelemetry), "garden/%s/telemetry", DEVICE_ID);
    snprintf(topicControl, sizeof(topicControl), "garden/%s/control", DEVICE_ID);
    snprintf(topicAck, sizeof(topicAck), "garden/%s/ack", DEVICE_ID);
    snprintf(topicState, sizeof(topicState), "garden/%s/state", DEVICE_ID);

    // 4. Khởi tạo I2C & Cảm biến AHT20
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    if (aht.begin(&Wire)) {
        aht20Available = true;
        Serial.println(F("[HARDWARE] Cảm biến AHT20: SẴN SÀNG"));
    } else {
        aht20Available = false;
        Serial.println(F("[HARDWARE] Cảm biến AHT20: KHÔNG TÌM THẤY (Sẽ báo lỗi sensor_status.aht20 = error)"));
    }

    // 5. Cấu hình ADC cho cảm biến độ ẩm đất
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(PIN_SOIL_ADC, INPUT);

    // 6. Cấu hình MQTT Client
    mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    mqttClient.setBufferSize(1024);
    mqttClient.setCallback(mqttCallback);

    // 7. Kết nối Wi-Fi & SNTP
    setupWiFi();
}

void loop() {
    unsigned long currentMillis = millis();

    // 1. Quản lý kết nối Wi-Fi
    if (WiFi.status() != WL_CONNECTED) {
        if (currentMillis - lastWiFiCheckMillis >= 5000) {
            lastWiFiCheckMillis = currentMillis;
            Serial.println(F("[WIFI] Mất kết nối Wi-Fi, đang thử kết nối lại..."));
            WiFi.reconnect();
        }
    }

    // 2. Quản lý kết nối MQTT & BẢO VỆ AN TOÀN FAIL-SAFE
    if (!mqttClient.connected()) {
        // FAIL-SAFE: Ngay khi mất MQTT, ngắt bơm ngay lập tức để tránh tràn nước
        if (relayState == RELAY_ON) {
            setRelay(RELAY_OFF);
            pumpStopMillis = 0;
            currentRunningCommandId[0] = '\0';
            Serial.println(F("[SAFETY FAIL-SAFE] Mất MQTT -> NGẮT BƠM KHẨN CẤP!"));
        }
        reconnectMQTT();
    } else {
        mqttClient.loop();
    }

    // 3. HARDWARE WATCHDOG: Tự động dừng bơm khi hết thời lượng cục bộ
    if (relayState == RELAY_ON && pumpStopMillis > 0 && currentMillis >= pumpStopMillis) {
        setRelay(RELAY_OFF);
        pumpStopMillis = 0;
        Serial.println(F("[WATCHDOG] Hết thời lượng tưới cục bộ -> TỰ ĐỘNG TẮT BƠM!"));
        sendState("off", lastAppliedCommandId, lastAppliedCommandSequence);
        currentRunningCommandId[0] = '\0';
    }

    // 4. Định kỳ gửi Telemetry
    if (currentMillis - lastTelemetryMillis >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryMillis = currentMillis;
        if (mqttClient.connected()) {
            sendTelemetry();
        }
    }

    // 5. Định kỳ gửi State Heartbeat
    if (currentMillis - lastHeartbeatMillis >= STATE_HEARTBEAT_MS) {
        lastHeartbeatMillis = currentMillis;
        if (mqttClient.connected()) {
            sendState(relayState == RELAY_ON ? "on" : "off", 
                      lastAppliedCommandId[0] != '\0' ? lastAppliedCommandId : nullptr, 
                      lastAppliedCommandSequence);
        }
    }

    delay(10);
}
