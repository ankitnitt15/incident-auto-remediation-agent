"""Webhook ingestor + alert/event standardization (Day-0 design): each alert
source has its own webhook shape; standardize() normalizes it into
StandardizedAlert, alert_store dedupes/upserts it, and a ticket is opened for
every genuinely new alert (a duplicate delivery is folded into its existing
ticket instead of opening a second one)."""

import hashlib
import uuid

from shared.models import StandardizedAlert, Ticket
from storage import alert_store, ticket_store

_PAGERDUTY_URGENCY_TO_SEVERITY = {"high": "critical", "low": "medium"}
_ZENDUTY_PRIORITY_TO_SEVERITY = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}


def _fingerprint(service: str, title: str) -> str:
    # Dedup key: same service + same alert title collapses retried/duplicate
    # webhook deliveries into one alert, regardless of source-specific IDs.
    return hashlib.sha256(f"{service}:{title}".lower().encode()).hexdigest()[:16]


def standardize(raw: dict, source: str) -> StandardizedAlert:
    if source == "pagerduty":
        service = raw["service_name"]
        title = raw["summary"]
        severity = _PAGERDUTY_URGENCY_TO_SEVERITY.get(raw.get("urgency", "low"), "medium")
        return StandardizedAlert(
            alert_id=str(uuid.uuid4()),
            fingerprint=_fingerprint(service, title),
            source=source,
            service=service,
            title=title,
            description=raw.get("details", ""),
            severity=severity,
            metric_name=raw.get("metric_name"),
            received_at=raw["created_at"],
        )

    if source == "zenduty":
        service = raw["service"]
        title = raw["title"]
        severity = _ZENDUTY_PRIORITY_TO_SEVERITY.get(raw.get("priority", "P3"), "medium")
        return StandardizedAlert(
            alert_id=str(uuid.uuid4()),
            fingerprint=_fingerprint(service, title),
            source=source,
            service=service,
            title=title,
            description=raw.get("description", ""),
            severity=severity,
            metric_name=raw.get("metric_name"),
            received_at=raw["timestamp"],
        )

    raise ValueError(f"Unknown alert source: {source}")


def receive_alert(raw_payload: dict, source: str) -> tuple[Ticket, bool]:
    """The webhook ingestor entrypoint. Returns (ticket, is_duplicate)."""
    alert = standardize(raw_payload, source)

    alert_conn = alert_store.get_connection()
    alert_id, is_duplicate = alert_store.upsert_alert(alert_conn, alert)

    ticket_conn = ticket_store.get_connection()
    if is_duplicate:
        existing_ticket_id = alert_store.get_linked_ticket(alert_conn, alert_id)
        ticket = ticket_store.get_ticket(ticket_conn, existing_ticket_id)
        return ticket, True

    ticket = ticket_store.create_ticket(ticket_conn, Ticket(
        ticket_id=f"IAR-{alert_id[:8]}",
        alert_id=alert_id,
        service=alert.service,
        title=alert.title,
        status="open",
        created_at=alert.received_at,
    ))
    alert_store.link_ticket(alert_conn, alert_id, ticket.ticket_id)
    return ticket, False


if __name__ == "__main__":
    pagerduty_payload = {
        "service_name": "checkout-service", "summary": "High latency", "urgency": "high",
        "details": "p99 latency above threshold", "created_at": "2026-07-21T10:00:00Z",
    }
    ticket, is_duplicate = receive_alert(pagerduty_payload, source="pagerduty")
    print(ticket, "is_duplicate=", is_duplicate)

    # retried webhook delivery for the same underlying alert -> folds into the same ticket
    ticket2, is_duplicate2 = receive_alert(pagerduty_payload, source="pagerduty")
    print(ticket2, "is_duplicate=", is_duplicate2)
    assert ticket.ticket_id == ticket2.ticket_id
