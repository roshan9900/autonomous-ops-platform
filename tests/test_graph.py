import sys
import os
import pytest

# Ensure enterprice_ops is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph.state import AgentState
from app.graph.nodes import planner_node, executor_node
from app.graph.graph import create_investigation_agent, should_continue
from app.tools.mock_tools import get_service_status, query_logs, query_metrics


# 1. Test Mock Tools
def test_mock_tools_payment_service():
    """Proves mock tools return degraded telemetry for payment-service."""
    status = get_service_status("payment-service")
    assert status["status"] == "unhealthy"
    assert status["replicas_ready"] == "1/3"

    logs = query_logs("payment-service")
    assert any("connection pool exhausted" in log.lower() for log in logs)

    metrics = query_metrics("payment-service")
    assert metrics["alert"] == "CRITICAL"
    assert metrics["value"] > metrics["threshold"]


# 2. Test Planner Node
def test_planner_node_generates_plan():
    """Proves planner extracts service and formulates structured plan."""
    initial_state = {
        "question": "payment service is down",
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }
    update = planner_node(initial_state)
    assert "plan" in update
    assert len(update["plan"]) == 3
    assert "check_status:payment-service" in update["plan"]


# 3. Test Executor Node
def test_executor_node_gathers_evidence():
    """Proves executor executes plan and diagnoses root cause."""
    planned_state = {
        "question": "payment service is failing",
        "plan": [
            "check_status:payment-service",
            "query_logs:payment-service",
            "query_metrics:payment-service"
        ],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }
    update = executor_node(planned_state)
    assert update["is_complete"] is True
    assert len(update["observations"]) >= 3
    assert update["final_answer"] is not None
    assert "Database connection exhaustion" in update["final_answer"]


# 4. Test State Reducer Behavior
def test_state_reducer_accumulates_observations():
    """Proves LangGraph reducer appends observations across state updates."""
    from langgraph.graph import StateGraph

    # Define minimal test graph with our state reducer
    builder = StateGraph(AgentState)
    builder.add_node("step_one", lambda s: {"observations": ["obs_1"]})
    builder.add_node("step_two", lambda s: {"observations": ["obs_2"]})
    builder.set_entry_point("step_one")
    builder.add_edge("step_one", "step_two")
    builder.set_finish_point("step_two")
    
    test_graph = builder.compile()
    result = test_graph.invoke({
        "question": "test",
        "plan": [],
        "observations": ["initial_obs"],
        "is_complete": False,
        "final_answer": None
    })

    # Reducer must accumulate all 3 items without overwriting!
    assert result["observations"] == ["initial_obs", "obs_1", "obs_2"]


# 5. Test Conditional Routing Decision
def test_conditional_routing_logic():
    """Proves should_continue properly evaluates routing condition."""
    state_incomplete = {"is_complete": False}
    assert should_continue(state_incomplete) == "continue"

    state_complete = {"is_complete": True}
    assert should_continue(state_complete) == "complete"


# 6. Test Full Graph End-to-End
def test_full_graph_execution():
    """Proves entire investigation agent completes successfully from START to END."""
    agent = create_investigation_agent()
    result = agent.invoke({
        "question": "Investigate failure in payment service",
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    },
    config={'configurable':{'thread_id':'test-thread-001'}})

    assert result["is_complete"] is True
    assert len(result["plan"]) > 0
    assert len(result["observations"]) > 0
    assert "ROOT CAUSE" in result["final_answer"]


# 7. Test Human-in-the-Loop Interrupt & Resumption
def test_human_in_the_loop_approval_gate():
    """Proves graph pauses before remediation and resumes only when approved."""
    agent = create_investigation_agent()
    config = {"configurable": {"thread_id": "test-hitl-thread-42"}}

    initial_state = {
        "question": "Payment service is failing",
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }

    # 1. First run: Must halt at 'remediation'
    first_pass = agent.invoke(initial_state, config=config)
    paused_state = agent.get_state(config)

    # Verify execution paused BEFORE remediation
    assert paused_state.next == ("remediation",)
    assert paused_state.values.get("remediation_action") == "restart_pool:payment-service"
    assert paused_state.values.get("remediation_result") is None

    # 2. Simulate human approval: Resume by passing None
    resumed_pass = agent.invoke(None, config=config)
    completed_state = agent.get_state(config)

    # Verify remediation executed and graph reached END
    assert completed_state.next == ()  # Reached END
    assert resumed_pass.get("remediation_result") is not None
    assert any("REMEDIATION EXECUTED" in obs for obs in resumed_pass.get("observations", []))

    
from app.graph.graph import route_verification
from app.graph.nodes import verification_node


# 8. Test Verification Node (Critic)
def test_verification_node_verifies_health():
    """Proves verification node independently verifies healthy state."""
    state = {
        "question": "test",
        "plan": [],
        "observations": [],
        "is_complete": True,
        "final_answer": "ok"
    }
    update = verification_node(state)
    assert update["verification_status"] == "VERIFIED_HEALTHY"
    assert any("VERIFICATION PASSED" in obs for obs in update["observations"])


# 9. Test Verification Routing Decisions
def test_route_verification_logic():
    """Proves route_verification routes to complete, retry, or escalate."""
    # Healthy -> complete
    assert route_verification({"verification_status": "VERIFIED_HEALTHY", "remediation_attempts": 1}) == "complete"

    # Failed but attempt 1 -> retry
    assert route_verification({"verification_status": "VERIFICATION_FAILED", "remediation_attempts": 1}) == "retry"

    # Failed and max attempts reached -> escalate!
    assert route_verification({"verification_status": "VERIFICATION_FAILED", "remediation_attempts": 2}) == "escalate"


# 10. Test Full End-to-End with Verification
def test_full_cycle_with_verification():
    """Proves graph runs through investigation, remediation, and verification."""
    agent = create_investigation_agent()
    config = {"configurable": {"thread_id": "test-full-cycle-99"}}

    # Phase 1: Investigation halts before remediation
    agent.invoke({
        "question": "Payment outage",
        "plan": [],
        "observations": [],
        "is_complete": False,
        "final_answer": None
    }, config=config)

    # Phase 2: Operator approves remediation
    final_result = agent.invoke(None, config=config)

    assert final_result.get("remediation_result") is not None
    assert final_result.get("verification_status") == "VERIFIED_HEALTHY"
    assert any("VERIFICATION PASSED" in obs for obs in final_result.get("observations", []))
