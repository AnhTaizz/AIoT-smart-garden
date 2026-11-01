#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <ArduinoMqttClient.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_task_wdt.h>
#include <esp_arduino_version.h>
#include <esp_sntp.h>
#include <sys/time.h>
#include <deque>
#include "config.h"
#include "garden.h"
#include "payloads.h"

WiFiClient transport;
MqttClient mqtt(transport);
garden::Runtime* runtime=nullptr;
std::string baseTopic;
volatile bool timeSynchronized=false;
portMUX_TYPE outputMux=portMUX_INITIALIZER_UNLOCKED;
garden::OutputGuard output;
bool stateDirty=true;
struct Incoming { std::string payload; bool retained; };
std::deque<Incoming> inbox;
bool inboxOverflow=false;

void onTimeSync(struct timeval*) { timeSynchronized=true; }

// All writes to the active-low output have one owner interface. No network,
// allocation or sensor I/O inside the critical section.
bool applyOutput(bool requested, uint32_t duration) {
  bool connected=WiFi.status()==WL_CONNECTED && mqtt.connected();
  portENTER_CRITICAL(&outputMux);
  bool result=output.apply(requested,!GARDEN_DRY_RUN && GARDEN_CONTROL_ENABLED,
                           connected,millis(),duration);
  digitalWrite(PIN_RELAY,result ? LOW:HIGH);
  portEXIT_CRITICAL(&outputMux);
  return result;
}
void safetyTask(void*) {
  for (;;) {
    bool wifi=WiFi.status()==WL_CONNECTED;
    uint32_t now=millis();
    portENTER_CRITICAL(&outputMux);
    if (output.tick(now,wifi)) digitalWrite(PIN_RELAY,HIGH);
    portEXIT_CRITICAL(&outputMux);
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

struct Clock {
  int64_t utc=-1;
  char text[25]{};
  const char* value() const { return utc<0 ? nullptr:text; }
};
Clock clockNow() {
  Clock c;
  timeval tv{}; gettimeofday(&tv,nullptr);
  if (!timeSynchronized || tv.tv_sec<1704067200) return c;
  tm utc{}; gmtime_r(&tv.tv_sec,&utc);
  char seconds[21]{};
  strftime(seconds,sizeof(seconds),"%Y-%m-%dT%H:%M:%S",&utc);
  snprintf(c.text,sizeof(c.text),"%s.%03uZ",seconds,unsigned(tv.tv_usec/1000));
  c.utc=int64_t(tv.tv_sec)*1000+tv.tv_usec/1000;
  return c;
}
bool publish(const char* suffix, const std::string& text, int qos) {
  std::string topic=baseTopic+suffix;
  if (!mqtt.connected() || !mqtt.beginMessage(topic.c_str(),text.size(),false,qos)) return false;
  if (mqtt.write(reinterpret_cast<const uint8_t*>(text.data()),text.size())!=text.size()) {
    mqtt.stop(); return false;
  }
  return mqtt.endMessage()==1;
}
bool publishDoc(const char* suffix, JsonDocument& doc, int qos) {
  std::string encoded; serializeJson(doc,encoded); return publish(suffix,encoded,qos);
}
bool sendState() {
  portENTER_CRITICAL(&outputMux); bool actual=output.on; portEXIT_CRITICAL(&outputMux);
  if (runtime->on && !actual) runtime->stop();
  Clock c=clockNow();
  auto doc=garden::statePayload(*runtime,uint64_t(esp_timer_get_time()/1000),c.value());
  return publishDoc("state",doc,1);
}
bool ahtWrite(const uint8_t* bytes, size_t size) {
  Wire.beginTransmission(0x38); Wire.write(bytes,size);
  return Wire.endTransmission()==0;
}
bool ahtRead(uint8_t* bytes, uint8_t size) {
  if (Wire.requestFrom(uint8_t(0x38),size)!=size) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i=0;i<size;++i) bytes[i]=Wire.read();
  return true;
}
bool ahtReady(uint8_t& status) {
  uint32_t start=millis();
  do {
    if (!ahtRead(&status,1)) return false;
    if (!(status&0x80)) return true;
    delay(5);
  } while (!garden::elapsed(millis(),start,150));
  return false;
}
bool readAht20(float& temperature, float& humidity) {
  uint8_t status=0;
  if (!ahtReady(status)) return false;
  if (!(status&0x08)) {
    const uint8_t calibrate[]={0xbe,0x08,0x00};
    if (!ahtWrite(calibrate,sizeof(calibrate))) return false;
    delay(10);
    if (!ahtReady(status) || !(status&0x08)) return false;
  }
  const uint8_t trigger[]={0xac,0x33,0x00};
  if (!ahtWrite(trigger,sizeof(trigger))) return false;
  delay(80);
  if (!ahtReady(status)) return false;
  uint8_t data[7]{};
  return ahtRead(data,7) && garden::decodeAht20(data,temperature,humidity);
}
void sendTelemetry() {
  float temperature=NAN, humidity=NAN;
  bool ok=readAht20(temperature,humidity);
  int raw=0; bool adcOk=true;
  for (int i=0;i<8;++i) {
    int sample=analogRead(PIN_SOIL);
    if (sample<=15 || sample>=4080) adcOk=false;
    raw+=sample;
  }
  raw/=8;
  float soil=adcOk ? garden::soilPercent(raw,GARDEN_SOIL_DRY,GARDEN_SOIL_WET):NAN;
  Serial.printf("soil_adc_raw=%d calibrated=%s dry_run=%d\n",raw,std::isfinite(soil)?"yes":"no",GARDEN_DRY_RUN);
  Clock c=clockNow();
  auto doc=garden::telemetryPayload(*runtime,uint64_t(esp_timer_get_time()/1000),c.value(),
                                    ok ? temperature:NAN,ok ? humidity:NAN,soil);
  publishDoc("telemetry",doc,0);
}
void message(int length) {
  // Drain oversized/wrong-topic payloads without buffering unbounded input.
  bool eligible=length>0 && length<=2048 && mqtt.messageTopic()==(baseTopic+"control").c_str();
  bool retained=mqtt.messageRetain();
  std::string payload;
  if (eligible) payload.reserve(length);
  while (mqtt.available()) { int ch=mqtt.read(); if (eligible && ch>=0) payload.push_back(char(ch)); }
  if (!eligible || payload.size()!=size_t(length)) return;
  // QoS1 publish internally polls MQTT. Do not recursively execute commands
  // from that poll or mutate the runtime before the previous ACK/state is sent.
  if (inbox.size()>=8) { inboxOverflow=true; return; }
  inbox.push_back({std::move(payload),retained});
}
void processMessage(const Incoming& incoming) {
  const auto& payload=incoming.payload;
  Clock c=clockNow();
  bool authorized=!GARDEN_DRY_RUN && GARDEN_CONTROL_ENABLED &&
                  strlen(GARDEN_MQTT_USER)>0 && strlen(GARDEN_MQTT_PASSWORD)>0;
  auto previousId=runtime->lastId;
  auto previousSequence=runtime->lastSequence;
  auto result=runtime->command(payload.data(),payload.size(),millis(),c.utc,c.value(),authorized,incoming.retained);
  if (!result.reply) return;
  // Apply OFF before publishing anything. ON only follows successful validation.
  bool actual=applyOutput(runtime->on,runtime->durationMs);
  if (runtime->on && !actual) {
    // A safety task won the race: do not falsely claim the new ON was applied.
    if (!result.duplicate) {
      runtime->rejectActuation(result);
      runtime->lastId=previousId; runtime->lastSequence=previousSequence;
    } else runtime->stop();
  }
  if (!publish("ack",result.ack,1)) {
    applyOutput(false,0); runtime->stop(); mqtt.stop();
  }
  stateDirty=true;
}

void setup() {
  // Prepare inactive latch BEFORE enabling output direction.
  digitalWrite(PIN_RELAY,HIGH); pinMode(PIN_RELAY,OUTPUT);
  Serial.begin(115200);
  char boot[38]; snprintf(boot,sizeof(boot),"boot_%08lx%08lx%08lx%08lx",
      (unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random());
  runtime=new garden::Runtime(GARDEN_DEVICE_ID,boot);
  baseTopic="garden/"+runtime->device+"/";
  Serial.printf("boot=%s dry_run=%d control_enabled=%d\n",boot,GARDEN_DRY_RUN,GARDEN_CONTROL_ENABLED);
  if (!garden::identifier(GARDEN_DEVICE_ID)) { Serial.println("Invalid device ID; halted OFF"); while(true) delay(1000); }
  if (xTaskCreatePinnedToCore(safetyTask,"pump-safety",3072,nullptr,3,nullptr,0)!=pdPASS) {
    Serial.println("Cannot start safety task; halted OFF"); while(true) delay(1000);
  }
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t watchdog{};
  watchdog.timeout_ms=3000;
  watchdog.idle_core_mask=(1U<<portNUM_PROCESSORS)-1;
  watchdog.trigger_panic=true;
  esp_err_t watchdogStatus=esp_task_wdt_init(&watchdog);
  if (watchdogStatus==ESP_ERR_INVALID_STATE) watchdogStatus=esp_task_wdt_reconfigure(&watchdog);
#else
  esp_err_t watchdogStatus=esp_task_wdt_init(3,true);
#endif
  if (watchdogStatus!=ESP_OK || esp_task_wdt_add(nullptr)!=ESP_OK) {
    Serial.println("Cannot configure watchdog; halted OFF"); while(true) delay(1000);
  }
  Wire.begin(PIN_SDA,PIN_SCL); Wire.setTimeOut(50);
  analogReadResolution(12); analogSetPinAttenuation(PIN_SOIL,ADC_11db);
  WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true);
  if (strlen(GARDEN_WIFI_SSID)) WiFi.begin(GARDEN_WIFI_SSID,GARDEN_WIFI_PASSWORD);
  sntp_set_time_sync_notification_cb(onTimeSync);
  if (strlen(GARDEN_NTP_HOST)) configTime(0,0,GARDEN_NTP_HOST);
  mqtt.setId(("garden-"+runtime->device+"-"+runtime->boot).c_str());
  mqtt.setCleanSession(true); mqtt.setKeepAliveInterval(2000); mqtt.setConnectionTimeout(1000);
  mqtt.setUsernamePassword(GARDEN_MQTT_USER,GARDEN_MQTT_PASSWORD);
  mqtt.onMessage(message);
}
void loop() {
  esp_task_wdt_reset();
  uint32_t now=millis();
  bool connected=WiFi.status()==WL_CONNECTED && mqtt.connected();
  portENTER_CRITICAL(&outputMux);
  bool fault=output.fault;
  portEXIT_CRITICAL(&outputMux);
  if (fault || runtime->tick(now,connected)) {
    applyOutput(false,0); runtime->stop(); stateDirty=true;
    // Fault includes missed network lease; invalidate the transport/session.
    if (fault) mqtt.stop();
    portENTER_CRITICAL(&outputMux); output.fault=false; portEXIT_CRITICAL(&outputMux);
    if (fault) connected=false;
  }
  static uint32_t retry=uint32_t(-5000), telemetry=uint32_t(-5000), heartbeat=0;
  if (!connected) {
    applyOutput(false,0);
    mqtt.stop();
    inbox.clear(); inboxOverflow=false;
    if (WiFi.status()==WL_CONNECTED && strlen(GARDEN_MQTT_HOST) && garden::elapsed(now,retry,5000)) {
      retry=now;
      if (mqtt.connect(GARDEN_MQTT_HOST,GARDEN_MQTT_PORT)) {
        if (!mqtt.subscribe((baseTopic+"control").c_str(),1)) { mqtt.stop(); return; }
        stateDirty=true;
        // Publish OFF boot state before processing any command.
        if (!sendState()) mqtt.stop(); else stateDirty=false;
      }
    }
    delay(5); return;
  }
  portENTER_CRITICAL(&outputMux); output.lease=now; portEXIT_CRITICAL(&outputMux);
  mqtt.poll();
  if (inboxOverflow || !mqtt.connected()) {
    applyOutput(false,0); runtime->stop(); mqtt.stop(); stateDirty=true;
    inbox.clear(); inboxOverflow=false; return;
  }
  if (!inbox.empty()) {
    Incoming incoming=std::move(inbox.front()); inbox.pop_front();
    processMessage(incoming);
  }
  if (stateDirty || garden::elapsed(now,heartbeat,10000)) {
    if (sendState()) { stateDirty=false; heartbeat=now; }
    else { applyOutput(false,0); runtime->stop(); mqtt.stop(); }
  }
  if (mqtt.connected() && garden::elapsed(now,telemetry,5000)) { telemetry=now; sendTelemetry(); }
  delay(2);
}
