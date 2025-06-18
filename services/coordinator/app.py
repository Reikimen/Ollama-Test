import os
import json
import logging
import asyncio
import aiohttp
import websockets
import time
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")  # 默认模型，可被动态切换
STT_HOST = os.getenv("STT_HOST", "stt-service")
STT_PORT = os.getenv("STT_PORT", "8000")
TTS_HOST = os.getenv("TTS_HOST", "tts-service")
TTS_PORT = os.getenv("TTS_PORT", "8001")
IOT_HOST = os.getenv("IOT_HOST", "iot-control")
IOT_PORT = os.getenv("IOT_PORT", "8002")

# Enhanced ModelManager with configuration persistence
class ModelManager:
    def __init__(self):
        self.current_model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3:8b")
        self.available_models = []
        self.model_info = {}
        self.last_model_check = 0
        self.model_check_interval = 30  # 30秒检查一次可用模型
        
        # 配置文件路径
        self.config_dir = "/app/config"
        self.config_file = os.path.join(self.config_dir, "model_preferences.json")
        
        # 启动时加载已保存的配置
        self._load_saved_preferences()
    
    def _ensure_config_directory(self):
        """确保配置目录存在"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create config directory: {str(e)}")
            return False
    
    def _save_preferences_to_file(self):
        """自动保存模型偏好设置到配置文件"""
        try:
            if not self._ensure_config_directory():
                return False
            
            # 构建配置数据
            preferences = {
                "current_model": self.current_model,
                "available_models": [
                    {
                        "name": model_name,
                        "info": self.model_info.get(model_name, {})
                    }
                    for model_name in self.available_models
                ],
                "model_info": self.model_info,
                "last_updated": time.time(),
                "last_model_check": self.last_model_check,
                "config_version": "1.0",
                "auto_generated": True,
                "creation_method": "model_switch"
            }
            
            # 写入配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(preferences, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Model preferences automatically saved to {self.config_file}")
            logger.info(f"📋 Current model: {self.current_model}")
            logger.info(f"📋 Total models: {len(self.available_models)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save model preferences: {str(e)}")
            return False
    
    def _load_saved_preferences(self):
        """启动时加载已保存的配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    preferences = json.load(f)
                
                # 加载保存的当前模型
                saved_model = preferences.get("current_model")
                if saved_model:
                    self.current_model = saved_model
                    logger.info(f"🔄 Restored current model from config: {self.current_model}")
                
                # 加载模型信息（如果有的话）
                self.model_info = preferences.get("model_info", {})
                self.last_model_check = preferences.get("last_model_check", 0)
                
                last_updated = preferences.get("last_updated", 0)
                logger.info(f"📁 Loaded saved preferences from {self.config_file}")
                logger.info(f"⏰ Last updated: {time.ctime(last_updated) if last_updated else 'Unknown'}")
                
            else:
                logger.info(f"🆕 No existing config file found, will create on first model switch")
                
        except Exception as e:
            logger.error(f"❌ Failed to load saved preferences: {str(e)}")
            logger.info(f"🔄 Will use default configuration")
    
    async def get_available_models(self, force_refresh=False):
        """获取可用模型列表"""
        current_time = time.time()
        
        # 如果需要强制刷新或超过检查间隔，重新获取模型列表
        if force_refresh or (current_time - self.last_model_check) > self.model_check_interval:
            try:
                ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags"
                response = requests.get(ollama_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    
                    # 检查是否有新模型
                    old_models = set(self.available_models)
                    self.available_models = []
                    self.model_info = {}
                    
                    for model in models:
                        model_name = model.get("name", "")
                        if model_name:
                            self.available_models.append(model_name)
                            self.model_info[model_name] = {
                                "name": model_name,
                                "size": model.get("size", 0),
                                "modified_at": model.get("modified_at", ""),
                                "digest": model.get("digest", ""),
                                "details": model.get("details", {})
                            }
                    
                    self.last_model_check = current_time
                    
                    # 检查模型变化
                    new_models = set(self.available_models)
                    if old_models != new_models:
                        added_models = new_models - old_models
                        removed_models = old_models - new_models
                        
                        if added_models:
                            logger.info(f"🆕 New models detected: {list(added_models)}")
                        if removed_models:
                            logger.info(f"🗑️ Models removed: {list(removed_models)}")
                        
                        # 模型列表有变化时自动保存配置
                        self._save_preferences_to_file()
                    
                    logger.info(f"📋 Found {len(self.available_models)} available models: {self.available_models}")
                
                else:
                    logger.error(f"Failed to get models: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error getting available models: {str(e)}")
        
        return self.available_models
    
    def set_current_model(self, model_name):
        """设置当前使用的模型 - 增强版本，自动保存配置"""
        if model_name in self.available_models:
            old_model = self.current_model
            self.current_model = model_name
            
            logger.info(f"🔄 Model switched: {old_model} → {model_name}")
            
            # 🔥 关键功能：在模型切换时自动生成/更新配置文件
            save_success = self._save_preferences_to_file()
            
            if save_success:
                logger.info(f"✅ Configuration file automatically updated after model switch")
            else:
                logger.warning(f"⚠️ Model switched successfully but failed to save configuration")
            
            return True
        else:
            logger.warning(f"⚠️ Model not available: {model_name}")
            return False
    
    def get_current_model(self):
        """获取当前模型"""
        return self.current_model
    
    def get_model_info(self, model_name=None):
        """获取模型详细信息"""
        if model_name is None:
            model_name = self.current_model
        return self.model_info.get(model_name, {})
    
    def get_config_status(self):
        """获取配置文件状态"""
        config_exists = os.path.exists(self.config_file)
        config_size = 0
        config_modified = None
        
        if config_exists:
            try:
                stat = os.stat(self.config_file)
                config_size = stat.st_size
                config_modified = time.ctime(stat.st_mtime)
            except:
                pass
        
        return {
            "config_file_path": self.config_file,
            "config_exists": config_exists,
            "config_size_bytes": config_size,
            "config_modified": config_modified,
            "current_model": self.current_model,
            "total_available_models": len(self.available_models)
        }
    
    def reset_preferences(self):
        """重置配置到默认值"""
        try:
            self.current_model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3:8b")
            self.available_models = []
            self.model_info = {}
            self.last_model_check = 0
            
            # 删除配置文件
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
                logger.info(f"🗑️ Configuration file deleted: {self.config_file}")
            
            logger.info("🔄 Model preferences reset to defaults")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to reset preferences: {str(e)}")
            return False

# 全局模型管理器实例
model_manager = ModelManager()

# Enhanced device states - 保持原有的设备状态
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
app = FastAPI(title="AI Voice Assistant Coordinator Service - Enhanced")

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

class ModelSwitchRequest(BaseModel):
    model_name: str

class ModelPullRequest(BaseModel):
    model_name: str

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

class ConfigResetRequest(BaseModel):
    confirm: bool = False

class ConfigExportRequest(BaseModel):
    export_path: Optional[str] = None

# ==================== 增强的模型管理API ====================

@app.get("/models")
async def get_available_models():
    """获取所有可用的Ollama模型 - 增强版本"""
    try:
        models = await model_manager.get_available_models(force_refresh=True)
        current_model = model_manager.get_current_model()
        config_status = model_manager.get_config_status()
        
        model_list = []
        for model_name in models:
            model_info = model_manager.get_model_info(model_name)
            model_list.append({
                "name": model_name,
                "size": model_info.get("size", 0),
                "size_mb": round(model_info.get("size", 0) / (1024 * 1024), 1),
                "modified_at": model_info.get("modified_at", ""),
                "is_current": model_name == current_model,
                "details": model_info.get("details", {})
            })
        
        return {
            "current_model": current_model,
            "available_models": model_list,
            "total_models": len(models),
            "config_file_info": {
                "exists": config_status["config_exists"],
                "path": config_status["config_file_path"],
                "size_bytes": config_status["config_size_bytes"],
                "last_modified": config_status["config_modified"]
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting models: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error getting models: {str(e)}"}
        )

@app.post("/models/switch")
async def switch_model(request: ModelSwitchRequest):
    """切换当前使用的模型 - 增强版本，自动生成配置文件"""
    try:
        logger.info(f"🔄 Attempting to switch to model: {request.model_name}")
        
        # 先获取最新的模型列表
        available_models = await model_manager.get_available_models(force_refresh=True)
        
        if request.model_name not in available_models:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"Model not found: {request.model_name}",
                    "available_models": available_models
                }
            )
        
        # 获取切换前的状态
        old_model = model_manager.get_current_model()
        config_status_before = model_manager.get_config_status()
        
        # 切换模型（会自动保存配置文件）
        success = model_manager.set_current_model(request.model_name)
        
        if success:
            # 获取切换后的配置状态
            config_status_after = model_manager.get_config_status()
            
            # 测试新模型是否正常工作
            test_result = await test_model_functionality(request.model_name)
            
            if test_result["success"]:
                # 广播模型切换事件到所有连接的客户端
                await broadcast_model_switch(request.model_name)
                
                logger.info(f"✅ Successfully switched from {old_model} to {request.model_name}")
                
                return {
                    "success": True,
                    "message": f"Successfully switched to model: {request.model_name}",
                    "old_model": old_model,
                    "current_model": request.model_name,
                    "test_result": test_result,
                    "config_file_info": {
                        "before_switch": config_status_before,
                        "after_switch": config_status_after,
                        "config_updated": config_status_after["config_exists"],
                        "config_file_path": config_status_after["config_file_path"]
                    },
                    "timestamp": time.time()
                }
            else:
                # 测试失败，但模型切换可能已经成功，记录警告
                logger.warning(f"⚠️ Model switched to {request.model_name} but failed functionality test")
                
                return {
                    "success": True,  # 模型切换成功
                    "message": f"Model switched to {request.model_name} but failed functionality test",
                    "current_model": request.model_name,
                    "test_result": test_result,
                    "warning": "Model may not be fully functional",
                    "config_file_info": {
                        "config_updated": config_status_after["config_exists"],
                        "config_file_path": config_status_after["config_file_path"]
                    }
                }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to switch model",
                    "current_model": model_manager.get_current_model(),
                    "requested_model": request.model_name
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Error switching model: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Error switching model: {str(e)}",
                "current_model": model_manager.get_current_model()
            }
        )

# Add this endpoint to your services/coordinator/app.py
# Place it after the @app.post("/models/switch") endpoint

@app.post("/models/pull")
async def pull_model(request: ModelPullRequest):
    """Download/pull a new model - matches your JavaScript expectation"""
    try:
        model_name = request.model_name.strip()
        logger.info(f"🔄 Starting model pull: {model_name}")
        
        if not model_name:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Model name is required"
                }
            )
        
        # Make request to Ollama service
        ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/pull"
        pull_payload = {"name": model_name}  # Ollama expects 'name' parameter
        
        logger.info(f"📡 Requesting model from Ollama: {ollama_url}")
        
        response = requests.post(
            ollama_url,
            json=pull_payload,
            timeout=600  # 10 minutes for large models
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully pulled model: {model_name}")
            
            # Refresh model list
            await model_manager.get_available_models(force_refresh=True)
            
            # Test the model works
            test_result = await test_model_functionality(model_name)
            
            # Return format your JavaScript expects
            return {
                "success": True,
                "message": f"Model {model_name} downloaded successfully",
                "model_name": model_name,
                "test_result": test_result
            }
        else:
            error_text = response.text
            logger.error(f"❌ Model pull failed: HTTP {response.status_code}")
            
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "success": False,
                    "error": f"Failed to download model: {error_text}",
                    "model_name": model_name
                }
            )
            
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout pulling model {model_name}")
        return JSONResponse(
            status_code=408,
            content={
                "success": False,
                "error": "Model download timeout (10 minutes exceeded)",
                "model_name": model_name
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error pulling model {model_name}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "model_name": model_name
            }
        )

@app.get("/models/config/status")
async def get_config_status():
    """获取配置文件状态"""
    try:
        config_status = model_manager.get_config_status()
        
        return {
            "success": True,
            "config_status": config_status,
            "message": "Configuration status retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting config status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error getting config status: {str(e)}"}
        )

@app.post("/models/config/save")
async def save_config():
    """手动保存当前配置"""
    try:
        model_manager._save_preferences_to_file()
        config_info = model_manager.get_config_status()
        
        return {
            "success": True,
            "message": "Configuration saved successfully",
            "config_info": config_info
        }
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error saving config: {str(e)}"}
        )

@app.post("/models/config/reset")
async def reset_config(request: ConfigResetRequest):
    """重置配置到默认值"""
    try:
        if not request.confirm:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Configuration reset requires confirmation",
                    "message": "Set 'confirm' to true to proceed with reset"
                }
            )
        
        success = model_manager.reset_preferences()
        
        if success:
            # 重新获取可用模型
            await model_manager.get_available_models(force_refresh=True)
            
            return {
                "success": True,
                "message": "Configuration reset successfully",
                "current_model": model_manager.get_current_model(),
                "available_models": model_manager.available_models
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to reset configuration"}
            )
            
    except Exception as e:
        logger.error(f"Error resetting config: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error resetting config: {str(e)}"}
        )

# ==================== 模型测试功能 ====================

async def test_model_functionality(model_name):
    """测试模型是否正常工作"""
    try:
        ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
        
        test_payload = {
            "model": model_name,
            "prompt": "Hello, this is a test message. Please respond with 'Model test successful' if you can understand this.",
            "stream": False
        }
        
        response = requests.post(ollama_url, json=test_payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "").lower()
            
            # 检查响应是否包含预期内容
            if "model test" in response_text or "successful" in response_text or "hello" in response_text:
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "eval_count": data.get("eval_count", 0),
                    "eval_duration": data.get("eval_duration", 0)
                }
            else:
                return {
                    "success": False,
                    "error": "Unexpected response from model",
                    "response": data.get("response", "")
                }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ==================== 广播函数 ====================

async def broadcast_model_switch(new_model):
    """广播模型切换事件到所有连接的客户端 - 增强版本"""
    if not connected_clients:
        return
    
    config_status = model_manager.get_config_status()
    
    message = {
        "type": "model_switch",
        "new_model": new_model,
        "timestamp": time.time(),
        "message": f"System switched to model: {new_model}",
        "config_updated": config_status["config_exists"]
    }
    
    disconnected_clients = []
    for client_id, websocket in connected_clients.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to broadcast model switch to client {client_id}: {str(e)}")
            disconnected_clients.append(client_id)
    
    # Remove disconnected clients
    for client_id in disconnected_clients:
        del connected_clients[client_id]
    
    logger.info(f"📡 Model switch notification broadcasted to {len(connected_clients)} clients")

# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """Enhanced startup with configuration initialization"""
    logger.info("🚀 Enhanced AI Voice Assistant Coordinator starting up...")
    
    # 初始化模型管理器
    await model_manager.get_available_models(force_refresh=True)
    
    # 获取配置状态
    config_status = model_manager.get_config_status()
    
    logger.info(f"🤖 Current model: {model_manager.get_current_model()}")
    logger.info(f"📋 Available models: {model_manager.available_models}")
    logger.info(f"📁 Config file exists: {config_status['config_exists']}")
    logger.info(f"📁 Config file path: {config_status['config_file_path']}")
    
    # 如果配置文件不存在，在启动时创建一个
    if not config_status['config_exists']:
        model_manager._save_preferences_to_file()
        logger.info("💾 Initial configuration file created on startup")
    
    logger.info("✅ Enhanced Coordinator Service startup complete")

# ==================== 保持所有原有API ====================

@app.get("/")
async def root():
    return {"message": "AI Voice Assistant Coordinator Service is running", "current_model": model_manager.get_current_model()}

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
        
        # 2. Process through enhanced LLM
        result = await process_text_with_enhanced_llm(
            transcription, 
            location="living_room"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing audio: {str(e)}"}
        )

@app.post("/process_text")
async def process_text(request: TextRequest):
    """Process text and return AI response"""
    try:
        result = await process_text_with_enhanced_llm(
            request.text,
            location="living_room"
        )
        return result
        
    except Exception as e:
        logger.error(f"Error processing text: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing text: {str(e)}"}
        )

async def process_text_with_enhanced_llm(text_input, user_context=None, location="living_room"):
    """Enhanced text processing with current model"""
    
    # Get current model
    current_model = model_manager.get_current_model()
    
    # 1. Generate system prompt
    system_prompt = get_comprehensive_system_prompt(user_context, location)
    
    # 2. Extract IoT commands
    iot_commands = extract_iot_commands_enhanced(text_input, location)
    
    # 3. Execute IoT commands
    iot_results = []
    for command in iot_commands:
        try:
            iot_url = f"http://{IOT_HOST}:{IOT_PORT}/control"
            iot_response = requests.post(iot_url, json=command)
            if iot_response.status_code == 200:
                iot_results.append(iot_response.json())
            else:
                iot_results.append({"error": f"IoT command failed: {iot_response.text}"})
        except Exception as e:
            iot_results.append({"error": f"IoT service error: {str(e)}"})
    
    # 4. Generate AI response using current model
    ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    
    full_prompt = f"{system_prompt}\n\nUser: {text_input}\n\nAssistant:"
    
    ai_payload = {
        "model": current_model,
        "prompt": full_prompt,
        "stream": False
    }
    
    ai_response = requests.post(ollama_url, json=ai_payload)
    ai_response.raise_for_status()
    
    ai_text_response = ai_response.json().get("response", "I apologize, I couldn't process your request.")
    
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
        "user_context": user_context,
        "model_used": current_model,  # 新增：返回使用的模型信息
        "model_info": model_manager.get_model_info(current_model)
    }

# ==================== 保持所有原有辅助函数 ====================

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
    
    # 获取当前模型信息，用于系统提示
    current_model = model_manager.get_current_model()
    
    system_prompt = f"""You are a smart home voice assistant using model {current_model}. Control various smart devices based on user intent and current environmental conditions.

## Current Environmental Status
{env_data}

## Current Device Status  
{device_status}

## User Context
- Current Location: {location}
- Current Activity: {user_activity}
- Time of Day: {time_of_day}
- AI Model: {current_model}

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
   - Locations: living room, bedroom
   - Controls: on/off/temperature(16-30°C)/mode(cool/heat/auto)/fan speed
   - Keywords: 空调/冷气/AC/air conditioner

### Window Control
6. **Curtain** (curtain)
   - Locations: living room, bedroom, study, bathroom
   - Controls: open/close/position(0-100%)
   - Keywords: 窗帘/遮光帘/curtain/blinds

## Response Guidelines
- Always respond in the same language as the user's input
- Provide helpful, contextual responses about device control
- If no IoT commands are detected, engage in normal conversation
- Include environmental awareness in your responses
- Be concise but informative
- Use natural, friendly language"""

    return system_prompt

def format_all_device_states(current_device_states):
    """Format all device states for system prompt"""
    device_status = []
    
    for device_type, locations in current_device_states.items():
        if device_type == "sensors":
            continue
            
        device_status.append(f"\n**{device_type.replace('_', ' ').title()}:**")
        for location, state in locations.items():
            status_parts = []
            for key, value in state.items():
                if key == "status":
                    status_parts.append(f"{key}: {value}")
                else:
                    status_parts.append(f"{key}: {value}")
            
            device_status.append(f"  - {location}: {', '.join(status_parts)}")
    
    return '\n'.join(device_status)

def format_environmental_data(sensors_data):
    """Format environmental sensor data"""
    if not sensors_data:
        return "No environmental data available"
    
    env_status = []
    for location, data in sensors_data.items():
        env_status.append(f"\n**{location.replace('_', ' ').title()}:**")
        env_status.append(f"  - Temperature: {data.get('temperature', 'N/A')}°C")
        env_status.append(f"  - Humidity: {data.get('humidity', 'N/A')}%")
        env_status.append(f"  - CO2: {data.get('co2', 'N/A')} ppm")
        env_status.append(f"  - VOC: {data.get('voc', 'N/A')} ppb")
        env_status.append(f"  - Light Level: {data.get('light_level', 'N/A')} lux")
        env_status.append(f"  - Motion: {'Detected' if data.get('motion', False) else 'None'}")
    
    return '\n'.join(env_status)

def extract_iot_commands_enhanced(user_input, default_location="living_room"):
    """Enhanced IoT command extraction with better parsing"""
    user_lower = user_input.lower()
    commands = []
    
    # Device keyword mapping
    device_keywords = {
        # 灯光设备
        "天花板灯": "ceiling_light", "吸顶灯": "ceiling_light", "主灯": "ceiling_light",
        "台灯": "desk_lamp", "桌灯": "desk_lamp", "床头灯": "desk_lamp",
        "ceiling light": "ceiling_light", "main light": "ceiling_light", "overhead light": "ceiling_light",
        "desk lamp": "desk_lamp", "table lamp": "desk_lamp", "bedside lamp": "desk_lamp",
        "light": "ceiling_light", "lights": "ceiling_light", "灯": "ceiling_light",
        
        # 风扇设备
        "风扇": "fan", "电扇": "fan", "吊扇": "fan",
        "排气扇": "exhaust_fan", "抽风机": "exhaust_fan",
        "fan": "fan", "ceiling fan": "fan",
        "exhaust fan": "exhaust_fan", "exhaust": "exhaust_fan",
        
        # 空调设备
        "空调": "ac", "冷气": "ac", "暖气": "ac",
        "air conditioner": "ac", "aircon": "ac", "ac": "ac",
        
        # 窗帘设备
        "窗帘": "curtain", "遮光帘": "curtain", "百叶窗": "curtain",
        "curtain": "curtain", "curtains": "curtain", "blinds": "curtain"
    }
    
    # Action keyword mapping
    action_keywords = {
        # 开关控制
        "打开": "on", "开": "on", "开启": "on", "启动": "on",
        "关闭": "off", "关": "off", "停止": "off", "关掉": "off",
        "turn on": "on", "open": "on", "start": "on", "enable": "on",
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
            # 查找动作
            action = "on"  # 默认动作
            for action_keyword, action_type in action_keywords.items():
                if action_keyword in user_lower:
                    action = action_type
                    break
            
            # 查找位置
            location = default_location
            for location_keyword, location_type in location_keywords.items():
                if location_keyword in user_lower:
                    location = location_type
                    break
            
            commands.append({
                "device_type": device_type,
                "location": location,
                "action": action
            })
            break
    
    return commands

def determine_expression_enhanced(user_input, ai_response, iot_commands):
    """Determine facial expression based on context"""
    user_lower = user_input.lower()
    response_lower = ai_response.lower()
    
    # Positive expressions
    if any(word in user_lower for word in ["谢谢", "太好了", "很棒", "喜欢", "开心", "thank you", "great", "awesome", "love", "happy"]):
        return "happy"
    
    # Negative expressions
    if any(word in user_lower for word in ["不好", "糟糕", "讨厌", "不行", "错误", "bad", "terrible", "hate", "wrong", "error"]):
        return "sad"
    
    # Surprised expressions
    if any(word in user_lower for word in ["什么", "怎么", "为什么", "真的吗", "what", "how", "why", "really"]):
        return "surprised"
    
    # Thoughtful expressions
    if any(word in response_lower for word in ["让我想想", "分析", "考虑", "think", "analyze", "consider"]):
        return "thinking"
    
    # IoT control expressions
    if iot_commands:
        return "focused"
    
    return "neutral"

# ==================== WebSocket处理 ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket endpoint with model management support"""
    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    
    try:
        # Send initial connection message with current model info
        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "current_model": model_manager.get_current_model(),
            "config_exists": model_manager.get_config_status()["config_exists"],
            "timestamp": time.time()
        })
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type", "")
            
            if message_type == "text":
                # Text processing
                text_input = message.get("text", "")
                user_context = message.get("user_context", {})
                location = message.get("location", "living_room")
                
                try:
                    response = await process_text_with_enhanced_llm(
                        text_input, 
                        user_context, 
                        location
                    )
                    
                    await websocket.send_json({
                        "type": "text_response",
                        "response": response,
                        "client_id": client_id
                    })
                    
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Text processing failed: {str(e)}"
                    })
            
            elif message_type == "audio_ready":
                # Audio processing
                audio_path = message.get("audio_path", "")
                
                try:
                    audio_request = AudioRequest(audio_path=audio_path)
                    response = await process_audio(audio_request)
                    
                    await websocket.send_json({
                        "type": "audio_response",
                        "response": response,
                        "client_id": client_id
                    })
                    
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Audio processing failed: {str(e)}"
                    })
            
            elif message_type == "model_switch":
                # Model switching via WebSocket
                model_name = message.get("model_name", "")
                
                if model_name:
                    try:
                        # Get available models first
                        available_models = await model_manager.get_available_models(force_refresh=True)
                        
                        if model_name in available_models:
                            # Switch model
                            success = model_manager.set_current_model(model_name)
                            
                            if success:
                                # Test new model
                                test_result = await test_model_functionality(model_name)
                                
                                if test_result["success"]:
                                    await websocket.send_json({
                                        "type": "model_switch_result",
                                        "success": True,
                                        "new_model": model_name,
                                        "test_result": test_result,
                                        "config_updated": model_manager.get_config_status()["config_exists"]
                                    })
                                    
                                    # Broadcast to other clients
                                    await broadcast_model_switch(model_name)
                                else:
                                    await websocket.send_json({
                                        "type": "model_switch_result",
                                        "success": False,
                                        "error": "Model test failed",
                                        "test_result": test_result
                                    })
                            else:
                                await websocket.send_json({
                                    "type": "model_switch_result",
                                    "success": False,
                                    "error": "Failed to switch model"
                                })
                        else:
                            await websocket.send_json({
                                "type": "model_switch_result",
                                "success": False,
                                "error": f"Model not available: {model_name}"
                            })
                    
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "error": f"Model switch error: {str(e)}"
                        })
            
            elif message_type == "get_models":
                # Get available models
                try:
                    models = await model_manager.get_available_models(force_refresh=True)
                    current_model = model_manager.get_current_model()
                    
                    model_list = []
                    for model_name in models:
                        model_info = model_manager.get_model_info(model_name)
                        model_list.append({
                            "name": model_name,
                            "size": model_info.get("size", 0),
                            "size_mb": round(model_info.get("size", 0) / (1024 * 1024), 1),
                            "is_current": model_name == current_model
                        })
                    
                    await websocket.send_json({
                        "type": "models_list",
                        "current_model": current_model,
                        "available_models": model_list,
                        "config_status": model_manager.get_config_status()
                    })
                
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Failed to get models: {str(e)}"
                    })
            
            elif message_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "current_model": model_manager.get_current_model(),
                    "timestamp": time.time()
                })

            elif message_type == "get_status":
                try:
                    # 获取所有服务状态
                    iot_response = requests.get(f"http://{IOT_HOST}:8002/devices", timeout=5)
                    devices = iot_response.json() if iot_response.status_code == 200 else {}
                    
                    sensors_response = requests.get(f"http://{IOT_HOST}:8002/sensors", timeout=5)
                    sensors = sensors_response.json() if sensors_response.status_code == 200 else {}
                    
                    await websocket.send_json({
                        "type": "status_response",
                        "devices": devices,
                        "sensors": sensors,
                        "current_model": model_manager.get_current_model(),
                        "connected_clients": len(connected_clients),
                        # "registered_devices": len(registered_devices),
                        "timestamp": time.time()
                    })
                    
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to get status: {str(e)}"
                    })
            
            else:
                await websocket.send_json({"error": "Unknown message type"})
    
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