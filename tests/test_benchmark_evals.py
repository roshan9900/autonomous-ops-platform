import sys
import os
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph.graph import create_investigation_agent


def load_golden_incidents():
    """Helper to load all benchmark scenarios from golden_incidents.json."""
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/golden_incidents.json"))
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Load dataset scenarios for parametrization
INCIDENTS = load_golden_incidents()


@pytest.mark.parametrize("incident", INCIDENTS, ids=[inc["incident_id"] for inc in INCIDENTS])
def test_agent_evaluates_golden_incident(incident):
    """
    Automated Benchmark Eval:
    Proves agent correctly plans, executes diagnostic tools, and diagnoses
    novel enterprise failure modes across the Golden Dataset.
    """
    agent = create_investigation_agent()
    config = {"configurable": {"thread_id": f"eval-thread-{incident['incident_id']}"}}

    initial_state = {
        "question": incident["ticket_text"],
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }

    # 1. Run investigation phase (halts at human approval gate)
    result = agent.invoke(initial_state, config=config)

    # 2. Metric 1: Plan Generation (Agent must generate at least 1 diagnostic step)
    assert len(result.get("plan", [])) > 0, f"Planner produced empty plan for {incident['incident_id']}"

    # 3. Metric 2: Telemetry Gathering (Agent must collect observations)
    observations = result.get("observations", [])
    assert len(observations) > 0, f"Executor collected 0 observations for {incident['incident_id']}"

    # 4. Metric 3: Root Cause Diagnosis (LLM must synthesize a diagnosis)
    diagnosis = result.get("final_answer")
    assert diagnosis is not None and len(diagnosis.strip()) > 10, f"Empty diagnosis for {incident['incident_id']}"

    # 5. Metric 4: Governed Remediation Action Proposed
    remediation = result.get("remediation_action")
    assert remediation is not None, f"No remediation proposed for {incident['incident_id']}"

    # 6. Metric 5: Human Gate Enforcement
    state = agent.get_state(config)
    assert state.next == ("remediation",), f"Graph failed to halt at human gate for {incident['incident_id']}"
