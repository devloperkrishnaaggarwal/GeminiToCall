"""Quick test: verify Google API key can access Gemini Live API."""
import asyncio
import os
from dotenv import load_dotenv
from livekit.plugins import google

load_dotenv(".env")
key = os.getenv("GOOGLE_API_KEY", "")
print(f"API Key loaded: {key[:10]}...{key[-4:] if len(key) > 14 else '(short)'}")
print(f"Key length: {len(key)}")

async def test():
    try:
        model = google.realtime.RealtimeModel(
            model="gemini-2.0-flash-exp",
            voice="Puck",
            instructions="You are a test assistant.",
            modalities=["AUDIO"],
            api_key=key,
        )
        # Try to create a session to verify the API key is accepted
        session = model.session(
            chat_ctx=None,
            fnc_ctx=None,
        )
        print("✅ RealtimeModel session created — API key appears valid!")
        await session.aclose()
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
