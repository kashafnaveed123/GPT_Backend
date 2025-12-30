# debug_models.py
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

print("="*60)
print("🔍 Debugging Gemini API Access")
print("="*60)
print(f"API Key: {key[:15]}...")
print(f"Length: {len(key)}")
print()

# Configure
genai.configure(api_key=key)

# Try to list models
print("📋 Trying to list available models...")
print()

try:
    models = genai.list_models()
    model_count = 0
    
    for m in models:
        model_count += 1
        print(f"Model {model_count}: {m.name}")
        print(f"   Display Name: {m.display_name}")
        print(f"   Supported Methods: {m.supported_generation_methods}")
        print()
    
    if model_count == 0:
        print("❌ No models found!")
        print("This means your API key doesn't have access to Gemini models.")
        print()
        print("🔧 Solution:")
        print("1. Go to: https://aistudio.google.com/app/apikey")
        print("2. Delete old API key")
        print("3. Create NEW API key")
        print("4. Make sure you're logged into correct Google account")
    else:
        print(f"✅ Found {model_count} models")
        
except Exception as e:
    print(f"❌ Error listing models: {e}")
    print()
    print("This usually means:")
    print("1. API key is invalid")
    print("2. API key is for wrong Google service")
    print("3. Generative AI API not enabled")
    print()
    print("🔧 Solution:")
    print("1. Go to: https://aistudio.google.com/app/apikey")
    print("2. Create a FRESH API key")
    print("3. Copy the NEW key to .env file")

print()
print("="*60)