import os
import logging
import time
import asyncio
import subprocess
import io
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import edge_tts
import wave
import tempfile
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "mp3")

# Create audio directory
os.makedirs(AUDIO_DIR, exist_ok=True)

# Create FastAPI application
app = FastAPI(title="Text-to-Speech Service with ESP32 Optimization")

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
    format: str = OUTPUT_FORMAT  # mp3, pcm, wav

class PCMConfig:
    """PCM audio configuration for ESP32"""
    SAMPLE_RATE = 16000  # 16kHz
    CHANNELS = 1         # Mono
    SAMPLE_WIDTH = 2     # 16-bit
    CHUNK_SIZE = 4096    # Chunk size for streaming (4KB)

def mp3_to_pcm_stream(mp3_data: bytes) -> bytes:
    """
    Convert MP3 data to PCM using ffmpeg
    Returns PCM data as bytes
    """
    try:
        # Use ffmpeg to convert MP3 to raw PCM
        cmd = [
            'ffmpeg',
            '-i', 'pipe:0',  # Read from stdin
            '-ar', str(PCMConfig.SAMPLE_RATE),
            '-ac', str(PCMConfig.CHANNELS),
            '-f', 's16le',  # 16-bit little-endian PCM
            '-loglevel', 'error',
            'pipe:1'  # Write to stdout
        ]
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        pcm_data, error = process.communicate(input=mp3_data)
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {error.decode()}")
            raise Exception("PCM conversion failed")
            
        return pcm_data
        
    except Exception as e:
        logger.error(f"Error converting MP3 to PCM: {str(e)}")
        raise

async def generate_pcm_chunks(text: str, voice: str):
    """
    Generator that yields PCM chunks for streaming
    """
    try:
        # Create TTS communication object
        communicate = edge_tts.Communicate(text, voice)
        
        # Generate MP3 in memory
        mp3_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_data += chunk["data"]
        
        # Convert to PCM
        pcm_data = mp3_to_pcm_stream(mp3_data)
        
        # Yield chunks
        for i in range(0, len(pcm_data), PCMConfig.CHUNK_SIZE):
            yield pcm_data[i:i + PCMConfig.CHUNK_SIZE]
            
    except Exception as e:
        logger.error(f"Error generating PCM chunks: {str(e)}")
        raise

@app.get("/")
async def root():
    return {
        "message": "Text-to-Speech Service with ESP32 Optimization",
        "endpoints": {
            "esp32": {
                "/esp32/pcm": "Direct PCM streaming for ESP32",
                "/esp32/pcm/chunked": "Chunked PCM streaming",
                "/esp32/info": "Get PCM format information"
            },
            "web": {
                "/synthesize": "Generate and store audio (for web)",
                "/audio/{filename}": "Get stored audio file"
            }
        },
        "pcm_config": {
            "sample_rate": PCMConfig.SAMPLE_RATE,
            "channels": PCMConfig.CHANNELS,
            "bits_per_sample": PCMConfig.SAMPLE_WIDTH * 8,
            "chunk_size": PCMConfig.CHUNK_SIZE
        }
    }

# ==================== ESP32 Optimized Endpoints ====================

@app.post("/esp32/pcm")
async def esp32_pcm_stream(request: Request):
    """
    ESP32-optimized endpoint: Stream PCM data directly
    Accepts JSON body with text and optional voice
    Returns raw PCM stream without storing files
    """
    try:
        body = await request.json()
        text = body.get("text", "")
        voice = body.get("voice", TTS_VOICE)
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        logger.info(f"ESP32 PCM request: '{text[:50]}...'")
        
        # Generate PCM data
        pcm_chunks = []
        async for chunk in generate_pcm_chunks(text, voice):
            pcm_chunks.append(chunk)
        
        pcm_data = b"".join(pcm_chunks)
        
        # Return raw PCM data with appropriate headers
        return Response(
            content=pcm_data,
            media_type="audio/pcm",
            headers={
                "Content-Type": "audio/pcm",
                "X-Sample-Rate": str(PCMConfig.SAMPLE_RATE),
                "X-Channels": str(PCMConfig.CHANNELS),
                "X-Bits-Per-Sample": str(PCMConfig.SAMPLE_WIDTH * 8),
                "Content-Length": str(len(pcm_data))
            }
        )
        
    except Exception as e:
        logger.error(f"ESP32 PCM error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/esp32/pcm/chunked")
async def esp32_pcm_chunked_stream(request: Request):
    """
    ESP32-optimized endpoint: Chunked PCM streaming
    Allows ESP32 to start playing before full download
    """
    try:
        body = await request.json()
        text = body.get("text", "")
        voice = body.get("voice", TTS_VOICE)
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        logger.info(f"ESP32 chunked PCM request: '{text[:50]}...'")
        
        # Return streaming response
        return StreamingResponse(
            generate_pcm_chunks(text, voice),
            media_type="audio/pcm",
            headers={
                "Content-Type": "audio/pcm",
                "X-Sample-Rate": str(PCMConfig.SAMPLE_RATE),
                "X-Channels": str(PCMConfig.CHANNELS),
                "X-Bits-Per-Sample": str(PCMConfig.SAMPLE_WIDTH * 8),
                "Transfer-Encoding": "chunked"
            }
        )
        
    except Exception as e:
        logger.error(f"ESP32 chunked PCM error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/esp32/info")
async def esp32_audio_info():
    """
    Get PCM format information for ESP32 configuration
    """
    return {
        "pcm_format": {
            "sample_rate": PCMConfig.SAMPLE_RATE,
            "channels": PCMConfig.CHANNELS,
            "bits_per_sample": PCMConfig.SAMPLE_WIDTH * 8,
            "byte_order": "little-endian",
            "format": "signed 16-bit PCM"
        },
        "recommended_buffer_size": PCMConfig.CHUNK_SIZE,
        "estimated_bitrate": PCMConfig.SAMPLE_RATE * PCMConfig.CHANNELS * PCMConfig.SAMPLE_WIDTH * 8
    }

# ==================== Original Web Endpoints (保持兼容性) ====================

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
    """
    Original endpoint for web interface
    Generates and stores audio files
    """
    try:
        timestamp = int(time.time())
        base_filename = f"tts_{timestamp}"
        
        if request.format.lower() == "pcm":
            # Generate MP3 first
            mp3_filename = f"{base_filename}_temp.mp3"
            mp3_path = os.path.join(AUDIO_DIR, mp3_filename)
            
            communicate = edge_tts.Communicate(request.text, request.voice)
            await communicate.save(mp3_path)
            
            # Convert to PCM
            pcm_filename = f"{base_filename}.pcm"
            pcm_path = os.path.join(AUDIO_DIR, pcm_filename)
            
            # Read MP3 and convert
            with open(mp3_path, 'rb') as f:
                mp3_data = f.read()
            
            pcm_data = mp3_to_pcm_stream(mp3_data)
            
            with open(pcm_path, 'wb') as f:
                f.write(pcm_data)
            
            os.remove(mp3_path)
            
            return {
                "audio_path": f"/app/audio/{pcm_filename}",
                "filename": pcm_filename,
                "format": "pcm",
                "voice": request.voice,
                "sample_rate": PCMConfig.SAMPLE_RATE,
                "channels": PCMConfig.CHANNELS,
                "sample_width": PCMConfig.SAMPLE_WIDTH * 8
            }
        else:
            # Default MP3 format
            mp3_filename = f"{base_filename}.mp3"
            mp3_path = os.path.join(AUDIO_DIR, mp3_filename)
            
            communicate = edge_tts.Communicate(request.text, request.voice)
            await communicate.save(mp3_path)
            
            return {
                "audio_path": f"/app/audio/{mp3_filename}",
                "filename": mp3_filename,
                "format": "mp3",
                "voice": request.voice
            }
        
    except Exception as e:
        logger.error(f"Error synthesizing speech: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Get audio file"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    if filename.endswith('.mp3'):
        media_type = "audio/mpeg"
    elif filename.endswith('.pcm'):
        media_type = "audio/pcm"
    elif filename.endswith('.wav'):
        media_type = "audio/wav"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type, filename=filename)

@app.get("/download/{filename}")
async def download_audio(filename: str):
    """Download audio file (alternative endpoint)"""
    return await get_audio(filename)

# ==================== Legacy Endpoints (保持向后兼容) ====================

@app.get("/download/pcm")
async def download_pcm_direct(text: str = Query(..., description="Text to synthesize")):
    """
    Legacy endpoint for URL-based PCM generation
    Kept for backward compatibility
    """
    try:
        logger.info(f"Legacy PCM request: '{text[:50]}...'")
        
        pcm_chunks = []
        async for chunk in generate_pcm_chunks(text, TTS_VOICE):
            pcm_chunks.append(chunk)
        
        pcm_data = b"".join(pcm_chunks)
        
        return Response(
            content=pcm_data,
            media_type="audio/pcm",
            headers={
                "Content-Disposition": "attachment; filename=audio.pcm",
                "X-Sample-Rate": str(PCMConfig.SAMPLE_RATE),
                "X-Channels": str(PCMConfig.CHANNELS),
                "X-Sample-Width": str(PCMConfig.SAMPLE_WIDTH * 8)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in legacy PCM download: {str(e)}")
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