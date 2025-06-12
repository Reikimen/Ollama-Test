#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// WiFi配置
const char* ssid = "CE-Hub-Student";
const char* password = "casa-ce-gagarin-public-service";

// 服务器配置
const char* server_host = "10.129.113.188";
const int server_port = 8002; // IoT服务端口
const char* server_path = "/ws";

// WebSocket客户端
WebSocketsClient webSocket;

// 状态
bool wifiConnected = false;
bool wsConnected = false;
unsigned long lastSensorTime = 0;
const unsigned long SENSOR_INTERVAL = 30000; // 30秒发送一次

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("============================================================");
  Serial.println("🌡️ ESP8266 IoT Sensor Node (Correct Format)");
  Serial.println("============================================================");
  
  connectWiFi();
  
  if (wifiConnected) {
    delay(3000);
    initWebSocket();
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi lost, reconnecting...");
    connectWiFi();
    return;
  }
  
  webSocket.loop();
  
  // 定期发送传感器数据
  if (wsConnected && (millis() - lastSensorTime >= SENSOR_INTERVAL)) {
    sendSensorData();
    lastSensorTime = millis();
  }
  
  delay(100);
}

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

void initWebSocket() {
  Serial.printf("🔌 WebSocket: ws://%s:%d%s\n", server_host, server_port, server_path);
  
  webSocket.begin(server_host, server_port, server_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(10000);
  
  Serial.println("⚙️ WebSocket configured for IoT Service");
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  unsigned long elapsed = millis() / 1000;
  
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.printf("[%lus] 🔴 Disconnected from IoT Service\n", elapsed);
      break;
      
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.printf("[%lus] 🟢 Connected to IoT Service: %s\n", elapsed, payload);
      
      // 连接成功后等待3秒再发送第一条消息
      delay(3000);
      break;
      
    case WStype_TEXT:
      Serial.printf("[%lus] 📨 Received (%d bytes): %s\n", elapsed, length, payload);
      handleMessage((char*)payload);
      break;
      
    case WStype_ERROR:
      Serial.printf("[%lus] ❌ Error: %s\n", elapsed, payload);
      break;
      
    case WStype_PING:
      Serial.printf("[%lus] 🏓 Ping\n", elapsed);
      break;
      
    case WStype_PONG:
      Serial.printf("[%lus] 🏓 Pong\n", elapsed);
      break;
      
    default:
      Serial.printf("[%lus] 🔶 Event type: %d\n", elapsed, type);
      break;
  }
}

void sendSensorData() {
  if (!wsConnected) {
    Serial.println("⚠️ Cannot send sensor data - not connected");
    return;
  }
  
  // 生成真实的传感器数据
  float temperature = 23.5 + random(-50, 50) / 100.0; // 23.0-24.0°C
  float humidity = 55.0 + random(-200, 200) / 100.0;  // 53.0-57.0%
  int co2 = 420 + random(-50, 80);                     // 370-500 ppm
  int voc = 15 + random(-10, 25);                      // 5-40 ppb
  int light_level = 300 + random(-100, 300);          // 200-600 lux
  bool motion = (random(0, 100) < 10);                // 10% 概率有人

  // 使用IoT服务期望的正确格式
  DynamicJsonDocument doc(1024);
  
  // 重要：使用正确的消息类型和格式
  doc["type"] = "get_sensors";  // 请求获取传感器数据，而不是直接发送
  doc["location"] = "living_room";
  doc["device_id"] = WiFi.macAddress();
  
  String message;
  serializeJson(doc, message);
  
  Serial.printf("🔍 Requesting sensor data from IoT service\n");
  Serial.printf("📤 Message: %s\n", message.c_str());
  
  bool result = webSocket.sendTXT(message);
  Serial.printf("📤 Send result: %s\n", result ? "SUCCESS" : "FAILED");
  
  // 等待2秒后发送实际的传感器数据更新请求
  delay(2000);
  sendActualSensorUpdate(temperature, humidity, co2, voc, light_level, motion);
}

void sendActualSensorUpdate(float temp, float hum, int co2, int voc, int light, bool motion) {
  if (!wsConnected) return;
  
  // 发送符合IoT服务期望的设备控制格式
  DynamicJsonDocument doc(1024);
  
  // 使用control类型，模拟传感器设备的状态更新
  doc["type"] = "control";
  
  // 创建commands数组
  JsonArray commands = doc.createNestedArray("commands");
  
  // 添加传感器更新命令
  JsonObject sensorCmd = commands.createNestedObject();
  sensorCmd["device"] = "sensors";
  sensorCmd["action"] = "data_update";
  sensorCmd["location"] = "living_room";
  
  // 添加传感器参数
  JsonObject params = sensorCmd.createNestedObject("parameters");
  params["temperature"] = temp;
  params["humidity"] = hum;
  params["co2"] = co2;
  params["voc"] = voc;
  params["light_level"] = light;
  params["motion"] = motion;
  params["device_id"] = WiFi.macAddress();
  params["source"] = "esp8266";
  params["timestamp"] = millis();
  
  String message;
  serializeJson(doc, message);
  
  Serial.printf("🌡️ Updating sensor data: %.1f°C, %.1f%%, %dppm CO2, %dppb VOC\n", 
                temp, hum, co2, voc);
  Serial.printf("📤 Control message: %s\n", message.c_str());
  
  bool result = webSocket.sendTXT(message);
  Serial.printf("📤 Update result: %s\n", result ? "SUCCESS" : "FAILED");
}

void handleMessage(const char* message) {
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.printf("❌ JSON parse error: %s\n", error.c_str());
    return;
  }
  
  String type = doc["type"].as<String>();
  Serial.printf("📋 Message type: %s\n", type.c_str());
  
  if (type == "init") {
    Serial.println("✅ IoT Service initialization received");
    Serial.println("📊 Devices and sensors state received");
    
    // 显示接收到的设备状态
    if (doc["devices"].is<JsonObject>()) {
      Serial.println("🏠 Available devices:");
      for (JsonPair device : doc["devices"].as<JsonObject>()) {
        Serial.printf("   - %s\n", device.key().c_str());
      }
    }
    
    if (doc["sensors"].is<JsonObject>()) {
      Serial.println("🌡️ Available sensors:");
      for (JsonPair sensor : doc["sensors"].as<JsonObject>()) {
        Serial.printf("   - %s\n", sensor.key().c_str());
      }
    }
    
  } else if (type == "control_results") {
    Serial.println("✅ Control command results received");
    
    if (doc["results"].is<JsonArray>()) {
      for (JsonObject result : doc["results"].as<JsonArray>()) {
        String status = result["status"].as<String>();
        String device = result["device"].as<String>();
        String action = result["action"].as<String>();
        
        Serial.printf("   📋 %s %s: %s\n", device.c_str(), action.c_str(), status.c_str());
        
        if (status == "success") {
          Serial.println("   ✅ Sensor data successfully processed!");
        } else {
          Serial.printf("   ❌ Failed: %s\n", result["message"].as<String>().c_str());
        }
      }
    }
    
  } else if (type == "sensor_update") {
    // 接收到其他传感器的更新
    String location = doc["location"].as<String>();
    Serial.printf("📊 Sensor update from %s\n", location.c_str());
    
    if (doc["sensors"].is<JsonObject>()) {
      JsonObject sensors = doc["sensors"];
      Serial.printf("   🌡️ Temp: %.1f°C, Humidity: %.1f%%\n", 
                    sensors["temperature"].as<float>(), 
                    sensors["humidity"].as<float>());
      Serial.printf("   💨 CO2: %dppm, VOC: %dppb\n",
                    sensors["co2"].as<int>(),
                    sensors["voc"].as<int>());
    }
    
  } else if (type == "device_update") {
    String device = doc["device"].as<String>();
    String location = doc["location"].as<String>();
    Serial.printf("🔌 Device update: %s in %s\n", device.c_str(), location.c_str());
    
  } else if (type == "error") {
    String error_msg = doc["message"].as<String>();
    Serial.printf("❌ Error from server: %s\n", error_msg.c_str());
    
  } else {
    Serial.printf("ℹ️ Other message type: %s\n", type.c_str());
  }
}

// 添加一个简单的ping功能
void sendPing() {
  if (!wsConnected) return;
  
  DynamicJsonDocument doc(256);
  doc["type"] = "ping";
  doc["device_id"] = WiFi.macAddress();
  doc["timestamp"] = millis();
  
  String message;
  serializeJson(doc, message);
  
  webSocket.sendTXT(message);
  Serial.println("🏓 Ping sent to IoT service");
}