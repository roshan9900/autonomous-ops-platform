from app.graph.state import AgentState, InvestigationPlanSchema, RootCauseSchema
from app.tools.mock_tools import get_service_status,query_logs,query_metrics, remediate_service, verify_service_health
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
load_dotenv()

model_name = os.getenv("LLM_MODEL", "gemini-1.5-flash")

llm = ChatGoogleGenerativeAI(
    model=model_name,
    temperature=0,
    max_retries=3
)

structured_output = llm.with_structured_output(InvestigationPlanSchema)


def planner_node(state:AgentState)->dict:
    prompt = f"""
    You are an expert Enterprice SRE Planner.
    Analyze the incoming incident ticket and formulate a diagnostic plan.
    Available tools: check_status, query_logs, query_metrics

    Incident: {state['question']}
    """
    plan_obj :InvestigationPlanSchema=structured_output.invoke(prompt)
    return {
        "plan":plan_obj.steps
    }


structure_diagnoser = llm.with_structured_output(RootCauseSchema)
def executor_node(state: AgentState) -> dict:
    plan: List[str] = state.get('plan', [])
    new_observations: List[str] = []

    # 1. First, invoke the actual tools to collect telemetry
    for step in plan:
        action, _, target_service = step.partition(":")
        target_service = target_service.strip() or "payment-service"

        if "status" in action:
            status_data = get_service_status(target_service)
            new_observations.append(
                f"[STATUS] {target_service}: {status_data.get('status')} (Replicas: {status_data.get('replicas_ready')})"
            )
        elif "metrics" in action:
            metric_data = query_metrics(target_service, metric_name="db_latency")
            new_observations.append(
                f"[METRICS] {target_service} {metric_data.get('metric')}: {metric_data.get('value')}{metric_data.get('unit')} (Alert: {metric_data.get('alert')})"
            )
        elif "logs" in action:
            logs = query_logs(target_service)
            new_observations.append(f"[LOGS] {target_service}: {' | '.join(logs[-2:])}")

    # 2. Now let the LLM analyze the real collected evidence!
    all_evidence = "\n".join(state.get('observations', []) + new_observations)
    
    prompt = f"""
    You are an expert Incident Response SRE.
    Analyze the following telemetry evidence and determine the root cause and proposed remediation:

    Telemetry Evidence:
    {all_evidence}
    """
    
    result: RootCauseSchema = structure_diagnoser.invoke(prompt)

    return {
        'observations': new_observations,
        'final_answer': result.diagnosis,
        'is_complete': True,
        'remediation_action': result.proposed_remediation
    }

            

def remediation_node(state:AgentState)->dict:
    action_srt = state.get('remediation_action') or 'restart_pool:payment-service'
    action, _,target_service=action_srt.partition(':')

    result = remediate_service(service_name=target_service,action=action)

    current_attempt = state.get('remediation_attempts',0)+1

    return {
        "remediation_result": result.get("message"),
        "observations": [f"[REMEDIATION EXECUTED] {result.get('message')}"],
        "remediation_attempts":current_attempt
    }

def verification_node(state: AgentState) -> dict:
    """
    Verification Node (Critic):
    Independently verifies that the service returned to healthy state.
    """
    service = "payment-service"
    health = verify_service_health(service, has_remediated=True)
    
    if health.get("verified"):
        status = "VERIFIED_HEALTHY"
        obs = f"[VERIFICATION PASSED] {service} is {health.get('status')} (Latency: {health.get('latency_ms')}ms, Errors: {health.get('error_rate')})"
    else:
        status = "VERIFICATION_FAILED"
        obs = f"[VERIFICATION FAILED] {service} remains {health.get('status')} after remediation"
        
    return {
        "verification_status": status,
        "observations": [obs]
    }



