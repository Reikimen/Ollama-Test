import os
import json
import logging
import asyncio
import aiohttp
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
from pydantic import BaseModel

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

# Connected clients
connected_clients = {}

class AudioRequest(BaseModel):
    audio_path: str

class TextRequest(BaseModel):
    text: str

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
        
        # 2. Send text to Ollama for processing
        response = await process_text_with_llm(transcription)
        
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
        response = await process_text_with_llm(request.text)
        return response
    
    except Exception as e:
        logger.error(f"Error processing text: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing request: {str(e)}"}
        )

async def process_text_with_llm(text_input):
    """Send text to LLM and process response"""
    # 1. Send text to Ollama
    ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "prompt": add_system_instructions(text_input),
        "stream": False
    }
    
    ollama_response = requests.post(ollama_url, json=ollama_payload)
    ollama_response.raise_for_status()
    
    ai_text_response = ollama_response.json().get("response", "")
    
    # 2. Check if IoT control is needed
    iot_commands = extract_iot_commands(text_input, ai_text_response)
    
    if iot_commands:
        # Send to IoT control service
        iot_url = f"http://{IOT_HOST}:{IOT_PORT}/control"
        iot_response = requests.post(iot_url, json={"commands": iot_commands})
        iot_result = iot_response.json() if iot_response.status_code == 200 else {"status": "error"}
    else:
        iot_result = {"status": "no_commands"}
    
    # 3. Determine expression/emotion
    expression = determine_expression(text_input, ai_text_response)
    
    # 4. Send AI reply to TTS to generate speech
    tts_url = f"http://{TTS_HOST}:{TTS_PORT}/synthesize"
    tts_response = requests.post(tts_url, json={"text": ai_text_response})
    tts_response.raise_for_status()
    
    audio_file_path = tts_response.json().get("audio_path", "")
    
    # Return complete response
    return {
        "input_text": text_input,
        "ai_response": ai_text_response,
        "audio_path": audio_file_path,
        "expression": expression,
        "iot_commands": iot_commands,
        "iot_result": iot_result
    }

def add_system_instructions(user_input):
    """Add system instructions to user input"""
    # First, get current device status
    try:
        iot_url = f"http://{IOT_HOST}:{IOT_PORT}/devices"
        iot_response = requests.get(iot_url)
        if iot_response.status_code == 200:
            device_states = iot_response.json().get("devices", {})
            # Convert device states to human readable format
            device_status_text = format_device_states(device_states)
        else:
            device_status_text = "Unable to retrieve current device status."
    except Exception as e:
        logger.error(f"Error getting device status: {str(e)}")
        device_status_text = "Unable to retrieve current device status due to an error."
    
    system_prompt = f"""You are a friendly AI voice assistant, capable of answering questions and controlling smart home devices. If a user requests to control a device, please clearly state the action you will perform in your response, for example, "Okay, I'll turn on/off the living room light."
    
    Current device status:
    {device_status_text}
    
    Controllable devices include:
    - Lights (on/off/brighten/dim)
    - Fans (on/off/speed)
    - Air conditioners (on/off/temperature/mode)
    - Curtains (open/close)
    
    Please maintain a brief, friendly response style and accurately understand the user's control intentions. When asked about device status, provide the current status from the information above.
    """
    return f"{system_prompt}\n\nUser: {user_input}\nAssistant:"

def format_device_states(device_states):
    """Format device states into human-readable text"""
    result = []
    
    # Process lights
    if "light" in device_states:
        for location, state in device_states["light"].items():
            status = "ON" if state.get("status") == "on" else "OFF"
            brightness = state.get("brightness", 0)
            result.append(f"- Light ({location}): {status}, Brightness: {brightness}%")
    
    # Process fans
    if "fan" in device_states:
        for location, state in device_states["fan"].items():
            status = "ON" if state.get("status") == "on" else "OFF"
            speed = state.get("speed", 0)
            result.append(f"- Fan ({location}): {status}, Speed: {speed}")
    
    # Process air conditioners
    if "ac" in device_states:
        for location, state in device_states["ac"].items():
            status = "ON" if state.get("status") == "on" else "OFF"
            temp = state.get("temperature", 0)
            mode = state.get("mode", "unknown")
            result.append(f"- AC ({location}): {status}, Temperature: {temp}°C, Mode: {mode}")
    
    # Process curtains
    if "curtain" in device_states:
        for location, state in device_states["curtain"].items():
            status = state.get("status", "unknown")
            result.append(f"- Curtain ({location}): {status}")
    
    return "\n".join(result)

def extract_iot_commands(user_input, ai_response):
    """Extract IoT control commands from user input and AI response"""
    # Simple keyword matching, can use more complex NLU in practice
    commands = []
    
    # Check keywords
    keywords = {
        "light": "light",
        "lights": "light",
        "lamp": "light",
        "fan": "fan",
        "air conditioner": "ac",
        "ac": "ac",
        "curtain": "curtain",
        "curtains": "curtain"
    }
    
    actions = {
        "on": "on",
        "turn on": "on",
        "off": "off",
        "turn off": "off",
        "brighten": "brighten",
        "dim": "dim",
        "increase temperature": "temp_up",
        "decrease temperature": "temp_down"
    }
    
    # Location keywords
    locations = ["living room", "bedroom", "kitchen", "study"]
    
    for keyword, device in keywords.items():
        if keyword in user_input.lower():
            # Determine location
            location = "living room"  # Default location
            for loc in locations:
                if loc in user_input.lower():
                    location = loc
                    break
            
            # Determine action
            action = "on"  # Default action
            for act_key, act_val in actions.items():
                if act_key in user_input.lower():
                    action = act_val
                    break
            
            commands.append({
                "device": device,
                "action": action,
                "location": location
            })
    
    return commands

def determine_expression(user_input, ai_response):
    """Determine expression/emotion based on conversation content"""
    # Simple keyword matching
    if any(word in user_input.lower() for word in ["thank", "thanks", "grateful"]):
        return "smile"
    elif any(word in user_input.lower() for word in ["what", "how", "why", "explain"]):
        return "thinking"
    elif any(word in ai_response.lower() for word in ["sorry", "apologize", "regret"]):
        return "sad"
    elif any(word in user_input.lower() for word in ["surprise", "wow", "amazing"]):
        return "surprised"
    else:
        return "neutral"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection handler"""
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
                    # Process text message
                    response = await process_text_with_llm(message.get("text", ""))
                    await websocket.send_json(response)
                
                elif message_type == "audio_ready":
                    # Process audio ready notification
                    audio_path = message.get("path")
                    response = await process_audio(AudioRequest(audio_path=audio_path))
                    await websocket.send_json(response)
                
                else:
                    await websocket.send_json({"error": "Unknown message type"})
            
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
    
    except WebSocketDisconnect:
        if client_id in connected_clients:
            del connected_clients[client_id]
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if client_id in connected_clients:
            del connected_clients[client_id]

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)