import os
import logging
import time
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import edge_tts  # 使用微软Edge TTS作为TTS引擎

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 环境变量
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # 中文女声
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "mp3")  # 输出格式，ESP32通常使用MP3

# 创建音频目录
os.makedirs(AUDIO_DIR, exist_ok=True)

# 创建FastAPI应用
app = FastAPI(title="语音合成服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    voice: str = TTS_VOICE
    format: str = OUTPUT_FORMAT

@app.get("/")
async def root():
    return {"message": "语音合成服务运行中"}

@app.get("/voices")
async def list_voices():
    """列出所有可用的语音"""
    try:
        voices = await edge_tts.list_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"获取语音列表出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"获取语音列表出错: {str(e)}"}
        )

@app.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """合成语音并返回音频文件路径"""
    try:
        # 生成唯一文件名
        timestamp = int(time.time())
        filename = f"tts_{timestamp}.{request.format}"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # 使用Edge TTS合成语音
        communicate = edge_tts.Communicate(request.text, request.voice)
        await communicate.save(file_path)
        
        logger.info(f"语音已合成: {file_path}")
        
        return {
            "audio_path": file_path,
            "format": request.format,
            "voice": request.voice
        }
    
    except Exception as e:
        logger.error(f"语音合成出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"语音合成出错: {str(e)}"}
        )

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取合成的音频文件"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    return FileResponse(file_path)

@app.post("/stream")
async def stream_audio(request: TTSRequest):
    """流式合成音频（用于实时传输到ESP32）"""
    try:
        # 生成唯一文件名
        timestamp = int(time.time())
        filename = f"stream_{timestamp}.{request.format}"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # 使用Edge TTS合成语音
        communicate = edge_tts.Communicate(request.text, request.voice)
        
        # 直接保存
        await communicate.save(file_path)
        
        logger.info(f"流式语音已合成: {file_path}")
        
        return {
            "audio_path": file_path,
            "status": "ready"
        }
    
    except Exception as e:
        logger.error(f"流式语音合成出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"流式语音合成出错: {str(e)}"}
        )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)