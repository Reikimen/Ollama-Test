# services/coordinator/smart_home_config.py
"""
Smart Home Configuration Module
包含所有设备状态、传感器数据和系统提示词的定义
"""

import time
from typing import Dict, Any

# ==================== 设备状态定义 ====================

DEFAULT_DEVICE_STATES = {
    "light": {
        "living_room": {"status": "off", "brightness": 0, "color": "white"},
        "bedroom": {"status": "off", "brightness": 0, "color": "warm"},
        "kitchen": {"status": "on", "brightness": 80, "color": "white"},
        "bathroom": {"status": "off", "brightness": 0, "color": "white"},
        "study": {"status": "on", "brightness": 100, "color": "cool"}
    },
    "fan": {
        "living_room": {"status": "off", "speed": 0},
        "bedroom": {"status": "on", "speed": 2},
        "kitchen": {"status": "off", "speed": 0}
    },
    "ac": {
        "living_room": {"status": "off", "temperature": 24, "mode": "cool"},
        "bedroom": {"status": "on", "temperature": 22, "mode": "cool"},
        "study": {"status": "off", "temperature": 23, "mode": "auto"}
    },
    "curtain": {
        "living_room": {"status": "open", "position": 100},
        "bedroom": {"status": "closed", "position": 0},
        "study": {"status": "half", "position": 50}
    },
    "tv": {
        "living_room": {"status": "off", "channel": 1, "volume": 20},
        "bedroom": {"status": "off", "channel": 1, "volume": 15}
    },
    "speaker": {
        "living_room": {"status": "off", "volume": 30, "playing": ""},
        "bedroom": {"status": "off", "volume": 25, "playing": ""},
        "kitchen": {"status": "on", "volume": 40, "playing": "Morning Jazz"}
    }
}

# ==================== 传感器数据定义 ====================

DEFAULT_SENSOR_DATA = {
    "environment": {
        "living_room": {
            "temperature": 23.5,
            "humidity": 45,
            "co2": 450,
            "voc": 25,
            "motion": True,
            "light_level": 350,
            "last_update": "2025-06-03T10:30:00"
        },
        "bedroom": {
            "temperature": 22.8,
            "humidity": 48,
            "co2": 420,
            "voc": 15,
            "motion": False,
            "light_level": 50,
            "last_update": "2025-06-03T10:30:00"
        },
        "kitchen": {
            "temperature": 24.2,
            "humidity": 55,
            "co2": 480,
            "voc": 35,
            "motion": True,
            "light_level": 450,
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

# ==================== 场景模式定义 ====================

SCENE_MODES = {
    "sleep_mode": {
        "description": "睡眠模式 - 准备休息",
        "commands": [
            {"device": "light", "action": "off", "location": "bedroom"},
            {"device": "ac", "action": "on", "location": "bedroom", "temperature": 22},
            {"device": "curtain", "action": "close", "location": "bedroom"},
            {"device": "fan", "action": "on", "location": "bedroom", "speed": 1}
        ]
    },
    "wake_mode": {
        "description": "起床模式 - 早安例程",
        "commands": [
            {"device": "curtain", "action": "open", "location": "bedroom"},
            {"device": "light", "action": "on", "location": "bedroom", "brightness": 50},
            {"device": "ac", "action": "off", "location": "bedroom"}
        ]
    },
    "work_mode": {
        "description": "工作模式 - 专注环境",
        "commands": [
            {"device": "light", "action": "on", "location": "study", "brightness": 100},
            {"device": "ac", "action": "on", "location": "study", "temperature": 23},
            {"device": "fan", "action": "off", "location": "study"}
        ]
    },
    "movie_mode": {
        "description": "观影模式 - 家庭影院",
        "commands": [
            {"device": "light", "action": "dim", "location": "living_room", "brightness": 20},
            {"device": "curtain", "action": "close", "location": "living_room"},
            {"device": "tv", "action": "on", "location": "living_room"}
        ]
    },
    "cooking_mode": {
        "description": "烹饪模式 - 厨房环境优化",
        "commands": [
            {"device": "light", "action": "on", "location": "kitchen", "brightness": 100},
            {"device": "fan", "action": "on", "location": "kitchen", "speed": 3},
            {"device": "speaker", "action": "on", "location": "kitchen", "volume": 50}
        ]
    },
    "away_mode": {
        "description": "离家模式 - 安全节能",
        "commands": [
            {"device": "light", "action": "off", "location": "all"},
            {"device": "ac", "action": "off", "location": "all"},
            {"device": "fan", "action": "off", "location": "all"},
            {"device": "tv", "action": "off", "location": "all"}
        ]
    }
}

# ==================== 系统提示词模板 ====================

SYSTEM_PROMPT_TEMPLATE = """You are an intelligent home assistant with the following capabilities:
1. Control smart home devices (lights, fans, AC, curtains, TV, speakers)
2. Monitor environmental sensors (temperature, humidity, air quality)
3. Provide helpful information and answer questions
4. Execute scene modes for different activities
5. Understand context and user preferences

Current Context:
- Location: {location}
- Time: {time}
- Active Devices: {active_devices}
- Environmental Status: {env_status}
- User Preferences: {preferences}

Environmental Data:
{env_data}

Device Status:
{device_status}

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
   - Controls: on/off/speed adjustment(1-3)/timer mode
   - Keywords: 排气扇/抽风机/exhaust fan

### Climate Control
5. **Air Conditioner** (ac)
   - Locations: living room, bedroom, study
   - Controls: on/off/temperature(16-30°C)/mode(cool/heat/auto)/fan speed
   - Keywords: 空调/冷气/AC/air conditioner

### Window Control
6. **Curtain** (curtain)
   - Locations: living room, bedroom, study, bathroom
   - Controls: open/close/position(0-100%)
   - Keywords: 窗帘/遮光帘/curtain/blinds

### Entertainment
7. **TV** (tv)
   - Locations: living room, bedroom
   - Controls: on/off/channel/volume
   - Keywords: 电视/TV/television

8. **Speaker** (speaker)
   - Locations: living room, bedroom, kitchen
   - Controls: on/off/volume/play/pause
   - Keywords: 音响/扬声器/speaker/audio

## Response Guidelines
- Always respond in the same language as the user's input
- Provide helpful, contextual responses about device control
- If no IoT commands are detected, engage in normal conversation
- Include environmental awareness in your responses
- Be concise but informative
- Use natural, friendly language
- Consider energy efficiency and comfort in your suggestions

When controlling devices:
- Be specific about which device and location
- Confirm actions when executed
- Suggest optimal settings based on context
- Consider the current environmental conditions"""

# ==================== 设备和动作映射 ====================

DEVICE_KEYWORDS = {
    # 中文设备关键词
    "灯": "light",
    "电灯": "light",
    "照明": "light",
    "天花板灯": "light",
    "吸顶灯": "light",
    "主灯": "light",
    "台灯": "light",
    "桌灯": "light",
    "床头灯": "light",
    
    "风扇": "fan",
    "电扇": "fan",
    "电风扇": "fan",
    "吊扇": "fan",
    
    "空调": "ac",
    "冷气": "ac",
    "暖气": "ac",
    
    "窗帘": "curtain",
    "窗户": "curtain",
    "遮光帘": "curtain",
    "百叶窗": "curtain",
    
    "电视": "tv",
    "电视机": "tv",
    
    "音响": "speaker",
    "音箱": "speaker",
    "扬声器": "speaker",
    
    # English device keywords
    "light": "light",
    "lamp": "light",
    "lighting": "light",
    "ceiling light": "light",
    "desk lamp": "light",
    
    "fan": "fan",
    "ceiling fan": "fan",
    "ventilator": "fan",
    
    "ac": "ac",
    "air conditioner": "ac",
    "air conditioning": "ac",
    "aircon": "ac",
    
    "curtain": "curtain",
    "blind": "curtain",
    "blinds": "curtain",
    "window": "curtain",
    
    "tv": "tv",
    "television": "tv",
    
    "speaker": "speaker",
    "audio": "speaker",
    "sound": "speaker"
}

ACTION_KEYWORDS = {
    # 中文动作关键词
    "开": "on",
    "打开": "on",
    "开启": "on",
    "启动": "on",
    
    "关": "off",
    "关闭": "off",
    "关掉": "off",
    "停止": "off",
    
    "调亮": "brighten",
    "亮一点": "brighten",
    "增加亮度": "brighten",
    
    "调暗": "dim",
    "暗一点": "dim",
    "降低亮度": "dim",
    
    "调高": "increase",
    "升高": "increase",
    "增加": "increase",
    
    "调低": "decrease",
    "降低": "decrease",
    "减少": "decrease",
    
    # English action keywords
    "on": "on",
    "turn on": "on",
    "switch on": "on",
    "enable": "on",
    "activate": "on",
    
    "off": "off",
    "turn off": "off",
    "switch off": "off",
    "disable": "off",
    "deactivate": "off",
    
    "brighten": "brighten",
    "brighter": "brighten",
    "increase brightness": "brighten",
    
    "dim": "dim",
    "darker": "dim",
    "decrease brightness": "dim",
    
    "increase": "increase",
    "raise": "increase",
    "up": "increase",
    
    "decrease": "decrease",
    "lower": "decrease",
    "down": "decrease"
}

LOCATION_KEYWORDS = {
    # 中文位置关键词
    "客厅": "living_room",
    "起居室": "living_room",
    "大厅": "living_room",
    
    "卧室": "bedroom",
    "睡房": "bedroom",
    "主卧": "bedroom",
    
    "厨房": "kitchen",
    "烹饪间": "kitchen",
    
    "浴室": "bathroom",
    "洗手间": "bathroom",
    "卫生间": "bathroom",
    "厕所": "bathroom",
    
    "书房": "study",
    "办公室": "study",
    "工作间": "study",
    
    # English location keywords
    "living room": "living_room",
    "livingroom": "living_room",
    "lounge": "living_room",
    
    "bedroom": "bedroom",
    "bed room": "bedroom",
    "master bedroom": "bedroom",
    
    "kitchen": "kitchen",
    
    "bathroom": "bathroom",
    "bath": "bathroom",
    "toilet": "bathroom",
    "restroom": "bathroom",
    
    "study": "study",
    "office": "study",
    "study room": "study",
    "home office": "study"
}

# ==================== 环境阈值定义 ====================

ENVIRONMENTAL_THRESHOLDS = {
    "temperature": {
        "optimal_min": 20,
        "optimal_max": 26,
        "warning_min": 16,
        "warning_max": 30
    },
    "humidity": {
        "optimal_min": 40,
        "optimal_max": 60,
        "warning_min": 30,
        "warning_max": 70
    },
    "co2": {
        "good": 600,
        "fair": 1000,
        "poor": 1500
    },
    "voc": {
        "good": 50,
        "fair": 100,
        "poor": 200
    },
    "light_level": {
        "dark": 50,
        "dim": 200,
        "normal": 500,
        "bright": 1000
    }
}

# ==================== 错误消息模板 ====================

ERROR_MESSAGES = {
    "device_not_found": "设备未找到：{device} 在 {location} / Device not found: {device} at {location}",
    "action_not_supported": "不支持的操作：{action} 对于 {device} / Unsupported action: {action} for {device}",
    "location_not_found": "位置未找到：{location} / Location not found: {location}",
    "parameter_invalid": "无效参数：{parameter} = {value} / Invalid parameter: {parameter} = {value}",
    "service_unavailable": "服务不可用：{service} / Service unavailable: {service}",
    "api_error": "API错误：{error} / API error: {error}"
}

# ==================== 响应模板 ====================

RESPONSE_TEMPLATES = {
    "device_control_success": {
        "zh": "已{action} {location}的{device}",
        "en": "{device} in {location} has been turned {action}"
    },
    "temperature_query": {
        "zh": "{location}的温度是{temperature}°C，湿度{humidity}%",
        "en": "The temperature in {location} is {temperature}°C with {humidity}% humidity"
    },
    "scene_activated": {
        "zh": "已启动{scene_name}",
        "en": "{scene_name} has been activated"
    },
    "environmental_alert": {
        "zh": "注意：{location}的{metric}为{value}，{status}",
        "en": "Alert: {metric} in {location} is {value}, which is {status}"
    }
}