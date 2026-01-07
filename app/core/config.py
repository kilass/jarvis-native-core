from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_ID: str = "project-id-placeholder"
    LOCATION: str = "europe-west9" # Updated to Paris
    GOOGLE_API_KEY: str
    
    # LLM & TTS Config
    GEMINI_MODEL_ID: str = "gemini-2.5-pro"
    TTS_VOICE_NAME: str = "fr-FR-Neural2-C"
    SYSTEM_INSTRUCTION: str = "Tu es Jarvis, une assistante domotique. Tu réponds de manière brève, précise et chaleureuse."
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    # Audio Settings
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
