"""
SIP Trunk Setup — LiveKit ↔ Vobiz
===================================
CLI script for one-time configuration of LiveKit SIP trunks and dispatch rules.

Commands:
    python setup_trunk.py create-outbound   — Create outbound trunk (LiveKit → Vobiz → PSTN)
    python setup_trunk.py create-inbound    — Create inbound trunk  (PSTN → Vobiz → LiveKit)
    python setup_trunk.py create-dispatch   — Create dispatch rule (auto-spawn agent on inbound call)
    python setup_trunk.py list              — List all SIP trunks and dispatch rules

After running create-outbound, copy the printed OUTBOUND_TRUNK_ID into your .env file.
After running create-inbound, copy the printed INBOUND_TRUNK_ID into your .env file.
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")

# ── Env helpers ───────────────────────────────────────────────────────────────

def _require(var: str) -> str:
    value = os.getenv(var, "").strip()
    if not value:
        print(f"[ERROR] Missing required env var: {var}")
        print("        Set it in your .env file and try again.")
        sys.exit(1)
    return value


# ── Commands ──────────────────────────────────────────────────────────────────

async def create_outbound() -> None:
    """
    Create a LiveKit outbound SIP trunk using Vobiz credentials.
    This trunk is used when the agent places outgoing calls to phone numbers.
    """
    sip_domain = _require("VOBIZ_SIP_DOMAIN")
    username = _require("VOBIZ_USERNAME")
    password = _require("VOBIZ_PASSWORD")
    number = _require("VOBIZ_OUTBOUND_NUMBER")

    print(f"\nCreating outbound SIP trunk...")
    print(f"  SIP Domain : {sip_domain}")
    print(f"  Username   : {username}")
    print(f"  DID Number : {number}")

    lkapi = api.LiveKitAPI()
    try:
        trunk = await lkapi.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name="Vobiz Outbound Trunk",
                    address=sip_domain,
                    auth_username=username,
                    auth_password=password,
                    numbers=[number],
                )
            )
        )
        print(f"\n✅ Outbound trunk created!")
        print(f"   Trunk ID  : {trunk.sip_trunk_id}")
        print(f"\n>>> Add this to your .env file:")
        print(f"    OUTBOUND_TRUNK_ID={trunk.sip_trunk_id}")
    except Exception as exc:
        print(f"\n❌ Failed: {exc}")
    finally:
        await lkapi.aclose()


async def create_inbound() -> None:
    """
    Create a LiveKit inbound SIP trunk for your Vobiz DID number.
    Inbound calls from that number will be routed to LiveKit.

    IMPORTANT: Before running this, update your Vobiz trunk's inbound_destination
    to your LiveKit SIP URI (found in LiveKit Dashboard → Settings → Project → SIP URI).
    Remove the 'sip:' prefix when setting it in Vobiz.
    """
    number = _require("VOBIZ_OUTBOUND_NUMBER")

    livekit_sip_uri = os.getenv("LIVEKIT_SIP_URI", "").strip()
    if not livekit_sip_uri:
        print("[WARNING] LIVEKIT_SIP_URI not set. Find this in LiveKit Dashboard → Settings → SIP URI")
        print("          The inbound trunk will be created, but you must still configure Vobiz separately.")

    print(f"\nCreating inbound SIP trunk...")
    print(f"  DID Number       : {number}")
    print(f"  LiveKit SIP URI  : {livekit_sip_uri or '(not set)'}")

    lkapi = api.LiveKitAPI()
    try:
        trunk = await lkapi.sip.create_sip_inbound_trunk(
            api.CreateSIPInboundTrunkRequest(
                trunk=api.SIPInboundTrunkInfo(
                    name="Vobiz Inbound Trunk",
                    numbers=[number],
                    # Allow connections from all IPs (restrict in production)
                    allowed_addresses=["0.0.0.0/0"],
                )
            )
        )
        print(f"\n✅ Inbound trunk created!")
        print(f"   Trunk ID  : {trunk.sip_trunk_id}")
        print(f"\n>>> Add this to your .env file:")
        print(f"    INBOUND_TRUNK_ID={trunk.sip_trunk_id}")
        print(f"\n>>> Next: In your Vobiz dashboard, set the inbound_destination for your trunk to:")
        print(f"    {livekit_sip_uri.replace('sip:', '') if livekit_sip_uri else '<your-project>.sip.livekit.cloud'}")
    except Exception as exc:
        print(f"\n❌ Failed: {exc}")
    finally:
        await lkapi.aclose()


async def create_dispatch() -> None:
    """
    Create a LiveKit dispatch rule so that inbound SIP calls automatically
    spawn the voice agent.
    """
    inbound_trunk_id = _require("INBOUND_TRUNK_ID")
    agent_name = os.getenv("AGENT_NAME", "voice-assistant")

    print(f"\nCreating dispatch rule...")
    print(f"  Inbound Trunk ID : {inbound_trunk_id}")
    print(f"  Agent Name       : {agent_name}")

    lkapi = api.LiveKitAPI()
    try:
        rule = await lkapi.sip.create_sip_dispatch_rule(
            api.CreateSIPDispatchRuleRequest(
                rule=api.SIPDispatchRule(
                    dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                        room_prefix="call-",
                    )
                ),
                trunk_ids=[inbound_trunk_id],
                name="Vobiz Inbound Dispatch",
                # Tell LiveKit which agent worker to dispatch
                metadata=f'{{"agent_name": "{agent_name}"}}',
            )
        )
        print(f"\n✅ Dispatch rule created!")
        print(f"   Rule ID : {rule.sip_dispatch_rule_id}")
        print(f"\n   Inbound calls to your Vobiz number will now auto-spawn '{agent_name}'.")
    except Exception as exc:
        print(f"\n❌ Failed: {exc}")
    finally:
        await lkapi.aclose()


async def list_all() -> None:
    """List all SIP trunks (inbound + outbound) and dispatch rules."""
    lkapi = api.LiveKitAPI()
    try:
        # Outbound trunks
        out = await lkapi.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        print("\n── Outbound Trunks ──────────────────────────────")
        if out.items:
            for t in out.items:
                print(f"  ID      : {t.sip_trunk_id}")
                print(f"  Name    : {t.name}")
                print(f"  Address : {t.address}")
                print(f"  Numbers : {', '.join(t.numbers)}")
                print()
        else:
            print("  (none)")

        # Inbound trunks
        inp = await lkapi.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
        print("── Inbound Trunks ───────────────────────────────")
        if inp.items:
            for t in inp.items:
                print(f"  ID      : {t.sip_trunk_id}")
                print(f"  Name    : {t.name}")
                print(f"  Numbers : {', '.join(t.numbers)}")
                print()
        else:
            print("  (none)")

        # Dispatch rules
        rules = await lkapi.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
        print("── Dispatch Rules ───────────────────────────────")
        if rules.items:
            for r in rules.items:
                print(f"  ID     : {r.sip_dispatch_rule_id}")
                print(f"  Name   : {r.name}")
                print(f"  Trunks : {', '.join(r.trunk_ids)}")
                print()
        else:
            print("  (none)")
    except Exception as exc:
        print(f"\n❌ Failed to list: {exc}")
    finally:
        await lkapi.aclose()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set up LiveKit ↔ Vobiz SIP trunks and dispatch rules"
    )
    parser.add_argument(
        "command",
        choices=["create-outbound", "create-inbound", "create-dispatch", "list"],
        help="Command to run",
    )
    args = parser.parse_args()

    commands = {
        "create-outbound": create_outbound,
        "create-inbound": create_inbound,
        "create-dispatch": create_dispatch,
        "list": list_all,
    }

    asyncio.run(commands[args.command]())


if __name__ == "__main__":
    main()
