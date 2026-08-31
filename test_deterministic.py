"""Deterministic tests -- no live Gemini calls needed. Exercises the budget
tracker, alert dedup/upsert, ticket tag-detection, and the MCP tools'
infra_state mutations directly. LLM-backed behavior (subagent findings, root
cause synthesis, chat, NL->action parsing) is a live, end-to-end concern
instead -- see the README's "Running it" section for `main.py`.
"""

from pathlib import Path

from actions import mcp_tools
from shared.budget import BudgetExceededError, BudgetTracker
from shared.models import ActionRequest, StandardizedAlert
from storage import alert_store, infra_state, ticket_store


def test_budget_tracker_caps_calls():
    tracker = BudgetTracker(max_llm_calls=2, time_budget_seconds=90.0)
    tracker.record_call()
    tracker.record_call()
    raised = False
    try:
        tracker.record_call()
    except BudgetExceededError:
        raised = True
    if raised and tracker.calls_used == 2 and tracker.within_call_budget():
        print("PASS: BudgetTracker raises once the call ceiling is hit, and reports usage correctly")
    else:
        print(f"FAIL: raised={raised} calls_used={tracker.calls_used}")


def test_budget_tracker_time_budget():
    tracker = BudgetTracker(max_llm_calls=20, time_budget_seconds=90.0)
    if tracker.within_time_budget() and tracker.elapsed_seconds() < 1.0:
        print("PASS: a fresh tracker is within its 90s time budget")
    else:
        print(f"FAIL: within_time_budget={tracker.within_time_budget()} elapsed={tracker.elapsed_seconds()}")


def test_alert_dedup_upsert():
    conn = alert_store.get_connection(Path(":memory:"))
    alert = StandardizedAlert(
        alert_id="a1", fingerprint="fp-shared", source="pagerduty", service="checkout-service",
        title="High latency", description="p99 latency above threshold", severity="high",
        received_at="2026-07-21T10:00:00Z",
    )
    first_id, first_dup = alert_store.upsert_alert(conn, alert)

    retried = alert.model_copy(update={"alert_id": "a2"})  # same fingerprint, different alert_id
    second_id, second_dup = alert_store.upsert_alert(conn, retried)

    if first_id == "a1" and not first_dup and second_id == "a1" and second_dup:
        print("PASS: a retried alert with the same fingerprint collapses into the original alert_id")
    else:
        print(f"FAIL: first=({first_id}, {first_dup}) second=({second_id}, {second_dup})")


def test_ticket_tag_detection():
    cases = [
        ("@agent rollback the last deploy", "rollback the last deploy"),
        ("@Agent   scale up to 8 replicas", "scale up to 8 replicas"),
        ("thanks, looks good", None),
        ("cc @agent-team please review", None),  # not a leading tag
    ]
    all_passed = True
    for text, expected in cases:
        actual = ticket_store.extract_tagged_instruction(text)
        if actual != expected:
            all_passed = False
            print(f"FAIL: extract_tagged_instruction({text!r}) = {actual!r}, expected {expected!r}")
    if all_passed:
        print("PASS: extract_tagged_instruction correctly detects/ignores '@agent' tags")


def test_mcp_modify_infra_replica_count():
    # mcp_tools always reads/writes storage.infra_state's default STATE_PATH
    # (a single-process assumption documented in the README), so tests seed
    # that same default path rather than an isolated one.
    infra_state.seed({"checkout-service": {"replica_count": 4}})

    result = mcp_tools.modify_infra(ActionRequest(
        action_type="modify_infra", service="checkout-service",
        instruction_summary="scale up", replica_count=8,
    ))

    if result.success and result.before.get("replica_count") == 4 and result.after.get("replica_count") == 8:
        print("PASS: modify_infra scales replica_count and reports before/after state")
    else:
        print(f"FAIL: result={result}")


def test_mcp_deploy_service_rollback_and_missing_previous_version():
    infra_state.seed({"checkout-service": {"deployed_version": "v42", "previous_version": "v41"},
                       "orders-service": {"deployed_version": "v10"}})

    rollback = mcp_tools.deploy_service(ActionRequest(
        action_type="deploy_service", service="checkout-service",
        instruction_summary="rollback", deploy_action="rollback",
    ))
    no_previous = mcp_tools.deploy_service(ActionRequest(
        action_type="deploy_service", service="orders-service",
        instruction_summary="rollback", deploy_action="rollback",
    ))

    if (rollback.success and rollback.after["deployed_version"] == "v41"
            and not no_previous.success and "previous_version" in no_previous.message):
        print("PASS: deploy_service rolls back when a previous_version exists, "
              "and fails cleanly when it doesn't")
    else:
        print(f"FAIL: rollback={rollback} no_previous={no_previous}")


def test_mcp_update_database():
    infra_state.seed({"orders-db": {"connection_pool_size": 50}})

    result = mcp_tools.update_database(ActionRequest(
        action_type="update_database", service="orders-db",
        instruction_summary="bump pool size", connection_pool_size=200,
    ))

    if result.success and result.before["connection_pool_size"] == 50 and result.after["connection_pool_size"] == 200:
        print("PASS: update_database updates connection_pool_size and reports before/after state")
    else:
        print(f"FAIL: result={result}")


if __name__ == "__main__":
    print("--- BudgetTracker caps LLM calls ---")
    test_budget_tracker_caps_calls()

    print("\n--- BudgetTracker time budget ---")
    test_budget_tracker_time_budget()

    print("\n--- alert dedup/upsert by fingerprint ---")
    test_alert_dedup_upsert()

    print("\n--- ticket '@agent' tag detection ---")
    test_ticket_tag_detection()

    print("\n--- mcp_tools.modify_infra ---")
    test_mcp_modify_infra_replica_count()

    print("\n--- mcp_tools.deploy_service ---")
    test_mcp_deploy_service_rollback_and_missing_previous_version()

    print("\n--- mcp_tools.update_database ---")
    test_mcp_update_database()
