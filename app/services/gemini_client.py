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
        
        # Initialize the client
        # Note: Adjusting for specific SDK version usage. 
        # Assuming google-genai 0.2+ structure.
        self.client = genai.Client(
            api_key=self.api_key, 
            http_options={"api_version": "v1beta"}
        )
        # Using the model configured in settings
        self.model_id = settings.GEMINI_MODEL_ID
        
        # Live config
        self.config = {
            "response_modalities": ["TEXT"],
            # Prompt optimisé pour le texte conversationnel
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
