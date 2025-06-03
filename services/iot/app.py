import os
import logging
import json
import time
import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/devices.json")
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").lower() == "true"
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Create FastAPI application
app = FastAPI(title="IoT Control Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected ESP32 devices
connected_devices = {}

# Timer management for timed devices
active_timers = {}

# Enhanced device states - 对应Week 1设计
device_states = {
    # 天花板灯 - 支持调光和色温
    "ceiling_light": {
        "living_room": {"status": "off", "brightness": 50, "color_temp": 4000},
        "bedroom": {"status": "off", "brightness": 50, "color_temp": 3000},
        "kitchen": {"status": "off", "brightness": 80, "color_temp": 5000},
        "study": {"status": "off", "brightness": 70, "color_temp": 4500},
        "bathroom": {"status": "off", "brightness": 60, "color_temp": 4000}
    },
    
    # 台灯 - 支持调光和色温
    "desk_lamp": {
        "bedroom": {"status": "off", "brightness": 40, "color_temp": 2700},
        "study": {"status": "off", "brightness": 60, "color_temp": 4000}
    },
    
    # 风扇 - 支持多档速度和摆动
    "fan": {
        "living_room": {"status": "off", "speed": 1, "oscillation": False},
        "bedroom": {"status": "off", "speed": 1, "oscillation": False},
        "study": {"status": "off", "speed": 1, "oscillation": False}
    },
    
    # 排气扇 - 厨房和浴室
    "exhaust_fan": {
        "kitchen": {"status": "off", "speed": 2, "timer": 0},
        "bathroom": {"status": "off", "speed": 2, "timer": 0}
    },
    
    # 空调 - 原有基础上增加风速
    "ac": {
        "living_room": {"status": "off", "temperature": 26, "mode": "cool", "fan_speed": "auto"},
        "bedroom": {"status": "off", "temperature": 25, "mode": "cool", "fan_speed": "auto"}
    },
    
    # 窗帘 - 增加开启程度控制
    "curtain": {
        "living_room": {"status": "closed", "position": 0},
        "bedroom": {"status": "closed", "position": 0},
        "study": {"status": "closed", "position": 0},
        "bathroom": {"status": "closed", "position": 0}
    },
    
    # 传感器数据 - 只读设备，模拟真实环境数据
    "sensors": {
        "living_room": {
            "temperature": 23.5,
            "humidity": 55,
            "co2": 420,
            "voc": 15,
            "motion": False,
            "light_level": 300,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "bedroom": {
            "temperature": 22.8,
            "humidity": 58,
            "co2": 450,
            "voc": 12,
            "motion": False,
            "light_level": 150,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "kitchen": {
            "temperature": 24.2,
            "humidity": 62,
            "co2": 480,
            "voc": 25,
            "motion": False,
            "light_level": 400,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "study": {
            "temperature": 23.1,
            "humidity": 52,
            "co2": 430,
            "voc": 18,
            "motion": False,
            "light_level": 350,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "bathroom": {
            "temperature": 24.8,
            "humidity": 70,
            "co2": 400,
            "voc": 20,
            "motion": False,
            "light_level": 200,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
    }
}

class IoTCommand(BaseModel):
    device: str
    action: str
    location: str
    parameters: Optional[Dict[str, Any]] = None

class IoTControlRequest(BaseModel):
    commands: List[dict]

class SceneRequest(BaseModel):
    scene_name: str
    location: Optional[str] = None

# Helper functions defined first to avoid undefined variable errors

async def broadcast_device_update(device, location):
    """Broadcast device state update to all connected WebSocket clients"""
    if not connected_devices:
        return
    
    message = {
        "type": "device_update",
        "device": device,
        "location": location,
        "state": device_states[device][location],
        "timestamp": time.time()
    }
    
    disconnected_clients = []
    for client_id, websocket in connected_devices.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"WebSocket send failed for client {client_id}: {str(e)}")
            disconnected_clients.append(client_id)
    
    # Remove disconnected clients
    for client_id in disconnected_clients:
        del connected_devices[client_id]

async def broadcast_sensor_update(location):
    """Broadcast sensor data update"""
    if not connected_devices:
        return
    
    sensors = device_states.get("sensors", {}).get(location, {})
    message = {
        "type": "sensor_update",
        "location": location,
        "sensors": sensors,
        "timestamp": time.time()
    }
    
    disconnected_clients = []
    for client_id, websocket in connected_devices.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Sensor update failed for client {client_id}: {str(e)}")
            disconnected_clients.append(client_id)
    
    # Remove disconnected clients
    for client_id in disconnected_clients:
        del connected_devices[client_id]

async def update_environmental_impact(device, action, location, current_state):
    """Update environmental sensors based on device changes (simulation)"""
    sensors = device_states.get("sensors", {}).get(location, {})
    if not sensors:
        return
    
    # Simulate environmental changes based on device operations
    if device == "ceiling_light" or device == "desk_lamp":
        if action == "on" or current_state.get("status") == "on":
            # Lights generate heat and affect light level
            brightness = current_state.get("brightness", 50)
            sensors["light_level"] = min(1000, sensors.get("light_level", 0) + brightness * 5)
            sensors["temperature"] = min(35, sensors.get("temperature", 23) + brightness * 0.01)
        else:
            # Lights off reduce light level
            sensors["light_level"] = max(0, sensors.get("light_level", 300) - 200)
    
    elif device == "ac":
        if current_state.get("status") == "on":
            target_temp = current_state.get("temperature", 25)
            current_temp = sensors.get("temperature", 23)
            # Gradually adjust towards target temperature
            if current_temp > target_temp:
                sensors["temperature"] = max(target_temp, current_temp - 0.5)
            elif current_temp < target_temp:
                sensors["temperature"] = min(target_temp, current_temp + 0.5)
    
    elif device == "exhaust_fan":
        if current_state.get("status") == "on":
            # Exhaust fans reduce humidity and VOC
            sensors["humidity"] = max(30, sensors.get("humidity", 55) - 5)
            sensors["voc"] = max(5, sensors.get("voc", 15) - 3)
            sensors["co2"] = max(350, sensors.get("co2", 420) - 20)
    
    elif device == "fan":
        if current_state.get("status") == "on":
            # Fans help with air circulation, slight cooling effect
            speed = current_state.get("speed", 1)
            sensors["temperature"] = max(16, sensors.get("temperature", 23) - speed * 0.3)
    
    elif device == "curtain":
        position = current_state.get("position", 0)
        # Curtains affect light level
        if position > 50:
            sensors["light_level"] = max(sensors.get("light_level", 300) - 100, 50)
        else:
            sensors["light_level"] = min(sensors.get("light_level", 300) + 150, 800)
    
    # Update timestamp
    sensors["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    
    # Broadcast sensor updates
    await broadcast_sensor_update(location)

async def send_mqtt_command(device, action, location, parameters):
    """Send device control command via MQTT"""
    if not MQTT_ENABLED:
        return
    
    try:
        import paho.mqtt.client as mqtt
        
        # MQTT configuration
        client = mqtt.Client()
        if MQTT_USER and MQTT_PASSWORD:
            client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        
        # Create message
        topic = f"smarthome/{device}/{location}"
        payload = {
            "action": action,
            "parameters": parameters,
            "timestamp": time.time(),
            "device_id": f"{device}_{location}"
        }
        
        # Convert to JSON
        message = json.dumps(payload)
        
        # Connect and publish
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(topic, message)
        client.disconnect()
        
        logger.info(f"MQTT command sent: {topic} - {message}")
    
    except Exception as e:
        logger.error(f"MQTT send failed: {str(e)}")

def set_device_timer(device, location, minutes):
    """Set a timer for a device"""
    timer_id = f"{device}_{location}_{int(time.time())}"
    active_timers[timer_id] = {
        "device": device,
        "location": location,
        "expire_time": time.time() + (minutes * 60),
        "duration": minutes
    }
    return timer_id

# API Routes

@app.get("/")
async def root():
    return {"message": "IoT Control Service is running"}

@app.get("/devices")
async def get_devices():
    """Get all device states"""
    return {"devices": device_states}

@app.get("/device/{device_type}/{location}")
async def get_device_status(device_type: str, location: str):
    """Get specific device status"""
    if device_type not in device_states or location not in device_states[device_type]:
        return JSONResponse(
            status_code=404,
            content={"error": f"Device does not exist: {device_type} at {location}"}
        )
    
    return {
        "device": device_type,
        "location": location,
        "state": device_states[device_type][location]
    }

@app.get("/sensors")
async def get_all_sensors():
    """Get all sensor data"""
    return {"sensors": device_states.get("sensors", {})}

@app.get("/sensors/{location}")
async def get_sensor_data(location: str):
    """Get sensor data for specific location"""
    sensors = device_states.get("sensors", {})
    if location not in sensors:
        return JSONResponse(
            status_code=404,
            content={"error": f"No sensors found for location: {location}"}
        )
    
    return {
        "location": location,
        "sensors": sensors[location]
    }

@app.post("/control")
async def control_devices(request: IoTControlRequest):
    """Control IoT devices with enhanced support"""
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
                    "message": "Missing required parameters",
                    "command": cmd
                })
                continue
            
            # Check if device exists
            if device not in device_states or location not in device_states[device]:
                results.append({
                    "status": "error",
                    "message": f"Device does not exist: {device} at {location}",
                    "command": cmd
                })
                continue
            
            # Execute enhanced control command
            result = await execute_enhanced_command(device, action, location, parameters)
            results.append(result)
            
            # If MQTT is enabled, send control command
            if MQTT_ENABLED:
                await send_mqtt_command(device, action, location, parameters)
            
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            results.append({
                "status": "error",
                "message": f"Error executing command: {str(e)}",
                "command": cmd
            })
    
    return {"results": results}

@app.post("/execute_scene")
async def execute_scene(request: SceneRequest):
    """Execute predefined scene mode"""
    try:
        results = await execute_scene_mode(request.scene_name, request.location)
        return {
            "scene": request.scene_name,
            "location": request.location,
            "results": results,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error executing scene: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error executing scene: {str(e)}"}
        )

async def execute_enhanced_command(device, action, location, parameters):
    """Enhanced device control with full parameter support"""
    try:
        # Get current device state
        current_state = device_states[device][location].copy()
        
        # Execute different operations based on device type and action
        if device == "ceiling_light" or device == "light":  # 兼容性支持
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
                current_state["status"] = "on" if parameters["brightness"] > 0 else "off"
            elif action == "set_color_temp" and "color_temp" in parameters:
                current_state["color_temp"] = max(2700, min(6500, parameters["color_temp"]))
                current_state["status"] = "on"
        
        elif device == "desk_lamp":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
            elif action == "reading_mode":
                current_state["status"] = "on"
                current_state["brightness"] = 70
                current_state["color_temp"] = 4000
            elif action == "night_mode":
                current_state["status"] = "on"
                current_state["brightness"] = 20
                current_state["color_temp"] = 2700
            elif action == "set_brightness" and "brightness" in parameters:
                current_state["brightness"] = max(0, min(100, parameters["brightness"]))
                current_state["status"] = "on" if parameters["brightness"] > 0 else "off"
        
        elif device == "fan":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
            elif action == "speed_up":
                current_state["speed"] = min(5, current_state["speed"] + 1)
                current_state["status"] = "on"
            elif action == "speed_down":
                current_state["speed"] = max(0, current_state["speed"] - 1)
                if current_state["speed"] == 0:
                    current_state["status"] = "off"
                else:
                    current_state["status"] = "on"
            elif action == "set_speed" and "speed" in parameters:
                current_state["speed"] = max(0, min(5, parameters["speed"]))
                current_state["status"] = "on" if parameters["speed"] > 0 else "off"
            elif action == "toggle_oscillation":
                current_state["oscillation"] = not current_state.get("oscillation", False)
                current_state["status"] = "on"
        
        elif device == "exhaust_fan":
            if action == "on":
                current_state["status"] = "on"
            elif action == "off":
                current_state["status"] = "off"
                current_state["timer"] = 0
            elif action == "speed_up":
                current_state["speed"] = min(3, current_state["speed"] + 1)
                current_state["status"] = "on"
            elif action == "speed_down":
                current_state["speed"] = max(1, current_state["speed"] - 1)
            elif action == "set_timer" and "timer" in parameters:
                current_state["timer"] = max(0, min(120, parameters["timer"]))  # 最大2小时
                current_state["status"] = "on" if parameters["timer"] > 0 else current_state["status"]
                if parameters["timer"] > 0:
                    set_device_timer(device, location, parameters["timer"])
            elif action == "timer_30":
                current_state["timer"] = 30
                current_state["status"] = "on"
                set_device_timer(device, location, 30)
        
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
                if parameters["mode"] in ["cool", "heat", "fan", "auto", "dry"]:
                    current_state["mode"] = parameters["mode"]
                    current_state["status"] = "on"
            elif action == "set_fan_speed" and "fan_speed" in parameters:
                if parameters["fan_speed"] in ["auto", "low", "medium", "high"]:
                    current_state["fan_speed"] = parameters["fan_speed"]
                    current_state["status"] = "on"
        
        elif device == "curtain":
            if action == "on" or action == "open":
                current_state["status"] = "open"
                current_state["position"] = 100
            elif action == "off" or action == "close":
                current_state["status"] = "closed"
                current_state["position"] = 0
            elif action == "set_position" and "position" in parameters:
                position = max(0, min(100, parameters["position"]))
                current_state["position"] = position
                current_state["status"] = "open" if position > 0 else "closed"
        
        # Update device state
        device_states[device][location] = current_state
        
        # Broadcast update to connected devices
        await broadcast_device_update(device, location)
        
        # Update related sensor data (simulate environmental impact)
        await update_environmental_impact(device, action, location, current_state)
        
        return {
            "status": "success",
            "device": device,
            "location": location,
            "action": action,
            "parameters": parameters,
            "current_state": current_state
        }
    
    except Exception as e:
        logger.error(f"Error executing enhanced command: {str(e)}")
        return {
            "status": "error",
            "message": f"Error executing command: {str(e)}",
            "device": device,
            "location": location,
            "action": action
        }

async def execute_scene_mode(scene_name, location=None):
    """Execute predefined scene modes"""
    scene_commands = []
    
    if scene_name == "home_mode":
        # 回家模式
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {"brightness": 70}},
            {"device": "ac", "action": "on", "location": "living_room", "parameters": {"temperature": 25}},
            {"device": "curtain", "action": "set_position", "location": "living_room", "parameters": {"position": 50}}
        ]
    
    elif scene_name == "sleep_mode":
        # 睡眠模式
        target_location = location or "bedroom"
        scene_commands = [
            {"device": "ceiling_light", "action": "off", "location": target_location},
            {"device": "desk_lamp", "action": "off", "location": target_location},
            {"device": "ac", "action": "set_temperature", "location": target_location, "parameters": {"temperature": 24}},
            {"device": "curtain", "action": "close", "location": target_location},
            # 关闭其他房间主要灯光
            {"device": "ceiling_light", "action": "off", "location": "living_room"},
            {"device": "ceiling_light", "action": "off", "location": "kitchen"},
            {"device": "ceiling_light", "action": "off", "location": "study"}
        ]
    
    elif scene_name == "work_mode":
        # 工作模式
        target_location = location or "study"
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": target_location, "parameters": {"brightness": 80, "color_temp": 4500}},
            {"device": "desk_lamp", "action": "on", "location": target_location, "parameters": {"brightness": 70, "color_temp": 4000}},
            {"device": "curtain", "action": "set_position", "location": target_location, "parameters": {"position": 30}},
            {"device": "ac", "action": "on", "location": target_location, "parameters": {"temperature": 23}}
        ]
    
    elif scene_name == "cooking_mode":
        # 烹饪模式
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {"brightness": 100, "color_temp": 5000}},
            {"device": "exhaust_fan", "action": "on", "location": "kitchen", "parameters": {"speed": 2}}
        ]
    
    elif scene_name == "movie_mode":
        # 观影模式
        target_location = location or "living_room"
        scene_commands = [
            {"device": "ceiling_light", "action": "set_brightness", "location": target_location, "parameters": {"brightness": 15}},
            {"device": "curtain", "action": "close", "location": target_location},
            {"device": "ac", "action": "on", "location": target_location, "parameters": {"temperature": 22, "mode": "cool"}}
        ]
    
    elif scene_name == "bath_mode":
        # 洗浴模式
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": "bathroom", "parameters": {"brightness": 80}},
            {"device": "exhaust_fan", "action": "on", "location": "bathroom", "parameters": {"speed": 2, "timer": 30}}
        ]
    
    elif scene_name == "morning_mode":
        # 早晨模式 (新增)
        target_location = location or "bedroom"
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": target_location, "parameters": {"brightness": 60, "color_temp": 4000}},
            {"device": "curtain", "action": "set_position", "location": target_location, "parameters": {"position": 80}},
            {"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {"brightness": 70}},
            {"device": "ac", "action": "set_temperature", "location": target_location, "parameters": {"temperature": 23}}
        ]
    
    elif scene_name == "away_mode":
        # 离家模式 (新增)
        scene_commands = [
            {"device": "ceiling_light", "action": "off", "location": "living_room"},
            {"device": "ceiling_light", "action": "off", "location": "bedroom"},
            {"device": "ceiling_light", "action": "off", "location": "kitchen"},
            {"device": "ceiling_light", "action": "off", "location": "study"},
            {"device": "ceiling_light", "action": "off", "location": "bathroom"},
            {"device": "desk_lamp", "action": "off", "location": "bedroom"},
            {"device": "desk_lamp", "action": "off", "location": "study"},
            {"device": "fan", "action": "off", "location": "living_room"},
            {"device": "fan", "action": "off", "location": "bedroom"},
            {"device": "fan", "action": "off", "location": "study"},
            {"device": "ac", "action": "set_temperature", "location": "living_room", "parameters": {"temperature": 26}},
            {"device": "ac", "action": "set_temperature", "location": "bedroom", "parameters": {"temperature": 26}},
            {"device": "curtain", "action": "close", "location": "living_room"},
            {"device": "curtain", "action": "close", "location": "bedroom"}
        ]
    
    elif scene_name == "relax_mode":
        # 休闲模式 (新增)
        target_location = location or "living_room"
        scene_commands = [
            {"device": "ceiling_light", "action": "set_brightness", "location": target_location, "parameters": {"brightness": 40, "color_temp": 2700}},
            {"device": "fan", "action": "on", "location": target_location, "parameters": {"speed": 1}},
            {"device": "ac", "action": "on", "location": target_location, "parameters": {"temperature": 24}},
            {"device": "curtain", "action": "set_position", "location": target_location, "parameters": {"position": 50}}
        ]
    
    else:
        # 未知场景模式
        return [{"status": "error", "message": f"Unknown scene mode: {scene_name}"}]
    
    # 执行场景命令
    results = []
    for cmd in scene_commands:
        try:
            result = await execute_enhanced_command(
                cmd["device"], 
                cmd["action"], 
                cmd["location"], 
                cmd.get("parameters", {})
            )
            results.append(result)
        except Exception as e:
            results.append({
                "status": "error", 
                "command": cmd, 
                "error": str(e)
            })
    
    return results

# Timer management for timed devices
async def manage_device_timers():
    """Manage device timers (for exhaust fans, etc.)"""
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        current_time = time.time()
        expired_timers = []
        
        for timer_id, timer_info in active_timers.items():
            if current_time >= timer_info["expire_time"]:
                # Timer expired, turn off device
                device = timer_info["device"]
                location = timer_info["location"]
                
                try:
                    result = await execute_enhanced_command(device, "off", location, {})
                    logger.info(f"Timer expired: {device} at {location} turned off")
                    expired_timers.append(timer_id)
                except Exception as e:
                    logger.error(f"Failed to turn off {device} at {location}: {str(e)}")
        
        # Remove expired timers
        for timer_id in expired_timers:
            del active_timers[timer_id]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket connection handler"""
    await websocket.accept()
    client_id = id(websocket)
    connected_devices[client_id] = websocket
    
    logger.info(f"WebSocket client {client_id} connected")
    
    try:
        # Send current device states and sensor data
        await websocket.send_json({
            "type": "init",
            "devices": {k: v for k, v in device_states.items() if k != "sensors"},
            "sensors": device_states.get("sensors", {}),
            "timestamp": time.time(),
            "message": "Connected to IoT Control Service"
        })
        
        # Continuously listen for commands
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                command_type = message.get("type")
                
                if command_type == "control":
                    # Process control commands
                    commands = message.get("commands", [])
                    results = []
                    
                    for cmd in commands:
                        device = cmd.get("device")
                        action = cmd.get("action")
                        location = cmd.get("location")
                        parameters = cmd.get("parameters", {})
                        
                        if all([device, action, location]):
                            result = await execute_enhanced_command(device, action, location, parameters)
                            results.append(result)
                    
                    await websocket.send_json({
                        "type": "control_results",
                        "results": results,
                        "timestamp": time.time()
                    })
                
                elif command_type == "get_status":
                    # Get specific device status
                    device = message.get("device")
                    location = message.get("location")
                    
                    if device and location and device in device_states and location in device_states[device]:
                        await websocket.send_json({
                            "type": "device_status",
                            "device": device,
                            "location": location,
                            "state": device_states[device][location],
                            "timestamp": time.time()
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Device not found"
                        })
                
                elif command_type == "get_sensors":
                    # Get sensor data
                    location = message.get("location")
                    if location:
                        sensors = device_states.get("sensors", {}).get(location, {})
                        await websocket.send_json({
                            "type": "sensor_data",
                            "location": location,
                            "sensors": sensors,
                            "timestamp": time.time()
                        })
                    else:
                        await websocket.send_json({
                            "type": "all_sensors",
                            "sensors": device_states.get("sensors", {}),
                            "timestamp": time.time()
                        })
                
                elif command_type == "execute_scene":
                    # Execute scene mode
                    scene_name = message.get("scene_name")
                    location = message.get("location")
                    
                    results = await execute_scene_mode(scene_name, location)
                    await websocket.send_json({
                        "type": "scene_results",
                        "scene": scene_name,
                        "results": results,
                        "timestamp": time.time()
                    })
                
                elif command_type == "ping":
                    # Heartbeat ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown command type: {command_type}"
                    })
            
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected")
    
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
    
    finally:
        if client_id in connected_devices:
            del connected_devices[client_id]

# Simulate realistic environmental changes
async def simulate_environmental_changes():
    """Simulate realistic environmental sensor changes"""
    while True:
        await asyncio.sleep(30)  # Update every 30 seconds
        
        for location, sensors in device_states.get("sensors", {}).items():
            # Natural temperature fluctuation
            current_temp = sensors.get("temperature", 23)
            
            # Time-based temperature changes
            hour = time.localtime().tm_hour
            if 6 <= hour <= 18:  # Daytime
                target_temp = 24 + random.uniform(-1, 2)
            else:  # Nighttime
                target_temp = 22 + random.uniform(-1, 1)
            
            # Gradual temperature change
            temp_diff = target_temp - current_temp
            sensors["temperature"] = round(current_temp + temp_diff * 0.1, 1)
            
            # Natural humidity changes
            sensors["humidity"] = max(40, min(80, 
                sensors.get("humidity", 55) + random.uniform(-2, 2)))
            
            # CO2 natural variation with time-based patterns
            base_co2 = 400 if 22 <= hour or hour <= 6 else 450  # Lower at night
            sensors["co2"] = max(350, min(1000,
                base_co2 + random.uniform(-20, 40)))
            
            # VOC slight variation
            sensors["voc"] = max(5, min(50,
                sensors.get("voc", 15) + random.uniform(-2, 3)))
            
            # Light level based on time and weather simulation
            if 6 <= hour <= 8:  # Morning
                sensors["light_level"] = 200 + hour * 50 + random.uniform(-50, 50)
            elif 8 <= hour <= 17:  # Daytime
                base_light = 500 + random.uniform(-100, 200)
                # Simulate cloudy/sunny weather
                weather_factor = random.choice([0.7, 0.8, 0.9, 1.0, 1.1])
                sensors["light_level"] = int(base_light * weather_factor)
            elif 17 <= hour <= 20:  # Evening
                sensors["light_level"] = max(50, 400 - (hour - 17) * 80 + random.uniform(-30, 30))
            else:  # Night
                sensors["light_level"] = max(10, 50 + random.uniform(-20, 20))
            
            # Occasional motion detection simulation
            if random.random() < 0.1:  # 10% chance
                sensors["motion"] = True
                # Motion detection lasts for 2 minutes
                asyncio.create_task(reset_motion_detection(location))
            
            # Update timestamp
            sensors["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Broadcast sensor updates
        for location in device_states.get("sensors", {}):
            await broadcast_sensor_update(location)

async def reset_motion_detection(location):
    """Reset motion detection after 2 minutes"""
    await asyncio.sleep(120)  # 2 minutes
    if location in device_states.get("sensors", {}):
        device_states["sensors"][location]["motion"] = False
        await broadcast_sensor_update(location)

@app.on_event("startup")
async def startup_event():
    """Event handler for application startup"""
    logger.info("IoT Control Service starting up...")
    
    # Start environmental simulation
    asyncio.create_task(simulate_environmental_changes())
    
    # Start timer management
    asyncio.create_task(manage_device_timers())
    
    # Initialize device states
    logger.info(f"Initialized {len(device_states)} device categories")
    for device_type, locations in device_states.items():
        if device_type != "sensors":
            logger.info(f"  {device_type}: {len(locations)} locations")
        else:
            logger.info(f"  sensors: {len(locations)} locations")
    
    logger.info("IoT Control Service startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Event handler for application shutdown"""
    logger.info("IoT Control Service shutting down...")
    
    # Cancel all active timers
    active_timers.clear()
    
    # Close all WebSocket connections
    for client_id, websocket in connected_devices.items():
        try:
            await websocket.close()
        except:
            pass
    
    connected_devices.clear()
    
    logger.info("IoT Control Service shutdown complete")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=False)