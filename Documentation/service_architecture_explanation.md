# Smart Home System - 服务架构与WebSocket管理详解

## 🏗️ 系统架构总览

你的智能家居系统采用**微服务架构**，共有5个核心服务，每个服务都有独立的职责：

```
┌─────────────────────────────────────────────────────────────┐
│                    🌐 用户界面层                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Web Browser   │  │   ESP8266/32    │  │  Mobile App  │ │
│  │  (Port 1145)    │  │   Devices       │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   🎯 协调服务 (主控制器)                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           Coordinator Service (Port 8080)              │ │
│  │  • WebSocket 主管理器 (/ws)                             │ │
│  │  • HTTP API 接口                                       │ │
│  │  • 服务间通信协调                                        │ │
│  │  • 语义理解与处理                                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     🔧 微服务层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │STT Service  │  │TTS Service  │  │IoT Control  │         │
│  │(Port 8000)  │  │(Port 8001)  │  │(Port 8002)  │         │
│  │• 语音识别    │  │• 语音合成    │  │• 设备控制    │         │
│  │• 音频处理    │  │• 音频生成    │  │• 状态管理    │         │
│  └─────────────┘  └─────────────┘  │• WebSocket   │         │
│                                    │  (/ws)      │         │
│  ┌─────────────────────────────────┐  └─────────────┘         │
│  │        Ollama Service           │                        │
│  │        (Port 11434)             │                        │
│  │      • LLM 推理引擎              │                        │
│  │      • 自然语言处理               │                        │
│  └─────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 协调服务 (Coordinator) - WebSocket 主管理器

### 核心职责
**Coordinator Service** 是整个系统的**中央指挥官**，也是**主要的WebSocket管理者**：

```python
# services/coordinator/app.py
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """主要的WebSocket端点 - 处理所有客户端连接"""
    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    
    # 处理所有类型的客户端消息
    while True:
        data = await websocket.receive_text()
        message = json.loads(data)
        
        if message_type == "text":
            # 文本处理 → 调用其他服务
            response = await process_text_with_enhanced_llm(message["text"])
            await websocket.send_json(response)
        
        elif message_type == "audio_ready":
            # 音频处理 → 调用STT服务
            response = await process_audio(message["path"])
            await websocket.send_json(response)
        
        elif message_type == "scene_command":
            # 场景控制 → 调用IoT服务
            results = await execute_scene_mode(message["scene"])
            await websocket.send_json(results)
```

### WebSocket连接管理
1. **接受所有客户端连接** (浏览器、ESP8266、移动应用)
2. **维护连接池** - 跟踪所有活跃连接
3. **消息路由** - 根据消息类型分发到相应服务
4. **响应聚合** - 收集各服务响应并返回给客户端

---

## 🏠 IoT控制服务 - 设备状态WebSocket

### 辅助WebSocket管理
**IoT Control Service** 提供**设备专用的WebSocket**：

```python
# services/iot/app.py
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """IoT专用WebSocket - 实时设备状态更新"""
    await websocket.accept()
    
    # 发送初始设备状态
    await websocket.send_json({
        "type": "init",
        "devices": device_states,
        "sensors": sensor_data
    })
    
    # 实时广播设备状态变化
    while True:
        # 监听设备状态变化
        if device_state_changed:
            await broadcast_device_update(device, location)
```

### 专门职责
1. **实时设备状态广播** - 当设备状态改变时立即通知所有连接
2. **传感器数据流** - 持续发送环境传感器数据
3. **设备控制确认** - 发送设备操作结果

---

## 🔄 服务间通信流程

### 典型的语音命令处理流程：

```
1. ESP8266/浏览器 → WebSocket → Coordinator (/ws)
   "Turn on living room lights"

2. Coordinator → STT Service (HTTP)
   POST /upload (如果是音频)

3. Coordinator → Ollama Service (HTTP)
   POST /api/generate (语义理解)

4. Coordinator → IoT Service (HTTP)
   POST /control (设备控制)

5. IoT Service → 所有IoT WebSocket客户端
   广播设备状态更新

6. Coordinator → TTS Service (HTTP)
   POST /synthesize (生成回复语音)

7. Coordinator → 原始客户端 (WebSocket)
   发送完整响应 (文本+音频+IoT结果)
```

---

## 📊 详细服务分工

### 1. 🎯 Coordinator Service (端口 8080)
```yaml
主要职责:
  - WebSocket主管理器 (ws://localhost:8080/ws)
  - 用户请求路由和协调
  - 语义理解和意图识别
  - 服务间通信编排
  - 响应聚合和格式化

HTTP API:
  - POST /process_text - 文本处理
  - POST /process_audio - 音频处理
  - POST /execute_scene - 场景执行
  - GET /room_status/{room} - 房间状态

WebSocket 消息类型:
  - text: 文本命令处理
  - audio_ready: 音频文件处理
  - scene_command: 场景模式执行
  - device_registration: 设备注册
```

### 2. 🎤 STT Service (端口 8000)
```yaml
主要职责:
  - 语音转文字 (Whisper)
  - 音频文件处理
  - UDP音频流接收 (ESP32)

HTTP API:
  - POST /upload - 上传音频文件转录
  - POST /transcribe - 转录指定路径音频

特殊功能:
  - UDP服务器 (端口8000) - 接收ESP32音频流
```

### 3. 🔊 TTS Service (端口 8001)
```yaml
主要职责:
  - 文字转语音 (Edge TTS)
  - 音频文件生成和管理
  - 多语言语音合成

HTTP API:
  - POST /synthesize - 语音合成
  - GET /voices - 可用语音列表
  - GET /audio/{filename} - 下载音频文件
  - POST /stream - 流式音频合成
```

### 4. 🏠 IoT Control Service (端口 8002)
```yaml
主要职责:
  - 智能设备状态管理
  - 实时传感器数据
  - 场景模式执行

HTTP API:
  - GET /devices - 所有设备状态
  - POST /control - 设备控制
  - GET /sensors - 传感器数据
  - POST /execute_scene - 场景执行

WebSocket功能:
  - ws://localhost:8002/ws
  - 实时设备状态广播
  - 传感器数据流
  - 设备控制结果通知
```

### 5. 🧠 Ollama Service (端口 11434)
```yaml
主要职责:
  - 大语言模型推理
  - 自然语言理解
  - 智能回复生成

HTTP API:
  - POST /api/generate - 文本生成
  - POST /api/chat - 对话模式
  - GET /api/tags - 可用模型列表
  - POST /api/pull - 下载模型
```

---

## 🔌 WebSocket连接策略

### 主WebSocket (Coordinator)
```javascript
// 用于主要的用户交互
const mainWS = new WebSocket('ws://10.129.113.188:8080/ws');

// 发送各种类型的命令
mainWS.send(JSON.stringify({
    type: 'text',
    text: 'Turn on lights'
}));

mainWS.send(JSON.stringify({
    type: 'scene_command',
    scene: 'sleep_mode'
}));
```

### IoT专用WebSocket
```javascript
// 用于实时设备状态监控
const iotWS = new WebSocket('ws://10.129.113.188:8002/ws');

// 接收设备状态更新
iotWS.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'device_update') {
        updateDeviceUI(data.device, data.state);
    }
};
```

---

## 🎭 ESP8266连接策略

对于ESP8266，推荐连接到**Coordinator的主WebSocket**：

```cpp
// ESP8266应该连接到主协调服务
WebSocketsClient webSocket;
webSocket.begin("10.129.113.188", 8080, "/ws");

// 发送设备注册
void sendRegistration() {
    DynamicJsonDocument doc(512);
    doc["type"] = "device_registration";
    doc["device_info"]["type"] = "esp8266";
    doc["capabilities"][0] = "sensor";
    doc["capabilities"][1] = "actuator";
    
    String message;
    serializeJson(doc, message);
    webSocket.sendTXT(message);
}

// 发送传感器数据
void sendSensorData() {
    DynamicJsonDocument doc(256);
    doc["type"] = "sensor_data";
    doc["location"] = "living_room";
    doc["temperature"] = 23.5;
    doc["humidity"] = 55;
    
    String message;
    serializeJson(doc, message);
    webSocket.sendTXT(message);
}
```

---

## 📈 数据流向图

```
用户命令: "Turn on living room lights"
    │
    ▼
[Coordinator WebSocket] (/ws)
    │
    ├─→ [Ollama] 语义理解
    │       │
    │       ▼
    │   "device=light, action=on, location=living_room"
    │
    ├─→ [IoT Control] 设备控制
    │       │
    │       ├─→ 更新设备状态
    │       └─→ [IoT WebSocket] 广播状态变化
    │
    ├─→ [TTS] 生成语音回复
    │       │
    │       ▼
    │   "lights_turned_on.mp3"
    │
    └─→ [Coordinator WebSocket] 发送完整响应
            │
            ▼
        { 
          ai_response: "已为您打开客厅灯",
          audio_path: "/audio/response.mp3",
          iot_commands: [...],
          expression: "neutral"
        }
```

## 🎯 总结

- **主WebSocket管理器**: Coordinator Service (8080端口)
- **设备状态WebSocket**: IoT Control Service (8002端口)  
- **推荐ESP8266连接**: Coordinator WebSocket (更全面的功能)
- **浏览器可以连接**: 两个WebSocket都可以，根据需求选择

你的ESP8266应该主要连接到 `ws://10.129.113.188:8080/ws` 来获得完整的智能家居功能！