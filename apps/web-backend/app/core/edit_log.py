"""Keeps score of what the assistant proposed for a sheet and what was taken.

Writing happens on two occasions and nowhere else: when changes are proposed,
and when the player applies some of them. Reading is one call, so the number
can be looked at without anyone remembering the schema.
"""

from datetime import UTC, datetime

from sqlmodel import Session, func, select

from app.models.character import Character
from app.models.sheet_edit import OUTCOME_APPLIED, OUTCOME_PROPOSED, SheetEditOutcome


def record_proposals(
    session: Session,
    *,
    character: Character | None,
    changes: list[dict],
    message_id: int | None,
) -> list[SheetEditOutcome]:
    """Stores one row per proposed change, before anyone has acted on it.

    Nothing is recorded for a question that touched no sheet: a row with no
    character would count toward a rate it cannot belong to.
    """
    if character is None or character.id is None or not changes:
        return []

    rows = [
        SheetEditOutcome(
            character_id=character.id,
            ruleset=character.ruleset,
            message_id=message_id,
            path=str(change.get("path", "")),
            section=str(change.get("section") or ""),
            verified=bool(change.get("verified")),
        )
        for change in changes
        if change.get("path")
    ]
    for row in rows:
        session.add(row)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


def mark_applied(
    session: Session,
    *,
    character_id: int,
    message_id: int,
    paths: list[str],
) -> int:
    """Marks the named proposals as applied, and returns how many moved.

    Only rows still waiting are touched, so applying the same section twice
    (a double click, a retried request) does not inflate the count.
    """
    if not paths:
        return 0

    waiting = session.exec(
        select(SheetEditOutcome).where(
            SheetEditOutcome.character_id == character_id,
            SheetEditOutcome.message_id == message_id,
            SheetEditOutcome.outcome == OUTCOME_PROPOSED,
            SheetEditOutcome.path.in_(paths),  # type: ignore[attr-defined]
        )
    ).all()

    now = datetime.now(UTC)
    for row in waiting:
        row.outcome = OUTCOME_APPLIED
        row.resolved_at = now
        session.add(row)
    if waiting:
        session.commit()
    return len(waiting)


def outcome_counts(session: Session, *, ruleset: str | None = None) -> dict[str, int]:
    """How many proposals were made and how many were taken.

    Returns totals rather than a ratio: a rate over three proposals is a
    number that invites the wrong conclusion, and the caller can divide.
    """
    statement = select(SheetEditOutcome.outcome, func.count()).group_by(SheetEditOutcome.outcome)
    if ruleset is not None:
        statement = statement.where(SheetEditOutcome.ruleset == ruleset)

    counts = {outcome: count for outcome, count in session.exec(statement).all()}
    applied = counts.get(OUTCOME_APPLIED, 0)
    return {
        "proposed": sum(counts.values()),
        "applied": applied,
        "waiting": counts.get(OUTCOME_PROPOSED, 0),
    }
