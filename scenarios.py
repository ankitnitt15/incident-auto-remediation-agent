"""Three synthetic incidents used by main.py's demo run. Each seeds
observability data (metrics/logs/deployments) consistent with
storage/infra_catalog.py's log/metric names, so the triage subagents have
real data to reason over deterministically -- and an initial infra_state
snapshot the Command Executor demo later mutates."""

from observability import deployments, logs, metrics

SCENARIOS = [
    {
        "name": "checkout-bad-deploy",
        "source": "pagerduty",
        "payload": {
            "service_name": "checkout-service",
            "summary": "checkout-service p99 latency above threshold",
            "urgency": "high",
            "details": "checkout.latency_p99_ms crossed the 300ms alert threshold at 10:02Z.",
            "created_at": "2026-07-21T10:03:00Z",
        },
    },
    {
        "name": "orders-db-pool-exhaustion",
        "source": "zenduty",
        "payload": {
            "service": "orders-service",
            "title": "orders-service elevated error rate",
            "priority": "P1",
            "description": "orders.error_rate crossed 5% at 11:15Z.",
            "timestamp": "2026-07-21T11:16:00Z",
        },
    },
    {
        "name": "payments-feature-flag-500s",
        "source": "pagerduty",
        "payload": {
            "service_name": "payments-service",
            "summary": "payments-service 5xx spike",
            "urgency": "high",
            "details": "payments.5xx_rate crossed 2% at 12:30Z.",
            "created_at": "2026-07-21T12:31:00Z",
        },
    },
]


def seed_observability_data() -> None:
    metrics.seed_metrics("checkout-service", "checkout.latency_p99_ms", [
        ("10:00:00Z", 118.0), ("10:01:00Z", 121.0), ("10:02:00Z", 405.0), ("10:03:00Z", 412.0),
    ])
    metrics.seed_metrics("checkout-service", "checkout.error_rate", [
        ("10:00:00Z", 0.001), ("10:02:00Z", 0.004), ("10:03:00Z", 0.005),
    ])
    metrics.seed_metrics("checkout-service", "checkout.request_rate", [
        ("10:00:00Z", 850.0), ("10:02:00Z", 860.0), ("10:03:00Z", 855.0),
    ])
    logs.seed_logs("checkout-service", "checkout-service.app.log", [
        {"ts": "10:01:59Z", "level": "INFO", "message": "request handled"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment client sync retry exhausted after 3 attempts"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment client sync retry exhausted after 3 attempts"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment client sync retry exhausted after 3 attempts"},
        {"ts": "10:02:30Z", "level": "ERROR", "message": "payment client sync retry exhausted after 3 attempts"},
    ])
    logs.seed_logs("checkout-service", "checkout-service.access.log", [
        {"ts": "10:02:00Z", "level": "INFO", "message": "POST /checkout 200"},
    ])
    deployments.seed_deployments("checkout-service", [
        {"version": "v41", "deployed_at": "2026-07-20T09:00:00Z", "author": "alice",
         "change_summary": "Add loyalty points calculation"},
        {"version": "v42", "deployed_at": "2026-07-21T10:01:30Z", "author": "bob",
         "change_summary": "Switch payment client from async fire-and-forget to synchronous retries"},
    ])

    metrics.seed_metrics("orders-service", "orders.latency_p99_ms", [
        ("11:10:00Z", 140.0), ("11:14:00Z", 520.0), ("11:15:00Z", 610.0),
    ])
    metrics.seed_metrics("orders-service", "orders.error_rate", [
        ("11:10:00Z", 0.002), ("11:14:00Z", 0.048), ("11:15:00Z", 0.061),
    ])
    metrics.seed_metrics("orders-service", "orders.db_pool_wait_ms", [
        ("11:10:00Z", 5.0), ("11:14:00Z", 480.0), ("11:15:00Z", 610.0),
    ])
    metrics.seed_metrics("orders-db", "orders_db.connection_pool_usage", [
        ("11:10:00Z", 0.55), ("11:14:00Z", 0.97), ("11:15:00Z", 1.0),
    ])
    metrics.seed_metrics("orders-db", "orders_db.query_latency_ms", [
        ("11:10:00Z", 12.0), ("11:14:00Z", 45.0), ("11:15:00Z", 61.0),
    ])
    logs.seed_logs("orders-service", "orders-service.app.log", [
        {"ts": "11:14:00Z", "level": "ERROR", "message": "timeout acquiring connection from orders-db pool"},
        {"ts": "11:14:30Z", "level": "ERROR", "message": "timeout acquiring connection from orders-db pool"},
        {"ts": "11:15:00Z", "level": "ERROR", "message": "timeout acquiring connection from orders-db pool"},
        {"ts": "11:15:15Z", "level": "ERROR", "message": "timeout acquiring connection from orders-db pool"},
    ])
    logs.seed_logs("orders-db", "orders-db.slow_query.log", [
        {"ts": "11:14:00Z", "level": "ERROR", "message": "connection pool exhausted, request queued"},
        {"ts": "11:15:00Z", "level": "CRITICAL", "message": "connection pool exhausted, rejecting new connections"},
    ])
    deployments.seed_deployments("orders-service", [
        {"version": "v9", "deployed_at": "2026-07-15T09:00:00Z", "author": "carol",
         "change_summary": "Add order-history pagination"},
        {"version": "v10", "deployed_at": "2026-07-15T09:30:00Z", "author": "carol",
         "change_summary": "Minor logging cleanup"},
    ])

    metrics.seed_metrics("payments-service", "payments.5xx_rate", [
        ("12:25:00Z", 0.001), ("12:29:00Z", 0.031), ("12:30:00Z", 0.045),
    ])
    metrics.seed_metrics("payments-service", "payments.error_rate", [
        ("12:25:00Z", 0.002), ("12:29:00Z", 0.033), ("12:30:00Z", 0.047),
    ])
    metrics.seed_metrics("payments-service", "payments.latency_p99_ms", [
        ("12:25:00Z", 95.0), ("12:29:00Z", 98.0), ("12:30:00Z", 97.0),
    ])
    logs.seed_logs("payments-service", "payments-service.app.log", [
        {"ts": "12:29:00Z", "level": "ERROR", "message": "NullPointerException in new-pricing-engine handler"},
        {"ts": "12:29:15Z", "level": "ERROR", "message": "NullPointerException in new-pricing-engine handler"},
        {"ts": "12:29:30Z", "level": "ERROR", "message": "NullPointerException in new-pricing-engine handler"},
        {"ts": "12:30:00Z", "level": "CRITICAL", "message": "NullPointerException in new-pricing-engine handler"},
    ])
    deployments.seed_deployments("payments-service", [
        {"version": "v6", "deployed_at": "2026-07-10T09:00:00Z", "author": "dave",
         "change_summary": "Add refund retries"},
        {"version": "v7", "deployed_at": "2026-07-18T09:00:00Z", "author": "dave",
         "change_summary": "Prep new-pricing-engine behind a feature flag (not yet enabled)"},
    ])


def initial_infra_state() -> dict:
    return {
        "checkout-service": {
            "replica_count": 4, "deployed_version": "v42", "previous_version": "v41",
            "feature_flags": {},
        },
        "orders-service": {
            "replica_count": 3, "deployed_version": "v10", "previous_version": "v9",
            "feature_flags": {},
        },
        "orders-db": {
            "connection_pool_size": 50,
        },
        "payments-service": {
            "replica_count": 3, "deployed_version": "v7", "previous_version": "v6",
            "feature_flags": {"new-pricing-engine": True},
        },
    }


if __name__ == "__main__":
    seed_observability_data()
    print(f"seeded {len(SCENARIOS)} scenarios")
    for scenario in SCENARIOS:
        print(f"  - {scenario['name']} ({scenario['source']})")
    print(initial_infra_state())
