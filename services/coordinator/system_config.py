# services/coordinator/system_config.py
"""
系统配置文件 - 包含所有提示词、传感器状态和系统行为定义
"""

import json
from typing import Dict, Any, Optional, List

# ==================== 环境数据和传感器状态 ====================
ENVIRONMENTAL_DATA = {
    "sensors": {
        "living_room": {
            "temperature": 22.5,
            "humidity": 45,
            "co2": 480,
            "voc": 25,
            "motion": False,
            "light_level": 300,
            "last_update": "2025-06-03T10:30:00"
        },
        "bedroom": {
            "temperature": 21.8,
            "humidity": 48,
            "co2": 420,
            "voc": 15,
            "motion": False,
            "light_level": 150,
            "last_update": "2025-06-03T10:30:00"
        },
        "kitchen": {
            "temperature": 23.5,
            "humidity": 55,
            "co2": 550,
            "voc": 35,
            "motion": True,
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

# ==================== 系统提示词 ====================
BASE_SYSTEM_PROMPT = """You are an intelligent AI assistant for a smart home system. Your capabilities include:
1. Controlling various IoT devices (lights, fans, air conditioners, curtains) in different rooms
2. Understanding and responding in both English and Chinese
3. Providing natural, conversational responses
4. Interpreting user intent even from indirect requests

Technical Details about this Smart Home System:
- Architecture: Microservices-based system with Docker containers
- Author: Dankao, supervised by Steve
- Core Services:
  * STT Service: Speech-to-text using OpenAI Whisper
  * TTS Service: Text-to-speech with multiple voice options
  * IoT Control: Device management/monitor with ESP23 support
  * Coordinator: Central orchestration with LLM integration
  * Ollama: Local/Remote LLM model for intent extraction
- Communication: RESTful APIs and WebSocket for real-time updates
- LLM Integration: Supports both local Ollama and remote API modes
- Audio Formats: MP3 for web clients, PCM for ESP32 devices
- Intro: Integrated with ESP32 hardware for audio processing and ESP8266 for environmental monitoring, it supports multi-language commands (English/Chinese) and scene-based automation. Unlike traditional rule-based systems, this framework leverages LLM-powered intent extraction for superior accuracy and user experience while ensuring privacy through complete local processing.

Current environment:"""

# ==================== 场景模式定义 ====================
SCENE_MODES = {
    "home_mode": {
        "name": "Home Mode",
        "description": "Welcome home lighting and comfort settings",
        "actions": [
            {"device": "lights", "room": "living_room", "action": "on", "brightness": 80},
            {"device": "lights", "room": "hallway", "action": "on", "brightness": 60},
            {"device": "ac", "room": "living_room", "action": "on", "temperature": 24}
        ]
    },
    "sleep_mode": {
        "name": "Sleep Mode", 
        "description": "Optimal settings for sleep",
        "actions": [
            {"device": "lights", "room": "all", "action": "off"},
            {"device": "ac", "room": "bedroom", "action": "on", "temperature": 23},
            {"device": "curtains", "room": "bedroom", "action": "close"}
        ]
    },
    "work_mode": {
        "name": "Work Mode",
        "description": "Focused work environment",
        "actions": [
            {"device": "lights", "room": "study", "action": "on", "brightness": 100},
            {"device": "ac", "room": "study", "action": "on", "temperature": 24},
            {"device": "fan", "room": "study", "action": "on", "speed": 2}
        ]
    },
    "movie_mode": {
        "name": "Movie Mode",
        "description": "Theater-like experience",
        "actions": [
            {"device": "lights", "room": "living_room", "action": "dim", "brightness": 20},
            {"device": "curtains", "room": "living_room", "action": "close"},
            {"device": "ac", "room": "living_room", "action": "on", "temperature": 22}
        ]
    },
    "cooking_mode": {
        "name": "Cooking Mode",
        "description": "Kitchen optimized for cooking",
        "actions": [
            {"device": "lights", "room": "kitchen", "action": "on", "brightness": 100},
            {"device": "exhaust_fan", "room": "kitchen", "action": "on"},
            {"device": "fan", "room": "kitchen", "action": "on", "speed": 3}
        ]
    },
    "away_mode": {
        "name": "Away Mode",
        "description": "Energy saving and security",
        "actions": [
            {"device": "lights", "room": "all", "action": "off"},
            {"device": "ac", "room": "all", "action": "off"},
            {"device": "curtains", "room": "all", "action": "close"}
        ]
    }
}

# ==================== IoT命令关键词映射 ====================
IOT_COMMAND_KEYWORDS = {
    "lights": {
        "on": ["turn on", "open", "打开", "开", "light up", "亮"],
        "off": ["turn off", "close", "关闭", "关", "shut"],
        "dim": ["dim", "dimmer", "darker", "调暗", "暗一点"],
        "bright": ["bright", "brighter", "调亮", "亮一点"]
    },
    "ac": {
        "on": ["turn on ac", "air conditioner on", "开空调", "打开空调"],
        "off": ["turn off ac", "air conditioner off", "关空调", "关闭空调"],
        "temperature": ["set temperature", "temperature to", "温度调到", "设置温度"]
    },
    "fan": {
        "on": ["turn on fan", "fan on", "开风扇", "打开风扇"],
        "off": ["turn off fan", "fan off", "关风扇", "关闭风扇"],
        "speed": ["fan speed", "风扇速度", "调节风速"]
    },
    "curtains": {
        "open": ["open curtains", "curtains open", "拉开窗帘", "打开窗帘"],
        "close": ["close curtains", "curtains close", "拉上窗帘", "关闭窗帘"],
        "half": ["half open", "halfway", "开一半", "半开"]
    }
}

# ==================== 房间名称映射 ====================
ROOM_MAPPINGS = {
    "living room": "living_room",
    "客厅": "living_room",
    "bedroom": "bedroom", 
    "卧室": "bedroom",
    "kitchen": "kitchen",
    "厨房": "kitchen",
    "study": "study",
    "书房": "study",
    "bathroom": "bathroom",
    "浴室": "bathroom",
    "洗手间": "bathroom"
}

# ==================== 表情/情绪判断关键词 ====================
EMOTION_KEYWORDS = {
    "positive": ["good", "great", "nice", "perfect", "excellent", "wonderful", 
                 "好", "很好", "不错", "完美", "棒", "太好了"],
    "negative": ["bad", "terrible", "wrong", "error", "fail", "problem",
                 "糟糕", "不好", "错误", "失败", "问题"],
    "question": ["what", "how", "why", "when", "where", "who",
                 "什么", "怎么", "为什么", "哪里", "谁"]
}

# ==================== 辅助函数 ====================
def get_comprehensive_system_prompt(user_context: Optional[Dict] = None, 
                                  location: str = "living_room") -> str:
    """生成包含所有房间信息的系统提示词"""
    prompt = BASE_SYSTEM_PROMPT
    
    # 添加所有房间的传感器数据
    prompt += "\n\nCurrent environment status across all rooms:"
    
    # 遍历所有房间
    for room_name, sensor_data in ENVIRONMENTAL_DATA["sensors"].items():
        room_display_name = room_name.replace('_', ' ').title()
        prompt += f"\n\n{room_display_name}:"
        prompt += f"\n- Temperature: {sensor_data['temperature']}°C"
        prompt += f"\n- Humidity: {sensor_data['humidity']}%"
        prompt += f"\n- CO2: {sensor_data['co2']} ppm"
        prompt += f"\n- VOC: {sensor_data['voc']}"
        prompt += f"\n- Motion detected: {sensor_data['motion']}"
        prompt += f"\n- Light level: {sensor_data['light_level']} lux"
    
    # 如果指定了当前位置，强调一下
    if location and location in ENVIRONMENTAL_DATA["sensors"]:
        prompt += f"\n\nUser is currently in: {location}"
    
    # 添加用户上下文
    if user_context:
        prompt += f"\n\nUser context: {json.dumps(user_context, ensure_ascii=False)}"
    
    # 添加指导说明
    prompt += "\n\nImportant instructions:"
    prompt += "\n- You have access to ALL rooms in the house (living_room, bedroom, kitchen, study, bathroom)"
    prompt += "\n- You can control devices in ANY room, not just the current location"
    prompt += "\n- When users mention a room, execute commands for that specific room"
    prompt += "\n- If no room is specified, you can ask which room they mean or use the current location"
    prompt += "\n- Respond naturally in the language the user uses (English or Chinese)"
    
    return prompt

def extract_iot_commands_enhanced(text: str, location: str = "living_room") -> List[Dict]:
    """从文本中提取IoT控制命令"""
    commands = []
    text_lower = text.lower()
    
    # 检查每种设备类型
    for device_type, actions in IOT_COMMAND_KEYWORDS.items():
        for action, keywords in actions.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # 提取房间信息
                    target_room = location
                    for room_phrase, room_code in ROOM_MAPPINGS.items():
                        if room_phrase in text_lower:
                            target_room = room_code
                            break
                    
                    # 构建命令
                    command = {
                        "device": device_type,
                        "room": target_room,
                        "action": action
                    }
                    
                    # 特殊处理：温度设置
                    if device_type == "ac" and action == "temperature":
                        import re
                        temp_match = re.search(r'\d+', text)
                        if temp_match:
                            command["temperature"] = int(temp_match.group())
                    
                    # 特殊处理：亮度设置
                    if device_type == "lights" and action in ["dim", "bright"]:
                        if "dim" in text_lower or "暗" in text_lower:
                            command["brightness"] = 30
                        elif "bright" in text_lower or "亮" in text_lower:
                            command["brightness"] = 100
                    
                    commands.append(command)
                    break
    
    return commands

def determine_expression_enhanced(user_input: str, ai_response: str, 
                                iot_commands: List[Dict]) -> str:
    """根据对话内容判断表情/情绪"""
    user_lower = user_input.lower()
    
    # 根据关键词判断
    if any(keyword in user_lower for keyword in EMOTION_KEYWORDS["negative"]):
        return "sad"
    elif any(keyword in user_lower for keyword in EMOTION_KEYWORDS["positive"]):
        return "happy"
    elif any(keyword in user_lower for keyword in EMOTION_KEYWORDS["question"]):
        return "thinking"
    
    # 如果有IoT命令被执行，通常是积极的
    if iot_commands:
        return "happy"
    
    return "neutral"

def get_scene_actions(scene_name: str) -> List[Dict]:
    """获取场景模式的动作列表"""
    if scene_name in SCENE_MODES:
        return SCENE_MODES[scene_name]["actions"]
    return []

def update_sensor_data(room: str, sensor_type: str, value: Any) -> bool:
    """更新传感器数据"""
    if room in ENVIRONMENTAL_DATA["sensors"]:
        if sensor_type in ENVIRONMENTAL_DATA["sensors"][room]:
            ENVIRONMENTAL_DATA["sensors"][room][sensor_type] = value
            return True
    return False

def get_all_sensors_data() -> Dict:
    """获取所有传感器数据"""
    return ENVIRONMENTAL_DATA["sensors"].copy()