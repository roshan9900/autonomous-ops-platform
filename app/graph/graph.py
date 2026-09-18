from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
load_dotenv()


from app.graph.state import AgentState
from app.graph.nodes import (
    planner_node, 
    executor_node, 
    remediation_node, 
    verification_node
)


def should_continue(state: AgentState) -> str:
    if state.get('is_complete', False):
        return 'complete'
    return 'continue'


def route_verification(state: AgentState) -> str:
    """
    Evaluates post-remediation health:
    - If verified healthy -> terminate at END
    - If failed but under max attempts -> retry investigation
    - If max attempts reached -> escalate to human
    """
    if state.get("verification_status") == "VERIFIED_HEALTHY":
        return "complete"
    
    if state.get("remediation_attempts", 0) >= 2:
        return "escalate"
        
    return "retry"


def create_investigation_agent(checkpointer=None) -> StateGraph:
    builder = StateGraph(AgentState)

    # 1. Register all 4 nodes
    builder.add_node("planner", planner_node)
    builder.add_node("executor", executor_node)
    builder.add_node("remediation", remediation_node)
    builder.add_node("verification", verification_node)

    # 2. Wire entry and investigation
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "executor")

    # 3. Investigation routing (loop back to executor or proceed to remediation)
    builder.add_conditional_edges(
        "executor",
        should_continue,
        {
            "continue": "executor",
            "complete": "remediation"
        }
    )

    # 4. Remediation leads to independent verification
    builder.add_edge("remediation", "verification")

    # 5. Verification routing (complete, retry, or escalate)
    builder.add_conditional_edges(
        "verification",
        route_verification,
        {
            "complete": END,
            "retry": "executor",
            "escalate": END
        }
    )

    if checkpointer is None:
        checkpointer = MemorySaver()

    # 6. Compile with human-in-the-loop gate before remediation
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["remediation"]
    )
