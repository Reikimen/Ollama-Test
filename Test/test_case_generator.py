#!/usr/bin/env python3
"""
Smart Home Intent Test Cases Generator
Generates categorized test cases for intent recognition accuracy testing
"""

import json
import random
from typing import List, Dict
import os
from datetime import datetime

class TestCaseGenerator:
    def __init__(self):
        # Define rooms
        self.rooms = ["living_room", "bedroom", "kitchen", "study", "bathroom"]
        
        # Define devices per room - 根据实际项目配置
        self.devices = {
            "living_room": ["ceiling_light", "ac", "fan", "curtain"],
            "bedroom": ["ceiling_light", "ac", "fan", "curtain"],
            "kitchen": ["ceiling_light", "exhaust_fan"],
            "study": ["ceiling_light", "desk_lamp", "ac", "curtain"],
            "bathroom": ["ceiling_light", "exhaust_fan"]
        }
        
        # Define possible actions per device
        self.device_actions = {
            "ceiling_light": ["on", "off", "dim", "brighten", "set"],
            "desk_lamp": ["on", "off", "dim", "brighten", "set"],
            "ac": ["on", "off", "set_temperature", "increase", "decrease"],
            "fan": ["on", "off", "increase", "decrease", "set"],
            "exhaust_fan": ["on", "off"],
            "curtain": ["open", "close", "set"]
        }
         
        self.room_display_names = {
            "living_room": "living room",
            "bedroom": "bedroom",
            "kitchen": "kitchen",
            "bathroom": "bathroom",
            "study": "study room",  # 关键修改
            "balcony": "balcony"
        }
            
        # Temperature settings for air conditioner
        self.temperatures = list(range(18, 31))
        
        # Brightness levels
        self.brightness_levels = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
    
    def get_room_display_name(self, room: str) -> str:
        """Return a user-friendly room display name."""
        return self.room_display_names.get(room, room.replace("_", " "))

    def format_command_with_room(self, template: str, room: str, **kwargs) -> str:
        """Format a command template using the room display name."""
        room_display = self.get_room_display_name(room)
        return template.format(room=room_display, **kwargs)
        
    def generate_simple_light_commands(self, count: int = 100) -> List[Dict]:
        """Generate simple light control commands"""
        test_cases = []
        templates = [
            "Turn {action} the {room} {device}",
            "Switch {action} the {device} in the {room}",
            "{action_verb} the {room} {device}",
            "Please {action_verb} the {device} in the {room}",
            "Can you {action_verb} the {room} {device}?",
            "I'd like to {action_verb} the {device} in the {room}",
            "{room} {device} {action}",
            "Make the {room} {device} {action}",
            "Set the {room} {device} {action}",
            "Could you please {action_verb} the {room} {device}?"
        ]
        
        for i in range(count):
            room = random.choice(self.rooms)
            devices = [d for d in self.devices[room] if "light" in d or "lamp" in d]
            if not devices:
                continue
                
            device = random.choice(devices)
            action = random.choice(["on", "off"])
            
            template = random.choice(templates)
            
            # Format the command
            if action == "on":
                action_verb = "turn on"
            else:
                action_verb = "turn off"
                
            room_name = self.get_room_display_name(room)
            device_name = device.replace("_", " ")
            
            command = template.format(
                action=action,
                action_verb=action_verb,
                room=room_name,
                device=device_name
            )
            
            test_cases.append({
                "id": f"simple_light_{i+1:03d}",
                "input": command,
                "expected_devices": [device],
                "expected_locations": [room],
                "expected_actions": [action],
                "category": "simple_light_control",
                "description": f"Simple {action} command for {device} in {room}"
            })
        
        return test_cases
    
    def generate_brightness_commands(self, count: int = 100) -> List[Dict]:
        """Generate brightness control commands"""
        test_cases = []
        templates = [
            "Dim the {room} {device}",
            "Brighten the {room} {device}",
            "Make the {room} {device} dimmer",
            "Make the {room} {device} brighter",
            "Increase the brightness of the {room} {device}",
            "Decrease the brightness of the {room} {device}",
            "Set the {room} {device} to {level} brightness",
            "Adjust the {room} {device} to {level}",
            "Turn the {room} {device} brightness to {level}",
            "Change the {room} {device} brightness to {level}"
        ]
        
        for i in range(count):
            room = random.choice(self.rooms)
            devices = [d for d in self.devices[room] if "light" in d or "lamp" in d]
            if not devices:
                continue
                
            device = random.choice(devices)
            template = random.choice(templates)
            
            # Determine action and parameters
            if "{level}" in template:
                level = random.choice(self.brightness_levels)
                action = "set_brightness"
                command = template.format(
                    room=self.get_room_display_name(room),
                    device=device.replace("_", " "),
                    level=level
                )
                parameters = {"brightness": level}
            else:
                if "dim" in template.lower() or "decrease" in template.lower():
                    action = "dim"
                else:
                    action = "brighten"
                command = template.format(
                    room=self.get_room_display_name(room),
                    device=device.replace("_", " ")
                )
                parameters = {}
            
            test_cases.append({
                "id": f"brightness_{i+1:03d}",
                "input": command,
                "expected_devices": [device],
                "expected_locations": [room],
                "expected_actions": [action],
                "expected_parameters": parameters,
                "category": "brightness_control",
                "description": f"Brightness control for {device} in {room}"
            })
        
        return test_cases
    
    # Temperature/scene/multi-device/contextual/complex generators removed per request.
    
    # multi-device generator removed per request.
    
    # scene generator removed per request.
    
    # contextual generator removed per request.
    
    def generate_non_control_commands(self, count: int = 100) -> List[Dict]:
        """Generate commands that should NOT trigger any device control (negative tests)."""
        test_cases = []

        templates = [
            # Questions about status
            "What's the temperature in the {room}?",
            "Is the {device} on?",
            "How bright is the {room} light?",
            "What's the current setting of the air conditioner?",
            "Are all the lights off?",
            "What's the status of the {device}?",
            "Tell me about the room conditions",
            "How many lights are on?",
            "What devices are currently active?",
            "Check the {device} status",

            # General questions
            "What's the weather like?",
            "What time is it?",
            "How are you?",
            "Tell me a joke",
            "What can you do?",
            "Hello there",
            "Good afternoon",
            "Thank you",
            "That's great",
            "I appreciate it",

            # Information requests
            "How does the air conditioner work?",
            "What's the best temperature for sleeping?",
            "Tell me about energy saving",
            "What's the recommended humidity level?",
            "How much electricity does the {device} use?",
            "When should I change the air filter?",
            "What's the warranty on the {device}?",
            "How do I clean the {device}?",
            "What's the model number of the {device}?",
            "Who installed the {device}?",

            # Comments without commands
            "The room looks nice",
            "I like this temperature",
            "The lighting is perfect",
            "Everything is fine",
            "No changes needed",
            "Keep everything as is",
            "Don't change anything",
            "I'm comfortable",
            "The room feels good",
            "Nice atmosphere"
        ]

        for i in range(count):
            template = random.choice(templates)

            # Fill in placeholders if needed
            if "{room}" in template:
                room = random.choice(self.rooms)
                command = template.format(room=self.get_room_display_name(room))
            elif "{device}" in template:
                room = random.choice(self.rooms)
                device = random.choice(self.devices[room])
                command = template.format(device=device.replace("_", " "))
            else:
                command = template

            test_cases.append({
                "id": f"non_control_{i+1:03d}",
                "input": command,
                "expected_devices": [],
                "expected_locations": [],
                "expected_actions": [],
                "category": "non_control_commands",
                "description": "Should not trigger any device control"
            })

        return test_cases
    
    # complex conditional generator removed per request.

def generate_all_test_cases():
    """Generate all categories of test cases"""
    generator = TestCaseGenerator()
    
    print("Generating test cases...")
    
    # Generate all categories
    all_test_cases = {
        "simple_light_control": generator.generate_simple_light_commands(100),
        "brightness_control": generator.generate_brightness_commands(100),
        "non_control_commands": generator.generate_non_control_commands(100)
    }
    
    # Create output directory
    output_dir = "test_cases"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save each category separately
    for category, test_cases in all_test_cases.items():
        filename = f"{output_dir}/{category}_test_cases.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, indent=2)
        print(f"✓ Generated {len(test_cases)} test cases for {category}")
    
    # Save all test cases combined
    all_combined = []
    for category, test_cases in all_test_cases.items():
        all_combined.extend(test_cases)
    
    with open(f"{output_dir}/all_test_cases_combined.json", 'w', encoding='utf-8') as f:
        json.dump(all_combined, f, indent=2)
    
    print(f"\n✓ Total test cases generated: {len(all_combined)}")
    print(f"✓ Test cases saved to: {output_dir}/")
    
    # Generate summary report
    summary = {
        "generation_date": datetime.now().isoformat(),
        "total_test_cases": len(all_combined),
        "categories": {
            category: {
                "count": len(test_cases),
                "description": get_category_description(category)
            }
            for category, test_cases in all_test_cases.items()
        }
    }
    
    with open(f"{output_dir}/test_cases_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    return all_test_cases

def get_category_description(category: str) -> str:
    """Get description for each category"""
    descriptions = {
        "simple_light_control": "Basic on/off commands for lights and lamps",
        "brightness_control": "Commands for dimming, brightening, and setting specific brightness levels",
        # Removed categories: temperature_control, multi_device_control, scene_control, contextual_control
        "non_control_commands": "Commands that should NOT trigger any device control (negative test cases)",
        # complex_conditional removed
    }
    return descriptions.get(category, "")

if __name__ == "__main__":
    generate_all_test_cases()