"""Command Executor: the one place natural-language instructions turn into
MCP-tool calls, fed from either trigger the diagrams show -- a ticket
comment starting with '@agent' (storage.ticket_store.extract_tagged_instruction)
or a direct ask in the IAR chat. Both paths funnel through
try_execute_from_text, so there is exactly one parser and one dispatcher,
and exactly one place a human's request is required before anything in
infra_state changes."""

from datetime import datetime, timezone

from common.gemini_client import generate_content
from shared.models import ActionRequest, ActionResult, TicketComment
from storage import infra_catalog, ticket_store
from actions import mcp_tools, prompts


def _log_action(ticket_id: str, result: ActionResult, requested_by: str, origin: str) -> None:
    status = "executed" if result.success else "failed"
    text = (
        f"**Action {status}** (requested by {requested_by} via {origin})\n"
        f"{result.message}\n"
        f"Before: {result.before}\n"
        f"After: {result.after}"
    )
    conn = ticket_store.get_connection()
    ticket_store.add_comment(conn, TicketComment(
        ticket_id=ticket_id, author="iar-command-executor", text=text,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))


def try_execute_from_text(
    ticket_id: str, instruction_text: str, requested_by: str, origin: str
) -> ActionResult | None:
    """Parses instruction_text into an ActionRequest and dispatches it to the
    matching MCP tool. Returns None (no action taken, no comment logged) if
    the instruction doesn't actually ask for a change -- callers can then
    fall back to treating it as a plain question."""
    known_resources = list(infra_catalog.CATALOG.keys())
    request = generate_content(
        prompts.build_action_extraction_prompt(instruction_text, known_resources),
        config={"response_mime_type": "application/json", "response_schema": ActionRequest},
    ).parsed

    if request.action_type == "unrecognized":
        return None

    result = mcp_tools.dispatch(request)
    _log_action(ticket_id, result, requested_by, origin)
    return result


def process_ticket_comment(ticket_id: str, comment: TicketComment) -> ActionResult | None:
    """The tag-triggered path: '@agent <instruction>' comments feed here."""
    instruction = ticket_store.extract_tagged_instruction(comment.text)
    if instruction is None:
        return None
    return try_execute_from_text(ticket_id, instruction, requested_by=comment.author, origin="ticket-comment")


if __name__ == "__main__":
    from storage import infra_state

    infra_state.seed({"checkout-service": {"replica_count": 4, "deployed_version": "v42",
                                            "previous_version": "v41"}})

    result = process_ticket_comment("t1", TicketComment(
        ticket_id="t1", author="on-call-engineer",
        text="@agent rollback the last deploy for checkout-service",
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    print(result)

    not_an_action = process_ticket_comment("t1", TicketComment(
        ticket_id="t1", author="on-call-engineer", text="thanks, looks good",
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    print("not an action:", not_an_action)
