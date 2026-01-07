import asyncio
import logging
import os
from google import genai
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class GeminiClient:
    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.project_id = settings.PROJECT_ID
        self.location = settings.LOCATION
        
        # Reverting to v1alpha for experimental model stability (gemini-2.0-flash-exp)
        self.client = genai.Client(
            api_key=self.api_key, 
            http_options={"api_version": "v1alpha"}
        )
        # Using the model configured in settings (Recommending gemini-2.0-flash)
        self.model_id = settings.GEMINI_MODEL_ID
        
        # Live config with Google Search Tool enabled
        self.config = {
            "tools": [{"google_search": {}}],
            "response_modalities": ["TEXT"],
            "system_instruction": settings.SYSTEM_INSTRUCTION
        }

    def start_session(self):
        """
        Starts a live session with Gemini.
        Returns the session context manager.
        """
        logger.info(f"Connecting to Gemini Live API: {self.model_id}")
        # Connect to the live session
        return self.client.aio.live.connect(
            model=self.model_id,
            config=self.config
        )
