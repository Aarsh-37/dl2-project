"""Routing: pure functions, no LLM. Bounded retries, gap-category heuristics."""

MAX_OPTIMIZER_RETRIES = 2


def validation_status(validation: dict | None) -> str | None:
    """contracts.md §4 uses `status`; tolerate legacy `verdict` in old rows."""
    validation = validation or {}
    return validation.get("status", validation.get("verdict"))


def validator_route(validation: dict, retries: int) -> str:
    """PASS -> approve | REJECT + retries left -> retry | else -> approve_with_flags."""
    if validation_status(validation) == "PASS":
        return "approve"
    if retries < MAX_OPTIMIZER_RETRIES:
        return "retry"
    return "approve_with_flags"
