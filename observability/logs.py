"""Log backend substitute (ELK/Splunk). Seeded log lines per service/stream,
plus the two "scripts" the diagrams call out for the logs subagent: filtering
by level and a simple anomaly detector (burst of ERROR/CRITICAL lines)."""

from collections import Counter

# service -> log_name -> [{"ts": ..., "level": ..., "message": ...}, ...]
_LOGS: dict[str, dict[str, list[dict]]] = {}


def seed_logs(service: str, log_name: str, lines: list[dict]) -> None:
    _LOGS.setdefault(service, {})[log_name] = lines


def query_logs(service: str, log_name: str) -> list[dict]:
    """query.logs -- one of the data sources an executor subagent calls."""
    return _LOGS.get(service, {}).get(log_name, [])


def filter_by_level(lines: list[dict], levels: set[str]) -> list[dict]:
    """Script: filter logs by error/level."""
    return [line for line in lines if line.get("level") in levels]


def detect_anomalies(lines: list[dict], error_levels: set[str] = frozenset({"ERROR", "CRITICAL"}),
                      burst_threshold: int = 3) -> list[str]:
    """Script: crude anomaly detection -- flag timestamps where error-level
    lines cluster past a threshold, rather than a steady trickle."""
    counts = Counter(line["ts"] for line in lines if line.get("level") in error_levels)
    return [ts for ts, count in counts.items() if count >= burst_threshold]


if __name__ == "__main__":
    seed_logs("checkout-service", "checkout-service.app.log", [
        {"ts": "10:01:00Z", "level": "INFO", "message": "request handled"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
        {"ts": "10:02:00Z", "level": "ERROR", "message": "payment gateway timeout"},
    ])
    lines = query_logs("checkout-service", "checkout-service.app.log")
    print(filter_by_level(lines, {"ERROR", "CRITICAL"}))
    print(detect_anomalies(lines))
