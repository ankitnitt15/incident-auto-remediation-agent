from typing import Literal

from pydantic import BaseModel

Severity = Literal["critical", "high", "medium", "low"]
TicketStatus = Literal["open", "triaging", "triaged", "resolved"]
ActionType = Literal["modify_infra", "deploy_service", "update_database", "unrecognized"]
DeployAction = Literal["rollback", "redeploy"]
ChatRole = Literal["user", "assistant"]


class StandardizedAlert(BaseModel):
    """Common schema every source adapter (PagerDuty-like, ZenDuty-like, ...) normalizes into."""

    alert_id: str
    fingerprint: str  # dedup key: stable across retries/duplicate webhook deliveries
    source: str
    service: str
    title: str
    description: str
    severity: Severity
    metric_name: str | None = None
    received_at: str


class Ticket(BaseModel):
    ticket_id: str
    alert_id: str
    service: str
    title: str
    status: TicketStatus
    created_at: str


class TicketComment(BaseModel):
    ticket_id: str
    author: str
    text: str
    created_at: str


class SubagentFindingDraft(BaseModel):
    """What the LLM actually fills in for a subagent finding -- the
    'subagent' label is known by the caller, not the model."""

    summary: str
    evidence: list[str]
    confidence: float


class SubagentFinding(BaseModel):
    """One subagent's structured read on the incident -- persisted raw, and
    folded into the synthesis prompt for the root-cause hypothesis."""

    subagent: Literal["metrics", "logs", "deployment"]
    summary: str
    evidence: list[str]
    confidence: float


class RootCauseHypothesis(BaseModel):
    root_cause: str
    confidence: float
    evidence_summary: str
    recommended_action: str
    contributing_signals: list[str]


class TriageResult(BaseModel):
    ticket_id: str
    hypothesis: RootCauseHypothesis
    findings: list[SubagentFinding]
    llm_calls_used: int
    elapsed_seconds: float
    within_call_budget: bool
    within_time_budget: bool


class ActionRequest(BaseModel):
    """Flattened NL -> action schema. All the fields a Gemini call could fill in
    across the three MCP-style tools; each tool only reads the fields it needs."""

    action_type: ActionType
    service: str
    instruction_summary: str
    replica_count: int | None = None
    feature_flag: str | None = None
    feature_flag_enabled: bool | None = None
    deploy_action: DeployAction | None = None
    target_version: str | None = None
    connection_pool_size: int | None = None


class ActionResult(BaseModel):
    action_type: ActionType
    service: str
    success: bool
    message: str
    before: dict
    after: dict


class ChatTurn(BaseModel):
    role: ChatRole
    content: str
