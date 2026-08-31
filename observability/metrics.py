"""Metrics backend substitute (Datadog/Prometheus). Each scenario seeds a
small time series per metric name; query_metrics reads it back rather than
hitting a real TSDB."""

# service -> metric_name -> [(timestamp, value), ...]
_SERIES: dict[str, dict[str, list[tuple[str, float]]]] = {}


def seed_metrics(service: str, metric_name: str, series: list[tuple[str, float]]) -> None:
    _SERIES.setdefault(service, {})[metric_name] = series


def query_metrics(service: str, metric_name: str) -> list[tuple[str, float]]:
    """query.metrics -- one of the data sources an executor subagent calls."""
    return _SERIES.get(service, {}).get(metric_name, [])


def query_all_metrics(service: str) -> dict[str, list[tuple[str, float]]]:
    return _SERIES.get(service, {})


if __name__ == "__main__":
    seed_metrics("checkout-service", "checkout.latency_p99_ms", [
        ("10:00:00Z", 120.0), ("10:01:00Z", 118.0), ("10:02:00Z", 410.0), ("10:03:00Z", 405.0),
    ])
    print(query_metrics("checkout-service", "checkout.latency_p99_ms"))
    print(query_metrics("checkout-service", "unknown-metric"))
