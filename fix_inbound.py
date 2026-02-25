"""Create dispatch rule with ONLY valid proto fields."""
import asyncio
import os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")
TRUNK_ID = "ST_6nDRxpxDmZ92"


async def main():
    lkapi = api.LiveKitAPI()
    try:
        print(f"Creating dispatch rule for trunk {TRUNK_ID}...")

        # Only use fields confirmed to exist: 'rule' and 'trunk_ids'
        rule = await lkapi.sip.create_sip_dispatch_rule(
            api.CreateSIPDispatchRuleRequest(
                rule=api.SIPDispatchRule(
                    dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                        room_prefix="call-",
                    )
                ),
                trunk_ids=[TRUNK_ID],
            )
        )
        print(f"✅ Dispatch rule created: {rule.sip_dispatch_rule_id}")

    except Exception as e:
        print(f"create_sip_dispatch_rule failed: {e}")
        # Try without trunk_ids restriction (match all trunks)
        try:
            print("Trying without trunk restriction...")
            rule = await lkapi.sip.create_sip_dispatch_rule(
                api.CreateSIPDispatchRuleRequest(
                    rule=api.SIPDispatchRule(
                        dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                            room_prefix="call-",
                        )
                    ),
                )
            )
            print(f"✅ Dispatch rule created (no trunk filter): {rule.sip_dispatch_rule_id}")
        except Exception as e2:
            print(f"Also failed: {e2}")
            import traceback; traceback.print_exc()
    finally:
        await lkapi.aclose()


asyncio.run(main())
