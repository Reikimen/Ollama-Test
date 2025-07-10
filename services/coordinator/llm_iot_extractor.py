import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class LLMIoTExtractor:
    """Enhanced LLM-based IoT command extractor with comprehensive prompt engineering"""
    
    def __init__(self, ollama_endpoint: str, model_name: str, api_headers: dict = None):
        self.ollama_endpoint = ollama_endpoint
        self.model_name = model_name
        self.api_headers = api_headers or {}
        
    def extract_iot_commands_with_llm(self, text_input: str, location: str = "living_room") -> List[Dict[str, Any]]:
        """Extract IoT commands using enhanced LLM understanding"""
        
        # Quick check for non-IoT queries
        lower_text = text_input.lower()
        excluded_patterns = [
            "who created", "who made", "who are the creators",
            "better than alexa", "smarter than google", "vs siri",
            "how do you work", "how does", "how do the", "why can you",
            "how the system", "how this work", "how it work",
            "without internet", "your advantage", "architecture",
            "hello", "hi", "good morning", "good night",
            "weather", "time", "date", "news",
            "thank you", "thanks", "good job", "that's wrong",
            "what is", "what are", "explain", "tell me about"
        ]
        
        if any(pattern in lower_text for pattern in excluded_patterns):
            logger.info(f"Detected non-IoT query, skipping extraction: {text_input[:50]}...")
            return []
        
        # Build comprehensive extraction prompt
        extraction_prompt = self._build_extraction_prompt(text_input, location)
        
        try:
            # Get LLM response
            llm_response = self._query_llm(extraction_prompt)
            
            # Parse and validate commands
            commands = self._parse_llm_response(llm_response)
            
            # Additional safety check: if the input looks like a question about the system,
            # but LLM still extracted commands, reject them
            if commands and self._is_system_question(text_input):
                logger.warning(f"LLM extracted commands from apparent system question, rejecting: {text_input}")
                return []
            
            # Post-process commands for consistency
            validated_commands = self._validate_and_normalize_commands(commands, text_input, location)
            
            if validated_commands:
                logger.info(f"Successfully extracted {len(validated_commands)} commands: {validated_commands}")
            
            return validated_commands
            
        except Exception as e:
            logger.error(f"Error in LLM IoT extraction: {str(e)}")
            return []
    
    def _is_system_question(self, text: str) -> bool:
        """Check if the text is likely a question about the system rather than a command"""
        lower_text = text.lower().strip()
        
        # Check for question patterns about the system
        system_question_patterns = [
            r"^(how|what|why|who|when|where)\s+(do|does|is|are|can|could)",
            r"(explain|tell me|describe)\s+(how|what|about)",
            r"(work|function|operate)s?\?",
            r"(system|this|project)\s+(work|function)",
            r"(creator|created|made|built)\s+(this|the system)",
            r"(better|different|compare|versus)\s+(than|to|with)",
        ]
        
        for pattern in system_question_patterns:
            if re.search(pattern, lower_text):
                return True
        
        return False
    
    def _build_extraction_prompt(self, text_input: str, default_location: str) -> str:
        """Build a comprehensive prompt for accurate command extraction"""
        
        prompt = f"""You are an IoT command parser. Extract ALL device control commands from the user's input.

USER INPUT: "{text_input}"
DEFAULT ROOM: {default_location}

CRITICAL INSTRUCTIONS:
1. Be VERY tolerant of typos and misspellings (e.g., "urn" → "turn", "oof" → "off")
2. Handle polite/conversational language (e.g., "Could you please", "I'd like", "Can you")
3. Understand context words: "in here" = current room, "everywhere" = all rooms
4. Extract commands even from explanatory sentences
5. Support various numeric formats and descriptive values

IMPORTANT: DO NOT extract commands from these types of inputs:
- Questions about the system: "who created this", "who made this project", "who are the creators"
- System comparisons: "what makes you better than Alexa", "smarter than Google", "vs Siri"
- How it works: "how do you work", "how does the system work", "how do the system works", "why can you understand", "how does this work", "explain how"
- Technical questions: "can you work without internet", "what's your advantage", "architecture"
- General conversation: greetings, weather, news, time, general questions
- Feedback: "good job", "that's wrong", "thank you"
- Explanations: "what is", "tell me about", "explain"

CRITICAL: If the user is asking ABOUT the system rather than giving a command TO control devices, return an empty array [].

DEVICE MAPPING (recognize ALL variations):
- ceiling_light: lights, light, lamp, lighting, main lights, overhead lights, room lights
- desk_lamp: desk light, table lamp, reading lamp, side lamp, work lamp
- fan: ceiling fan, room fan, fan, cooling fan, ventilation
- exhaust_fan: exhaust, ventilation fan, bathroom fan, kitchen fan, vent
- ac: air conditioner, AC, aircon, cooling, air conditioning
- curtain: curtains, blinds, shades, window covering

ROOM MAPPING (handle variations):
- living_room: living room, lounge, main room, front room, sitting room
- bedroom: bed room, sleeping room, master bedroom
- kitchen: cooking area, kitchen area
- study: office, study room, work room, workspace
- bathroom: bath room, restroom, washroom, toilet
- Special: "here" = {default_location}, "everywhere"/"all"/"whole home"/"house" = all rooms

ACTION MAPPING (with ALL variations):
- on: turn on, switch on, enable, activate, start, power on, put on
- off: turn off, switch off, disable, deactivate, stop, power off, shut off
- set_brightness: dim, brighten, set brightness, adjust brightness, % brightness, percent
- set_temperature: set temp, temperature, degrees, celsius
- set_speed: speed, fan speed, level, fast, slow, medium, maximum, minimum
- set_position: open, close, position
- brighten: brighter, increase brightness, more light, too dark
- dim: dimmer, decrease brightness, less light, too bright, lower

NUMERIC VALUE PATTERNS:
- Brightness: X%, X percent, half (50%), quarter (25%), full (100%), maximum (100%), minimum (10%)
- Speed: 1-5, slow (1), medium (3), fast (4), maximum/max (5), minimum/min (1)
- Temperature: X degrees, X°, X celsius, just X as number
- Position: X%, fully open (100%), fully closed (0%), half/halfway (50%)

COMPREHENSIVE EXAMPLES:

"Could you please turn on the lights in here?" → 
[{{"device": "ceiling_light", "action": "on", "location": "{default_location}", "parameters": {{}}}}]

"I need the living room fan on, it's getting warm." → 
[{{"device": "fan", "action": "on", "location": "living_room", "parameters": {{}}}}]

"Turn oof the living room lights" (typo: oof) → 
[{{"device": "ceiling_light", "action": "off", "location": "living_room", "parameters": {{}}}}]

"urn on the living room lights" (typo: urn) → 
[{{"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {{}}}}]

"Can you dim the bedroom lights a bit? They're too bright." → 
[{{"device": "ceiling_light", "action": "dim", "location": "bedroom", "parameters": {{}}}}]

"Please turn off all the lights in the house." → 
[
  {{"device": "ceiling_light", "action": "off", "location": "living_room", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "off", "location": "bedroom", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "off", "location": "bedroom", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "off", "location": "kitchen", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "off", "location": "study", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "off", "location": "study", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "off", "location": "bathroom", "parameters": {{}}}}
]

"Set the kitchen fan to speed 3, there's a lot of smoke." → 
[{{"device": "exhaust_fan", "action": "set_speed", "location": "kitchen", "parameters": {{"speed": 3}}}}]

"The study is too dark, can you make the lights brighter?" → 
[{{"device": "ceiling_light", "action": "brighten", "location": "study", "parameters": {{}}}}]

"Turn on the bathroom exhaust fan, it's getting steamy." → 
[{{"device": "exhaust_fan", "action": "on", "location": "bathroom", "parameters": {{}}}}]

"I'd like the bedroom lights at about 40 percent brightness." → 
[{{"device": "ceiling_light", "action": "set_brightness", "location": "bedroom", "parameters": {{"brightness": 40}}}}]

"It's getting cool now, turn off all the fans please." → 
[
  {{"device": "fan", "action": "off", "location": "living_room", "parameters": {{}}}},
  {{"device": "fan", "action": "off", "location": "bedroom", "parameters": {{}}}},
  {{"device": "fan", "action": "off", "location": "study", "parameters": {{}}}}
]

"Can you put the fan on maximum speed? It's really hot." → 
[{{"device": "fan", "action": "set_speed", "location": "{default_location}", "parameters": {{"speed": 5}}}}]

"I need lights on everywhere, I'm looking for something." → 
[
  {{"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bathroom", "parameters": {{}}}}
]

"Please turn on both the lights and fan in the living room." → 
[
  {{"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {{}}}},
  {{"device": "fan", "action": "on", "location": "living_room", "parameters": {{}}}}
]

"That's too bright, can you set it to half brightness?" → 
[{{"device": "ceiling_light", "action": "set_brightness", "location": "{default_location}", "parameters": {{"brightness": 50}}}}]

"We're done cooking, turn off the kitchen lights." → 
[{{"device": "ceiling_light", "action": "off", "location": "kitchen", "parameters": {{}}}}]

"Put the bedroom fan on slow speed for sleeping." → 
[{{"device": "fan", "action": "set_speed", "location": "bedroom", "parameters": {{"speed": 1}}}}]

"Turn on all lights" (no location specified) → 
[
  {{"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bathroom", "parameters": {{}}}}
]

"Lights and fan off" (minimal input) → 
[
  {{"device": "ceiling_light", "action": "off", "location": "{default_location}", "parameters": {{}}}},
  {{"device": "fan", "action": "off", "location": "{default_location}", "parameters": {{}}}}
]

"Make it brighter here" → 
[{{"device": "ceiling_light", "action": "brighten", "location": "{default_location}", "parameters": {{}}}}]

"Too hot, fan please" → 
[{{"device": "fan", "action": "on", "location": "{default_location}", "parameters": {{}}}}]

"Lights everywhere please" → 
[
  {{"device": "ceiling_light", "action": "on", "location": "living_room", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "bedroom", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "kitchen", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "desk_lamp", "action": "on", "location": "study", "parameters": {{}}}},
  {{"device": "ceiling_light", "action": "on", "location": "bathroom", "parameters": {{}}}}
]

"Hello, how are you?" → []
"What's the weather?" → []
"Thank you!" → []
"Who created this system?" → []
"Are you better than Alexa?" → []
"How does this work?" → []
"How do the system works?" → []
"Can you explain how this works?" → []
"What makes you different from Siri?" → []
"Tell me about yourself" → []

IMPORTANT REMINDER: Only extract IoT device control commands. Questions ABOUT the system should return [].

OUTPUT FORMAT (JSON array only, no explanations):
Return ONLY a JSON array. Empty array [] if no IoT commands found."""
        
        return prompt
    
    def _query_llm(self, prompt: str) -> str:
        """Query the LLM with the extraction prompt"""
        
        if self.api_headers.get("Authorization"):  # Remote API mode
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a precise IoT command parser. Output only valid JSON arrays. Be very tolerant of typos and conversational language. Do NOT extract commands from questions about the system, comparisons with other assistants, or general conversation. NEVER hallucinate or invent commands that are not explicitly stated in the user input. If the user is asking a question ABOUT the system rather than giving a command TO control devices, return an empty array []."
                    },
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
                logger.warning(f"LLM returned non-list: {type(commands)}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return []
    
    def _validate_and_normalize_commands(self, commands: List[Dict[str, Any]], 
                                       original_text: str, 
                                       default_location: str) -> List[Dict[str, Any]]:
        """Validate and normalize extracted commands"""
        
        valid_devices = {"ceiling_light", "desk_lamp", "fan", "exhaust_fan", "ac", "curtain"}
        valid_actions = {"on", "off", "toggle", "set_brightness", "set_temperature", 
                        "set_speed", "set_position", "set_color_temp", "brighten", "dim"}
        valid_locations = {"living_room", "bedroom", "kitchen", "study", "bathroom", "all"}
        
        normalized_commands = []
        
        for cmd in commands:
            try:
                # Validate required fields
                device = cmd.get("device", "").lower().strip()
                action = cmd.get("action", "").lower().strip()
                location = cmd.get("location", default_location).lower().strip()
                parameters = cmd.get("parameters", {})
                
                # Skip invalid commands
                if not device or not action:
                    continue
                
                # Normalize device names
                if device not in valid_devices:
                    logger.warning(f"Unknown device: {device}")
                    continue
                
                # Normalize actions
                if action not in valid_actions:
                    logger.warning(f"Unknown action: {action}")
                    continue
                
                # Normalize locations
                if location not in valid_locations:
                    # Try to fix common variations
                    location = location.replace(" ", "_")
                    if location not in valid_locations:
                        location = default_location
                
                # Handle "all" location by expanding to all rooms
                if location == "all":
                    # Determine which rooms have this device
                    rooms_with_device = self._get_rooms_with_device(device)
                    for room in rooms_with_device:
                        normalized_commands.append({
                            "device": device,
                            "action": action,
                            "location": room,
                            "parameters": parameters.copy()
                        })
                else:
                    # Validate and normalize parameters
                    normalized_params = self._normalize_parameters(action, parameters, original_text)
                    
                    normalized_commands.append({
                        "device": device,
                        "action": action,
                        "location": location,
                        "parameters": normalized_params
                    })
                    
            except Exception as e:
                logger.error(f"Error normalizing command: {e}")
                continue
        
        return normalized_commands
    
    def _get_rooms_with_device(self, device: str) -> List[str]:
        """Get list of rooms that have a specific device type"""
        # This matches the actual device configuration from IoT service
        device_room_mapping = {
            "ceiling_light": ["living_room", "bedroom", "kitchen", "study", "bathroom"],
            "desk_lamp": ["bedroom", "study"],
            "fan": ["living_room", "bedroom", "study"],
            "exhaust_fan": ["kitchen", "bathroom"],
            "ac": ["living_room", "bedroom"],
            "curtain": ["living_room", "bedroom", "study"]
        }
        
        return device_room_mapping.get(device, ["living_room"])
    
    def _normalize_parameters(self, action: str, parameters: Dict[str, Any], 
                            original_text: str) -> Dict[str, Any]:
        """Normalize parameters based on action type"""
        
        normalized = {}
        
        if action == "set_brightness" and "brightness" in parameters:
            # Ensure brightness is between 0-100
            brightness = parameters["brightness"]
            if isinstance(brightness, (int, float)):
                normalized["brightness"] = max(0, min(100, int(brightness)))
                
        elif action == "set_temperature" and "temperature" in parameters:
            # Ensure temperature is between 16-32
            temp = parameters["temperature"]
            if isinstance(temp, (int, float)):
                normalized["temperature"] = max(16, min(32, int(temp)))
                
        elif action == "set_speed" and "speed" in parameters:
            # Ensure speed is between 1-5
            speed = parameters["speed"]
            if isinstance(speed, (int, float)):
                normalized["speed"] = max(1, min(5, int(speed)))
                
        elif action == "set_position" and "position" in parameters:
            # Ensure position is between 0-100
            position = parameters["position"]
            if isinstance(position, (int, float)):
                normalized["position"] = max(0, min(100, int(position)))
                
        elif action == "set_color_temp" and "color_temp" in parameters:
            # Ensure color temp is between 2700-6500
            color_temp = parameters["color_temp"]
            if isinstance(color_temp, (int, float)):
                normalized["color_temp"] = max(2700, min(6500, int(color_temp)))
        
        # For brighten/dim actions, no parameters needed
        elif action in ["brighten", "dim"]:
            normalized = {}
        
        # Try to extract missing parameters from original text if needed
        if not normalized and action in ["set_brightness", "set_temperature", "set_speed"]:
            extracted_value = self._extract_value_from_text(original_text, action.replace("set_", ""))
            if extracted_value is not None:
                param_name = action.replace("set_", "")
                normalized[param_name] = extracted_value
        
        return normalized
    
    def _extract_value_from_text(self, text: str, param_type: str) -> Optional[int]:
        """Extract numeric value from text for specific parameter type"""
        text_lower = text.lower()
        
        if param_type == "temperature":
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
                    
        elif param_type == "brightness":
            # Look for brightness patterns
            bright_patterns = [
                r'(\d+)\s*(?:%|percent)',
                r'brightness\s*(?:to|at)?\s*(\d+)'
            ]
            
            for pattern in bright_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return self._validate_range(match.group(1), 0, 100)
                    
        elif param_type == "speed":
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
    
    def _validate_range(self, value: str, min_val: int, max_val: int) -> int:
        """Validate and clamp numeric value to range"""
        try:
            num_value = int(value)
            return max(min_val, min(max_val, num_value))
        except ValueError:
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