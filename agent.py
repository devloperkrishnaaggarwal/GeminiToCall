"""
Voice Call Agent — Bright Smile Dental AI Receptionist
=======================================================
English-speaking AI receptionist (Sarah) for Bright Smile Dental, Austin TX.
Books Google Calendar appointments + sends Gmail confirmations.

Run with: python agent.py start
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, Annotated

from dotenv import load_dotenv
from livekit import agents, api
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, WorkerOptions, cli
from livekit.agents import llm
from google.genai import types
from livekit.plugins import google

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv(".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice-agent")

OUTBOUND_TRUNK_ID: str = os.getenv("OUTBOUND_TRUNK_ID", "")
SIP_DOMAIN:        str = os.getenv("VOBIZ_SIP_DOMAIN", "")
AGENT_NAME:        str = os.getenv("AGENT_NAME", "voice-assistant")

# ── Agent Prompt (loaded from .env) ───────────────────────────────────────────
_raw_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
AGENT_INSTRUCTIONS = _raw_prompt.replace("\\n", "\n") if _raw_prompt else ""
AGENT_GREETING = os.getenv("AGENT_GREETING", "Greet the caller warmly.")


# ── Agent with Tools ──────────────────────────────────────────────────────────
class BrightSmileAgent(Agent):
    def __init__(self, ctx: JobContext, phone_number: Optional[str] = None) -> None:
        super().__init__(instructions=AGENT_INSTRUCTIONS)
        self._ctx = ctx
        self._phone_number = phone_number

    @llm.function_tool(
        description=(
            "Book a dental appointment for the patient. Call this only after collecting "
            "patient_name, phone, email, service, appointment_date (YYYY-MM-DD), and "
            "appointment_time (HH:MM 24-hour). Creates a Google Calendar event and sends "
            "a Gmail confirmation to the patient."
        )
    )
    async def book_appointment(
        self,
        patient_name:     Annotated[str, "Full name of the patient"],
        phone:            Annotated[str, "Patient's phone number"],
        email:            Annotated[str, "Patient's email address for confirmation"],
        service:          Annotated[str, "Dental service requested (e.g. 'Dental Checkup', 'RCT', 'Braces')"],
        appointment_date: Annotated[str, "Date in YYYY-MM-DD format"],
        appointment_time: Annotated[str, "Time in HH:MM 24-hour format (e.g. '10:00', '14:00')"],
    ) -> str:
        logger.info(
            "Booking appointment: %s | %s | %s | %s %s",
            patient_name, service, email, appointment_date, appointment_time
        )
        try:
            # Import here to avoid startup errors if Google creds not yet configured
            from google_services import create_calendar_event, send_confirmation_email

            # 1 — Create Google Calendar event
            event = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: create_calendar_event(
                    patient_name=patient_name,
                    service=service,
                    date_str=appointment_date,
                    time_str=appointment_time,
                    phone=phone,
                    email=email,
                )
            )

            # 2 — Send Gmail confirmation
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: send_confirmation_email(
                    patient_name=patient_name,
                    patient_email=email,
                    service=service,
                    date_str=appointment_date,
                    time_str=appointment_time,
                )
            )

            # Format a nice display time for the agent to read
            try:
                dt = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                display_time = dt.strftime("%d %B, %I:%M %p")
            except ValueError:
                display_time = f"{appointment_date} at {appointment_time}"

            return (
                f"Appointment successfully booked! "
                f"Patient: {patient_name}, Service: {service}, "
                f"Date/Time: {display_time}. "
                f"Confirmation email sent to {email}."
            )

        except KeyError as e:
            logger.warning("Google credentials missing: %s", e)
            return (
                f"Appointment details noted but Google integration not configured yet "
                f"(missing env var: {e}). Patient: {patient_name}, {service} on "
                f"{appointment_date} at {appointment_time}. Email: {email}."
            )
        except Exception as exc:
            logger.error("Appointment booking failed: %s", exc)
            return f"There was a technical problem with booking: {exc}. Please manually note: {patient_name}, {service}, {appointment_date} {appointment_time}, {email}."

    @llm.function_tool(description="Transfer the call to a human staff member or doctor.")
    async def transfer_call(
        self,
        destination: Annotated[Optional[str], "Phone number or SIP URI to transfer to"] = None,
    ) -> str:
        if destination is None:
            destination = os.getenv("DEFAULT_TRANSFER_NUMBER", "")
            if not destination:
                return "Transfer number is not configured. Please connect the caller manually."

        if "@" not in destination:
            clean = destination.replace("tel:", "").replace("sip:", "")
            destination = f"sip:{clean}@{SIP_DOMAIN}" if SIP_DOMAIN else f"tel:{clean}"
        elif not destination.startswith("sip:"):
            destination = f"sip:{destination}"

        participant_identity: Optional[str] = None
        if self._phone_number:
            participant_identity = f"sip_{self._phone_number.replace('+', '')}"
        else:
            for p in self._ctx.room.remote_participants.values():
                participant_identity = p.identity
                break

        if not participant_identity:
            return "Transfer failed: caller identity not found."

        try:
            await self._ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self._ctx.room.name,
                    participant_identity=participant_identity,
                    transfer_to=destination,
                    play_dialtone=False,
                )
            )
            return "Transfer initiated."
        except Exception as exc:
            return f"Transfer error: {exc}"


# ── Entrypoint ────────────────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext) -> None:
    logger.info("Job received for room: %s", ctx.room.name)

    phone_number: Optional[str] = None
    metadata = getattr(ctx.job, "metadata", "") or ""
    if metadata:
        try:
            meta = json.loads(metadata)
            phone_number = meta.get("phone_number")
        except (json.JSONDecodeError, AttributeError):
            phone_number = metadata.strip() or None

    await ctx.connect()
    logger.info("Connected to room: %s", ctx.room.name)

    # Outbound: dial the phone number
    if phone_number and OUTBOUND_TRUNK_ID:
        logger.info("Placing outbound call to %s", phone_number)
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    room_name=ctx.room.name,
                    participant_identity=f"sip_{phone_number.replace('+', '')}",
                    participant_name="Caller",
                    play_ringtone=True,
                )
            )
        except Exception as exc:
            logger.error("Failed to place outbound call: %s", exc)
            return

    logger.info("Waiting for participant...")
    participant = await ctx.wait_for_participant()
    logger.info("Participant joined: %s", participant.identity)

    # ── Gemini Live API ───────────────────────────────────────────────────────
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            voice="Sulafat",   # female — warm, confident, professional (Puck was male)
            temperature=0.6,
            modalities=["AUDIO"],
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,  # disable thinking — eliminates 1-3s latency
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    silence_duration_ms=300,
                    prefix_padding_ms=100,
                )
            ),
        )
    )

    await session.start(
        room=ctx.room,
        agent=BrightSmileAgent(ctx, phone_number),
        room_input_options=RoomInputOptions(
            participant_identity=participant.identity,
        ),
    )
    logger.info("Session started for: %s", participant.identity)

    # Greeting (configured via AGENT_GREETING in .env)
    await session.generate_reply(
        instructions=AGENT_GREETING
    )

    # Keep alive until caller hangs up
    end_call = asyncio.Event()

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p):
        if p.identity == participant.identity:
            logger.info("Caller disconnected")
            end_call.set()

    await end_call.wait()
    logger.info("Call ended — participant disconnected")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=AGENT_NAME,
        )
    )
