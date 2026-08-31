import sqlite3
from pathlib import Path

from shared.models import StandardizedAlert

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    # Direct substitute for a Postgres alert table: fingerprint is the
    # dedup/upsert key, mirroring how PagerDuty/ZenDuty collapse retried
    # webhook deliveries for the same underlying condition into one alert.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id     TEXT PRIMARY KEY,
            fingerprint  TEXT NOT NULL UNIQUE,
            source       TEXT NOT NULL,
            service      TEXT NOT NULL,
            title        TEXT NOT NULL,
            description  TEXT NOT NULL,
            severity     TEXT NOT NULL,
            metric_name  TEXT,
            received_at  TEXT NOT NULL,
            ticket_id    TEXT
        )
    """)
    conn.commit()


def upsert_alert(conn: sqlite3.Connection, alert: StandardizedAlert) -> tuple[str, bool]:
    """Insert a new alert, or return the existing alert_id if this fingerprint
    was already seen. Returns (alert_id, is_duplicate)."""
    row = conn.execute(
        "SELECT alert_id FROM alerts WHERE fingerprint = ?", (alert.fingerprint,)
    ).fetchone()
    if row:
        return row[0], True

    conn.execute(
        """
        INSERT INTO alerts (alert_id, fingerprint, source, service, title, description,
                             severity, metric_name, received_at, ticket_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            alert.alert_id, alert.fingerprint, alert.source, alert.service, alert.title,
            alert.description, alert.severity, alert.metric_name, alert.received_at,
        ),
    )
    conn.commit()
    return alert.alert_id, False


def link_ticket(conn: sqlite3.Connection, alert_id: str, ticket_id: str) -> None:
    conn.execute("UPDATE alerts SET ticket_id = ? WHERE alert_id = ?", (ticket_id, alert_id))
    conn.commit()


def get_linked_ticket(conn: sqlite3.Connection, alert_id: str) -> str | None:
    row = conn.execute("SELECT ticket_id FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
    return row[0] if row else None


def get_alert(conn: sqlite3.Connection, alert_id: str) -> StandardizedAlert | None:
    row = conn.execute(
        """SELECT alert_id, fingerprint, source, service, title, description, severity,
                  metric_name, received_at FROM alerts WHERE alert_id = ?""",
        (alert_id,),
    ).fetchone()
    if not row:
        return None
    return StandardizedAlert(
        alert_id=row[0], fingerprint=row[1], source=row[2], service=row[3], title=row[4],
        description=row[5], severity=row[6], metric_name=row[7], received_at=row[8],
    )


if __name__ == "__main__":
    conn = get_connection(Path(":memory:"))
    alert = StandardizedAlert(
        alert_id="a1", fingerprint="fp-1", source="pagerduty", service="checkout-service",
        title="High latency", description="p99 latency above threshold", severity="high",
        metric_name="latency_p99_ms", received_at="2026-07-21T10:00:00Z",
    )
    print(upsert_alert(conn, alert))
    print(upsert_alert(conn, alert))  # duplicate fingerprint -> is_duplicate=True
    print(get_alert(conn, "a1"))
