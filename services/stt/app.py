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
            content={"error": f"Error processing uploaded audio: {str(e)}"}
        )

# UDP server to handle ESP32 audio stream
async def start_udp_server():
    """Start UDP server to receive ESP32 audio data"""
    logger.info(f"Starting UDP server on port: {UDP_PORT}")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    sock.setblocking(False)
    
    # Frame counter
    frame_count = 0
    buffer = bytearray()
    current_file = None
    
    while True:
        try:
            # Receive data
            data, addr = await asyncio.get_event_loop().sock_recv(sock, 1024)
            
            if data.startswith(b'START'):
                # New recording starts
                frame_count = 0
                buffer = bytearray()
                logger.info(f"Receiving new recording from: {addr}")
                continue
                
            elif data.startswith(b'END'):
                # Recording ends, save file
                if len(buffer) > 0:
                    file_name = f"esp32_{int(time.time())}.wav"
                    file_path = os.path.join(AUDIO_DIR, file_name)
                    
                    # Save as WAV file
                    with wave.open(file_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)  # 16-bit
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(buffer)
                    
                    logger.info(f"Recording saved to: {file_path}")
                    current_file = file_path
                    
                    # Process transcription asynchronously
                    asyncio.create_task(process_new_audio(file_path))
                
                buffer = bytearray()
                frame_count = 0
                continue
            
            # Accumulate audio data
            buffer.extend(data)
            frame_count += 1
            
        except BlockingIOError:
            await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"UDP processing error: {str(e)}")
            await asyncio.sleep(1)

async def process_new_audio(file_path):
    """Process newly received audio file"""
    try:
        # Use Whisper for transcription
        result = model.transcribe(file_path)
        transcription = result["text"]
        
        logger.info(f"Transcription result: {transcription}")
        
        # Here you can send to coordinator service or other processing
        # TODO: Implement communication with coordinator service
        
    except Exception as e:
        logger.error(f"Error processing new audio: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Event handler for application startup"""
    # Start UDP server
    asyncio.create_task(start_udp_server())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)