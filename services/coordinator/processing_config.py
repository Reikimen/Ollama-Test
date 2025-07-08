"""
Processing Mode Configuration
处理模式配置管理 - 支持智能模式和传统模式切换
"""

import json
import os
from enum import Enum
from typing import Dict, Optional

class ProcessingMode(Enum):
    """处理模式枚举"""
    INTELLIGENT = "intelligent"  # LLM智能分析模式
    TRADITIONAL = "traditional"  # 传统关键词匹配模式
    HYBRID = "hybrid"           # 混合模式（优先智能，失败时降级）

class ProcessingConfig:
    """处理模式配置管理器"""
    
    def __init__(self, config_path: str = "/app/config/processing_mode.json"):
        self.config_path = config_path
        self.current_mode = ProcessingMode.HYBRID  # 默认混合模式
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # 设置当前模式
                mode_str = config.get("mode", "hybrid")
                self.current_mode = ProcessingMode(mode_str)
                
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                
        # 返回默认配置
        return {
            "mode": "hybrid",
            "intelligent_mode": {
                "enabled": True,
                "timeout": 30,
                "confidence_threshold": 0.6,
                "fallback_on_error": True
            },
            "traditional_mode": {
                "enabled": True,
                "enhanced_keywords": True
            },
            "hybrid_mode": {
                "intelligent_first": True,
                "confidence_threshold": 0.5,
                "always_try_intelligent": True
            }
        }
    
    def save_config(self):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        self.config["mode"] = self.current_mode.value
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def set_mode(self, mode: ProcessingMode):
        """设置处理模式"""
        self.current_mode = mode
        self.config["mode"] = mode.value
        self.save_config()
    
    def get_mode(self) -> ProcessingMode:
        """获取当前处理模式"""
        return self.current_mode
    
    def get_intelligent_config(self) -> Dict:
        """获取智能模式配置"""
        return self.config.get("intelligent_mode", {})
    
    def get_traditional_config(self) -> Dict:
        """获取传统模式配置"""
        return self.config.get("traditional_mode", {})
    
    def get_hybrid_config(self) -> Dict:
        """获取混合模式配置"""
        return self.config.get("hybrid_mode", {})
    
    def should_use_intelligent(self, user_input: str) -> bool:
        """判断是否应该使用智能模式"""
        if self.current_mode == ProcessingMode.INTELLIGENT:
            return True
        elif self.current_mode == ProcessingMode.TRADITIONAL:
            return False
        else:  # HYBRID mode
            hybrid_config = self.get_hybrid_config()
            
            # 在混合模式下，可以根据输入特征决定
            # 例如：复杂句子使用智能模式，简单命令使用传统模式
            
            # 简单判断逻辑示例
            simple_keywords = ["开灯", "关灯", "turn on", "turn off", "open", "close"]
            is_simple = any(keyword in user_input.lower() for keyword in simple_keywords)
            
            if hybrid_config.get("always_try_intelligent", True):
                return True  # 总是先尝试智能模式
            else:
                return not is_simple  # 复杂句子用智能模式
    
    def update_config(self, config_updates: Dict):
        """更新配置"""
        for key, value in config_updates.items():
            if key in self.config:
                if isinstance(self.config[key], dict) and isinstance(value, dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value
        
        self.save_config()

# 全局配置实例
processing_config = ProcessingConfig()

# API端点处理函数
async def switch_processing_mode(mode: str) -> Dict:
    """切换处理模式的API处理函数"""
    try:
        # 验证模式
        if mode not in ["intelligent", "traditional", "hybrid"]:
            return {
                "status": "error",
                "message": f"Invalid mode: {mode}. Must be one of: intelligent, traditional, hybrid"
            }
        
        # 设置新模式
        new_mode = ProcessingMode(mode)
        processing_config.set_mode(new_mode)
        
        return {
            "status": "success",
            "mode": mode,
            "message": f"Processing mode switched to: {mode}",
            "config": processing_config.config
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

async def get_processing_status() -> Dict:
    """获取当前处理模式状态"""
    return {
        "current_mode": processing_config.get_mode().value,
        "config": processing_config.config,
        "available_modes": [mode.value for mode in ProcessingMode]
    }