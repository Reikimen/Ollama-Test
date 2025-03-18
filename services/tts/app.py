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
import edge_tts  # Using Microsoft Edge TTS as the TTS engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")  # English female voice
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "mp3")  # Output format, ESP32 typically uses MP3

# Create audio directory
os.makedirs(AUDIO_DIR, exist_ok=True)

# Create FastAPI application
app = FastAPI(title="Text-to-Speech Service")

# Configure CORS
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
    return {"message": "Text-to-Speech Service is running"}

@app.get("/voices")
async def list_voices():
    """List all available voices"""
    try:
        voices = await edge_tts.list_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Error getting voice list: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error getting voice list: {str(e)}"}
        )

@app.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Synthesize speech and return audio file path"""
    try:
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"tts_{timestamp}.{request.format}"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # Use Edge TTS to synthesize speech
        communicate = edge_tts.Communicate(request.text, request.voice)
        await communicate.save(file_path)
        
        logger.info(f"Speech synthesized: {file_path}")
        
        return {
            "audio_path": file_path,
            "format": request.format,
            "voice": request.voice
        }
    
    except Exception as e:
        logger.error(f"Speech synthesis error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Speech synthesis error: {str(e)}"}
        )

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Get synthesized audio file"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file does not exist")
    
    return FileResponse(file_path)

@app.post("/stream")
async def stream_audio(request: TTSRequest):
    """Stream audio synthesis (for real-time transmission to ESP32)"""
    try:
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"stream_{timestamp}.{request.format}"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # Use Edge TTS to synthesize speech
        communicate = edge_tts.Communicate(request.text, request.voice)
        
        # Direct save
        await communicate.save(file_path)
        
        logger.info(f"Streaming speech synthesized: {file_path}")
        
        return {
            "audio_path": file_path,
            "status": "ready"
        }
    
    except Exception as e:
        logger.error(f"Streaming speech synthesis error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Streaming speech synthesis error: {str(e)}"}
        )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)