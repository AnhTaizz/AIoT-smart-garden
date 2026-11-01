#pragma once
#include "garden.h"

namespace garden {
inline JsonDocument statePayload(Runtime& runtime, uint64_t uptime, const char* timestamp) {
  JsonDocument doc;
  doc["schema"]="state-v1"; doc["device_id"]=runtime.device; doc["boot_id"]=runtime.boot;
  doc["state_sequence"]=++runtime.stateSequence;
  // G02 v1 has no AUTO configuration action. Decisions stay on the server.
  doc["mode"]="MANUAL"; doc["relay_state"]=runtime.on ? "on":"off";
  if (runtime.lastId.empty()) { doc["last_command_id"]=nullptr; doc["last_command_sequence"]=nullptr; }
  else { doc["last_command_id"]=runtime.lastId; doc["last_command_sequence"]=runtime.lastSequence; }
  doc["clock_synced"]=timestamp!=nullptr; doc["reported_at"]=timestamp; doc["uptime_ms"]=uptime;
  return doc;
}
inline JsonDocument telemetryPayload(Runtime& runtime, uint64_t uptime, const char* timestamp,
                                    float temperature, float humidity, float soil) {
  bool aht=ahtValid(temperature,humidity);
  bool soilOk=std::isfinite(soil) && soil>=0 && soil<=100;
  JsonDocument doc;
  // Dry-run disables actuation; these remain measurements from physical sensors.
  doc["schema"]="telemetry-v1"; doc["simulated"]=false;
  doc["device_id"]=runtime.device; doc["boot_id"]=runtime.boot;
  doc["sequence"]=++runtime.telemetrySequence; doc["clock_synced"]=timestamp!=nullptr;
  doc["measured_at"]=timestamp; doc["uptime_ms"]=uptime;
  doc["temperature_c"]=nullptr; doc["air_humidity_pct"]=nullptr; doc["soil_moisture_pct"]=nullptr;
  if (aht) { doc["temperature_c"]=temperature; doc["air_humidity_pct"]=humidity; }
  if (soilOk) doc["soil_moisture_pct"]=soil;
  doc["sensor_status"]["aht20"]=aht ? "ok":"error";
  doc["sensor_status"]["soil"]=soilOk ? "ok":"error";
  return doc;
}
} // namespace garden
