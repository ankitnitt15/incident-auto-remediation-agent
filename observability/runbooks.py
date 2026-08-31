"""Runbook index substitute (query.runbook.index). A real system would
vector-search a runbook corpus; a handful of hand-authored runbooks only
needs keyword overlap to find the right one, so no embedding call is spent
on it -- it doesn't count against the triage LLM-call budget."""

RUNBOOKS: list[dict] = [
    {
        "runbook_id": "rb-rollback",
        "title": "Rollback a bad deploy",
        "keywords": ["deploy", "latency", "regression", "rollback", "version"],
        "steps": "Identify the last deployed version, confirm the metric spike aligns with its "
                 "deploy timestamp, then roll the service back to the previous version.",
    },
    {
        "runbook_id": "rb-db-pool",
        "title": "Database connection pool exhaustion",
        "keywords": ["connection", "pool", "database", "db", "timeout", "exhaustion"],
        "steps": "Check connection_pool_usage; if saturated, increase the pool size and/or "
                 "restart the affected service to clear stuck connections.",
    },
    {
        "runbook_id": "rb-feature-flag",
        "title": "Feature-flag-induced errors",
        "keywords": ["feature", "flag", "500", "errors", "rollout"],
        "steps": "Check recently toggled feature flags for the service; disable any flag "
                 "toggled around the time errors started.",
    },
]


def query_runbook_index(query: str, top_k: int = 2) -> list[dict]:
    """query.runbook.index -- keyword-overlap search, not a vector search."""
    query_terms = set(query.lower().split())
    scored = [
        (len(query_terms & set(rb["keywords"])), rb) for rb in RUNBOOKS
    ]
    scored = [(score, rb) for score, rb in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rb for _, rb in scored[:top_k]]


if __name__ == "__main__":
    print(query_runbook_index("latency spike after deploy rollback needed"))
    print(query_runbook_index("database connection pool timeout"))
