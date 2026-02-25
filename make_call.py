"""
Make Outbound Call — LiveKit → Vobiz → PSTN
============================================
CLI script to initiate an outbound phone call via LiveKit + Vobiz SIP.

The call flow:
  1. This script creates a SIP participant in a LiveKit room.
  2. LiveKit routes the call via Vobiz SIP trunk to the real phone number.
  3. The person answers → they join the LiveKit room as a SIP participant.
  4. The running agent.py worker auto-picks up the job and starts talking.

Usage:
    python make_call.py --phone +1234567890
    python make_call.py --phone +919876543210 --room my-call-room
    python make_call.py --phone +1234567890 --list-trunks
"""

import argparse
import asyncio
import json
import os
import sys
import uuid

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")


def _require(var: str) -> str:
    value = os.getenv(var, "").strip()
    if not value:
        print(f"[ERROR] Missing required env var: {var}")
        print(f"        Set it in your .env file and try again.")
        sys.exit(1)
    return value


async def make_call(phone_number: str, room_name: str) -> None:
    """Place an outbound SIP call via LiveKit + Vobiz."""
    trunk_id = _require("OUTBOUND_TRUNK_ID")

    print(f"\n📞 Placing outbound call...")
    print(f"   Phone   : {phone_number}")
    print(f"   Room    : {room_name}")
    print(f"   Trunk   : {trunk_id}")

    lkapi = api.LiveKitAPI()
    try:
        # Ask LiveKit to create an agent dispatch so our agent joins the room
        # The agent worker (agent.py) must be running for this to work.
        await lkapi.agent.create_agent_dispatch(
            api.CreateAgentDispatchRequest(
                room=room_name,
                agent_name=os.getenv("AGENT_NAME", "voice-assistant"),
                metadata=json.dumps({"phone_number": phone_number}),
            )
        )
        print(f"   Agent dispatch created ✅")

        # Now create the SIP participant (places the actual call)
        participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=phone_number,
                room_name=room_name,
                participant_identity=f"sip_{phone_number.replace('+', '')}",
                participant_name="Caller",
                play_ringtone=True,
                # Pass metadata so agent knows it's outbound
                participant_metadata=json.dumps({"phone_number": phone_number}),
            )
        )

        print(f"\n✅ Call initiated!")
        print(f"   Participant identity : {participant.participant_identity}")
        print(f"   Room                 : {room_name}")
        print(f"\n   The phone should be ringing at {phone_number}.")
        print(f"   When answered, the Gemini voice agent will begin the conversation.")
        print(f"\n   Agent must be running: python agent.py start")

    except Exception as exc:
        print(f"\n❌ Failed to place call: {exc}")
        sys.exit(1)
    finally:
        await lkapi.aclose()


async def list_trunks() -> None:
    """Quick listing of outbound trunks to verify setup."""
    lkapi = api.LiveKitAPI()
    try:
        trunks = await lkapi.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        if trunks.items:
            print("\n── Outbound Trunks ──")
            for t in trunks.items:
                print(f"  {t.sip_trunk_id}  |  {t.name}  |  {t.address}  |  {', '.join(t.numbers)}")
        else:
            print("\nNo outbound trunks found. Run: python setup_trunk.py create-outbound")
    finally:
        await lkapi.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Place an outbound phone call via LiveKit + Vobiz",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python make_call.py --phone +1234567890
  python make_call.py --phone +919876543210 --room sales-call-001
  python make_call.py --list-trunks
        """,
    )
    parser.add_argument(
        "--phone", "-p",
        metavar="NUMBER",
        help="Phone number to call in E.164 format (e.g. +1234567890)",
    )
    parser.add_argument(
        "--room", "-r",
        metavar="ROOM",
        default=None,
        help="LiveKit room name (default: auto-generated)",
    )
    parser.add_argument(
        "--list-trunks",
        action="store_true",
        help="List existing outbound SIP trunks and exit",
    )
    args = parser.parse_args()

    if args.list_trunks:
        asyncio.run(list_trunks())
        return

    if not args.phone:
        parser.print_help()
        print("\n[ERROR] --phone is required to place a call.")
        sys.exit(1)

    # Validate E.164 format
    phone = args.phone.strip()
    if not phone.startswith("+"):
        print(f"[ERROR] Phone number must be in E.164 format (start with +). Got: {phone}")
        sys.exit(1)

    room = args.room or f"call-{uuid.uuid4().hex[:8]}"

    asyncio.run(make_call(phone, room))


if __name__ == "__main__":
    main()
