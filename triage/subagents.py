"""The three data-gathering subagents the Executor fans out to. Each one:
looks up which log/metric names it's allowed to query from the infra
catalog, pulls the relevant data from the observability substitutes, then
spends exactly one LLM call turning that raw data into a structured
SubagentFinding. One call per subagent keeps a full triage at ~4 LLM calls
(3 subagents + 1 synthesis), well under the 20-call ceiling -- see
shared/budget.py."""

from common.gemini_client import generate_content
from observability import deployments, logs, metrics
from shared.budget import BudgetTracker
from shared.models import StandardizedAlert, SubagentFinding, SubagentFindingDraft
from storage.infra_catalog import get_infra_profile
from triage import prompts

_SCHEMA_CONFIG = {"response_mime_type": "application/json", "response_schema": SubagentFindingDraft}


def metrics_subagent(alert: StandardizedAlert, budget: BudgetTracker) -> SubagentFinding:
    profile = get_infra_profile(alert.service)
    series = {name: metrics.query_metrics(alert.service, name) for name in profile["metric_names"]}

    budget.record_call()
    draft = generate_content(
        prompts.build_metrics_prompt(alert, series), config=_SCHEMA_CONFIG
    ).parsed
    return SubagentFinding(subagent="metrics", **draft.model_dump())


def logs_subagent(alert: StandardizedAlert, budget: BudgetTracker) -> SubagentFinding:
    profile = get_infra_profile(alert.service)
    all_lines = [
        line for name in profile["log_names"] for line in logs.query_logs(alert.service, name)
    ]
    error_lines = logs.filter_by_level(all_lines, {"ERROR", "CRITICAL"})
    anomaly_timestamps = logs.detect_anomalies(all_lines)

    budget.record_call()
    draft = generate_content(
        prompts.build_logs_prompt(alert, error_lines, anomaly_timestamps), config=_SCHEMA_CONFIG
    ).parsed
    return SubagentFinding(subagent="logs", **draft.model_dump())


def deployment_subagent(alert: StandardizedAlert, budget: BudgetTracker) -> SubagentFinding:
    history = deployments.query_deployment_history(alert.service)

    budget.record_call()
    draft = generate_content(
        prompts.build_deployment_prompt(alert, history), config=_SCHEMA_CONFIG
    ).parsed
    return SubagentFinding(subagent="deployment", **draft.model_dump())


if __name__ == "__main__":
    from observability import deployments as dep_mod, logs as log_mod, metrics as met_mod

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

    alert = StandardizedAlert(
        alert_id="a1", fingerprint="fp1", source="pagerduty", service="checkout-service",
        title="High latency", description="p99 latency above threshold", severity="high",
        received_at="2026-07-21T10:03:00Z",
    )
    tracker = BudgetTracker()
    print(metrics_subagent(alert, tracker))
    print(logs_subagent(alert, tracker))
    print(deployment_subagent(alert, tracker))
    print("calls used:", tracker.calls_used)
