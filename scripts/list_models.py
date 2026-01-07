import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    
    print("Listing available models...")
    try:
        pager = client.models.list()
        for model in pager:
            if "gemini" in model.name:
                print(f"- {model.name} ({model.display_name})")
                
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
