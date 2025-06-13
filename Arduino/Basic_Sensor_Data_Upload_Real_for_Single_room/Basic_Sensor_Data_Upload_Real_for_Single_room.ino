#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "sensor.h"
#include "network.h"

// Sensor 数据刷新频率
#define DETECTFREQ 300
int sensor_detect_freq = 0;

void setup() {
  Serial.begin(115200);
  delay(200);
  
  Serial.println("============================================================");
  Serial.printf("🌡️ ESP8266 IoT Sensor Node - Room: %s Only\n", TARGET_ROOM);
  Serial.println("============================================================");

  Wire.begin();
  
  Serial.println("\n=== ESP8266 传感器测试 ===");
  
  // 扫描I2C设备
  scanI2CDevices();
  
  // 初始化传感器
  initSensors();
  
  Serial.println("初始化完成，开始读取传感器数据...\n");
  
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

  // 定期检测传感器数据
  // if (sensor_detect_freq = DETECTFREQ){
  //   sensor_detect_freq = 0;

  // } else {
  //   sensor_detect_freq++;
  // }


  if (wsConnected && (millis() - lastSensorTime >= SENSOR_INTERVAL)) {

    // 定期检测传感器数据
    Serial.println("=== 传感器读数 ===");
  
    #if ENABLE_AHT21
    readAHT21();
    #endif
    
    #if ENABLE_ENS160
    readENS160();
    #endif
    
    #if ENABLE_VEML7700
    readVEML7700();
    #endif
    
    Serial.println();

    // 定期发送传感器数据
    sendSensorData();
    lastSensorTime = millis();
  }

  delay(100);
}