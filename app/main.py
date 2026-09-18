import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.graph.graph import create_investigation_agent
from dotenv import load_dotenv
load_dotenv()


def main():
    print("*" * 80)
    print("🚀 ENTERPRISE OPERATIONS INVESTIGATION AGENT (WITH HUMAN APPROVAL GATE)")
    print("*" * 80)

    app = create_investigation_agent()
    config = {'configurable': {'thread_id': 'incident-001'}}

    initial_state = {
        "question": "Payment service is failing and users cannot checkout. Find the root cause.",
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }

    # =========================================================================
    # STAGE 1: AUTONOMOUS INVESTIGATION (Runs until Human Gate)
    # =========================================================================
    print("\n[STAGE 1] Running Autonomous Investigation...")
    result = app.invoke(initial_state, config=config)

    print("\n🔍 Collected Evidence So Far:")
    for obs in result.get("observations", []):
        print(f"  • {obs}")

    print("\n📄 Diagnosis:")
    print(result.get("final_answer"))

    # =========================================================================
    # STAGE 2: HUMAN APPROVAL GATE (Inspect Pending State)
    # =========================================================================
    state = app.get_state(config)
    print("\n" + "=" * 80)
    print(f"⏸️ GRAPH PAUSED AT HUMAN GATE!")
    print(f"Pending Next Node: {state.next}")  # Should show: ('remediation',)
    print(f"Proposed Remediation Action: {state.values.get('remediation_action')}")
    print("=" * 80)

    # In a real app, this waits for a Slack button click or Webhook.
    # Here, we simulate operator approval:
    user_approval = input("\n[HUMAN OPERATOR] Approve this remediation action? (y/n): ")

    if user_approval.lower() == 'y':
        print("\n[STAGE 3] Human approved! Resuming execution...")
        # Notice: passing None signals LangGraph to resume from the breakpoint!
        final_result = app.invoke(None, config=config)

        print("\n✅ Remediation Result:")
        print(final_result.get("remediation_result"))
        print("\nAll Observations (including remediation):")
        for obs in final_result.get("observations", []):
            print(f"  • {obs}")
    else:
        print("\n❌ Remediation rejected by operator. Handing over to SRE team.")


if __name__ == '__main__':
    main()
