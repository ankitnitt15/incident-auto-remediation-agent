import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.models import RootCauseHypothesis, SubagentFinding

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "findings.db"


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    # Where the executor's subagents share their raw findings (diagram: "where
    # will executor share its findings?") -- kept separate from the
    # human-readable ticket comment, which only gets the synthesized summary.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subagent_findings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id   TEXT NOT NULL,
            subagent    TEXT NOT NULL,
            summary     TEXT NOT NULL,
            evidence    TEXT NOT NULL,
            confidence  REAL NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS root_cause_hypotheses (
            ticket_id            TEXT PRIMARY KEY,
            root_cause           TEXT NOT NULL,
            confidence           REAL NOT NULL,
            evidence_summary     TEXT NOT NULL,
            recommended_action   TEXT NOT NULL,
            contributing_signals TEXT NOT NULL,
            created_at           TEXT NOT NULL
        )
    """)
    conn.commit()


def save_finding(conn: sqlite3.Connection, ticket_id: str, finding: SubagentFinding) -> None:
    conn.execute(
        """INSERT INTO subagent_findings (ticket_id, subagent, summary, evidence, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticket_id, finding.subagent, finding.summary, json.dumps(finding.evidence),
         finding.confidence, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_findings(conn: sqlite3.Connection, ticket_id: str) -> list[SubagentFinding]:
    rows = conn.execute(
        "SELECT subagent, summary, evidence, confidence FROM subagent_findings WHERE ticket_id = ?",
        (ticket_id,),
    ).fetchall()
    return [
        SubagentFinding(subagent=r[0], summary=r[1], evidence=json.loads(r[2]), confidence=r[3])
        for r in rows
    ]


def save_hypothesis(conn: sqlite3.Connection, ticket_id: str, hypothesis: RootCauseHypothesis) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO root_cause_hypotheses
           (ticket_id, root_cause, confidence, evidence_summary, recommended_action,
            contributing_signals, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ticket_id, hypothesis.root_cause, hypothesis.confidence, hypothesis.evidence_summary,
         hypothesis.recommended_action, json.dumps(hypothesis.contributing_signals),
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_hypothesis(conn: sqlite3.Connection, ticket_id: str) -> RootCauseHypothesis | None:
    row = conn.execute(
        """SELECT root_cause, confidence, evidence_summary, recommended_action, contributing_signals
           FROM root_cause_hypotheses WHERE ticket_id = ?""",
        (ticket_id,),
    ).fetchone()
    if not row:
        return None
    return RootCauseHypothesis(
        root_cause=row[0], confidence=row[1], evidence_summary=row[2], recommended_action=row[3],
        contributing_signals=json.loads(row[4]),
    )


if __name__ == "__main__":
    conn = get_connection(Path(":memory:"))
    save_finding(conn, "t1", SubagentFinding(
        subagent="metrics", summary="p99 latency tripled after deploy v42",
        evidence=["latency_p99_ms: 120 -> 410 at 10:02Z"], confidence=0.8,
    ))
    print(get_findings(conn, "t1"))
    save_hypothesis(conn, "t1", RootCauseHypothesis(
        root_cause="Bad deploy v42 introduced a latency regression",
        confidence=0.85, evidence_summary="Metrics spike aligns with deploy timestamp",
        recommended_action="Rollback checkout-service to v41",
        contributing_signals=["metrics", "deployment"],
    ))
    print(get_hypothesis(conn, "t1"))
