"""Static infra metadata (the CMDB substitute): for a given service, what log
streams and metric names it emits, which services it depends on, which
databases and autoscaling groups back it. This is the answer to "how would
the executor know what to access?" -- it looks the service up here first,
then only queries the specific log/metric names this catalog says exist for
it, instead of guessing across "many log streams, many metrics/names, etc."
"""

CATALOG: dict[str, dict] = {
    "checkout-service": {
        "log_names": ["checkout-service.app.log", "checkout-service.access.log"],
        "metric_names": ["checkout.latency_p99_ms", "checkout.error_rate", "checkout.request_rate"],
        "dependencies": ["payments-service", "orders-service"],
        "databases": [],
        "autoscaling_groups": ["checkout-asg"],
    },
    "orders-service": {
        "log_names": ["orders-service.app.log"],
        "metric_names": ["orders.latency_p99_ms", "orders.error_rate", "orders.db_pool_wait_ms"],
        "dependencies": ["orders-db"],
        "databases": ["orders-db"],
        "autoscaling_groups": ["orders-asg"],
    },
    "payments-service": {
        "log_names": ["payments-service.app.log"],
        "metric_names": ["payments.latency_p99_ms", "payments.error_rate", "payments.5xx_rate"],
        "dependencies": [],
        "databases": [],
        "autoscaling_groups": ["payments-asg"],
    },
    "orders-db": {
        "log_names": ["orders-db.slow_query.log"],
        "metric_names": ["orders_db.connection_pool_usage", "orders_db.query_latency_ms"],
        "dependencies": [],
        "databases": [],
        "autoscaling_groups": [],
    },
}


def get_infra_profile(service: str) -> dict:
    return CATALOG.get(service, {
        "log_names": [], "metric_names": [], "dependencies": [], "databases": [],
        "autoscaling_groups": [],
    })


if __name__ == "__main__":
    print(get_infra_profile("checkout-service"))
    print(get_infra_profile("unknown-service"))
