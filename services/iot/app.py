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

# Device states
device_states = {
    "light": {
        "living room": {"status": "off", "brightness": 50},
        "bedroom": {"status": "off", "brightness": 50},
        "kitchen": {"status": "off", "brightness": 50},
        "study": {"status": "off", "brightness": 50}
    },
    "fan": {
        "living room": {"status": "off", "speed": 1},
        "bedroom": {"status": "off", "speed": 1}
    },
    "ac": {
        "living room": {"status": "off", "temperature": 26, "mode": "cool"},
        "bedroom": {"status": "off", "temperature": 26, "mode": "cool"}
    },
    "curtain": {
        "living room": {"status": "closed"},
        "bedroom": {"status": "closed"}
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

@app.post("/control")
async def control_devices(request: IoTControlRequest):
    """Control IoT devices"""
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
            
            # Execute control command
            result = await execute_command(device, action, location, parameters)
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

async def execute_command(device, action, location, parameters):
    """Execute device control command"""
    try:
        # Get current device state
        current_state = device_states[device][location]
        
        # Execute different operations based on device type and action
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
        
        # Update device state
        device_states[device][location] = current_state
        
        # Broadcast update to connected devices
        await broadcast_device_update(device, location)
        
        return {
            "status": "success",
            "device": device,
            "location": location,
            "action": action,
            "current_state": current_state
        }
    
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return {
            "status": "error",
            "message": f"Error executing command: {str(e)}",
            "device": device,
            "location": location,
            "action": action
        }

async def broadcast_device_update(device, location):
    """Broadcast device state update to all connected WebSocket clients"""
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
            logger.error(f"WebSocket send failed: {str(e)}")

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
        topic = f"iot/{device}/{location}"
        payload = {
            "action": action,
            "parameters": parameters,
            "timestamp": time.time()
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection handler"""
    await websocket.accept()
    client_id = id(websocket)
    connected_devices[client_id] = websocket
    
    try:
        # Send current device states
        await websocket.send_json({
            "type": "init",
            "devices": device_states
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
                            result = await execute_command(device, action, location, parameters)
                            results.append(result)
                    
                    await websocket.send_json({
                        "type": "control_results",
                        "results": results
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
                            "state": device_states[device][location]
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Device not found"
                        })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Unknown command type"
                    })
            
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
    
    except WebSocketDisconnect:
        if client_id in connected_devices:
            del connected_devices[client_id]
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if client_id in connected_devices:
            del connected_devices[client_id]

# Simulate device state updates
async def simulate_device_updates():
    """Simulate device state updates (for testing)"""
    while True:
        await asyncio.sleep(60)  # Update every minute
        
        # Simulate temperature fluctuation
        for location in device_states["ac"]:
            if device_states["ac"][location]["status"] == "on":
                # Random temperature fluctuation ±0.5°C
                import random
                current_temp = device_states["ac"][location]["temperature"]
                new_temp = max(16, min(30, current_temp + random.uniform(-0.5, 0.5)))
                device_states["ac"][location]["temperature"] = round(new_temp, 1)
                
                # Broadcast update
                await broadcast_device_update("ac", location)

@app.on_event("startup")
async def startup_event():
    """Event handler for application startup"""
    # Start simulation task
    asyncio.create_task(simulate_device_updates())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=False)