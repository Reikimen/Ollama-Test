#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_NeoPixel.h>

// ===== 家具配置宏 =====
#define ENABLE_DESK_LAMP true      // 台灯
#define ENABLE_CEILING_LIGHT true  // WS2812顶灯
#define ENABLE_FAN true            // 风扇

// ===== 硬件引脚配置 =====
#define DESK_LAMP_PIN 5            // GPIO5 (D1)
#define FAN_PIN 12                 // GPIO12 (D6)
#define WS2812_PIN 4               // GPIO4 (D2)
#define WS2812_COUNT 12            // WS2812 LED数量

// ===== 网络配置 =====
// const char* ssid = "CE-Dankao";
// const char* password = "CELAB2025";
const char* ssid = "CE-Wlan-Helper";
const char* password = "ThanksDankao";

// 服务器配置
// const char* server_host = "192.168.153.177";
const char* server_host = "192.168.8.198";
const int server_port = 8002;
const char* server_path = "/ws";

// 房间配置
// const char* TARGET_ROOM = "living_room";  // 修改这里指定目标房间
// const char* TARGET_ROOM = "bedroom";     // 卧室
// const char* TARGET_ROOM = "kitchen";     // 厨房
// const char* TARGET_ROOM = "study";       // 书房
const char* TARGET_ROOM = "bathroom";    // 浴室

// WebSocket客户端
WebSocketsClient webSocket;

// 状态变量
bool wifiConnected = false;
bool wsConnected = false;

// ===== 设备状态 =====
struct DeviceState {
  bool status;
  int brightness;
  int color_temp;
};

#if ENABLE_DESK_LAMP
DeviceState desk_lamp = {false, 50, 3000};
#endif

#if ENABLE_CEILING_LIGHT
DeviceState ceiling_light = {false, 50, 4000};
Adafruit_NeoPixel strip(WS2812_COUNT, WS2812_PIN, NEO_GRB + NEO_KHZ800);
#endif

#if ENABLE_FAN
bool fan_status = false;  // 风扇只需要开关状态
#endif

// ===== WiFi连接函数 =====
void connectWiFi() {
  Serial.printf("📶 Connecting to: %s\n", ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(1000);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n✅ WiFi Connected!");
    Serial.printf("📍 ESP8266 IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("📡 Signal: %d dBm\n", WiFi.RSSI());
  } else {
    wifiConnected = false;
    Serial.println("\n❌ WiFi failed!");
  }
}

// ===== WS2812控制函数 =====
#if ENABLE_CEILING_LIGHT
void updateCeilingLight() {
  Serial.println("🎨 === WS2812 Ceiling Light Update ===");
  
  if (ceiling_light.status) {
    // 根据色温和亮度计算RGB值
    int brightness = map(ceiling_light.brightness, 0, 100, 0, 255);
    
    // 简化的色温转换（2700K暖白 - 6500K冷白）
    int warmth = map(ceiling_light.color_temp, 2700, 6500, 255, 0);
    int r = brightness;
    int g = (brightness * (255 - warmth / 2)) / 255;
    int b = (brightness * warmth) / 255;
    
    Serial.printf("   💡 Status: ON\n");
    Serial.printf("   🔆 Brightness: %d%% (PWM: %d)\n", ceiling_light.brightness, brightness);
    Serial.printf("   🌡️ Color Temp: %dK (Warmth: %d)\n", ceiling_light.color_temp, warmth);
    Serial.printf("   🎨 RGB Values: R=%d, G=%d, B=%d\n", r, g, b);
    Serial.printf("   📍 Updating %d LEDs\n", WS2812_COUNT);
    
    // 设置所有LED
    for(int i = 0; i < WS2812_COUNT; i++) {
      strip.setPixelColor(i, strip.Color(r, g, b));
    }
  } else {
    Serial.printf("   💡 Status: OFF\n");
    Serial.printf("   ⚫ Turning off all %d LEDs\n", WS2812_COUNT);
    
    // 关闭所有LED
    for(int i = 0; i < WS2812_COUNT; i++) {
      strip.setPixelColor(i, strip.Color(0, 0, 0));
    }
  }
  
  strip.show();
  Serial.println("   ✅ WS2812 update complete");
  Serial.println("=====================================");
}
#endif

// ===== 台灯控制函数 =====
#if ENABLE_DESK_LAMP
void updateDeskLamp() {
  Serial.println("💡 === Desk Lamp Update ===");
  
  if (desk_lamp.status) {
    // PWM控制亮度
    int pwmValue = map(desk_lamp.brightness, 0, 100, 0, 1023);
    analogWrite(DESK_LAMP_PIN, pwmValue);
    
    Serial.printf("   💡 Status: ON\n");
    Serial.printf("   🔆 Brightness: %d%%\n", desk_lamp.brightness);
    Serial.printf("   📊 PWM Value: %d/1023\n", pwmValue);
    Serial.printf("   📍 Output Pin: GPIO%d\n", DESK_LAMP_PIN);
  } else {
    digitalWrite(DESK_LAMP_PIN, LOW);
    
    Serial.printf("   💡 Status: OFF\n");
    Serial.printf("   📍 Output Pin: GPIO%d set to LOW\n", DESK_LAMP_PIN);
  }
  
  Serial.println("   ✅ Desk lamp update complete");
  Serial.println("===========================");
}
#endif

// ===== 风扇控制函数 =====
#if ENABLE_FAN
void updateFan() {
  Serial.println("🌀 === Fan Update ===");
  
  digitalWrite(FAN_PIN, fan_status ? HIGH : LOW);
  
  Serial.printf("   🌀 Status: %s\n", fan_status ? "ON" : "OFF");
  Serial.printf("   📍 Output Pin: GPIO%d set to %s\n", 
                FAN_PIN, fan_status ? "HIGH" : "LOW");
  Serial.println("   ✅ Fan update complete");
  Serial.println("=====================");
}
#endif

// ===== 处理IoT控制消息 =====
void handleControlMessage(JsonObject& command) {
  String device = command["device"].as<String>();
  String action = command["action"].as<String>();
  String location = command["location"].as<String>();
  
  // 只处理目标房间的命令
  if (location != TARGET_ROOM) {
    Serial.printf("🚫 Ignoring command for room: %s (target: %s)\n", 
                  location.c_str(), TARGET_ROOM);
    return;
  }
  
  JsonObject params = command["parameters"];
  
  Serial.println("\n🎮 === Processing Control Command ===");
  Serial.printf("   📍 Room: %s\n", location.c_str());
  Serial.printf("   🔧 Device: %s\n", device.c_str());
  Serial.printf("   ⚡ Action: %s\n", action.c_str());
  
  // 打印所有参数
  if (params) {
    Serial.println("   📊 Parameters:");
    for (JsonPair kv : params) {
      Serial.printf("      - %s: ", kv.key().c_str());
      if (kv.value().is<int>()) {
        Serial.printf("%d\n", kv.value().as<int>());
      } else if (kv.value().is<float>()) {
        Serial.printf("%.1f\n", kv.value().as<float>());
      } else {
        Serial.printf("%s\n", kv.value().as<String>().c_str());
      }
    }
  }
  Serial.println("=====================================");
  
  // 处理顶灯命令
  #if ENABLE_CEILING_LIGHT
  if (device == "ceiling_light") {
    if (action == "on") {
      ceiling_light.status = true;
    } else if (action == "off") {
      ceiling_light.status = false;
    } else if (action == "toggle") {
      ceiling_light.status = !ceiling_light.status;
    } else if (action == "set_brightness" && params.containsKey("brightness")) {
      ceiling_light.brightness = params["brightness"];
      ceiling_light.status = (ceiling_light.brightness > 0);
    } else if (action == "set_color_temp" && params.containsKey("color_temp")) {
      ceiling_light.color_temp = params["color_temp"];
    }
    updateCeilingLight();
    Serial.printf("💡 Ceiling light - Status: %s, Brightness: %d%%, Color temp: %dK\n", 
                  ceiling_light.status ? "ON" : "OFF", 
                  ceiling_light.brightness, 
                  ceiling_light.color_temp);
  }
  #endif
  
  // 处理台灯命令
  #if ENABLE_DESK_LAMP
  if (device == "desk_lamp") {
    if (action == "on") {
      desk_lamp.status = true;
    } else if (action == "off") {
      desk_lamp.status = false;
    } else if (action == "toggle") {
      desk_lamp.status = !desk_lamp.status;
    } else if (action == "set_brightness" && params.containsKey("brightness")) {
      desk_lamp.brightness = params["brightness"];
      desk_lamp.status = (desk_lamp.brightness > 0);
    }
    updateDeskLamp();
    Serial.printf("🛋️ Desk lamp - Status: %s, Brightness: %d%%\n", 
                  desk_lamp.status ? "ON" : "OFF", 
                  desk_lamp.brightness);
  }
  #endif
  
  // 处理风扇命令
  #if ENABLE_FAN
  if (device == "fan") {
    if (action == "on") {
      fan_status = true;
    } else if (action == "off") {
      fan_status = false;
    } else if (action == "toggle") {
      fan_status = !fan_status;
    }
    updateFan();
    Serial.printf("🌀 Fan - Status: %s\n", 
                  fan_status ? "ON" : "OFF");
  }
  #endif
}

// ===== WebSocket消息处理 =====
void handleMessage(const char* message) {
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.printf("❌ JSON parse error: %s\n", error.c_str());
    return;
  }
  
  String type = doc["type"].as<String>();
  
  // 过滤sensor_update消息，不显示日志
  if (type == "sensor_update") {
    return;  // 直接返回，不处理也不显示
  }
  
  // 过滤error消息的原始内容
  if (type == "error") {
    Serial.println("\n❌ === Error Message ===");
    Serial.printf("Error: %s\n", doc["message"].as<String>().c_str());
    Serial.println("======================");
    return;
  }
  
  // 其他消息只显示类型，不显示原始内容
  Serial.printf("\n📋 Processing message type: %s\n", type.c_str());
  
  if (type == "control") {
    // 处理控制命令
    if (doc["commands"].is<JsonArray>()) {
      JsonArray commands = doc["commands"];
      Serial.printf("🎮 Found %d commands to process\n", commands.size());
      
      for (JsonObject command : commands) {
        Serial.println("\n--- Processing Command ---");
        Serial.printf("Device: %s\n", command["device"].as<String>().c_str());
        Serial.printf("Action: %s\n", command["action"].as<String>().c_str());
        Serial.printf("Location: %s\n", command["location"].as<String>().c_str());
        
        handleControlMessage(command);
      }
    }
  } else if (type == "control_results") {
    // 处理控制结果反馈
    Serial.println("✅ Control command acknowledged");
  } else if (type == "init") {
    Serial.println("🏠 === IoT Service Initialized ===");
    
    // 解析并应用初始设备状态
    if (doc["devices"].is<JsonObject>()) {
      JsonObject devices = doc["devices"];
      
      // 检查并更新ceiling_light状态
      #if ENABLE_CEILING_LIGHT
      if (devices.containsKey("ceiling_light")) {
        JsonObject lights = devices["ceiling_light"];
        if (lights.containsKey(TARGET_ROOM)) {
          JsonObject roomLight = lights[TARGET_ROOM];
          ceiling_light.status = (roomLight["status"].as<String>() == "on");
          ceiling_light.brightness = roomLight["brightness"] | 50;
          ceiling_light.color_temp = roomLight["color_temp"] | 4000;
          
          Serial.printf("   💡 Ceiling light initial state: %s, %d%%, %dK\n", 
                        ceiling_light.status ? "ON" : "OFF",
                        ceiling_light.brightness,
                        ceiling_light.color_temp);
          updateCeilingLight();
        }
      }
      #endif
      
      // 检查并更新desk_lamp状态
      #if ENABLE_DESK_LAMP
      if (devices.containsKey("desk_lamp")) {
        JsonObject lamps = devices["desk_lamp"];
        if (lamps.containsKey(TARGET_ROOM)) {
          JsonObject roomLamp = lamps[TARGET_ROOM];
          desk_lamp.status = (roomLamp["status"].as<String>() == "on");
          desk_lamp.brightness = roomLamp["brightness"] | 50;
          
          Serial.printf("   🛋️ Desk lamp initial state: %s, %d%%\n", 
                        desk_lamp.status ? "ON" : "OFF",
                        desk_lamp.brightness);
          updateDeskLamp();
        }
      }
      #endif
      
      // 检查并更新fan状态
      #if ENABLE_FAN
      if (devices.containsKey("fan")) {
        JsonObject fans = devices["fan"];
        if (fans.containsKey(TARGET_ROOM)) {
          JsonObject roomFan = fans[TARGET_ROOM];
          fan_status = (roomFan["status"].as<String>() == "on");
          
          Serial.printf("   🌀 Fan initial state: %s\n", 
                        fan_status ? "ON" : "OFF");
          updateFan();
        }
      }
      #endif
    }
    
    Serial.println("=================================");
  } else if (type == "device_update") {
    // 处理设备状态更新
    Serial.println("📡 === Device Update Message ===");
    
    // 显示完整的JSON消息用于调试
    Serial.println("📄 Debug - Full device_update JSON:");
    String jsonStr;
    serializeJson(doc, jsonStr);
    Serial.println(jsonStr);
    Serial.println("---");
    
    String device = doc["device"].as<String>();
    String location = doc["location"].as<String>();
    String status = "";
    
    // 检查state对象
    if (doc.containsKey("state")) {
      JsonObject state = doc["state"];
      status = state["status"].as<String>();
      Serial.println("   📦 Found state object:");
      Serial.printf("      - Status from state: %s\n", status.c_str());
    } else if (doc.containsKey("status")) {
      // 向后兼容：如果有直接的status字段
      status = doc["status"].as<String>();
      Serial.printf("   📊 Status from root: %s\n", status.c_str());
    }
    
    Serial.printf("   🔧 Device: %s\n", device.c_str());
    Serial.printf("   📍 Location: %s\n", location.c_str());
    Serial.printf("   📊 Final Status: %s\n", status.c_str());
    
    // 只处理目标房间的更新
    if (location != TARGET_ROOM) {
      Serial.printf("   🚫 Ignoring update for room: %s\n", location.c_str());
      return;
    }
    
    // 根据设备类型处理状态更新
    #if ENABLE_CEILING_LIGHT
    if (device == "ceiling_light") {
      ceiling_light.status = (status == "on");
      
      // 检查state对象中的其他参数
      if (doc.containsKey("state")) {
        JsonObject state = doc["state"];
        if (state.containsKey("brightness")) {
          ceiling_light.brightness = state["brightness"];
        }
        if (state.containsKey("color_temp")) {
          ceiling_light.color_temp = state["color_temp"];
        }
      }
      
      Serial.println("   🎨 Updating ceiling light from device_update");
      updateCeilingLight();
    }
    #endif
    
    #if ENABLE_DESK_LAMP
    if (device == "desk_lamp") {
      desk_lamp.status = (status == "on");
      
      // 检查state对象中的其他参数
      if (doc.containsKey("state")) {
        JsonObject state = doc["state"];
        if (state.containsKey("brightness")) {
          desk_lamp.brightness = state["brightness"];
        }
      }
      
      Serial.println("   💡 Updating desk lamp from device_update");
      updateDeskLamp();
    }
    #endif
    
    #if ENABLE_FAN
    if (device == "fan") {
      Serial.printf("   🔍 Debug - Comparing device '%s' with 'fan'\n", device.c_str());
      Serial.printf("   🔍 Debug - Current fan_status before update: %s\n", fan_status ? "ON" : "OFF");
      Serial.printf("   🔍 Debug - Status value: '%s'\n", status.c_str());
      
      fan_status = (status == "on");
      
      Serial.printf("   🔍 Debug - New fan_status after update: %s\n", fan_status ? "ON" : "OFF");
      Serial.println("   🌀 Updating fan from device_update");
      updateFan();
    }
    #endif
    
    Serial.println("===============================");
  } else if (type != "pong" && type != "ping") {
    // 忽略ping/pong，只报告真正未知的消息
    Serial.printf("❓ Unknown message type: %s\n", type.c_str());
  }
}

// ===== WebSocket事件处理 =====
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println("🔴 Disconnected from IoT Service");
      break;
      
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.printf("🟢 Connected to IoT Service: %s\n", payload);
      // 连接成功后，服务器会自动发送init消息
      break;
      
    case WStype_TEXT:
      handleMessage((char*)payload);
      break;
      
    case WStype_ERROR:
      Serial.printf("❌ WebSocket Error: %s\n", payload);
      break;
  }
}

// ===== 初始化WebSocket =====
void initWebSocket() {
  Serial.printf("🔌 Connecting to WebSocket: ws://%s:%d%s\n", 
                server_host, server_port, server_path);
  
  webSocket.begin(server_host, server_port, server_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

// ===== Setup函数 =====
void setup() {
  Serial.begin(115200);
  delay(1000);  // 增加延迟等待串口稳定
  
  // 清除串口缓冲区
  while(Serial.available()) {
    Serial.read();
  }
  
  // 输出一些空行来分隔乱码
  Serial.println("\n\n\n");
  
  Serial.println("============================================================");
  Serial.printf("🏠 ESP8266 IoT Furniture Controller - Room: %s\n", TARGET_ROOM);
  Serial.println("============================================================");
  
  // 显示启用的设备
  Serial.println("\n📋 Enabled devices:");
  #if ENABLE_DESK_LAMP
  Serial.println("   ✅ Desk Lamp");
  #endif
  #if ENABLE_CEILING_LIGHT
  Serial.println("   ✅ Ceiling Light (WS2812)");
  #endif
  #if ENABLE_FAN
  Serial.println("   ✅ Fan");
  #endif
  
  // 初始化硬件引脚
  Serial.println("\n🔧 Initializing hardware...");
  
  #if ENABLE_DESK_LAMP
  pinMode(DESK_LAMP_PIN, OUTPUT);
  digitalWrite(DESK_LAMP_PIN, LOW);
  Serial.println("   ✅ Desk lamp pin configured");
  #endif
  
  #if ENABLE_CEILING_LIGHT
  strip.begin();
  strip.show(); // 初始化所有LED为关闭状态
  Serial.printf("   ✅ WS2812 initialized with %d LEDs\n", WS2812_COUNT);
  #endif
  
  #if ENABLE_FAN
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);
  Serial.println("   ✅ Fan pin configured");
  #endif
  
  // 连接WiFi
  Serial.println("\n📶 Connecting to network...");
  connectWiFi();
  
  if (wifiConnected) {
    delay(2000);
    initWebSocket();
  } else {
    Serial.println("❌ Cannot proceed without WiFi connection");
  }
  
  Serial.println("\n✅ Setup complete!");
  Serial.println("============================================================\n");
}

// ===== 主循环 =====
void loop() {
  // 检查WiFi连接
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi lost, reconnecting...");
    connectWiFi();
    if (wifiConnected) {
      initWebSocket();
    }
    return;
  }
  
  // 处理WebSocket
  webSocket.loop();
  
  // 添加看门狗喂狗
  yield();
  delay(10);
}