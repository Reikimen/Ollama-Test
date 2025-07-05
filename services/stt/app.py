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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
UDP_PORT = int(os.getenv("UDP_PORT", 8000))
SAMPLE_RATE = 16000  # ESP32 recording sample rate

# Create audio directory
os.makedirs(AUDIO_DIR, exist_ok=True)

# Initialize Whisper model
logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
model = whisper.load_model(WHISPER_MODEL)
logger.info("Whisper model loaded")

# Create FastAPI application
app = FastAPI(title="Speech Recognition Service")

# Configure CORS
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
    return {"message": "Speech Recognition Service is running"}

@app.post("/transcribe")
async def transcribe_audio(request: AudioRequest):
    """Transcribe audio file at specified path"""
    try:
        audio_path = request.audio_path
        
        if not os.path.exists(audio_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"Audio file does not exist: {audio_path}"}
            )
        
        # Use Whisper for transcription
        logger.info(f"Starting transcription: {audio_path}")
        result = model.transcribe(audio_path)
        transcription = result["text"]
        logger.info(f"Transcription complete: {transcription}")
        
        return {"text": transcription}
    
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Transcription error: {str(e)}"}
        )

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Upload audio file and transcribe"""
    try:
        # Save uploaded file
        filename = f"upload_{int(time.time())}.wav"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Use Whisper for transcription
        result = model.transcribe(file_path)
        transcription = result["text"]
        
        return {
            "text": transcription,
            "audio_path": file_path
        }
    
    except Exception as e:
        logger.error(f"Error processing uploaded audio: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing error: {str(e)}"}
        )

@app.post("/upload_pcm")
async def upload_pcm_audio(
    file: UploadFile = File(...),
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2
):
    """Upload PCM audio data and transcribe
    
    This endpoint is specifically for ESP32 devices that send raw PCM data.
    Default parameters match ESP32 recording settings.
    """
    try:
        # Read PCM data
        pcm_data = await file.read()
        logger.info(f"Received PCM data: {len(pcm_data)} bytes")
        
        # Save as WAV file for Whisper
        timestamp = int(time.time())
        filename = f"pcm_upload_{timestamp}.wav"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # Convert PCM to WAV
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        logger.info(f"Saved PCM as WAV: {file_path}")
        
        # Use Whisper for transcription
        result = model.transcribe(file_path)
        transcription = result["text"]
        
        logger.info(f"Transcription: {transcription}")
        
        return {
            "text": transcription,
            "audio_path": file_path,
            "format": "pcm",
            "sample_rate": sample_rate,
            "duration": len(pcm_data) / (sample_rate * channels * sample_width)
        }
    
    except Exception as e:
        logger.error(f"Error processing PCM audio: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"PCM processing error: {str(e)}"}
        )

# WebSocket endpoint for real-time audio streaming (future feature)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    try:
        while True:
            # Receive audio data
            data = await websocket.receive_bytes()
            
            # Process audio chunk (placeholder for future implementation)
            # For now, just echo back a message
            await websocket.send_text("Audio chunk received")
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

# UDP server for real-time audio (alternative to WebSocket)
async def udp_server():
    """UDP server for receiving audio streams"""
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPServerProtocol(),
        local_addr=('0.0.0.0', UDP_PORT)
    )
    
    logger.info(f"UDP server listening on port {UDP_PORT}")
    
    try:
        await asyncio.sleep(3600)  # Run for 1 hour
    finally:
        transport.close()

class UDPServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
    
    def datagram_received(self, data, addr):
        # Process received audio data
        logger.debug(f"Received {len(data)} bytes from {addr}")
        # TODO: Implement audio processing

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("STT Service started")
    logger.info(f"Whisper model: {WHISPER_MODEL}")
    logger.info(f"Audio directory: {AUDIO_DIR}")
    
    # Start UDP server in background (optional)
    # asyncio.create_task(udp_server())

# Cleanup old audio files
async def cleanup_old_files():
    """Remove audio files older than 1 hour"""
    while True:
        try:
            current_time = time.time()
            for filename in os.listdir(AUDIO_DIR):
                file_path = os.path.join(AUDIO_DIR, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > 3600:  # 1 hour
                        os.remove(file_path)
                        logger.debug(f"Removed old file: {filename}")
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
        
        await asyncio.sleep(600)  # Run every 10 minutes

# Start cleanup task
@app.on_event("startup")
async def start_cleanup():
    asyncio.create_task(cleanup_old_files())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)