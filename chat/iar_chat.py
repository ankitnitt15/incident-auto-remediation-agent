"""IAR chat: what the on-call engineer gets after triage. Scoped to one
ticket, backed by its alert, root-cause hypothesis, and subagent findings.
Every message is first offered to the Command Executor -- if it reads as an
action request (rollback, scale, toggle a flag, ...) it's executed there and
the confirmation is returned directly; otherwise it falls through to a
plain question-answering call over the incident context."""

from common.gemini_client import generate_content
from actions import command_executor
from chat import prompts
from shared.models import ChatTurn
from storage import alert_store, findings_store, ticket_store


def ask(ticket_id: str, user_message: str, history: list[ChatTurn] | None = None,
        requested_by: str = "on-call-engineer") -> str:
    history = history or []

    action_result = command_executor.try_execute_from_text(
        ticket_id, user_message, requested_by=requested_by, origin="iar-chat"
    )
    if action_result is not None:
        return action_result.message

    ticket_conn = ticket_store.get_connection()
    ticket = ticket_store.get_ticket(ticket_conn, ticket_id)
    if ticket is None:
        return f"Unknown ticket_id: {ticket_id}"

    alert_conn = alert_store.get_connection()
    alert = alert_store.get_alert(alert_conn, ticket.alert_id)

    findings_conn = findings_store.get_connection()
    hypothesis = findings_store.get_hypothesis(findings_conn, ticket_id)
    findings = findings_store.get_findings(findings_conn, ticket_id)

    prompt = prompts.build_chat_prompt(alert, hypothesis, findings, history, user_message)
    return generate_content(prompt).text


if __name__ == "__main__":
    from datetime import datetime, timezone

    from ingestion import ingestor
    from observability import deployments as dep_mod, logs as log_mod, metrics as met_mod
    from triage import executor as triage_executor

    met_mod.seed_metrics("checkout-service", "checkout.latency_p99_ms", [
        ("10:00:00Z", 120.0), ("10:02:00Z", 410.0),
    ])
    log_mod.seed_logs("checkout-service", "checkout-service.app.log", [
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
    ])
    dep_mod.seed_deployments("checkout-service", [
        {"version": "v42", "deployed_at": "2026-07-21T10:01:30Z", "author": "bob",
         "change_summary": "Switch payment client to sync retries"},
    ])

    ticket, _ = ingestor.receive_alert({
        "service_name": "checkout-service", "summary": "High latency", "urgency": "high",
        "details": "p99 latency above threshold",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, source="pagerduty")
    triage_executor.run_triage(ticket.ticket_id)

    print(ask(ticket.ticket_id, "What do you think is causing this?"))
