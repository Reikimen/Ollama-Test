import os
import logging
import time
import asyncio
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import edge_tts  # Using Microsoft Edge TTS as the TTS engine
import wave
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")  # English female voice
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "mp3")  # Output format

# Create audio directory
os.makedirs(AUDIO_DIR, exist_ok=True)

# Create FastAPI application
app = FastAPI(title="Text-to-Speech Service with PCM Support")

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
    format: str = OUTPUT_FORMAT  # Optional, defaults to mp3

class PCMConfig:
    """PCM audio configuration for ESP32"""
    SAMPLE_RATE = 16000  # 16kHz
    CHANNELS = 1         # Mono
    SAMPLE_WIDTH = 2     # 16-bit

def mp3_to_pcm(mp3_file_path: str, pcm_file_path: str) -> bool:
    """
    Convert MP3 file to PCM using ffmpeg
    Returns True if successful, False otherwise
    """
    try:
        # Use ffmpeg to convert MP3 to raw PCM
        # -ar: sample rate, -ac: channels, -f s16le: 16-bit little-endian PCM
        cmd = [
            'ffmpeg',
            '-i', mp3_file_path,
            '-ar', str(PCMConfig.SAMPLE_RATE),
            '-ac', str(PCMConfig.CHANNELS),
            '-f', 's16le',
            '-y',  # Overwrite output file
            pcm_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Successfully converted MP3 to PCM: {pcm_file_path}")
            return True
        else:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error converting MP3 to PCM: {str(e)}")
        return False

def create_wav_header(pcm_data: bytes) -> bytes:
    """
    Create WAV header for PCM data
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(PCMConfig.CHANNELS)
        wav_file.setsampwidth(PCMConfig.SAMPLE_WIDTH)
        wav_file.setframerate(PCMConfig.SAMPLE_RATE)
        wav_file.writeframes(pcm_data)
    
    return wav_buffer.getvalue()

@app.get("/")
async def root():
    return {
        "message": "Text-to-Speech Service with PCM Support is running",
        "features": ["MP3 generation", "PCM conversion", "Direct PCM streaming"],
        "pcm_config": {
            "sample_rate": PCMConfig.SAMPLE_RATE,
            "channels": PCMConfig.CHANNELS,
            "sample_width": PCMConfig.SAMPLE_WIDTH * 8  # bits
        }
    }

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
        base_filename = f"tts_{timestamp}"
        
        # Default to mp3 if format not specified
        output_format = request.format.lower()
        
        if output_format == "pcm":
            # For PCM, generate MP3 first then convert
            mp3_filename = f"{base_filename}_temp.mp3"
            mp3_path = os.path.join(AUDIO_DIR, mp3_filename)
            
            # Create TTS communication object
            communicate = edge_tts.Communicate(request.text, request.voice)
            await communicate.save(mp3_path)
            
            # Convert to PCM
            pcm_filename = f"{base_filename}.pcm"
            pcm_path = os.path.join(AUDIO_DIR, pcm_filename)
            
            if mp3_to_pcm(mp3_path, pcm_path):
                # Delete temporary MP3 file
                os.remove(mp3_path)
                
                # Return format compatible with original API
                return {
                    "audio_path": f"/app/audio/{pcm_filename}",  # Path expected by frontend
                    "filename": pcm_filename,
                    "format": "pcm",
                    "voice": request.voice,
                    "sample_rate": PCMConfig.SAMPLE_RATE,
                    "channels": PCMConfig.CHANNELS,
                    "sample_width": PCMConfig.SAMPLE_WIDTH * 8
                }
            else:
                os.remove(mp3_path)
                raise HTTPException(status_code=500, detail="Failed to convert to PCM")
        else:
            # Default MP3 format (original behavior)
            mp3_filename = f"{base_filename}.mp3"
            mp3_path = os.path.join(AUDIO_DIR, mp3_filename)
            
            # Create TTS communication object
            communicate = edge_tts.Communicate(request.text, request.voice)
            
            # Save to MP3 file
            await communicate.save(mp3_path)
            logger.info(f"Generated MP3: {mp3_path}")
            
            # Return format compatible with original API
            return {
                "audio_path": f"/app/audio/{mp3_filename}",  # Path expected by frontend
                "filename": mp3_filename,
                "format": "mp3",
                "voice": request.voice
            }
        
    except Exception as e:
        logger.error(f"Error synthesizing speech: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Get audio file - compatible with original API"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Determine media type based on file extension
    if filename.endswith('.mp3'):
        media_type = "audio/mpeg"
    elif filename.endswith('.pcm'):
        media_type = "audio/pcm"
    elif filename.endswith('.wav'):
        media_type = "audio/wav"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type, filename=filename)

@app.get("/download/pcm")
async def download_pcm_direct(text: str = Query(..., description="Text to synthesize")):
    """
    Direct PCM download endpoint for ESP32
    Synthesizes text and returns raw PCM data
    """
    try:
        # Generate temporary MP3
        timestamp = int(time.time())
        mp3_path = os.path.join(AUDIO_DIR, f"temp_{timestamp}.mp3")
        pcm_path = os.path.join(AUDIO_DIR, f"temp_{timestamp}.pcm")
        
        # Create TTS
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(mp3_path)
        
        # Convert to PCM
        if not mp3_to_pcm(mp3_path, pcm_path):
            raise HTTPException(status_code=500, detail="PCM conversion failed")
        
        # Read PCM data
        with open(pcm_path, 'rb') as f:
            pcm_data = f.read()
        
        # Clean up temporary files
        os.remove(mp3_path)
        os.remove(pcm_path)
        
        # Return PCM data as streaming response
        return StreamingResponse(
            io.BytesIO(pcm_data),
            media_type="audio/pcm",
            headers={
                "Content-Disposition": "attachment; filename=audio.pcm",
                "X-Sample-Rate": str(PCMConfig.SAMPLE_RATE),
                "X-Channels": str(PCMConfig.CHANNELS),
                "X-Sample-Width": str(PCMConfig.SAMPLE_WIDTH * 8)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in direct PCM download: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/wav")
async def download_wav_direct(text: str = Query(..., description="Text to synthesize")):
    """
    Direct WAV download endpoint (PCM with WAV header)
    """
    try:
        # Generate temporary MP3
        timestamp = int(time.time())
        mp3_path = os.path.join(AUDIO_DIR, f"temp_{timestamp}.mp3")
        pcm_path = os.path.join(AUDIO_DIR, f"temp_{timestamp}.pcm")
        
        # Create TTS
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(mp3_path)
        
        # Convert to PCM
        if not mp3_to_pcm(mp3_path, pcm_path):
            raise HTTPException(status_code=500, detail="PCM conversion failed")
        
        # Read PCM data and create WAV
        with open(pcm_path, 'rb') as f:
            pcm_data = f.read()
        
        wav_data = create_wav_header(pcm_data)
        
        # Clean up temporary files
        os.remove(mp3_path)
        os.remove(pcm_path)
        
        # Return WAV data
        return StreamingResponse(
            io.BytesIO(wav_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=audio.wav"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in WAV download: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/audio/{filename}")
async def delete_audio(filename: str):
    """Delete audio file"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(file_path)
        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list")
async def list_audio_files():
    """List all audio files in the directory"""
    try:
        files = []
        for filename in os.listdir(AUDIO_DIR):
            file_path = os.path.join(AUDIO_DIR, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created": stat.st_ctime,
                    "format": filename.split('.')[-1]
                })
        
        return {"files": files, "count": len(files)}
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)