import os
import asyncio
from google.cloud import texttospeech_v1beta1 as texttospeech
from dotenv import load_dotenv
import pyaudio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

FEMALE_VOICES = [
    "fr-FR-Chirp3-HD-Aoede", 
    "fr-FR-Chirp3-HD-Callirrhoe", 
    "fr-FR-Chirp3-HD-Despina", 
    "fr-FR-Chirp3-HD-Erinome", 
    "fr-FR-Chirp3-HD-Kore", 
    "fr-FR-Chirp3-HD-Leda", 
    "fr-FR-Chirp3-HD-Zephyr", 
]

async def synthesize_and_play(client, voice_name):
    short_name = voice_name.split("-")[-1]
    text = f"Bonjour ! Je suis la voix {short_name}. Je suis une voix haute définition conçue pour être naturelle et expressive. Qu'en penses-tu ?"
    
    logger.info(f"--- Testing Voice: {voice_name} ---")
    logger.info(f"Text: {text}")
    
    input_text = texttospeech.SynthesisInput(text=text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code="fr-FR",
        name=voice_name
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=24000
    )

    try:
        response = await asyncio.to_thread(
            client.synthesize_speech,
            input=input_text,
            voice=voice,
            audio_config=audio_config
        )
        
        # Playback using PyAudio
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=24000,
                        output=True)
        
        stream.write(response.audio_content)
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    except Exception as e:
        logger.error(f"Failed for {voice_name}: {e}")

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        client = texttospeech.TextToSpeechClient(
            client_options={"api_key": api_key}
        )
    except Exception as e:
        logger.error(f"Client init failed: {e}")
        return

    for voice in FEMALE_VOICES:
        await synthesize_and_play(client, voice)
        await asyncio.sleep(1) # Short pause between voices

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
