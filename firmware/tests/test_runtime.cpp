#include "garden.h"
#include "payloads.h"
#include <cassert>
#include <iostream>

using garden::Runtime;
const char* timestamp="2026-11-01T00:00:00.000Z";
const int64_t utc=garden::utcMillis(timestamp);
int assertions=0;
#define CHECK(...) do { ++assertions; if (!(__VA_ARGS__)) { std::cerr << "FAILED line " << __LINE__ << ": " << #__VA_ARGS__ << '\n'; return 1; } } while(0)

JsonDocument command(int id=1, const char* action="pump_on", int seconds=2, uint64_t sequence=1) {
  JsonDocument d;
  char uuid[37]; snprintf(uuid,sizeof(uuid),"00000000-0000-4000-8000-%012d",id);
  d["schema"]="command-v1"; d["command_id"]=uuid; d["device_id"]="node_01";
  d["command_sequence"]=sequence; d["action"]=action;
  d["target_boot_id"]="boot_test";
  d["issued_at"]=timestamp; d["expires_at"]="2026-11-01T00:00:15.000Z";
  d["params"].to<JsonObject>();
  if (!strcmp(action,"pump_on")) d["params"]["duration_seconds"]=seconds;
  return d;
}
garden::Result send(Runtime& r, JsonDocument& d, uint32_t now=0, int64_t time=utc, bool enabled=true, bool retained=false) {
  std::string json; serializeJson(d,json);
  return r.command(json.data(),json.size(),now,time,time<0?nullptr:timestamp,enabled,retained);
}
std::string reason(const garden::Result& r) {
  JsonDocument d; deserializeJson(d,r.ack);
  return d["reason"].isNull() ? "":d["reason"].as<std::string>();
}
int main(int argc, char**) {
  garden::OutputGuard output;
  CHECK(!output.on);
  CHECK(!output.apply(true,false,true,0,2000) && !output.on); // dry-run
  CHECK(!output.apply(true,true,false,0,2000)); // broker disconnected
  CHECK(!output.apply(true,true,true,0,60001));
  CHECK(output.apply(true,true,true,0,2000));
  CHECK(!output.tick(499,true)); CHECK(output.tick(500,true) && !output.on);
  CHECK(!output.apply(true,true,true,501,2000)); // fault latched
  output=garden::OutputGuard{};
  CHECK(output.apply(true,true,true,0,2000));
  CHECK(output.tick(1,false) && !output.on); // Wi-Fi loss
  output=garden::OutputGuard{};
  output.lease=0xfffffff0U;
  CHECK(output.apply(true,true,true,0xfffffff0U,1000));
  output.lease=uint32_t(0xfffffff0U+999);
  CHECK(!output.tick(output.lease,true));
  CHECK(output.tick(uint32_t(0xfffffff0U+1000),true));
  Runtime r("node_01","boot_test");
  CHECK(!r.on && r.order==0 && r.lastId.empty());
  auto on=command(); auto applied=send(r,on,100);
  CHECK(applied.reply && reason(applied).empty() && r.on);
  std::string json; serializeJson(on,json); json+="garbage";
  Runtime trailing("node_01","boot_test");
  CHECK(!trailing.command(json.data(),json.size(),0,utc,timestamp,true).reply && !trailing.on);
  auto duplicate=send(r,on,1500);
  CHECK(duplicate.duplicate && duplicate.ack==applied.ack && r.started==100);
  CHECK(!r.tick(2099,true)); CHECK(r.tick(2100,true)); CHECK(!r.on);
  CHECK(send(r,on).duplicate && !r.on);
  auto next=command(2,"pump_on",60,2);
  CHECK(reason(send(r,next,0xfffffff0U)).empty());
  CHECK(!r.tick(uint32_t(0xfffffff0U+59999),true));
  CHECK(r.tick(uint32_t(0xfffffff0U+60000),true) && !r.on);
  for (int duration: {0,-1,61,120}) {
    Runtime t("node_01","boot_test"); auto d=command(1,"pump_on",duration);
    CHECK(reason(send(t,d))=="invalid_duration" && !t.on);
  }
  for (const char* value: {"true","1.5","\"2\"","null"}) {
    Runtime t("node_01","boot_test"); auto d=command();
    JsonDocument v; deserializeJson(v,value); d["params"]["duration_seconds"]=v.as<JsonVariant>();
    CHECK(reason(send(t,d))=="invalid_duration");
  }
  for (const char* field: {"schema","command_sequence","params","target_boot_id","issued_at","expires_at","action","device_id"}) {
    Runtime t("node_01","boot_test"); auto d=command(); d.remove(field);
    CHECK(reason(send(t,d))=="invalid_payload" && !t.on);
  }
  for (const char* value: {"true","0","-1","1.5","\"2\"","null"}) {
    Runtime t("node_01","boot_test"); auto d=command();
    JsonDocument v; deserializeJson(v,value); d["command_sequence"]=v.as<JsonVariant>();
    CHECK(reason(send(t,d))=="invalid_payload");
  }
  for (const char* bad: {"{","[]","null","{\"command_id\":null}","{\"command_id\":\"bad\"}"}) {
    CHECK(!r.command(bad,strlen(bad),0,utc,timestamp,true).reply);
  }
  Runtime nulls("node_01","boot_test");
  auto nul=command(); nul["action"]=std::string("pump_on\0extra",13);
  CHECK(reason(send(nulls,nul))=="invalid_payload");
  auto wrong=command(3); wrong["device_id"]="node_02";
  CHECK(!send(r,wrong).reply);
  wrong["device_id"]="node_01"; wrong["target_boot_id"]="old_boot";
  CHECK(reason(send(r,wrong))=="boot_mismatch");
  Runtime unsync("node_01","boot_test"); auto d=command();
  CHECK(reason(send(unsync,d,0,-1))=="clock_unsynced");
  Runtime expired("node_01","boot_test"); d=command(); d["expires_at"]=timestamp;
  CHECK(reason(send(expired,d))=="expired");
  auto off=command(4,"pump_off",0,10); off["target_boot_id"]="old_boot";
  CHECK(reason(send(r,off,0,-1)).empty() && !r.on && r.order==10);
  auto oldOn=command(5,"pump_on",2,9);
  CHECK(reason(send(r,oldOn))=="superseded");
  auto oldOff=command(6,"pump_off",0,2);
  CHECK(reason(send(r,oldOff)).empty() && r.order==10);
  Runtime busy("node_01","boot_test"); d=command(); send(busy,d);
  auto another=command(2,"pump_on",2,2);
  CHECK(reason(send(busy,another))=="busy");
  CHECK(busy.tick(1,false) && !busy.on); CHECK(send(busy,d).duplicate && !busy.on);
  Runtime reset("node_01","new_boot"); CHECK(!reset.on && reset.order==0);
  CHECK(reason(send(reset,d))=="boot_mismatch");
  Runtime dry("node_01","boot_test");
  CHECK(reason(send(dry,d,0,utc,false))=="safety_lock" && !dry.on);
  Runtime retained("node_01","boot_test");
  CHECK(reason(send(retained,d,0,utc,true,true))=="safety_lock" && !retained.on);
  Runtime full("node_01","boot_test");
  for (int i=1;i<=128;++i) { auto stop=command(i,"pump_off",0,i); send(full,stop); }
  auto overflow=command(129,"pump_on",2,129);
  CHECK(reason(send(full,overflow))=="safety_lock" && !full.on);
  off=command(130,"pump_off",0,130); CHECK(reason(send(full,off)).empty());
  const char* invalidDates[]={"2026-02-30T00:00:00Z","2025-02-29T00:00:00Z","2026-11-01T24:00:00Z",
    "2026-11-01T00:00:60Z","2026-11-01T00:00:00","2026-11-01T00:00:00.Z","2026-11-01T00:00:00Zjunk"};
  for (auto value: invalidDates) CHECK(garden::utcMillis(value)<0);
  CHECK(garden::utcMillis("2024-02-29T00:00:00Z")>=0);
  CHECK(garden::utcMillis("1970-01-01T00:00:00.001Z")==1);
  CHECK(std::isnan(garden::soilPercent(2000,0,0)));
  CHECK(std::isnan(garden::soilPercent(0,3200,1400)));
  CHECK(std::isnan(garden::soilPercent(4095,3200,1400)));
  CHECK(garden::soilPercent(2300,3200,1400)==50);
  CHECK(!garden::ahtValid(NAN,50) && !garden::ahtValid(25,101));
  CHECK(garden::ahtValid(25,50));
  Runtime refused("node_01","boot_test"); auto request=command();
  auto refusedAck=send(refused,request); refused.rejectActuation(refusedAck);
  CHECK(reason(refusedAck)=="safety_lock" && !refused.on);
  CHECK(send(refused,request).ack==refusedAck.ack && !refused.on);
  // Encoded 25 C / 50% RH, calibrated and not busy, with AHT20 CRC-8.
  uint8_t data[]={0x08,0x80,0x00,0x06,0x00,0x00,0};
  uint8_t crc=0xff;
  for (int i=0;i<6;++i) {
    crc^=data[i];
    for (int bit=0;bit<8;++bit) crc=uint8_t((crc&0x80) ? (crc<<1)^0x31:crc<<1);
  }
  data[6]=crc; float t=NAN,h=NAN;
  CHECK(garden::decodeAht20(data,t,h) && t==25 && h==50);
  data[6]^=1; CHECK(!garden::decodeAht20(data,t,h));
  data[0]=0x80; CHECK(!garden::decodeAht20(data,t,h));
  Runtime samples("node_01","boot_test");
  auto errors=garden::telemetryPayload(samples,100,nullptr,NAN,50,NAN);
  CHECK(errors["temperature_c"].isNull() && errors["air_humidity_pct"].isNull());
  CHECK(errors["soil_moisture_pct"].isNull() && errors["sensor_status"]["soil"]=="error");
  CHECK(!errors["clock_synced"].as<bool>() && errors["measured_at"].isNull());
  CHECK(errors["simulated"]==false);
  auto bootState=garden::statePayload(samples,100,nullptr);
  CHECK(bootState["relay_state"]=="off" && bootState["last_command_id"].isNull());
  CHECK(bootState["last_command_sequence"].isNull() && bootState["reported_at"].isNull());
  auto readings=garden::telemetryPayload(samples,200,timestamp,25,50,50);
  CHECK(readings["sensor_status"]["aht20"]=="ok" && readings["sequence"]==2);
  std::cout << "PASS " << assertions << " checks\n";
  // Fixture is consumed by backend's real Pydantic validator in software tests.
  if (argc>1) {
    std::cout << applied.ack << '\n';
    for (auto* doc: {&errors,&readings,&bootState}) {
      std::string encoded; serializeJson(*doc,encoded); std::cout << encoded << '\n';
    }
  }
  return 0;
}
