import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")

print("--- DIAGNOSTIC CHECK ---")
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY environment variable is missing or empty!")
else:
    print(f"✅ Key Found! Key starts with: {api_key[:6]}...")
    try:
        client = genai.Client(api_key=api_key)
        print("\nFetching available models for your key...")
        models = list(client.models.list())
        
        print(f"✅ Connected successfully! Found {len(models)} models:")
        for m in models:
            if "gemini" in m.name:
                print(f"  - {m.name}")
    except Exception as e:
        print(f"\n❌ API Call Failed!")
        print(f"Error Details: {e}")
print("------------------------")
