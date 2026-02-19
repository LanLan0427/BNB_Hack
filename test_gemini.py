
import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = "You are a helpful assistant."

async def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        return

    print(f"🔑 API Key found: {api_key[:5]}...{api_key[-5:]}")

    try:
        client = genai.Client(api_key=api_key)
        model_name = "gemini-2.0-flash"
        
        print(f"🤖 Testing model: {model_name}...")
        
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Hello, suggest a random crypto coin.",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        print("✅ Success! Response:")
        print(response.text)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
