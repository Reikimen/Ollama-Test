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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 环境变量配置
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
STT_HOST = os.getenv("STT_HOST", "stt-service")
STT_PORT = os.getenv("STT_PORT", "8000")
TTS_HOST = os.getenv("TTS_HOST", "tts-service")
TTS_PORT = os.getenv("TTS_PORT", "8001")
IOT_HOST = os.getenv("IOT_HOST", "iot-control")
IOT_PORT = os.getenv("IOT_PORT", "8002")

# 创建FastAPI应用
app = FastAPI(title="AI语音助手协调服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 连接的客户端
connected_clients = {}

class AudioRequest(BaseModel):
    audio_path: str

class TextRequest(BaseModel):
    text: str

@app.get("/")
async def root():
    return {"message": "AI语音助手协调服务运行中"}

@app.post("/process_audio")
async def process_audio(request: AudioRequest):
    """处理音频并返回AI响应"""
    try:
        # 1. 发送音频到STT服务
        audio_path = request.audio_path
        stt_url = f"http://{STT_HOST}:{STT_PORT}/transcribe"
        stt_response = requests.post(stt_url, json={"audio_path": audio_path})
        stt_response.raise_for_status()
        transcription = stt_response.json().get("text", "")
        
        if not transcription:
            return JSONResponse(
                status_code=400,
                content={"error": "无法识别音频内容"}
            )
        
        # 2. 发送文本到Ollama处理
        response = await process_text_with_llm(transcription)
        
        return response
    
    except Exception as e:
        logger.error(f"处理音频时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理请求时出错: {str(e)}"}
        )

@app.post("/process_text")
async def process_text(request: TextRequest):
    """处理文本输入并返回AI响应"""
    try:
        response = await process_text_with_llm(request.text)
        return response
    
    except Exception as e:
        logger.error(f"处理文本时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理请求时出错: {str(e)}"}
        )

async def process_text_with_llm(text_input):
    """将文本发送到LLM并处理响应"""
    # 1. 发送文本到Ollama
    ollama_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "prompt": add_system_instructions(text_input),
        "stream": False
    }
    
    ollama_response = requests.post(ollama_url, json=ollama_payload)
    ollama_response.raise_for_status()
    
    ai_text_response = ollama_response.json().get("response", "")
    
    # 2. 检查是否需要IoT控制
    iot_commands = extract_iot_commands(text_input, ai_text_response)
    
    if iot_commands:
        # 发送到IoT控制服务
        iot_url = f"http://{IOT_HOST}:{IOT_PORT}/control"
        iot_response = requests.post(iot_url, json={"commands": iot_commands})
        iot_result = iot_response.json() if iot_response.status_code == 200 else {"status": "error"}
    else:
        iot_result = {"status": "no_commands"}
    
    # 3. 确定表情动作
    expression = determine_expression(text_input, ai_text_response)
    
    # 4. 发送AI回复到TTS生成语音
    tts_url = f"http://{TTS_HOST}:{TTS_PORT}/synthesize"
    tts_response = requests.post(tts_url, json={"text": ai_text_response})
    tts_response.raise_for_status()
    
    audio_file_path = tts_response.json().get("audio_path", "")
    
    # 返回完整响应
    return {
        "input_text": text_input,
        "ai_response": ai_text_response,
        "audio_path": audio_file_path,
        "expression": expression,
        "iot_commands": iot_commands,
        "iot_result": iot_result
    }

def add_system_instructions(user_input):
    """添加系统指令到用户输入"""
    system_prompt = """你是一个友好的AI语音助手，能够回答问题并控制智能家居设备。如果用户请求控制设备，请在回复中明确说明你将执行的操作，例如"好的，我将打开（关闭）客厅的灯"。
    
    可控制的设备包括：
    - 灯光 (开/关/调亮/调暗)
    - 风扇 (开/关/调速)
    - 空调 (开/关/调温/模式)
    - 窗帘 (开/关)
    
    请保持简短友好的回复风格，并准确理解用户的控制意图。
    """
    return f"{system_prompt}\n\n用户: {user_input}\n助手:"

def extract_iot_commands(user_input, ai_response):
    """从用户输入和AI响应中提取IoT控制命令"""
    # 简单的关键词匹配，实际可使用更复杂的NLU
    commands = []
    
    # 检查关键词
    keywords = {
        "灯": "light",
        "风扇": "fan",
        "空调": "ac",
        "窗帘": "curtain"
    }
    
    actions = {
        "开": "on",
        "打开": "on",
        "关": "off",
        "关闭": "off",
        "调亮": "brighten",
        "调暗": "dim",
        "升温": "temp_up",
        "降温": "temp_down"
    }
    
    # 位置关键词
    locations = ["客厅", "卧室", "厨房", "书房"]
    
    for keyword, device in keywords.items():
        if keyword in user_input:
            # 确定位置
            location = "客厅"  # 默认位置
            for loc in locations:
                if loc in user_input:
                    location = loc
                    break
            
            # 确定动作
            action = "on"  # 默认动作
            for act_key, act_val in actions.items():
                if act_key in user_input:
                    action = act_val
                    break
            
            commands.append({
                "device": device,
                "action": action,
                "location": location
            })
    
    return commands

def determine_expression(user_input, ai_response):
    """根据对话内容决定表情动作"""
    # 简单的关键词匹配
    if any(word in user_input for word in ["谢谢", "感谢"]):
        return "smile"
    elif any(word in user_input for word in ["什么", "怎么", "为什么", "如何"]):
        return "thinking"
    elif any(word in ai_response for word in ["抱歉", "对不起"]):
        return "sad"
    elif any(word in user_input for word in ["惊讶", "哇", "厉害"]):
        return "surprised"
    else:
        return "neutral"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接处理"""
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
                    # 处理文本消息
                    response = await process_text_with_llm(message.get("text", ""))
                    await websocket.send_json(response)
                
                elif message_type == "audio_ready":
                    # 处理音频就绪通知
                    audio_path = message.get("path")
                    response = await process_audio(AudioRequest(audio_path=audio_path))
                    await websocket.send_json(response)
                
                else:
                    await websocket.send_json({"error": "未知消息类型"})
            
            except json.JSONDecodeError:
                await websocket.send_json({"error": "无效的JSON格式"})
    
    except WebSocketDisconnect:
        if client_id in connected_clients:
            del connected_clients[client_id]
    
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        if client_id in connected_clients:
            del connected_clients[client_id]

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)