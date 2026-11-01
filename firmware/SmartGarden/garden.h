#pragma once
#include <ArduinoJson.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace garden {
inline bool plainString(JsonVariantConst value) {
  if (!value.is<const char*>()) return false;
  auto str=value.as<JsonString>();
  return str.size()==strlen(str.c_str());
}
inline bool identifier(const char* s) {
  if (!s || !*s || strlen(s) > 64) return false;
  for (; *s; ++s) if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') ||
      (*s >= '0' && *s <= '9') || *s == '_' || *s == '-')) return false;
  return true;
}
inline bool uuid(const char* s) {
  if (!s || strlen(s) != 36) return false;
  for (int i = 0; i < 36; ++i) {
    if (i == 8 || i == 13 || i == 18 || i == 23) { if (s[i] != '-') return false; }
    else if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f') ||
               (s[i] >= 'A' && s[i] <= 'F'))) return false;
  }
  return true;
}
// Strict calendar validation; no mktime normalization, local timezone or DST.
// Accept server UTC timestamps with optional 1..9 fractional digits.
inline int64_t utcMillis(const char* s) {
  if (!s) return -1;
  const size_t n = strlen(s);
  if (n < 20 || n > 30 || s[4]!='-' || s[7]!='-' || s[10]!='T' ||
      s[13]!=':' || s[16]!=':' || s[n-1]!='Z') return -1;
  auto number = [&](int p, int len) {
    int v=0; for (int i=p;i<p+len;++i) {
      if (s[i]<'0' || s[i]>'9') return -1;
      v=v*10+s[i]-'0';
    } return v;
  };
  int y=number(0,4), m=number(5,2), d=number(8,2);
  int h=number(11,2), min=number(14,2), sec=number(17,2), ms=0;
  if (y<1970 || y>9999 || m<1 || m>12 || d<1 || h<0 || h>23 ||
      min<0 || min>59 || sec<0 || sec>59) return -1;
  const int days[]={31,28,31,30,31,30,31,31,30,31,30,31};
  bool leap=y%4==0 && (y%100!=0 || y%400==0);
  if (d>days[m-1]+(m==2 && leap)) return -1;
  if (n!=20) {
    if (s[19]!='.' || n<22) return -1;
    int factor=100;
    for (size_t i=20;i<n-1;++i) {
      if (s[i]<'0' || s[i]>'9') return -1;
      ms+=(s[i]-'0')*factor; factor/=10;
    }
  }
  int64_t total=0;
  for (int year=1970;year<y;++year) total+=365+(year%4==0 && (year%100!=0 || year%400==0));
  for (int month=1;month<m;++month) total+=days[month-1]+(month==2 && leap);
  total+=d-1;
  return ((total*24+h)*3600+min*60+sec)*1000+ms;
}
inline bool elapsed(uint32_t now, uint32_t start, uint32_t duration) {
  return uint32_t(now-start)>=duration;
}
// Pure actuator guard shared by the ESP32 safety task and native tests.
struct OutputGuard {
  bool on=false, fault=false;
  uint32_t start=0, duration=0, lease=0;
  void stop() { on=false; }
  bool apply(bool requested, bool enabled, bool connected, uint32_t now, uint32_t ms) {
    if (!requested || !enabled || !connected || fault || elapsed(now,lease,500) || ms<1000 || ms>60000) {
      stop(); return false;
    }
    if (!on) { start=now; duration=ms; on=true; }
    return on;
  }
  bool tick(uint32_t now, bool wifi) {
    if (on && (!wifi || elapsed(now,start,duration) || elapsed(now,lease,500))) {
      stop(); fault=true; return true;
    }
    return false;
  }
};
inline float soilPercent(int raw, int dry, int wet) {
  if (raw<=15 || raw>=4080 || dry<16 || dry>4079 || wet<16 || wet>4079 ||
      std::abs(dry-wet)<100) return NAN;
  return std::max(0.0f, std::min(100.0f, 100.0f*(raw-dry)/(wet-dry)));
}
inline bool ahtValid(float t, float h) {
  return std::isfinite(t) && std::isfinite(h) && t>=-40 && t<=85 && h>=0 && h<=100;
}
inline bool decodeAht20(const uint8_t* data, float& t, float& h) {
  uint8_t crc=0xff;
  for (int i=0;i<6;++i) {
    crc^=data[i];
    for (int bit=0;bit<8;++bit) crc=uint8_t((crc&0x80) ? (crc<<1)^0x31:crc<<1);
  }
  if (crc!=data[6] || (data[0]&0x80) || !(data[0]&0x08)) return false;
  uint32_t humidity=(uint32_t(data[1])<<12) | (uint32_t(data[2])<<4) | (data[3]>>4);
  uint32_t temperature=(uint32_t(data[3]&15)<<16) | (uint32_t(data[4])<<8) | data[5];
  h=humidity*100.0f/1048576; t=temperature*200.0f/1048576-50;
  return ahtValid(t,h);
}

struct Result { bool reply=false; bool duplicate=false; std::string ack; };
struct JsonInput {
  const char* data; size_t length, offset=0;
  int read() { return offset<length ? uint8_t(data[offset++]):-1; }
  size_t readBytes(char* buffer, size_t count) {
    count=std::min(count,length-offset);
    memcpy(buffer,data+offset,count); offset+=count; return count;
  }
};
class Runtime {
 public:
  std::string device, boot, lastId;
  uint64_t order=0, lastSequence=0, stateSequence=0, telemetrySequence=0;
  bool on=false;
  uint32_t started=0, durationMs=0;
  explicit Runtime(std::string id, std::string bootId):device(id),boot(bootId) {}
  bool stop() { bool changed=on; on=false; durationMs=0; return changed; }
  bool tick(uint32_t now, bool connected) {
    return on && (!connected || elapsed(now,started,durationMs)) ? stop() : false;
  }
  void rejectActuation(Result& result) {
    // Validation succeeded but the separately guarded driver refused ON.
    JsonDocument ack; deserializeJson(ack,result.ack);
    std::string id=ack["command_id"].as<std::string>();
    ack["status"]="rejected"; ack["reason"]="safety_lock";
    result.ack.clear(); serializeJson(ack,result.ack);
    for (auto& item: cache) if (item.first==id) { item.second=result.ack; break; }
    stop();
  }
  // Call only from the owner task; actuator safety task uses its own guarded timer.
  Result command(const char* data, size_t len, uint32_t now, int64_t utc,
                 const char* timestamp, bool authorized, bool retained=false) {
    JsonDocument doc;
    JsonInput input{data,len};
    if (len>2048 || memchr(data,0,len) || deserializeJson(doc,input,DeserializationOption::NestingLimit(6)) ||
        !doc.is<JsonObject>()) return {};
    for (size_t i=input.offset;i<len;++i)
      if (data[i]!=' ' && data[i]!='\r' && data[i]!='\n' && data[i]!='\t') return {};
    const char* id=doc["command_id"].as<const char*>();
    if (!plainString(doc["command_id"]) || !uuid(id)) return {};
    const char* target=doc["device_id"].as<const char*>();
    if (identifier(target) && device!=target) return {};
    for (const auto& item: cache) if (item.first==id) return {true,true,item.second};
    auto finish=[&](const char* reason) {
      JsonDocument ack;
      ack["schema"]="ack-v1"; ack["command_id"]=id; ack["device_id"]=device;
      ack["boot_id"]=boot; ack["status"]=reason ? "rejected":"applied";
      ack["reason"]=reason; ack["clock_synced"]=utc>=0; ack["acked_at"]=timestamp;
      std::string encoded; serializeJson(ack,encoded);
      // Never evict IDs and accidentally reapply an old ON. Once full, lock ON
      // until reboot; still permit OFF. Memory remains bounded.
      if (cache.size()<128) cache.emplace_back(id,encoded);
      return Result{true,false,encoded};
    };
    const char* schema=doc["schema"].as<const char*>();
    const char* action=doc["action"].as<const char*>();
    int64_t issued=utcMillis(doc["issued_at"].as<const char*>());
    int64_t expiry=utcMillis(doc["expires_at"].as<const char*>());
    if (!plainString(doc["device_id"]) || !identifier(target) ||
        !plainString(doc["schema"]) || !schema || strcmp(schema,"command-v1") ||
        !plainString(doc["action"]) || !action || strlen(action)>64 || !doc["command_sequence"].is<uint64_t>() ||
        doc["command_sequence"].is<bool>() || doc["command_sequence"].as<uint64_t>()<1 ||
        !doc["params"].is<JsonObject>() || doc["target_boot_id"].isUnbound() ||
        !(doc["target_boot_id"].isNull() || (plainString(doc["target_boot_id"]) && identifier(doc["target_boot_id"].as<const char*>()))) ||
        !plainString(doc["issued_at"]) || !plainString(doc["expires_at"]) || issued<0 || expiry<0)
      return finish("invalid_payload");
    bool off=strcmp(action,"pump_off")==0;
    if (!off && strcmp(action,"pump_on")) return finish("unsupported_action");
    auto params=doc["params"].as<JsonObject>();
    uint64_t seq=doc["command_sequence"].as<uint64_t>();
    if (off) {
      if (params.size()!=0) return finish("invalid_payload");
      stop();
    } else {
      if (params.size()!=1 || params["duration_seconds"].isUnbound()) return finish("invalid_payload");
      JsonVariantConst value=params["duration_seconds"];
      if (!value.is<unsigned>() || value.is<bool>() || value.as<unsigned>()<1 || value.as<unsigned>()>60)
        return finish("invalid_duration");
      if (doc["target_boot_id"].isNull() || boot!=doc["target_boot_id"].as<const char*>()) return finish("boot_mismatch");
      if (utc<0) return finish("clock_unsynced");
      if (expiry<=utc) return finish("expired");
      if (seq<=order) return finish("superseded");
      if (on) return finish("busy");
      if (!authorized || retained || cache.size()>=128) return finish("safety_lock");
      on=true; started=now; durationMs=value.as<unsigned>()*1000;
    }
    order=std::max(order,seq); lastId=id; lastSequence=seq;
    return finish(nullptr);
  }
 private:
  std::vector<std::pair<std::string,std::string>> cache;
};
} // namespace garden
