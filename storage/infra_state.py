"""Mutable simulated infra: the K8s / AWS / feature-flag-service substitute
that the Command Executor's MCP-style tools act on. A resource (a service or
a database name) maps to whatever attributes apply to it -- replica_count /
deployed_version / feature_flags for services, connection_pool_size for
databases. Backed by a JSON file .
"""

import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "infra_state.json"


def _load(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def seed(initial: dict, path: Path = STATE_PATH) -> None:
    """Write the initial infra state. Overwrites any prior run's state --
    call once at the start of the demo."""
    _save(initial, path)


def snapshot(path: Path = STATE_PATH) -> dict:
    return _load(path)


def get_resource(resource: str, path: Path = STATE_PATH) -> dict:
    return _load(path).get(resource, {})


def update_resource(resource: str, path: Path = STATE_PATH, **fields) -> dict:
    state = _load(path)
    entry = state.setdefault(resource, {})
    entry.update({k: v for k, v in fields.items() if v is not None})
    _save(state, path)
    return dict(entry)


def set_feature_flag(resource: str, flag: str, enabled: bool, path: Path = STATE_PATH) -> dict:
    state = _load(path)
    entry = state.setdefault(resource, {})
    entry.setdefault("feature_flags", {})[flag] = enabled
    _save(state, path)
    return dict(entry)


if __name__ == "__main__":
    demo_path = Path(__file__).resolve().parent.parent / "data" / "_infra_state_demo.json"
    seed({"checkout-service": {"replica_count": 4, "deployed_version": "v42",
                                "previous_version": "v41", "feature_flags": {}}}, path=demo_path)
    print(get_resource("checkout-service", path=demo_path))
    print(update_resource("checkout-service", path=demo_path, replica_count=8))
    print(snapshot(path=demo_path))
    demo_path.unlink()
