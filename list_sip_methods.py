"""List all SIP methods available in the installed LiveKit SDK."""
import asyncio, os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")

async def main():
    lkapi = api.LiveKitAPI()
    methods = [m for m in dir(lkapi.sip) if not m.startswith('_')]
    print("Available SIP methods:")
    for m in methods:
        print(f"  {m}")
    await lkapi.aclose()

asyncio.run(main())
