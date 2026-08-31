import re
import sqlite3
from pathlib import Path

from shared.models import StandardizedAlert, Ticket, TicketComment, TicketStatus

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.db"

TAG_PATTERN = re.compile(r"^\s*@agent\b(.*)$", re.IGNORECASE | re.DOTALL)


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    # Substitute for a Jira/ticket-system project: one row per ticket, one row
    # per comment. Comments are where the executor posts its triage summary
    # and where a human can tag the agent to request an action.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id   TEXT PRIMARY KEY,
            alert_id    TEXT NOT NULL,
            service     TEXT NOT NULL,
            title       TEXT NOT NULL,
            status      TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id   TEXT NOT NULL,
            author      TEXT NOT NULL,
            text        TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()


def create_ticket(conn: sqlite3.Connection, ticket: Ticket) -> Ticket:
    conn.execute(
        """INSERT INTO tickets (ticket_id, alert_id, service, title, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticket.ticket_id, ticket.alert_id, ticket.service, ticket.title, ticket.status,
         ticket.created_at),
    )
    conn.commit()
    return ticket


def get_ticket(conn: sqlite3.Connection, ticket_id: str) -> Ticket | None:
    row = conn.execute(
        "SELECT ticket_id, alert_id, service, title, status, created_at FROM tickets WHERE ticket_id = ?",
        (ticket_id,),
    ).fetchone()
    if not row:
        return None
    return Ticket(ticket_id=row[0], alert_id=row[1], service=row[2], title=row[3],
                  status=row[4], created_at=row[5])


def update_status(conn: sqlite3.Connection, ticket_id: str, status: TicketStatus) -> None:
    conn.execute("UPDATE tickets SET status = ? WHERE ticket_id = ?", (status, ticket_id))
    conn.commit()


def add_comment(conn: sqlite3.Connection, comment: TicketComment) -> TicketComment:
    conn.execute(
        "INSERT INTO comments (ticket_id, author, text, created_at) VALUES (?, ?, ?, ?)",
        (comment.ticket_id, comment.author, comment.text, comment.created_at),
    )
    conn.commit()
    return comment


def get_comments(conn: sqlite3.Connection, ticket_id: str) -> list[TicketComment]:
    rows = conn.execute(
        "SELECT ticket_id, author, text, created_at FROM comments WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ).fetchall()
    return [TicketComment(ticket_id=r[0], author=r[1], text=r[2], created_at=r[3]) for r in rows]


def extract_tagged_instruction(comment_text: str) -> str | None:
    """The tag-triggered action path: a comment starting with '@agent' is a
    human asking the Command Executor to do something. Returns the
    instruction text after the tag, or None if this comment isn't a tag."""
    match = TAG_PATTERN.match(comment_text)
    if not match:
        return None
    return match.group(1).strip()


if __name__ == "__main__":
    conn = get_connection(Path(":memory:"))
    ticket = create_ticket(conn, Ticket(
        ticket_id="t1", alert_id="a1", service="checkout-service", title="High latency",
        status="open", created_at="2026-07-21T10:00:00Z",
    ))
    print(get_ticket(conn, "t1"))
    add_comment(conn, TicketComment(ticket_id="t1", author="executor", text="Triage complete.",
                                     created_at="2026-07-21T10:01:00Z"))
    add_comment(conn, TicketComment(ticket_id="t1", author="on-call-engineer",
                                     text="@agent rollback the last deploy",
                                     created_at="2026-07-21T10:05:00Z"))
    for c in get_comments(conn, "t1"):
        print(c, "-> tagged instruction:", extract_tagged_instruction(c.text))
