"""
Voice Agent Dashboard — Web & Phone Demo
==========================================
Serves a premium web dashboard for demonstrating the voice agent.
Two modes: browser-based voice chat (Web) or phone call (Call).

Run with: python dashboard.py
Then open: http://localhost:8080
"""

import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from livekit import api
from pydantic import BaseModel

load_dotenv(".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
AGENT_NAME = os.getenv("AGENT_NAME", "voice-assistant")
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID", "")
CLINIC_PHONE = os.getenv("CLINIC_PHONE", "")

app = FastAPI(title="Bright Smile Dental — Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Models ────────────────────────────────────────────────────────────────────

class CallRequest(BaseModel):
    phone: str


class WebSessionResponse(BaseModel):
    token: str
    url: str
    room: str


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard page."""
    html_path = static_dir / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/web-session")
async def create_web_session():
    """Create a LiveKit room + token for browser-based voice chat."""
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        raise HTTPException(500, "LiveKit credentials not configured in .env")

    room_name = f"web-{uuid.uuid4().hex[:8]}"
    participant_identity = f"user-{uuid.uuid4().hex[:6]}"

    # Generate access token for the browser user
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(participant_identity)
    token.with_name("Web User")
    token.with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
        )
    )

    # Dispatch the agent into this room
    lkapi = api.LiveKitAPI()
    try:
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                room=room_name,
                agent_name=AGENT_NAME,
            )
        )
    finally:
        await lkapi.aclose()

    return WebSessionResponse(
        token=token.to_jwt(),
        url=LIVEKIT_URL,
        room=room_name,
    )


@app.post("/api/call")
async def place_call(req: CallRequest):
    """Place an outbound phone call via SIP trunk."""
    phone = req.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(400, "Phone number must be in E.164 format (start with +)")

    if not OUTBOUND_TRUNK_ID:
        raise HTTPException(500, "OUTBOUND_TRUNK_ID not configured in .env")

    room_name = f"call-{uuid.uuid4().hex[:8]}"

    lkapi = api.LiveKitAPI()
    try:
        # Dispatch agent
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                room=room_name,
                agent_name=AGENT_NAME,
                metadata=json.dumps({"phone_number": phone}),
            )
        )

        # Place the call
        participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone,
                room_name=room_name,
                participant_identity=f"sip_{phone.replace('+', '')}",
                participant_name="Caller",
                play_ringtone=True,
                participant_metadata=json.dumps({"phone_number": phone}),
            )
        )

        return {
            "status": "calling",
            "phone": phone,
            "room": room_name,
            "participant": participant.participant_identity,
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to place call: {exc}")
    finally:
        await lkapi.aclose()


@app.get("/api/config")
async def get_config():
    """Return public config for the frontend."""
    return {
        "agentName": AGENT_NAME,
        "hasOutboundTrunk": bool(OUTBOUND_TRUNK_ID),
        "livekitUrl": LIVEKIT_URL,
        "clinicPhone": CLINIC_PHONE,
    }


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    print(f"\n=> Dashboard running at http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
