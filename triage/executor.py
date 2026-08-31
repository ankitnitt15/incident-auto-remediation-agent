"""The Executor: given a ticket_id, fans out the 3 subagents in parallel
(the diagram's "5 calls in parallel" budget -- we only need 3 here),
looks up matching runbooks, and spends one more LLM call synthesizing a
single root-cause hypothesis. Findings are persisted raw to
findings_store; a human-readable summary is posted back to the ticket."""

import concurrent.futures
from datetime import datetime, timezone

from common.gemini_client import generate_content
from observability import runbooks
from shared.budget import BudgetTracker
from shared.models import RootCauseHypothesis, SubagentFinding, TicketComment, TriageResult
from storage import alert_store, findings_store, ticket_store
from triage import prompts, subagents

MAX_PARALLEL_SUBAGENTS = 5  # matches the diagram's "5 calls in parallel" triage budget
SUBAGENT_FNS = [subagents.metrics_subagent, subagents.logs_subagent, subagents.deployment_subagent]


def _format_summary_comment(hypothesis: RootCauseHypothesis, findings: list[SubagentFinding]) -> str:
    contributors = ", ".join(hypothesis.contributing_signals) or "none"
    lines = [
        "**Automated triage summary**",
        f"Root cause (confidence {hypothesis.confidence:.2f}): {hypothesis.root_cause}",
        f"Evidence: {hypothesis.evidence_summary}",
        f"Recommended action: {hypothesis.recommended_action}",
        f"Contributing signals: {contributors}",
        "",
        "Ask me questions in chat, or comment `@agent <instruction>` here to take an action.",
    ]
    return "\n".join(lines)


def run_triage(ticket_id: str) -> TriageResult:
    ticket_conn = ticket_store.get_connection()
    ticket = ticket_store.get_ticket(ticket_conn, ticket_id)
    if ticket is None:
        raise ValueError(f"Unknown ticket_id: {ticket_id}")

    alert_conn = alert_store.get_connection()
    alert = alert_store.get_alert(alert_conn, ticket.alert_id)

    ticket_store.update_status(ticket_conn, ticket_id, "triaging")
    budget = BudgetTracker()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_SUBAGENTS) as pool:
        futures = [pool.submit(fn, alert, budget) for fn in SUBAGENT_FNS]
        findings = [future.result() for future in concurrent.futures.as_completed(futures)]

    findings_conn = findings_store.get_connection()
    for finding in findings:
        findings_store.save_finding(findings_conn, ticket_id, finding)

    runbook_matches = runbooks.query_runbook_index(f"{alert.title} {alert.description}")

    budget.record_call()
    hypothesis = generate_content(
        prompts.build_synthesis_prompt(alert, findings, runbook_matches),
        config={"response_mime_type": "application/json", "response_schema": RootCauseHypothesis},
    ).parsed
    findings_store.save_hypothesis(findings_conn, ticket_id, hypothesis)

    ticket_store.add_comment(ticket_conn, TicketComment(
        ticket_id=ticket_id, author="iar-executor",
        text=_format_summary_comment(hypothesis, findings),
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    ticket_store.update_status(ticket_conn, ticket_id, "triaged")

    return TriageResult(
        ticket_id=ticket_id, hypothesis=hypothesis, findings=findings,
        llm_calls_used=budget.calls_used, elapsed_seconds=budget.elapsed_seconds(),
        within_call_budget=budget.within_call_budget(), within_time_budget=budget.within_time_budget(),
    )


if __name__ == "__main__":
    from ingestion import ingestor
    from observability import deployments as dep_mod, logs as log_mod, metrics as met_mod

    met_mod.seed_metrics("checkout-service", "checkout.latency_p99_ms", [
        ("10:00:00Z", 120.0), ("10:02:00Z", 410.0),
    ])
    log_mod.seed_logs("checkout-service", "checkout-service.app.log", [
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
    ])
    dep_mod.seed_deployments("checkout-service", [
        {"version": "v42", "deployed_at": "2026-07-21T10:01:30Z", "author": "bob",
         "change_summary": "Switch payment client to sync retries"},
    ])

    ticket, _ = ingestor.receive_alert({
        "service_name": "checkout-service", "summary": "High latency", "urgency": "high",
        "details": "p99 latency above threshold", "created_at": "2026-07-21T10:03:00Z",
    }, source="pagerduty")

    result = run_triage(ticket.ticket_id)
    print(result.model_dump_json(indent=2))
