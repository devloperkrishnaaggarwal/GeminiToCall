"""Inspect all LiveKit SIP inbound trunks and dispatch rules in detail."""
import asyncio
import os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")

async def main():
    lkapi = api.LiveKitAPI()
    try:
        print("── Inbound Trunks ──")
        inp = await lkapi.sip.list_inbound_trunk(api.ListSIPInboundTrunkRequest())
        if inp.items:
            for t in inp.items:
                print(f"  ID       : {t.sip_trunk_id}")
                print(f"  Name     : {t.name}")
                print(f"  Numbers  : {list(t.numbers)}")
                print(f"  Allowed  : {list(t.allowed_addresses)}")
                print()
        else:
            print("  (none)")

        print("── Dispatch Rules ──")
        rules = await lkapi.sip.list_dispatch_rules(api.ListSIPDispatchRuleRequest())
        if rules.items:
            for r in rules.items:
                print(f"  ID       : {r.sip_dispatch_rule_id}")
                print(f"  Name     : {r.name}")
                print(f"  Trunks   : {list(r.trunk_ids)}")
                print(f"  Metadata : {r.metadata}")
                print()
        else:
            print("  (none)")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        await lkapi.aclose()

asyncio.run(main())
