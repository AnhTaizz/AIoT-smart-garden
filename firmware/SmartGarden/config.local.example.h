#pragma once
// Copy to config.local.h; never commit real credentials.
#define GARDEN_WIFI_SSID ""
#define GARDEN_WIFI_PASSWORD ""
#define GARDEN_MQTT_HOST ""  // Private laptop LAN IP, never Docker hostname
#define GARDEN_MQTT_PORT 1883
#define GARDEN_MQTT_USER "esp32_node_01"
#define GARDEN_MQTT_PASSWORD ""
#define GARDEN_NTP_HOST ""  // Reachable LAN NTP service, or trusted Internet NTP
// First verify OFF with the pump adapter unplugged; keep these safe values.
// For an explicitly authorized real-control session, set DRY_RUN=0 and
// CONTROL_ENABLED=1. Never set soil endpoints from unmeasured placeholders.
#define GARDEN_DRY_RUN 1
#define GARDEN_CONTROL_ENABLED 0
// Actual measured dry/wet endpoints, not snapshot placeholders.
#define GARDEN_SOIL_DRY 0
#define GARDEN_SOIL_WET 0
