from typing import TypedDict, List, Annotated, Optional
from operator import add
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

class AgentState(TypedDict):
    """
    The share state schema for the enterprice ops investigation agent
    """
    question: str
    plan: List[str]
    observations: Annotated[List[str],add]
    is_complete: bool
    final_answer: Optional[str]
    remediation_action:Optional[str]

    remediation_result:Optional[str]

    verification_status :Optional[str]
    remediation_attempts: int


class InvestigationPlanSchema(BaseModel):
    target_service: str = Field(description="Identify microservice name (e.g., payment-service)")
    hypothesis: str = Field(description='Initial reasoning on why this service might be degraded')

    steps: List[str] = Field(
        description="Ordered tool action strings, e.g.['check_status:payment-service','check_logs: payment-service']"
    )

class RootCauseSchema(BaseModel):
    diagnosis:str=Field(description="Synthesized root cause analysis based strictly on observations")
    proposed_remediation:str=Field(description="Exact remediation action to take, e.g. 'restart_pool:payment-service")
