import os
import asyncio
import logging
import time
import math
import struct
import pyaudio
import numpy as np
import io
import wave
from google import genai
from google.genai import types
from google.cloud import texttospeech
from dotenv import load_dotenv
from openwakeword.model import Model

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Config
# Utilisation de FLASH pour la vitesse de test (2.5 Pro est trop lent pour du live)
MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-3-flash") 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
VOICE_NAME = "fr-FR-Chirp3-HD-Zephyr"
WAKEWORD_MODEL_PATH = os.path.join(os.getcwd(), "models", "Motisma-v1.onnx")

# Audio Settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280 
SILENCE_THRESHOLD = 500
SILENCE_DURATION = 1.3 # Temps de silence pour valider la fin de phrase

def pcm_to_wav(pcm_data, rate=16000):
    """Encapsule le PCM dans un container WAV pour que Gemini le comprenne"""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(rate)
            wav_file.writeframes(pcm_data)
        return wav_io.getvalue()

class BurstAssistant:
    def __init__(self):
        self.genai_client = genai.Client(
            api_key=GOOGLE_API_KEY, 
            http_options={"api_version": "v1beta"}
        )
        self.tts_client = texttospeech.TextToSpeechClient(
            client_options={"api_key": GOOGLE_API_KEY}
        )
        self.wakeword_model = Model(wakeword_models=[WAKEWORD_MODEL_PATH], inference_framework="onnx")
        
        self.p = pyaudio.PyAudio()
        self.stream_in = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        self.stream_out = self.p.open(format=FORMAT, channels=CHANNELS, rate=24000, output=True)
        
        self.audio_buffer = bytearray()
        self.last_speech_time = time.time()
        self.is_awake = False
        self.has_started_command = False

    async def speak(self, text):
        if not text.strip(): return
        logger.info(f"Jarvis: {text}")
        
        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code="fr-FR", name=VOICE_NAME)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=24000)

        try:
            response = await asyncio.to_thread(
                self.tts_client.synthesize_speech,
                input=input_text, voice=voice, audio_config=audio_config
            )
            await asyncio.to_thread(self.stream_out.write, response.audio_content)
        except Exception as e:
            logger.error(f"TTS Error: {e}")

    async def process_burst(self):
        if len(self.audio_buffer) < 3200: # Moins de 0.1s d'audio, on ignore
            return
            
        # CONVERSION WAV OBLIGATOIRE
        wav_data = pcm_to_wav(bytes(self.audio_buffer), RATE)
        self.audio_buffer = bytearray() 
        
        logger.info(f"🚀 Sending Burst ({len(wav_data)} bytes) to {MODEL_ID}...")
        start_time = time.time()
        
        try:
            stream = await self.genai_client.aio.models.generate_content_stream(
                model=MODEL_ID,
                contents=[types.Part.from_bytes(data=wav_data, mime_type="audio/wav")],
                config={"system_instruction": "Tu es Jarvis. Réponds de manière brève et naturelle en français."}
            )
            
            full_response = ""
            async for chunk in stream:
                if chunk.text:
                    if not full_response:
                        logger.info(f"⏱️ First token in {time.time() - start_time:.2f}s")
                    full_response += chunk.text
            
            await self.speak(full_response)
            
        except Exception as e:
            logger.error(f"Gemini Error: {e}")

    async def run(self):
        logger.info(f"--- Burst Multimodal Fix ({MODEL_ID}) ---")
        logger.info("Listening for 'Motisma'...")
        
        try:
            while True:
                data = await asyncio.to_thread(self.stream_in.read, CHUNK, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                
                # Calcul RMS pour le VAD
                shorts = struct.unpack("%dh" % (len(data) / 2), data)
                rms = math.sqrt(sum(s**2 for s in shorts) / len(shorts))

                if not self.is_awake:
                    prediction = self.wakeword_model.predict(audio_np)
                    for mdl, score in prediction.items():
                        if score > 0.5:
                            logger.info(f"✨ WAKE WORD DETECTED ({score:.3f})")
                            self.is_awake = True
                            self.has_started_command = False
                            self.audio_buffer = bytearray()
                            self.last_speech_time = time.time()
                else:
                    self.audio_buffer.extend(data)
                    
                    if rms > SILENCE_THRESHOLD:
                        self.last_speech_time = time.time()
                        self.has_started_command = True
                    
                    # Logique de fin de phrase :
                    # On attend au moins qu'il ait commencé à parler OU un timeout de 3s après le réveil
                    silence_duration = time.time() - self.last_speech_time
                    
                    if self.has_started_command and silence_duration > SILENCE_DURATION:
                        logger.info("🛑 End of speech detected. Processing...")
                        await self.process_burst()
                        self.is_awake = False
                        logger.info("Ready for next command. Say 'Motisma'.")
                    elif not self.has_started_command and silence_duration > 3.0:
                        logger.info("⌛ Timeout: No command heard after wakeup.")
                        self.is_awake = False
                        self.audio_buffer = bytearray()
                
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.p.terminate()

if __name__ == "__main__":
    assistant = BurstAssistant()
    asyncio.run(assistant.run())
