import os
import json
import logging
import asyncio
import aiohttp
import websockets
import time
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variable configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
STT_HOST = os.getenv("STT_HOST", "stt-service")
STT_PORT = os.getenv("STT_PORT", "8000")
TTS_HOST = os.getenv("TTS_HOST", "tts-service")
TTS_PORT = os.getenv("TTS_PORT", "8001")
IOT_HOST = os.getenv("IOT_HOST", "iot-control")
IOT_PORT = os.getenv("IOT_PORT", "8002")

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
    
    # 传感器数据 - 只读设备
    "sensors": {
        "living_room": {
            "temperature": 23.5,
            "humidity": 55,
            "co2": 420,
            "voc": 15,
            "motion": False,
            "light_level": 300,
            "last_update": "2025-06-03T10:30:00"
        },
        "bedroom": {
            "temperature": 22.8,
            "humidity": 58,
            "co2": 450,
            "voc": 12,
            "motion": False,
            "light_level": 150,
            "last_update": "2025-06-03T10:30:00"
        },
        "kitchen": {
            "temperature": 24.2,
            "humidity": 62,
            "co2": 480,
            "voc": 25,
            "motion": False,
            "light_level": 400,
            "last_update": "2025-06-03T10:30:00"
        },
        "study": {
            "temperature": 23.1,
            "humidity": 52,
            "co2": 430,
            "voc": 18,
            "motion": False,
            "light_level": 350,
            "last_update": "2025-06-03T10:30:00"
        },
        "bathroom": {
            "temperature": 24.8,
            "humidity": 70,
            "co2": 400,
            "voc": 20,
            "motion": False,
            "light_level": 200,
            "last_update": "2025-06-03T10:30:00"
        }
    }
}

# Create FastAPI application
app = FastAPI(title="AI Voice Assistant Coordinator Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected clients and devices
connected_clients = {}
registered_devices = {}
user_contexts = {}

class AudioRequest(BaseModel):
    audio_path: str

class TextRequest(BaseModel):
    text: str

class ContextualRequest(BaseModel):
    text: str
    user_context: Optional[Dict[str, Any]] = None
    location: str = "living_room"
    device_id: Optional[str] = None

class SceneRequest(BaseModel):
    scene_name: str
    location: Optional[str] = None

class DeviceRegistration(BaseModel):
    device_info: Dict[str, Any]
    capabilities: List[str]

@app.get("/")
async def root():
    return {"message": "AI Voice Assistant Coordinator Service is running"}

@app.post("/process_audio")
async def process_audio(request: AudioRequest):
    """Process audio and return AI response"""
    try:
        # 1. Send audio to STT service
        audio_path = request.audio_path
        stt_url = f"http://{STT_HOST}:{STT_PORT}/transcribe"
        stt_response = requests.post(stt_url, json={"audio_path": audio_path})
        stt_response.raise_for_status()
        transcription = stt_response.json().get("text", "")
        
        if not transcription:
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to recognize audio content"}
            )
        
        # 2. Send text to enhanced LLM processing
        response = await process_text_with_enhanced_llm(transcription)
        
        return response
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing request: {str(e)}"}
        )

@app.post("/process_text")
async def process_text(request: TextRequest):
    """Process text input and return AI response"""
    try:
        response = await process_text_with_enhanced_llm(request.text)
        return response
    
    except Exception as e:
        logger.error(f"Error processing text: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing request: {str(e)}"}
        )

@app.post("/process_voice_with_context")
async def process_voice_with_context(request: ContextualRequest):
    """Process voice command with user context"""
    try:
        # Update user context
        if request.device_id:
            user_contexts[request.device_id] = request.user_context or {}
        
        # Process with enhanced context
        response = await process_text_with_enhanced_llm(
            request.text, 
            request.user_context, 
            request.location
        )
        
        # Add recommendations based on context
        response["recommendations"] = generate_recommendations(
            request.user_context or {}, 
            request.location
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Error processing contextual request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing request: {str(e)}"}
        )

@app.post("/register_device")
async def register_device(request: DeviceRegistration):
    """Register mobile device"""
    device_id = f"mobile_{int(time.time())}"
    registered_devices[device_id] = {
        "device_info": request.device_info,
        "capabilities": request.capabilities,
        "last_seen": time.time(),
        "status": "active"
    }
    
    return {"device_id": device_id, "status": "registered"}

@app.post("/execute_scene")
async def execute_scene(request: SceneRequest):
    """Execute scene mode"""
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

@app.get("/room_status/{room}")
async def get_room_status(room: str):
    """Get specific room status"""
    room_devices = {}
    
    # Collect all devices in the specified room
    for device_type, locations in device_states.items():
        if room in locations and device_type != "sensors":
            room_devices[device_type] = locations[room]
    
    # Get sensor data
    sensor_data = device_states.get("sensors", {}).get(room, {})
    
    return {
        "room": room,
        "devices": room_devices,
        "sensors": sensor_data,
        "timestamp": time.time()
    }

async def process_text_with_enhanced_llm(text_input, user_context=None, location="living_room"):
    """Enhanced text processing with LLM"""
    
    # 1. Generate enhanced system prompt
    system_prompt = get_comprehensive_system_prompt(user_context, location)
    
    # 2. Send to Ollama
    ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{system_prompt}\n\n用户: {text_input}\n助手:",
        "stream": False
    }
    
    ollama_response = requests.post(ollama_url, json=ollama_payload)
    ollama_response.raise_for_status()
    
    ai_text_response = ollama_response.json().get("response", "")
    
    # 3. Enhanced IoT command extraction
    iot_commands = extract_iot_commands_enhanced(text_input, ai_text_response)
    
    # 4. Execute IoT commands
    iot_results = []
    if iot_commands:
        for cmd in iot_commands:
            if cmd.get("type") == "scene":
                # Execute scene mode
                scene_results = await execute_scene_mode(cmd["scene"], location)
                iot_results.extend(scene_results)
            else:
                # Execute individual device command
                iot_url = f"http://{IOT_HOST}:{IOT_PORT}/control"
                iot_response = requests.post(iot_url, json={"commands": [cmd]})
                if iot_response.status_code == 200:
                    iot_results.append(iot_response.json())
    
    # 5. Determine expression/emotion
    expression = determine_expression_enhanced(text_input, ai_text_response, iot_commands)
    
    # 6. Generate speech
    tts_url = f"http://{TTS_HOST}:{TTS_PORT}/synthesize"
    tts_response = requests.post(tts_url, json={"text": ai_text_response})
    tts_response.raise_for_status()
    
    audio_file_path = tts_response.json().get("audio_path", "")
    
    return {
        "input_text": text_input,
        "ai_response": ai_text_response,
        "audio_path": audio_file_path,
        "expression": expression,
        "iot_commands": iot_commands,
        "iot_results": iot_results,
        "location": location,
        "user_context": user_context
    }

def get_comprehensive_system_prompt(user_context=None, location="living_room"):
    """Generate comprehensive system prompt"""
    
    # Get current device status
    try:
        iot_url = f"http://{IOT_HOST}:{IOT_PORT}/devices"
        iot_response = requests.get(iot_url)
        if iot_response.status_code == 200:
            current_device_states = iot_response.json().get("devices", device_states)
        else:
            current_device_states = device_states
    except:
        current_device_states = device_states
    
    # Format device status
    device_status = format_all_device_states(current_device_states)
    
    # Format environmental data
    env_data = format_environmental_data(current_device_states.get("sensors", {}))
    
    # User context
    user_activity = user_context.get("activity", "unknown") if user_context else "unknown"
    time_of_day = user_context.get("time_of_day", "day") if user_context else "day"
    
    system_prompt = f"""You are a smart home voice assistant capable of understanding natural language in both Chinese and English. Control various smart devices based on user intent and current environmental conditions.

## Current Environmental Status
{env_data}

## Current Device Status  
{device_status}

## User Context
- Current Location: {location}
- Current Activity: {user_activity}
- Time of Day: {time_of_day}

## Controllable Device Types

### Lighting System
1. **Ceiling Light** (ceiling_light)
   - Locations: living room, bedroom, kitchen, study, bathroom
   - Controls: on/off/brighten/dim/set brightness(0-100%)/color temperature(2700K-6500K)
   - Keywords: 天花板灯/吸顶灯/主灯/ceiling light/main light/overhead light

2. **Desk Lamp** (desk_lamp)
   - Locations: bedroom, study
   - Controls: on/off/brighten/dim/reading mode/night mode
   - Keywords: 台灯/桌灯/床头灯/desk lamp/table lamp/bedside lamp

### Ventilation System
3. **Fan** (fan)
   - Locations: living room, bedroom, study
   - Controls: on/off/speed adjustment(1-5)/oscillation/timer
   - Keywords: 风扇/电扇/fan/ceiling fan

4. **Exhaust Fan** (exhaust_fan)
   - Locations: kitchen, bathroom
   - Controls: on/off/speed adjustment/timer
   - Keywords: 排气扇/抽风机/exhaust fan/extractor fan/ventilation fan

### Environmental Control
5. **Air Conditioner** (ac)
   - Locations: living room, bedroom
   - Controls: on/off/temperature/mode switching/fan speed
   - Keywords: 空调/冷气/暖气/air conditioner/AC/aircon/HVAC

6. **Curtain** (curtain)
   - Locations: living room, bedroom, study, bathroom
   - Controls: open/close/partial opening(0-100%)/timer
   - Keywords: 窗帘/百叶窗/curtain/blinds/drapes/shades

## Scene Mode Support
- **Home Mode** (home_mode): Turn on living room lights, adjust AC, partially open curtains
  - Keywords: 回家模式/到家/home mode/arrive home/coming home
- **Sleep Mode** (sleep_mode): Turn off lights, lower AC temperature, close curtains
  - Keywords: 睡眠模式/睡觉/晚安/sleep mode/bedtime/goodnight
- **Work Mode** (work_mode): Turn on study lighting, adjust to work-appropriate brightness
  - Keywords: 工作模式/学习/办公/work mode/study mode/office mode
- **Cooking Mode** (cooking_mode): Brightest kitchen lighting, auto exhaust fan
  - Keywords: 烹饪模式/做饭/cooking mode/kitchen mode
- **Movie Mode** (movie_mode): Dim living room lights, close curtains
  - Keywords: 观影模式/看电影/movie mode/cinema mode/watch TV
- **Bath Mode** (bath_mode): Turn on bathroom lights and exhaust fan
  - Keywords: 洗浴模式/洗澡/bath mode/shower mode

## Intelligent Response Rules
- Proactively suggest optimizations based on environmental sensor data
- Adjust device parameters considering user activity and time of day
- Clearly state what actions will be performed when executing controls
- Promptly alert users about environmental anomalies
- Provide energy-saving suggestions and comfort optimization advice
- **Always respond in the same language as the user's input**
- Support mixed Chinese-English commands
- Understand colloquial expressions and smart home slang

## Language Support Examples
### English Commands:
- "Turn on the living room ceiling light"
- "Set bedroom AC to 24 degrees"
- "Dim the study desk lamp to 50%"
- "Execute sleep mode"
- "Open curtains halfway"

### Chinese Commands:
- "打开客厅的天花板灯"
- "把卧室空调调到24度"
- "把书房台灯调暗到50%"
- "执行睡眠模式"
- "窗帘开一半"

### Mixed Commands:
- "Turn on 客厅的灯"
- "打开living room的AC"
- "Set 卧室fan to speed 3"

Please intelligently control devices based on user's natural language instructions and provide thoughtful suggestions. Always respond in the same language as the user's input."""

    return system_prompt

def format_all_device_states(device_states):
    """Format all device states"""
    result = []
    
    # 处理天花板灯
    if "ceiling_light" in device_states:
        result.append("### 天花板灯")
        for location, state in device_states["ceiling_light"].items():
            status = "开启" if state.get("status") == "on" else "关闭"
            brightness = state.get("brightness", 0)
            color_temp = state.get("color_temp", 4000)
            result.append(f"- {location}：{status}，亮度 {brightness}%，色温 {color_temp}K")
    
    # 处理台灯
    if "desk_lamp" in device_states:
        result.append("### 台灯")
        for location, state in device_states["desk_lamp"].items():
            status = "开启" if state.get("status") == "on" else "关闭"
            brightness = state.get("brightness", 0)
            color_temp = state.get("color_temp", 4000)
            result.append(f"- {location}：{status}，亮度 {brightness}%，色温 {color_temp}K")
    
    # 处理风扇
    if "fan" in device_states:
        result.append("### 风扇")
        for location, state in device_states["fan"].items():
            status = "开启" if state.get("status") == "on" else "关闭"
            speed = state.get("speed", 1)
            oscillation = "摇摆" if state.get("oscillation") else "固定"
            result.append(f"- {location}：{status}，档速 {speed}，{oscillation}")
    
    # 处理排气扇
    if "exhaust_fan" in device_states:
        result.append("### 排气扇")
        for location, state in device_states["exhaust_fan"].items():
            status = "开启" if state.get("status") == "on" else "关闭"
            speed = state.get("speed", 1)
            timer = state.get("timer", 0)
            timer_text = f"，定时 {timer}分钟" if timer > 0 else ""
            result.append(f"- {location}：{status}，档速 {speed}{timer_text}")
    
    # 处理空调
    if "ac" in device_states:
        result.append("### 空调")
        for location, state in device_states["ac"].items():
            status = "开启" if state.get("status") == "on" else "关闭"
            temp = state.get("temperature", 26)
            mode = state.get("mode", "cool")
            fan_speed = state.get("fan_speed", "auto")
            result.append(f"- {location}：{status}，温度 {temp}°C，模式 {mode}，风速 {fan_speed}")
    
    # 处理窗帘
    if "curtain" in device_states:
        result.append("### 窗帘")
        for location, state in device_states["curtain"].items():
            status = state.get("status", "closed")
            position = state.get("position", 0)
            result.append(f"- {location}：{status}，开启程度 {position}%")
    
    return "\n".join(result)

def format_environmental_data(sensors_data):
    """Format environmental sensor data"""
    if not sensors_data:
        return "环境传感器数据暂不可用"
    
    result = []
    for location, data in sensors_data.items():
        temp = data.get('temperature', 0)
        humidity = data.get('humidity', 0)
        co2 = data.get('co2', 0)
        voc = data.get('voc', 0)
        light = data.get('light_level', 0)
        
        # 添加环境状态评估
        status_indicators = []
        if co2 > 800:
            status_indicators.append("CO2偏高")
        if humidity > 70:
            status_indicators.append("湿度偏高")
        if temp > 28:
            status_indicators.append("温度偏高")
        elif temp < 18:
            status_indicators.append("温度偏低")
        
        status_text = f" ({', '.join(status_indicators)})" if status_indicators else " (正常)"
        
        result.append(f"- {location}：温度 {temp}°C，湿度 {humidity}%，CO2 {co2}ppm，VOC {voc}ppb，光照 {light}lux{status_text}")
    
    return "\n".join(result)

def extract_iot_commands_enhanced(user_input, ai_response):
    """Enhanced IoT command extraction"""
    commands = []
    user_lower = user_input.lower()
    
    # 设备关键词映射
    device_keywords = {
        # 天花板灯
        "天花板灯": "ceiling_light", "吸顶灯": "ceiling_light", "主灯": "ceiling_light",
        "ceiling light": "ceiling_light", "main light": "ceiling_light",
        
        # 台灯
        "台灯": "desk_lamp", "桌灯": "desk_lamp", "床头灯": "desk_lamp",
        "desk lamp": "desk_lamp", "table lamp": "desk_lamp",
        
        # 风扇
        "风扇": "fan", "电扇": "fan",
        "fan": "fan",
        
        # 排气扇
        "排气扇": "exhaust_fan", "抽风机": "exhaust_fan",
        "exhaust fan": "exhaust_fan", "extractor": "exhaust_fan",
        
        # 空调
        "空调": "ac", "冷气": "ac", "暖气": "ac",
        "air conditioner": "ac", "ac": "ac",
        
        # 窗帘
        "窗帘": "curtain", "百叶窗": "curtain",
        "curtain": "curtain", "blinds": "curtain",
        
        # 兼容原有的light（映射到ceiling_light）
        "light": "ceiling_light", "灯": "ceiling_light"
    }
    
    # 动作关键词映射
    action_keywords = {
        # 基础控制
        "开": "on", "打开": "on", "启动": "on", "开启": "on",
        "关": "off", "关闭": "off", "停止": "off", "关掉": "off",
        "turn on": "on", "open": "on", "start": "on",
        "turn off": "off", "close": "off", "stop": "off",
        
        # 亮度控制
        "调亮": "brighten", "变亮": "brighten", "亮一点": "brighten",
        "调暗": "dim", "变暗": "dim", "暗一点": "dim",
        "brighten": "brighten", "brighter": "brighten",
        "dim": "dim", "darker": "dim",
        
        # 温度控制
        "调高": "temp_up", "升温": "temp_up", "热一点": "temp_up",
        "调低": "temp_down", "降温": "temp_down", "冷一点": "temp_down",
        "warmer": "temp_up", "hotter": "temp_up",
        "cooler": "temp_down", "colder": "temp_down",
        
        # 速度控制
        "快一点": "speed_up", "加速": "speed_up",
        "慢一点": "speed_down", "减速": "speed_down",
        "speed up": "speed_up", "faster": "speed_up",
        "speed down": "speed_down", "slower": "speed_down"
    }
    
    # 位置关键词
    location_keywords = {
        "客厅": "living_room", "起居室": "living_room",
        "卧室": "bedroom", "睡房": "bedroom", "房间": "bedroom",
        "厨房": "kitchen", "灶间": "kitchen",
        "书房": "study", "工作室": "study", "办公室": "study",
        "浴室": "bathroom", "洗手间": "bathroom", "厕所": "bathroom",
        "living room": "living_room", "lounge": "living_room",
        "bedroom": "bedroom", "room": "bedroom",
        "kitchen": "kitchen",
        "study": "study", "office": "study",
        "bathroom": "bathroom", "toilet": "bathroom"
    }
    
    # 场景模式识别
    scene_keywords = {
        "回家": "home_mode", "到家": "home_mode", "回来": "home_mode",
        "睡觉": "sleep_mode", "休息": "sleep_mode", "睡眠": "sleep_mode", "晚安": "sleep_mode",
        "工作": "work_mode", "学习": "work_mode", "办公": "work_mode", "上班": "work_mode",
        "看电影": "movie_mode", "观影": "movie_mode", "看片": "movie_mode",
        "做饭": "cooking_mode", "烹饪": "cooking_mode", "煮饭": "cooking_mode",
        "洗澡": "bath_mode", "洗浴": "bath_mode", "沐浴": "bath_mode",
        "home": "home_mode", "arrive": "home_mode",
        "sleep": "sleep_mode", "rest": "sleep_mode", "goodnight": "sleep_mode",
        "work": "work_mode", "study": "work_mode",
        "movie": "movie_mode", "watch": "movie_mode",
        "cook": "cooking_mode", "cooking": "cooking_mode",
        "bath": "bath_mode", "shower": "bath_mode"
    }
    
    # 检查场景模式
    for keyword, scene in scene_keywords.items():
        if keyword in user_lower:
            commands.append({
                "type": "scene",
                "scene": scene
            })
            return commands
    
    # 检查设备控制
    for device_keyword, device_type in device_keywords.items():
        if device_keyword in user_lower:
            # 确定位置
            location = "living_room"  # 默认位置
            for loc_keyword, loc_value in location_keywords.items():
                if loc_keyword in user_lower:
                    location = loc_value
                    break
            
            # 确定动作
            action = "on"  # 默认动作
            parameters = {}
            
            for action_keyword, action_value in action_keywords.items():
                if action_keyword in user_lower:
                    action = action_value
                    break
            
            # 检查特定参数
            # 亮度设置
            brightness_match = re.search(r'(\d+)%|(\d+)成|亮度(\d+)', user_lower)
            if brightness_match:
                brightness = int(brightness_match.group(1) or brightness_match.group(2) or brightness_match.group(3))
                parameters["brightness"] = min(100, max(0, brightness))
                action = "set_brightness"
            
            # 温度设置
            temp_match = re.search(r'(\d+)度|(\d+)°', user_lower)
            if temp_match:
                temperature = int(temp_match.group(1) or temp_match.group(2))
                parameters["temperature"] = min(30, max(16, temperature))
                action = "set_temperature"
            
            # 速度设置
            speed_match = re.search(r'(\d+)档|(\d+)级', user_lower)
            if speed_match:
                speed = int(speed_match.group(1) or speed_match.group(2))
                parameters["speed"] = min(5, max(1, speed))
                action = "set_speed"
            
            # 位置设置（窗帘）
            position_match = re.search(r'开启(\d+)%|打开(\d+)%', user_lower)
            if position_match and device_type == "curtain":
                position = int(position_match.group(1) or position_match.group(2))
                parameters["position"] = min(100, max(0, position))
                action = "set_position"
            
            commands.append({
                "device": device_type,
                "action": action,
                "location": location,
                "parameters": parameters
            })
    
    return commands

async def execute_scene_mode(scene_name, location=None):
    """Execute scene mode"""
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
            {"device": "curtain", "action": "off", "location": target_location},
            # 关闭其他房间主要灯光
            {"device": "ceiling_light", "action": "off", "location": "living_room"},
            {"device": "ceiling_light", "action": "off", "location": "kitchen"}
        ]
    
    elif scene_name == "work_mode":
        # 工作模式
        target_location = location or "study"
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": target_location, "parameters": {"brightness": 80, "color_temp": 4500}},
            {"device": "desk_lamp", "action": "on", "location": target_location, "parameters": {"brightness": 70}},
            {"device": "curtain", "action": "set_position", "location": target_location, "parameters": {"position": 30}}
        ]
    
    elif scene_name == "cooking_mode":
        # 烹饪模式
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {"brightness": 100}},
            {"device": "exhaust_fan", "action": "on", "location": "kitchen", "parameters": {"speed": 2}}
        ]
    
    elif scene_name == "movie_mode":
        # 观影模式
        target_location = location or "living_room"
        scene_commands = [
            {"device": "ceiling_light", "action": "dim", "location": target_location, "parameters": {"brightness": 20}},
            {"device": "curtain", "action": "off", "location": target_location},
            {"device": "ac", "action": "on", "location": target_location, "parameters": {"temperature": 24}}
        ]
    
    elif scene_name == "bath_mode":
        # 洗浴模式
        scene_commands = [
            {"device": "ceiling_light", "action": "on", "location": "bathroom", "parameters": {"brightness": 80}},
            {"device": "exhaust_fan", "action": "on", "location": "bathroom", "parameters": {"speed": 2, "timer": 30}}
        ]
    
    # 执行场景命令
    results = []
    for cmd in scene_commands:
        try:
            iot_url = f"http://{IOT_HOST}:{IOT_PORT}/control"
            iot_response = requests.post(iot_url, json={"commands": [cmd]})
            if iot_response.status_code == 200:
                results.append(iot_response.json())
            else:
                results.append({"status": "error", "command": cmd, "error": "IoT service error"})
        except Exception as e:
            results.append({"status": "error", "command": cmd, "error": str(e)})
    
    return results

def determine_expression_enhanced(user_input, ai_response, iot_commands):
    """Enhanced expression determination"""
    user_lower = user_input.lower()
    
    # 基于场景模式的表情
    for cmd in iot_commands:
        if cmd.get("type") == "scene":
            scene = cmd.get("scene")
            if scene == "sleep_mode":
                return "sleeping"
            elif scene == "work_mode":
                return "working"
            elif scene == "cooking_mode":
                return "cooking"
            elif scene == "home_mode":
                return "happy"
            elif scene == "movie_mode":
                return "relaxing"
    
    # 基于用户情绪的表情
    if any(word in user_lower for word in ["谢谢", "感谢", "太好了", "棒", "great", "thanks", "wonderful"]):
        return "smile"
    elif any(word in user_lower for word in ["什么", "怎么", "为什么", "how", "what", "why"]):
        return "thinking"
    elif any(word in ai_response.lower() for word in ["抱歉", "对不起", "sorry", "apologize"]):
        return "sad"
    elif any(word in user_lower for word in ["惊喜", "哇", "amazing", "wow", "surprise"]):
        return "surprised"
    elif any(word in user_lower for word in ["困惑", "不懂", "confused", "don't understand"]):
        return "confused"
    else:
        return "neutral"

def generate_recommendations(user_context, location):
    """Generate personalized recommendations"""
    recommendations = []
    activity = user_context.get("activity", "")
    time_of_day = user_context.get("time_of_day", "")
    
    # 基于活动的建议
    if activity == "reading":
        recommendations.append("建议调节护眼模式：台灯亮度70%，色温4000K")
    elif activity == "sleeping":
        recommendations.append("建议开启睡眠模式：关闭主要灯光，调低空调温度")
    elif activity == "cooking":
        recommendations.append("建议开启厨房模式：最亮照明，自动排气扇")
    elif activity == "working":
        recommendations.append("建议开启工作模式：充足照明，适宜温度")
    
    # 基于时间的建议
    current_hour = time.localtime().tm_hour
    if current_hour >= 22 or current_hour <= 6:
        recommendations.append("夜间模式：建议使用暖色调照明，降低整体亮度")
    elif 6 <= current_hour <= 9:
        recommendations.append("早晨模式：逐渐提高亮度，保持新鲜空气循环")
    elif 18 <= current_hour <= 22:
        recommendations.append("傍晚模式：温暖照明，营造放松氛围")
    
    # 基于环境数据的建议
    sensors = device_states.get("sensors", {}).get(location, {})
    if sensors:
        co2 = sensors.get("co2", 0)
        humidity = sensors.get("humidity", 0)
        temperature = sensors.get("temperature", 0)
        light_level = sensors.get("light_level", 0)
        
        if co2 > 800:
            recommendations.append("CO2浓度较高，建议开窗通风或开启排气扇")
        if humidity > 70:
            recommendations.append("湿度较高，建议开启除湿功能或排气扇")
        if temperature > 28:
            recommendations.append("温度较高，建议开启空调或风扇")
        elif temperature < 18:
            recommendations.append("温度较低，建议开启暖气或关闭风扇")
        if light_level < 100 and 8 <= current_hour <= 20:
            recommendations.append("光线不足，建议开启照明设备")
    
    return recommendations

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket connection handler"""
    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "text":
                    # Process text message with context
                    user_context = message.get("user_context")
                    location = message.get("location", "living_room")
                    
                    response = await process_text_with_enhanced_llm(
                        message.get("text", ""), 
                        user_context, 
                        location
                    )
                    await websocket.send_json(response)
                
                elif message_type == "audio_ready":
                    # Process audio ready notification
                    audio_path = message.get("path")
                    response = await process_audio(AudioRequest(audio_path=audio_path))
                    await websocket.send_json(response)
                
                elif message_type == "scene_command":
                    # Execute scene mode
                    scene_name = message.get("scene")
                    location = message.get("location")
                    results = await execute_scene_mode(scene_name, location)
                    
                    await websocket.send_json({
                        "type": "scene_result",
                        "scene": scene_name,
                        "results": results
                    })
                
                elif message_type == "device_registration":
                    # Register device
                    device_info = message.get("device_info", {})
                    capabilities = message.get("capabilities", [])
                    
                    device_id = f"ws_{client_id}"
                    registered_devices[device_id] = {
                        "device_info": device_info,
                        "capabilities": capabilities,
                        "websocket_id": client_id,
                        "last_seen": time.time(),
                        "status": "active"
                    }
                    
                    await websocket.send_json({
                        "type": "registration_result",
                        "device_id": device_id,
                        "status": "registered"
                    })
                
                else:
                    await websocket.send_json({"error": "Unknown message type"})
            
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
    
    except WebSocketDisconnect:
        if client_id in connected_clients:
            del connected_clients[client_id]
        
        # Remove registered device if exists
        device_to_remove = None
        for device_id, device_info in registered_devices.items():
            if device_info.get("websocket_id") == client_id:
                device_to_remove = device_id
                break
        
        if device_to_remove:
            del registered_devices[device_to_remove]
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if client_id in connected_clients:
            del connected_clients[client_id]

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)