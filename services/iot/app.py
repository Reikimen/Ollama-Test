import os
import logging
import json
import time
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 环境变量
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/devices.json")
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").lower() == "true"
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# 创建FastAPI应用
app = FastAPI(title="IoT控制服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 连接的ESP32设备
connected_devices = {}

# 设备状态
device_states = {
    "light": {
        "客厅": {"status": "off", "brightness": 50},
        "卧室": {"status": "off", "brightness": 50},
        "厨房": {"status": "off", "brightness": 50},
        "书房": {"status": "off", "brightness": 50}
    },
    "fan": {
        "客厅": {"status": "off", "speed": 1},
        "卧室": {"status": "off", "speed": 1}
    },
    "ac": {
        "客厅": {"status": "off", "temperature": 26, "mode": "cool"},
        "卧室": {"status": "off", "temperature": 26, "mode": "cool"}
    },
    "curtain": {
        "客厅": {"status": "closed"},
        "卧室": {"status": "closed"}
    }
}

class IoTCommand(BaseModel):
    device: str
    action: str
    location: str
    parameters: Optional[Dict[str, Any]] = None

class IoTControlRequest(BaseModel):
    commands: List[dict]

@app.get("/")
async def root():
    return {"message": "IoT控制服务运行中"}

@app.get("/devices")
async def get_devices():
    """获取所有设备状态"""
    return {"devices": device_states}

@app.get("/device/{device_type}/{location}")
async def get_device_status(device_type: str, location: str):
    """获取特定设备的状态"""
    if device_type not in device_states or location not in device_states[device_type]:
        return JSONResponse(
            status_code=404,
            content={"error": f"设备不存在: {device_type} at {location}"}
        )
    
    return {
        "device": device_type,
        "location": location,
        "state": device_states[device_type][location]
    }

@app.post("/control")
async def control_devices(request: IoTControlRequest):
    """控制IoT设备"""
    results = []
    
    for cmd in request.commands:
        try:
            device = cmd.get("device")
            action = cmd.get("action")
            location = cmd.get("location")
            parameters = cmd.get("parameters", {})
            
            if not all([device, action, location]):
                results.append({
                    "status": "error",
                    "message": "缺少必要参数",
                    "command": cmd
                })
                continue
            
            # 检查设备是否存在
            if device not in device_states or location not in device_states[device]:
                results.append({
                    "status": "error",
                    "message": f"设备不存在: {device} at {location}",
                    "command": cmd
                })
                continue
            
            # 执行控制命令
            result = await execute_command(device, action, location, parameters)
            results.append(result)
            
            # 如果启用了MQTT，发送控制命令
            if MQTT_ENABLED:
                await send_mqtt_command(device, action, location, parameters)
            
        except Exception as e:
            logger.error(f"执行命令出错: {str(e)}")
            results.append({
                "status": "error",
                "message": f"执行命令出错: {str(e)}",
                "command": cmd
            })
    
    return {"results": results}

async def execute_command(device, action, location, parameters):
    """执行设备控制命令"""
    try:
        # 获取当前设备状态
        current_state = device_states[device][location]
        
        # 根据设备类型和动作执行不同操作
        if device == "light":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
            elif action == "brighten":
                current_state["brightness"] = min(100, current_state["brightness"] + 20)
                current_state["status"] = "on"
            elif action == "dim":
                current_state["brightness"] = max(0, current_state["brightness"] - 20)
                if current_state["brightness"] == 0:
                    current_state["status"] = "off"
                else:
                    current_state["status"] = "on"
            elif action == "set_brightness" and "brightness" in parameters:
                current_state["brightness"] = max(0, min(100, parameters["brightness"]))
                if current_state["brightness"] == 0:
                    current_state["status"] = "off"
                else:
                    current_state["status"] = "on"
        
        elif device == "fan":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
            elif action == "speed_up":
                current_state["speed"] = min(3, current_state["speed"] + 1)
                current_state["status"] = "on"
            elif action == "speed_down":
                current_state["speed"] = max(0, current_state["speed"] - 1)
                if current_state["speed"] == 0:
                    current_state["status"] = "off"
                else:
                    current_state["status"] = "on"
            elif action == "set_speed" and "speed" in parameters:
                current_state["speed"] = max(0, min(3, parameters["speed"]))
                if current_state["speed"] == 0:
                    current_state["status"] = "off"
                else:
                    current_state["status"] = "on"
        
        elif device == "ac":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
            elif action == "temp_up":
                current_state["temperature"] = min(30, current_state["temperature"] + 1)
                current_state["status"] = "on"
            elif action == "temp_down":
                current_state["temperature"] = max(16, current_state["temperature"] - 1)
                current_state["status"] = "on"
            elif action == "set_temperature" and "temperature" in parameters:
                current_state["temperature"] = max(16, min(30, parameters["temperature"]))
                current_state["status"] = "on"
            elif action == "set_mode" and "mode" in parameters:
                if parameters["mode"] in ["cool", "heat", "fan", "auto"]:
                    current_state["mode"] = parameters["mode"]
                    current_state["status"] = "on"
        
        elif device == "curtain":
            if action == "on" or action == "open":
                current_state["status"] = "open"
            elif action == "off" or action == "close":
                current_state["status"] = "closed"
        
        # 更新设备状态
        device_states[device][location] = current_state
        
        # 向已连接的设备发送更新
        await broadcast_device_update(device, location)
        
        return {
            "status": "success",
            "device": device,
            "location": location,
            "action": action,
            "current_state": current_state
        }
    
    except Exception as e:
        logger.error(f"执行命令出错: {str(e)}")
        return {
            "status": "error",
            "message": f"执行命令出错: {str(e)}",
            "device": device,
            "location": location,
            "action": action
        }

async def broadcast_device_update(device, location):
    """广播设备状态更新到所有连接的WebSocket客户端"""
    if not connected_devices:
        return
    
    message = {
        "type": "device_update",
        "device": device,
        "location": location,
        "state": device_states[device][location]
    }
    
    for client_id, websocket in connected_devices.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"WebSocket发送失败: {str(e)}")

async def send_mqtt_command(device, action, location, parameters):
    """通过MQTT发送设备控制命令"""
    if not MQTT_ENABLED:
        return
    
    try:
        import paho.mqtt.client as mqtt
        
        # MQTT配置
        client = mqtt.Client()
        if MQTT_USER and MQTT_PASSWORD:
            client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        
        # 创建消息
        topic = f"iot/{device}/{location}"
        payload = {
            "action": action,
            "parameters": parameters,
            "timestamp": time.time()
        }
        
        # 转换为JSON
        message = json.dumps(payload)
        
        # 连接并发布
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(topic, message)
        client.disconnect()
        
        logger.info(f"已发送MQTT命令: {topic} - {message}")
    
    except Exception as e:
        logger.error(f"MQTT发送失败: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接处理"""
    await websocket.accept()
    client_id = id(websocket)
    connected_devices[client_id] = websocket
    
    try:
        # 发送当前所有设备状态
        await websocket.send_json({
            "type": "init",
            "devices": device_states
        })
        
        # 持续监听命令
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                command_type = message.get("type")
                
                if command_type == "control":
                    # 处理控制命令
                    commands = message.get("commands", [])
                    results = []
                    
                    for cmd in commands:
                        device = cmd.get("device")
                        action = cmd.get("action")
                        location = cmd.get("location")
                        parameters = cmd.get("parameters", {})
                        
                        if all([device, action, location]):
                            result = await execute_command(device, action, location, parameters)
                            results.append(result)
                    
                    await websocket.send_json({
                        "type": "control_results",
                        "results": results
                    })
                
                elif command_type == "get_status":
                    # 获取特定设备状态
                    device = message.get("device")
                    location = message.get("location")
                    
                    if device and location and device in device_states and location in device_states[device]:
                        await websocket.send_json({
                            "type": "device_status",
                            "device": device,
                            "location": location,
                            "state": device_states[device][location]
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "设备未找到"
                        })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "未知命令类型"
                    })
            
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的JSON格式"
                })
    
    except WebSocketDisconnect:
        if client_id in connected_devices:
            del connected_devices[client_id]
    
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        if client_id in connected_devices:
            del connected_devices[client_id]

# 模拟ESP32状态更新
async def simulate_device_updates():
    """模拟设备状态更新（用于测试）"""
    while True:
        await asyncio.sleep(60)  # 每分钟更新一次
        
        # 模拟温度波动
        for location in device_states["ac"]:
            if device_states["ac"][location]["status"] == "on":
                # 随机温度波动 ±0.5°C
                import random
                current_temp = device_states["ac"][location]["temperature"]
                new_temp = max(16, min(30, current_temp + random.uniform(-0.5, 0.5)))
                device_states["ac"][location]["temperature"] = round(new_temp, 1)
                
                # 广播更新
                await broadcast_device_update("ac", location)

@app.on_event("startup")
async def startup_event():
    """应用启动时的事件处理"""
    # 启动模拟更新任务
    asyncio.create_task(simulate_device_updates())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=False)