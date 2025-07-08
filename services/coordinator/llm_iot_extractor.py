# llm_iot_extractor.py
# 最小化改动方案：使用LLM推理能力替代关键词匹配

import json
import logging
import requests
from typing import List, Dict, Any

# 配置logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMIoTExtractor:
    """使用LLM进行IoT命令提取的增强模块"""
    
    def __init__(self, ollama_endpoint: str, model_name: str, api_headers: dict = None):
        self.ollama_endpoint = ollama_endpoint
        self.model_name = model_name
        self.api_headers = api_headers or {}
        
    def extract_iot_commands_with_llm(self, text_input: str, location: str = "living_room") -> List[Dict[str, Any]]:
        """使用LLM推理能力提取IoT命令"""
        
        # 构建专门用于IoT命令提取的prompt（简化版本，减少token使用）
        extraction_prompt = f"""Extract IoT device commands from: "{text_input}"
Default room: {location}

Output JSON array of commands:
[{{"device": "type", "action": "name", "location": "room", "parameters": {{}}}}]

Device types: ceiling_light, desk_lamp, ac, fan, curtain, exhaust_fan
Actions: on, off, set_temperature, set_brightness, set_position, set_speed

Examples:
"turn on lights" → [{{"device": "ceiling_light", "action": "on", "location": "{location}"}}]
"set AC to 25" → [{{"device": "ac", "action": "set_temperature", "location": "{location}", "parameters": {{"temperature": 25}}}}]
"open bedroom curtains" → [{{"device": "curtain", "action": "on", "location": "bedroom"}}]

Return only JSON array, empty [] if no commands found."""

        try:
            # 根据API模式构建请求
            if self.api_headers.get("Authorization"):  # Remote API mode
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "You are an IoT command parser. Output only valid JSON arrays."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300,  # 减少token限制
                    "stream": False
                }
                
                logger.debug(f"Sending request to {self.ollama_endpoint}")
                response = requests.post(
                    self.ollama_endpoint,
                    json=payload,
                    headers=self.api_headers,
                    timeout=15  # 增加超时时间
                )
                
                if response.status_code == 200:
                    response_json = response.json()
                    llm_response = response_json["choices"][0]["message"]["content"]
                    logger.debug(f"LLM response: {llm_response}")
                else:
                    logger.error(f"LLM API error: {response.status_code} - {response.text}")
                    return []
                    
            else:  # Local Ollama mode
                payload = {
                    "model": self.model_name,
                    "prompt": extraction_prompt,
                    "stream": False,
                    "temperature": 0.3,
                    "options": {
                        "num_predict": 300  # 限制输出长度
                    }
                }
                response = requests.post(
                    f"{self.ollama_endpoint}/api/generate",
                    json=payload,
                    timeout=15
                )
                if response.status_code == 200:
                    llm_response = response.json().get("response", "[]")
                else:
                    logger.error(f"Ollama error: {response.status_code}")
                    return []
            
            # 解析LLM响应
            commands = self._parse_llm_response(llm_response)
            if commands:
                logger.info(f"Successfully extracted {len(commands)} commands: {commands}")
            return commands
            
        except requests.exceptions.Timeout:
            logger.error("LLM request timed out")
            return []
        except Exception as e:
            logger.error(f"Error in LLM IoT extraction: {str(e)}")
            return []
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """解析LLM响应并验证命令格式"""
        try:
            # 提取JSON部分（处理可能的额外文本）
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # 解析JSON
            commands = json.loads(response)
            
            # 验证命令格式
            validated_commands = []
            for cmd in commands:
                if isinstance(cmd, dict) and "device" in cmd and "action" in cmd:
                    # 确保必需字段存在
                    validated_cmd = {
                        "device": cmd.get("device"),
                        "action": cmd.get("action"),
                        "location": cmd.get("location", "living_room"),
                        "parameters": cmd.get("parameters", {})
                    }
                    validated_commands.append(validated_cmd)
            
            return validated_commands
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return []

# 向后兼容的包装函数
def create_llm_extractor(ollama_endpoint: str, model_name: str, api_headers: dict = None):
    """创建LLM提取器实例"""
    return LLMIoTExtractor(ollama_endpoint, model_name, api_headers)

# 替代原有的extract_iot_commands_enhanced函数
def extract_iot_commands_enhanced_llm(text_input: str, location: str, 
                                     ollama_endpoint: str, model_name: str, 
                                     api_headers: dict = None) -> List[Dict[str, Any]]:
    """向后兼容的函数签名"""
    extractor = LLMIoTExtractor(ollama_endpoint, model_name, api_headers)
    return extractor.extract_iot_commands_with_llm(text_input, location)