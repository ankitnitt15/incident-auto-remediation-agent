"""End-to-end demo: alerts -> tickets -> triage -> IAR chat -> command
executor. Run with `python main.py`. Delete data/ first for a clean run --
alerts dedupe by (service, title) fingerprint, so rerunning without clearing
data/ folds the demo alerts back into their existing tickets."""

from datetime import datetime, timezone

import scenarios
from actions import command_executor
from chat import iar_chat
from ingestion import ingestor
from shared.models import TicketComment
from storage import infra_state, ticket_store
from triage import executor as triage_executor


def _print_header(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def ingest_all() -> dict[str, object]:
    _print_header("1. Ingesting alerts -> tickets")
    tickets = {}
    for scenario in scenarios.SCENARIOS:
        ticket, is_duplicate = ingestor.receive_alert(scenario["payload"], source=scenario["source"])
        tickets[scenario["name"]] = ticket
        print(f"  [{scenario['name']}] ticket={ticket.ticket_id} service={ticket.service} "
              f"duplicate={is_duplicate}")
    return tickets


def triage_all(tickets: dict[str, object]) -> dict[str, object]:
    _print_header("2. Running triage (parallel subagents, budget-tracked)")
    results = {}
    for name, ticket in tickets.items():
        result = triage_executor.run_triage(ticket.ticket_id)
        results[name] = result
        budget_ok = "OK" if (result.within_call_budget and result.within_time_budget) else "OVER"
        print(f"\n  [{name}] ticket={ticket.ticket_id}")
        print(f"    root cause: {result.hypothesis.root_cause}")
        print(f"    confidence: {result.hypothesis.confidence:.2f}")
        print(f"    recommended action: {result.hypothesis.recommended_action}")
        print(f"    budget: {result.llm_calls_used}/20 LLM calls, "
              f"{result.elapsed_seconds:.1f}s/90s p99 target [{budget_ok}]")
    return results


def chat_demo(tickets: dict[str, object]) -> None:
    _print_header("3. IAR chat -- on-call engineer asks a follow-up question")
    ticket = tickets["orders-db-pool-exhaustion"]
    question = "What's the evidence this is a connection pool issue and not something else?"
    print(f"  [chat] on-call-engineer: {question}")
    reply = iar_chat.ask(ticket.ticket_id, question)
    print(f"  [chat] iar-chat: {reply}")


def tag_triggered_action_demo(tickets: dict[str, object]) -> None:
    _print_header("4. Tag-triggered action -- '@agent' comment on a ticket")
    ticket = tickets["checkout-bad-deploy"]
    before = infra_state.get_resource("checkout-service")
    print(f"  [infra_state before] checkout-service: {before}")

    conn = ticket_store.get_connection()
    comment = ticket_store.add_comment(conn, TicketComment(
        ticket_id=ticket.ticket_id, author="on-call-engineer",
        text="@agent rollback the last deploy for checkout-service",
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    print(f"  [comment] {comment.author}: {comment.text}")

    result = command_executor.process_ticket_comment(ticket.ticket_id, comment)
    print(f"  [action] success={result.success} message={result.message}")
    print(f"  [infra_state after] checkout-service: {infra_state.get_resource('checkout-service')}")


def chat_triggered_action_demo(tickets: dict[str, object]) -> None:
    _print_header("5. Chat-triggered action -- ask the IAR chat directly")
    ticket = tickets["payments-feature-flag-500s"]
    before = infra_state.get_resource("payments-service")
    print(f"  [infra_state before] payments-service: {before}")

    instruction = "Please disable the new-pricing-engine feature flag on payments-service."
    print(f"  [chat] on-call-engineer: {instruction}")
    reply = iar_chat.ask(ticket.ticket_id, instruction)
    print(f"  [chat] iar-chat: {reply}")
    print(f"  [infra_state after] payments-service: {infra_state.get_resource('payments-service')}")


def main() -> None:
    infra_state.seed(scenarios.initial_infra_state())
    scenarios.seed_observability_data()

    tickets = ingest_all()
    triage_all(tickets)
    chat_demo(tickets)
    tag_triggered_action_demo(tickets)
    chat_triggered_action_demo(tickets)


if __name__ == "__main__":
    main()
