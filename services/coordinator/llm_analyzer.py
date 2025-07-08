"""
LLM-based Intent Analysis Module
智能意图分析模块 - 使用LLM理解用户意图并生成结构化控制命令
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    """LLM智能分析器"""
    
    def __init__(self, ollama_host: str, ollama_port: str, model_name: str):
        self.ollama_url = f"http://{ollama_host}:{ollama_port}/api/generate"
        self.model_name = model_name
        
    async def analyze_intent(self, 
                           user_input: str, 
                           environmental_data: Dict,
                           device_states: Dict,
                           user_context: Optional[Dict] = None) -> Dict:
        """
        使用LLM分析用户意图并生成结构化命令
        
        Args:
            user_input: 用户输入的自然语言
            environmental_data: 当前环境数据（温度、湿度等）
            device_states: 当前设备状态
            user_context: 用户上下文信息
            
        Returns:
            包含意图分析结果和设备控制命令的字典
        """
        
        # 构建智能分析提示词
        analysis_prompt = self._build_analysis_prompt(
            user_input, 
            environmental_data, 
            device_states, 
            user_context
        )
        
        try:
            # 调用LLM进行智能分析
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": analysis_prompt,
                    "stream": False,
                    "format": "json"  # 要求JSON格式输出
                },
                timeout=30
            )
            
            if response.status_code == 200:
                llm_response = response.json()
                analysis_result = json.loads(llm_response.get("response", "{}"))
                
                # 验证和规范化输出
                return self._normalize_analysis_result(analysis_result)
            else:
                logger.error(f"LLM request failed: {response.status_code}")
                return self._get_fallback_result(user_input)
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            return self._get_fallback_result(user_input)
    
    def _build_analysis_prompt(self, 
                              user_input: str,
                              environmental_data: Dict,
                              device_states: Dict,
                              user_context: Optional[Dict]) -> str:
        """构建智能分析提示词"""
        
        prompt = f"""You are an intelligent home assistant analyzer. Analyze the user's intent and generate structured control commands.

Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== ENVIRONMENTAL DATA ===
{json.dumps(environmental_data, indent=2)}

=== DEVICE STATES ===
{json.dumps(device_states, indent=2)}

=== USER CONTEXT ===
{json.dumps(user_context or {}, indent=2)}

=== USER INPUT ===
"{user_input}"

=== TASK ===
Analyze the user's intent and generate a JSON response with the following structure:

{{
    "intent": {{
        "primary_intent": "control/query/scene/conversation",
        "confidence": 0.0-1.0,
        "detected_entities": {{
            "devices": [],
            "locations": [],
            "actions": [],
            "values": {{}}
        }}
    }},
    "commands": [
        {{
            "device": "device_type",
            "action": "action_type",
            "location": "room_name",
            "parameters": {{
                "value": "specific_value"
            }},
            "reason": "why this command"
        }}
    ],
    "context_awareness": {{
        "environmental_factors": [],
        "user_preferences": [],
        "time_based_suggestions": []
    }},
    "natural_response": "Natural language response to user",
    "follow_up_suggestions": []
}}

=== IMPORTANT RULES ===
1. Understand implicit requests (e.g., "我想睡觉了" → turn off lights, close curtains, set AC to sleep mode)
2. Consider environmental context (e.g., if temperature > 26°C and user mentions hot → turn on AC)
3. Handle complex conditions (e.g., "如果温度超过26度就开空调")
4. Support multi-device commands in single request
5. Infer location from context when not specified
6. Consider time of day for appropriate actions
7. Recognize both English and Chinese inputs

Valid device types: light, ac, fan, curtain, exhaust_fan
Valid locations: living_room, bedroom, kitchen, study, bathroom
Valid actions vary by device type

Generate the JSON response:"""
        
        return prompt
    
    def _normalize_analysis_result(self, result: Dict) -> Dict:
        """规范化和验证LLM输出"""
        
        # 确保所有必需字段存在
        normalized = {
            "intent": result.get("intent", {
                "primary_intent": "unknown",
                "confidence": 0.5,
                "detected_entities": {}
            }),
            "commands": [],
            "context_awareness": result.get("context_awareness", {}),
            "natural_response": result.get("natural_response", "我正在处理您的请求"),
            "follow_up_suggestions": result.get("follow_up_suggestions", [])
        }
        
        # 验证和规范化命令
        for cmd in result.get("commands", []):
            if self._validate_command(cmd):
                normalized["commands"].append(cmd)
        
        return normalized
    
    def _validate_command(self, command: Dict) -> bool:
        """验证命令格式是否正确"""
        required_fields = ["device", "action", "location"]
        return all(field in command for field in required_fields)
    
    def _get_fallback_result(self, user_input: str) -> Dict:
        """当LLM分析失败时的降级处理"""
        return {
            "intent": {
                "primary_intent": "unknown",
                "confidence": 0.0,
                "detected_entities": {}
            },
            "commands": [],
            "context_awareness": {},
            "natural_response": "抱歉，我暂时无法理解您的请求。请稍后再试。",
            "follow_up_suggestions": ["请尝试更明确地说明您的需求"]
        }

class IntentProcessor:
    """意图处理器 - 处理LLM分析结果"""
    
    def __init__(self, iot_service_url: str):
        self.iot_service_url = iot_service_url
        
    async def process_intent(self, analysis_result: Dict) -> Dict:
        """处理分析结果并执行相应动作"""
        
        results = {
            "executed_commands": [],
            "failed_commands": [],
            "query_results": None
        }
        
        # 根据主要意图类型处理
        primary_intent = analysis_result["intent"]["primary_intent"]
        
        if primary_intent == "control":
            # 执行设备控制命令
            results["executed_commands"] = await self._execute_commands(
                analysis_result["commands"]
            )
            
        elif primary_intent == "query":
            # 处理查询请求
            results["query_results"] = await self._handle_query(
                analysis_result["intent"]["detected_entities"]
            )
            
        elif primary_intent == "scene":
            # 执行场景模式
            scene_commands = self._expand_scene_commands(
                analysis_result["intent"]["detected_entities"]
            )
            results["executed_commands"] = await self._execute_commands(
                scene_commands
            )
            
        return results
    
    async def _execute_commands(self, commands: List[Dict]) -> List[Dict]:
        """执行设备控制命令"""
        executed = []
        
        for cmd in commands:
            try:
                response = requests.post(
                    f"{self.iot_service_url}/control",
                    json={"commands": [cmd]},
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    executed.append({
                        "command": cmd,
                        "status": "success",
                        "result": result
                    })
                else:
                    executed.append({
                        "command": cmd,
                        "status": "failed",
                        "error": f"IoT service error: {response.status_code}"
                    })
                    
            except Exception as e:
                executed.append({
                    "command": cmd,
                    "status": "failed",
                    "error": str(e)
                })
                
        return executed
    
    async def _handle_query(self, entities: Dict) -> Dict:
        """处理查询请求"""
        # 根据实体信息构建查询
        query_type = entities.get("query_type", "status")
        locations = entities.get("locations", ["all"])
        
        query_results = {}
        
        for location in locations:
            try:
                # 查询设备状态
                if query_type in ["status", "device"]:
                    response = requests.get(
                        f"{self.iot_service_url}/room/{location}/status",
                        timeout=5
                    )
                    if response.status_code == 200:
                        query_results[location] = response.json()
                        
                # 查询传感器数据
                elif query_type == "sensor":
                    response = requests.get(
                        f"{self.iot_service_url}/sensors/{location}",
                        timeout=5
                    )
                    if response.status_code == 200:
                        query_results[location] = response.json()
                        
            except Exception as e:
                query_results[location] = {"error": str(e)}
                
        return query_results
    
    def _expand_scene_commands(self, entities: Dict) -> List[Dict]:
        """展开场景模式为具体命令"""
        scene_name = entities.get("scene", "").lower()
        
        # 场景模式定义
        scene_definitions = {
            "sleep": [
                {"device": "light", "action": "off", "location": "all"},
                {"device": "curtain", "action": "close", "location": "bedroom"},
                {"device": "ac", "action": "on", "location": "bedroom", 
                 "parameters": {"temperature": 26, "mode": "sleep"}}
            ],
            "movie": [
                {"device": "light", "action": "dim", "location": "living_room",
                 "parameters": {"brightness": 20}},
                {"device": "curtain", "action": "close", "location": "living_room"},
                {"device": "ac", "action": "on", "location": "living_room",
                 "parameters": {"temperature": 24}}
            ],
            "work": [
                {"device": "light", "action": "on", "location": "study",
                 "parameters": {"brightness": 100, "color_temp": "cool"}},
                {"device": "curtain", "action": "open", "location": "study"},
                {"device": "fan", "action": "on", "location": "study",
                 "parameters": {"speed": "medium"}}
            ]
        }
        
        return scene_definitions.get(scene_name, [])