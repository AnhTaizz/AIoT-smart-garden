#pragma once

// Local secrets are deliberately excluded from Git.
#if __has_include("config.local.h")
#include "config.local.h"
#endif
#ifndef GARDEN_DRY_RUN
#define GARDEN_DRY_RUN 1
#endif
#ifndef GARDEN_WIFI_SSID
#define GARDEN_WIFI_SSID ""
#endif
#ifndef GARDEN_WIFI_PASSWORD
#define GARDEN_WIFI_PASSWORD ""
#endif
#ifndef GARDEN_MQTT_HOST
#define GARDEN_MQTT_HOST ""
#endif
#ifndef GARDEN_MQTT_PORT
#define GARDEN_MQTT_PORT 1883
#endif
#ifndef GARDEN_MQTT_USER
#define GARDEN_MQTT_USER ""
#endif
#ifndef GARDEN_MQTT_PASSWORD
#define GARDEN_MQTT_PASSWORD ""
#endif
#ifndef GARDEN_CONTROL_ENABLED
#define GARDEN_CONTROL_ENABLED 0
#endif
#ifndef GARDEN_DEVICE_ID
#define GARDEN_DEVICE_ID "node_01"
#endif
#ifndef GARDEN_NTP_HOST
#define GARDEN_NTP_HOST ""
#endif
#ifndef GARDEN_SOIL_DRY
#define GARDEN_SOIL_DRY 0
#endif
#ifndef GARDEN_SOIL_WET
#define GARDEN_SOIL_WET 0
#endif
constexpr int PIN_SDA = 21, PIN_SCL = 22, PIN_SOIL = 34, PIN_RELAY = 26;
constexpr unsigned PUMP_MAX_SECONDS = 60;
static_assert(PUMP_MAX_SECONDS >= 1 && PUMP_MAX_SECONDS <= 60, "Unsafe pump limit");
