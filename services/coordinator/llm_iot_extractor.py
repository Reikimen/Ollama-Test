# llm_iot_extractor.py
# Enhanced IoT command extraction with improved semantic understanding

import json
import logging
import requests
from typing import List, Dict, Any, Optional
import re

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMIoTExtractor:
    """Enhanced LLM-based IoT command extractor with universal command format"""
    
    # Universal Command Format Definition
    COMMAND_SCHEMA = {
        "device": str,      # Device type identifier
        "action": str,      # Action to perform
        "location": str,    # Target room/location
        "parameters": dict  # Optional parameters based on action
    }
    
    # Standardized device types
    DEVICE_TYPES = {
        "ceiling_light": ["ceiling light", "ceiling lights", "main light", "overhead light", "light", "lights"],
        "desk_lamp": ["desk lamp", "table lamp", "reading lamp", "lamp"],
        "ac": ["air conditioner", "air conditioning", "AC", "cooling", "heating"],
        "fan": ["fan", "ceiling fan", "room fan"],
        "exhaust_fan": ["exhaust fan", "ventilation fan", "bathroom fan", "kitchen fan"],
        "curtain": ["curtain", "curtains", "blinds", "shades", "window covering"]
    }
    
    # Standardized actions with parameter requirements
    ACTION_DEFINITIONS = {
        "on": {"parameters": []},
        "off": {"parameters": []},
        "toggle": {"parameters": []},
        "set_brightness": {"parameters": ["brightness"], "range": [0, 100]},
        "set_temperature": {"parameters": ["temperature"], "range": [16, 32]},
        "set_speed": {"parameters": ["speed"], "range": [1, 5]},
        "set_position": {"parameters": ["position"], "range": [0, 100]},
        "set_color_temp": {"parameters": ["color_temp"], "range": [2700, 6500]},
        "brighten": {"parameters": [], "implicit_brightness": "+20"},
        "dim": {"parameters": [], "implicit_brightness": "-20"}
    }
    
    # Room name standardization
    ROOM_MAPPINGS = {
        "living room": "living_room",
        "livingroom": "living_room",
        "lounge": "living_room",
        "bedroom": "bedroom",
        "bed room": "bedroom",
        "master bedroom": "bedroom",
        "kitchen": "kitchen",
        "cooking area": "kitchen",
        "study": "study",
        "office": "study",
        "study room": "study",
        "bathroom": "bathroom",
        "bath room": "bathroom",
        "restroom": "bathroom",
        "washroom": "bathroom",
        "all": "all",
        "everywhere": "all",
        "entire house": "all",
        "whole house": "all"
    }
    
    def __init__(self, ollama_endpoint: str, model_name: str, api_headers: dict = None):
        self.ollama_endpoint = ollama_endpoint
        self.model_name = model_name
        self.api_headers = api_headers or {}
        
    def extract_iot_commands_with_llm(self, text_input: str, location: str = "living_room") -> List[Dict[str, Any]]:
        """Extract IoT commands using enhanced LLM understanding"""
        
        # Build comprehensive extraction prompt
        extraction_prompt = self._build_extraction_prompt(text_input, location)
        
        try:
            # Get LLM response
            llm_response = self._query_llm(extraction_prompt)
            
            # Parse and validate commands
            commands = self._parse_llm_response(llm_response)
            
            # Post-process commands for consistency
            validated_commands = self._validate_and_normalize_commands(commands, text_input, location)
            
            if validated_commands:
                logger.info(f"Successfully extracted {len(validated_commands)} commands: {validated_commands}")
            
            return validated_commands
            
        except Exception as e:
            logger.error(f"Error in LLM IoT extraction: {str(e)}")
            return []
    
    def _build_extraction_prompt(self, text_input: str, default_location: str) -> str:
        """Build a comprehensive prompt for accurate command extraction"""
        
        prompt = f"""You are an IoT command parser. Extract ALL device control commands from the user's input.

USER INPUT: "{text_input}"
DEFAULT ROOM: {default_location}

INSTRUCTIONS:
1. Extract commands for ALL devices mentioned
2. Support compound commands (e.g., "turn on kitchen lights and bedroom fan")
3. If no room specified, use the default room
4. Recognize room names in various forms (living room = living_room)
5. Handle numeric values in any format (25°, 25 degrees, twenty-five)

DEVICE TYPES:
- ceiling_light (main lights, overhead lights)
- desk_lamp (table lamp, reading lamp)
- ac (air conditioner, AC, cooling)
- fan (ceiling fan, room fan)
- exhaust_fan (ventilation, bathroom/kitchen fan)
- curtain (blinds, shades)

STANDARD ACTIONS:
- on/off/toggle (basic control)
- set_brightness (0-100%)
- set_temperature (16-32°C)
- set_speed (1-5)
- set_position (0-100% for curtains)
- set_color_temp (2700-6500K)
- brighten/dim (increase/decrease by 20%)

OUTPUT FORMAT (JSON array only, no other text):
[
  {{
    "device": "device_type",
    "action": "action_name",
    "location": "room_name",
    "parameters": {{"param": value}}
  }}
]

EXAMPLES:
"turn on lights" → [{{"device": "ceiling_light", "action": "on", "location": "{default_location}", "parameters": {{}}}}]
"set bedroom AC to 25 degrees" → [{{"device": "ac", "action": "set_temperature", "location": "bedroom", "parameters": {{"temperature": 25}}}}]
"open kitchen curtains and turn on exhaust fan" → [
  {{"device": "curtain", "action": "set_position", "location": "kitchen", "parameters": {{"position": 100}}}},
  {{"device": "exhaust_fan", "action": "on", "location": "kitchen", "parameters": {{}}}}
]
"dim all lights" → [{{"device": "ceiling_light", "action": "dim", "location": "all", "parameters": {{}}}}]

Return ONLY the JSON array. Empty array [] if no commands found."""
        
        return prompt
    
    def _query_llm(self, prompt: str) -> str:
        """Query the LLM with the extraction prompt"""
        
        if self.api_headers.get("Authorization"):  # Remote API mode
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You are a precise IoT command parser. Output only valid JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # Lower temperature for more consistent parsing
                "max_tokens": 500,
                "stream": False
            }
            
            response = requests.post(
                self.ollama_endpoint,
                json=payload,
                headers=self.api_headers,
                timeout=20
            )
            
            if response.status_code == 200:
                response_json = response.json()
                return response_json["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return "[]"
                
        else:  # Local Ollama mode
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2,
                "options": {
                    "num_predict": 500
                }
            }
            
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                return response.json().get("response", "[]")
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return "[]"
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse and clean LLM response"""
        try:
            # Clean response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Remove any non-JSON content before/after array
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                response = response[start_idx:end_idx+1]
            
            # Parse JSON
            commands = json.loads(response)
            
            if isinstance(commands, list):
                return commands
            else:
                logger.error(f"LLM returned non-list: {type(commands)}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return []
    
    def _validate_and_normalize_commands(self, commands: List[Dict], 
                                        original_text: str, 
                                        default_location: str) -> List[Dict[str, Any]]:
        """Validate and normalize extracted commands"""
        
        validated_commands = []
        
        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
                
            # Extract and validate fields
            device = cmd.get("device", "").lower()
            action = cmd.get("action", "").lower()
            location = cmd.get("location", default_location).lower()
            parameters = cmd.get("parameters", {})
            
            # Skip if missing required fields
            if not device or not action:
                continue
            
            # Normalize device type
            normalized_device = self._normalize_device_type(device)
            if not normalized_device:
                continue
                
            # Normalize action
            normalized_action = self._normalize_action(action, normalized_device)
            if not normalized_action:
                continue
                
            # Normalize location
            normalized_location = self._normalize_location(location)
            
            # Validate and normalize parameters
            validated_params = self._validate_parameters(
                normalized_action, 
                parameters, 
                original_text
            )
            
            # Build validated command
            validated_cmd = {
                "device": normalized_device,
                "action": normalized_action,
                "location": normalized_location,
                "parameters": validated_params
            }
            
            validated_commands.append(validated_cmd)
        
        return validated_commands
    
    def _normalize_device_type(self, device: str) -> Optional[str]:
        """Normalize device type to standard format"""
        
        device = device.lower().strip()
        
        # Direct match
        if device in self.DEVICE_TYPES:
            return device
            
        # Check aliases
        for standard_device, aliases in self.DEVICE_TYPES.items():
            if device in [alias.lower() for alias in aliases]:
                return standard_device
                
        # Partial matching for common variations
        if "light" in device and "desk" not in device:
            return "ceiling_light"
        elif "lamp" in device:
            return "desk_lamp"
        elif "ac" in device or "air" in device:
            return "ac"
        elif "exhaust" in device or "ventilation" in device:
            return "exhaust_fan"
        elif "fan" in device and "exhaust" not in device:
            return "fan"
        elif "curtain" in device or "blind" in device:
            return "curtain"
            
        return None
    
    def _normalize_action(self, action: str, device: str) -> Optional[str]:
        """Normalize action to standard format"""
        
        action = action.lower().strip()
        
        # Direct match
        if action in self.ACTION_DEFINITIONS:
            return action
            
        # Common variations
        action_mappings = {
            "turn on": "on",
            "switch on": "on",
            "activate": "on",
            "turn off": "off",
            "switch off": "off",
            "deactivate": "off",
            "open": "on" if device != "curtain" else "set_position",
            "close": "off" if device != "curtain" else "set_position",
            "increase": "brighten" if device in ["ceiling_light", "desk_lamp"] else None,
            "decrease": "dim" if device in ["ceiling_light", "desk_lamp"] else None,
            "brighter": "brighten",
            "darker": "dim",
            "faster": "set_speed",
            "slower": "set_speed",
            "warmer": "set_temperature",
            "cooler": "set_temperature"
        }
        
        return action_mappings.get(action, action if action in self.ACTION_DEFINITIONS else None)
    
    def _normalize_location(self, location: str) -> str:
        """Normalize room/location names"""
        
        location = location.lower().strip()
        
        # Check direct mapping
        if location in self.ROOM_MAPPINGS:
            return self.ROOM_MAPPINGS[location]
            
        # Check if already in standard format
        if location in self.ROOM_MAPPINGS.values():
            return location
            
        # Default to original if no mapping found
        return location.replace(" ", "_")
    
    def _validate_parameters(self, action: str, parameters: Dict, original_text: str) -> Dict:
        """Validate and extract parameters based on action requirements"""
        
        action_def = self.ACTION_DEFINITIONS.get(action, {})
        required_params = action_def.get("parameters", [])
        validated_params = {}
        
        # Handle special cases
        if action == "set_position" and "curtain" in original_text.lower():
            # Special handling for curtain positions
            if "open" in original_text.lower() or "fully open" in original_text.lower():
                validated_params["position"] = 100
            elif "close" in original_text.lower() or "fully close" in original_text.lower():
                validated_params["position"] = 0
            elif "half" in original_text.lower() or "halfway" in original_text.lower():
                validated_params["position"] = 50
            elif "position" in parameters:
                validated_params["position"] = self._validate_range(
                    parameters["position"], 0, 100
                )
        
        # Process each required parameter
        for param in required_params:
            if param in parameters:
                value = parameters[param]
                
                # Validate based on parameter type
                if param == "brightness":
                    validated_params[param] = self._validate_range(value, 0, 100)
                elif param == "temperature":
                    validated_params[param] = self._validate_range(value, 16, 32)
                elif param == "speed":
                    validated_params[param] = self._validate_range(value, 1, 5)
                elif param == "position":
                    validated_params[param] = self._validate_range(value, 0, 100)
                elif param == "color_temp":
                    validated_params[param] = self._validate_range(value, 2700, 6500)
                else:
                    validated_params[param] = value
            else:
                # Try to extract from original text if not in parameters
                extracted_value = self._extract_parameter_from_text(param, original_text)
                if extracted_value is not None:
                    validated_params[param] = extracted_value
        
        return validated_params
    
    def _validate_range(self, value: Any, min_val: int, max_val: int) -> int:
        """Validate and clamp numeric values to acceptable range"""
        try:
            num_value = int(float(str(value)))
            return max(min_val, min(max_val, num_value))
        except (ValueError, TypeError):
            return min_val
    
    def _extract_parameter_from_text(self, param: str, text: str) -> Optional[int]:
        """Extract numeric parameters from original text"""
        
        text_lower = text.lower()
        
        if param == "temperature":
            # Look for temperature patterns
            temp_patterns = [
                r'(\d+)\s*(?:degree|°|celsius|c)',
                r'(?:to|at)\s*(\d+)',
                r'temperature\s*(?:to|at)?\s*(\d+)'
            ]
            
            for pattern in temp_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return self._validate_range(match.group(1), 16, 32)
                    
        elif param == "brightness":
            # Look for brightness patterns
            bright_patterns = [
                r'(\d+)\s*(?:%|percent)',
                r'brightness\s*(?:to|at)?\s*(\d+)'
            ]
            
            for pattern in bright_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return self._validate_range(match.group(1), 0, 100)
                    
        elif param == "speed":
            # Look for speed patterns
            speed_patterns = [
                r'speed\s*(\d+)',
                r'level\s*(\d+)',
                r'(?:to|at)\s*(\d+)'
            ]
            
            for pattern in speed_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return self._validate_range(match.group(1), 1, 5)
        
        return None

# Backward compatibility functions
def create_llm_extractor(ollama_endpoint: str, model_name: str, api_headers: dict = None):
    """Create LLM extractor instance"""
    return LLMIoTExtractor(ollama_endpoint, model_name, api_headers)

def extract_iot_commands_enhanced_llm(text_input: str, location: str, 
                                     ollama_endpoint: str, model_name: str, 
                                     api_headers: dict = None) -> List[Dict[str, Any]]:
    """Backward compatible function signature"""
    extractor = LLMIoTExtractor(ollama_endpoint, model_name, api_headers)
    return extractor.extract_iot_commands_with_llm(text_input, location)