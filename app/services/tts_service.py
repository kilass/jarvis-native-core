import logging
import asyncio
from google.cloud import texttospeech
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class TTSService:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient(
            client_options={"api_key": settings.GOOGLE_API_KEY} 
        )
        # Voice Configuration: Neural2 - French (Configurable)
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="fr-FR",
            name=settings.TTS_VOICE_NAME
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000
        )

    async def synthesize(self, text: str):
        """
        Synthesizes text to audio using Google Cloud TTS.
        Returns bytes of audio data.
        """
        if not text.strip():
            return None

        # Note: TTS API is synchronous by default, we wrap it to not block the event loop
        # For ultra-low latency, one might use the streaming API (beta), 
        # but standard request is often fast enough (<200ms) for short sentences.
        try:
            input_text = texttospeech.SynthesisInput(text=text)
            
            # Run blocking call in executor
            response = await asyncio.to_thread(
                self.client.synthesize_speech,
                input=input_text,
                voice=self.voice,
                audio_config=self.audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            logger.error(f"TTS Synthesis error: {e}")
            return None
