import os
import asyncio
from google.cloud import texttospeech_v1beta1 as texttospeech
from dotenv import load_dotenv

load_dotenv()

def list_voices():
    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        # Note: Using API Key with client_options might be tricky for some methods, 
        # but let's try standard client init.
        client = texttospeech.TextToSpeechClient(
            client_options={"api_key": api_key}
        )
    except Exception as e:
        print(f"Client init failed: {e}")
        return

    print("Fetching available voices...")
    try:
        response = client.list_voices()
        
        print("\n--- All French Voices ---")
        for voice in response.voices:
            if any("fr-" in code for code in voice.language_codes):
                codes = ", ".join(voice.language_codes)
                gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
                print(f"Name: {voice.name} | Language: {codes} | Gender: {gender}")

        print("\n--- All French Voices (Summary) ---")
        # Just to check if we see others
        count = 0
        for voice in response.voices:
             if any("fr-" in code for code in voice.language_codes):
                 count += 1
        print(f"Total French voices found: {count}")

    except Exception as e:
        print(f"Error listing voices: {e}")

if __name__ == "__main__":
    list_voices()
