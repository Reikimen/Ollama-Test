import os
import logging
import asyncio
import socket
import time
import wave
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import uvicorn
from pydantic import BaseModel
import whisper

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 环境变量
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
UDP_PORT = int(os.getenv("UDP_PORT", 8000))
SAMPLE_RATE = 16000  # ESP32录音采样率

# 创建音频目录
os.makedirs(AUDIO_DIR, exist_ok=True)

# 初始化Whisper模型
logger.info(f"加载Whisper模型: {WHISPER_MODEL}")
model = whisper.load_model(WHISPER_MODEL)
logger.info("Whisper模型加载完成")

# 创建FastAPI应用
app = FastAPI(title="语音识别服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AudioRequest(BaseModel):
    audio_path: str

@app.get("/")
async def root():
    return {"message": "语音识别服务运行中"}

@app.post("/transcribe")
async def transcribe_audio(request: AudioRequest):
    """转录指定路径的音频文件"""
    try:
        audio_path = request.audio_path
        
        if not os.path.exists(audio_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"音频文件不存在: {audio_path}"}
            )
        
        # 使用Whisper转录
        logger.info(f"开始转录: {audio_path}")
        result = model.transcribe(audio_path)
        transcription = result["text"]
        logger.info(f"转录完成: {transcription}")
        
        return {"text": transcription}
    
    except Exception as e:
        logger.error(f"转录出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"转录出错: {str(e)}"}
        )

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """上传音频文件并转录"""
    try:
        # 保存上传的文件
        filename = f"upload_{int(time.time())}.wav"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 使用Whisper转录
        result = model.transcribe(file_path)
        transcription = result["text"]
        
        return {
            "text": transcription,
            "audio_path": file_path
        }
    
    except Exception as e:
        logger.error(f"处理上传音频时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理上传音频时出错: {str(e)}"}
        )

# UDP服务器处理ESP32音频流
async def start_udp_server():
    """启动UDP服务器接收ESP32音频数据"""
    logger.info(f"启动UDP服务器，端口: {UDP_PORT}")
    
    # 创建UDP套接字
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    sock.setblocking(False)
    
    # 帧计数
    frame_count = 0
    buffer = bytearray()
    current_file = None
    
    while True:
        try:
            # 接收数据
            data, addr = await asyncio.get_event_loop().sock_recv(sock, 1024)
            
            if data.startswith(b'START'):
                # 新录音开始
                frame_count = 0
                buffer = bytearray()
                logger.info(f"接收新录音 来自: {addr}")
                continue
                
            elif data.startswith(b'END'):
                # 录音结束，保存文件
                if len(buffer) > 0:
                    file_name = f"esp32_{int(time.time())}.wav"
                    file_path = os.path.join(AUDIO_DIR, file_name)
                    
                    # 保存为WAV文件
                    with wave.open(file_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)  # 16位
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(buffer)
                    
                    logger.info(f"录音保存至: {file_path}")
                    current_file = file_path
                    
                    # 异步处理转录
                    asyncio.create_task(process_new_audio(file_path))
                
                buffer = bytearray()
                frame_count = 0
                continue
            
            # 累积音频数据
            buffer.extend(data)
            frame_count += 1
            
        except BlockingIOError:
            await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"UDP处理错误: {str(e)}")
            await asyncio.sleep(1)

async def process_new_audio(file_path):
    """处理新接收到的音频文件"""
    try:
        # 使用Whisper转录
        result = model.transcribe(file_path)
        transcription = result["text"]
        
        logger.info(f"转录结果: {transcription}")
        
        # 这里可以发送到协调服务或其他处理
        # TODO: 实现与协调服务的通信
        
    except Exception as e:
        logger.error(f"处理新音频时出错: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """应用启动时的事件处理"""
    # 启动UDP服务器
    asyncio.create_task(start_udp_server())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)