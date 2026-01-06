from google.cloud import texttospeech
from app.core.config import get_settings

def list_voices():
    settings = get_settings()
    client = texttospeech.TextToSpeechClient(
        client_options={"api_key": settings.GOOGLE_API_KEY}
    )

    response = client.list_voices(language_code="fr-FR")
    conversational_voices = [v for v in response.voices if "Neural2" in v.name or "Chirp" in v.name or "Studio" in v.name]
    
    print("\n--- Available High-Quality French Voices ---")
    for voice in conversational_voices:
        print(f"Name: {voice.name}")
        print(f"Gender: {texttospeech.SsmlVoiceGender(voice.ssml_gender).name}")
        print(f"Rate: {voice.natural_sample_rate_hertz} Hz")
        print("--------------------------------------------")

if __name__ == "__main__":
    list_voices()
