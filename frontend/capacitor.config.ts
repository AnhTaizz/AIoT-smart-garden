import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.aiot.smartgarden",
  appName: "Smart Garden",
  webDir: "dist-mobile",
  // Bundled assets, not a remote website/shortcut or live-reload server URL.
  server: {
    hostname: "localhost",
    androidScheme: "https",
    iosScheme: "capacitor",
  },
};

export default config;
