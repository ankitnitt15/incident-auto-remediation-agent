"""Deployment history substitute (CI/CD system). Seeded per service."""

# service -> [{"version": ..., "deployed_at": ..., "author": ..., "change_summary": ...}, ...]
_HISTORY: dict[str, list[dict]] = {}


def seed_deployments(service: str, deployments: list[dict]) -> None:
    _HISTORY[service] = deployments


def query_deployment_history(service: str) -> list[dict]:
    """query.deployment_history -- one of the data sources an executor subagent calls."""
    return _HISTORY.get(service, [])


def latest_deployment(service: str) -> dict | None:
    history = _HISTORY.get(service, [])
    return history[-1] if history else None


if __name__ == "__main__":
    seed_deployments("checkout-service", [
        {"version": "v41", "deployed_at": "2026-07-20T09:00:00Z", "author": "alice",
         "change_summary": "Add loyalty points calculation"},
        {"version": "v42", "deployed_at": "2026-07-21T10:01:30Z", "author": "bob",
         "change_summary": "Switch payment client to sync retries"},
    ])
    print(query_deployment_history("checkout-service"))
    print(latest_deployment("checkout-service"))
