import os
import pyaudio
import asyncio
import logging
import time
import math
import struct
from dotenv import load_dotenv
from google import genai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_ID = "models/gemini-2.5-flash"
# MODEL_ID = "models/gemini-2.0-flash-exp" # Fallback for testing

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000 # Gemini Native Audio is often 24kHz
CHUNK = 1024

async def native_audio_loop():
    if not API_KEY:
        logger.error("GOOGLE_API_KEY not found in .env")
        return

    client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
    
    p = pyaudio.PyAudio()
    
    # Input Stream (Mic) - 16kHz for input is usually safer, but let's try 16k resampled or just 16k
    # Gemini usually expects 16k input, 24k output.
    input_stream = p.open(format=FORMAT, channels=CHANNELS, rate=16000, input=True, frames_per_buffer=CHUNK)
    output_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

    logger.info(f"Connecting to Gemini Live ID: {MODEL_ID}...")
    
    # --- VOICE SELECTION ---
    # Puck (Default - Neutre)
    # Charon (Plus grave)
    # Kore (Féminin ?)
    # Fenrir (Masculin, grave)
    # Aoede (Féminin, doux)
    VOICE_NAME = "Kore" 
    
    # Config for Native Audio and Tools
    config = {
        "response_modalities": ["AUDIO"],
        "tools": [{"google_search": {}}], # Enable Google Search (Zebsearch)
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": VOICE_NAME
                }
            }
        },
        "system_instruction": "Tu es un assistant francophone. Tu t'appelle Motisma. Tu parles français naturellement. Tu emploies un ton taquin et moqueur. Si on te demande une info récente, utilise Google Search."
    }

    # Shared state for latency calculation
    state = {
        "last_user_speech_time": 0,
        "last_server_audio_time": 0
    }

    try:
        async with client.aio.live.connect(model=MODEL_ID, config=config) as session:
            logger.info("Connected to Gemini 2.5 Native Audio! Say something...")
            
            async def send_audio():
                while True:
                    try:
                        data = await asyncio.to_thread(input_stream.read, CHUNK, exception_on_overflow=False)
                        
                        # Simple RMS calculation
                        shorts = struct.unpack("%dh" % (len(data) / 2), data)
                        sum_squares = sum(s**2 for s in shorts)
                        rms = math.sqrt(sum_squares / len(shorts))
                        
                        # Threshold for speech (adjust if needed, 500 is conservative for silence)
                        if rms > 200: 
                            state["last_user_speech_time"] = time.time()
                            
                        await session.send_realtime_input(media={"data": data, "mime_type": "audio/pcm"})
                        await asyncio.sleep(0.001)
                    except Exception as e:
                        logger.error(f"Send Error: {e}")
                        break

            async def receive_loop():
                while True:
                    try:
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content:
                                # Tool Use Logging
                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.executable_code:
                                            logger.info("🛠️ TOOL USE DETECTED")
                                
                                # Audio Output
                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data:
                                            now = time.time()
                                            
                                            # Detect start of new turn (if silence > 500ms from server)
                                            if now - state["last_server_audio_time"] > 0.5:
                                                latency = now - state["last_user_speech_time"]
                                                logger.info(f"🔊 RESPONSE START - Latency: {latency:.3f}s")
                                            
                                            state["last_server_audio_time"] = now
                                            
                                            audio_data = part.inline_data.data
                                            await asyncio.to_thread(output_stream.write, audio_data)
                                
                            await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.error(f"Receive Error: {e}")
                        break

            await asyncio.gather(send_audio(), receive_loop())

    except Exception as e:
        logger.error(f"Connection Failed: {e}")
    finally:
        input_stream.stop_stream()
        output_stream.stop_stream()
        p.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(native_audio_loop())
    except KeyboardInterrupt:
        pass
