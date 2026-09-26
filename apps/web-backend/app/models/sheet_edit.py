from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

#: Proposed, and still waiting: the player has not acted on it.
OUTCOME_PROPOSED = "proposed"
#: The player applied it to the sheet.
OUTCOME_APPLIED = "applied"


def _now() -> datetime:
    return datetime.now(UTC)


class SheetEditOutcome(SQLModel, table=True):
    """One proposed sheet change, and what became of it.

    The point is a number: of everything the assistant offered, how much did
    the player actually take. That is the closest thing to "the assistant
    understands me" that can be measured without asking anyone.

    A row is written when the change is proposed, not when it is accepted —
    otherwise the denominator is lost and only successes are ever counted.

    Deliberately holds no sheet values and no PF2e vocabulary: the path and
    the section are opaque strings here, so a second ruleset needs no change
    to this table (see CLAUDE.md, §3).
    """

    id: int | None = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character.id", index=True)

    #: Copied from the character at proposal time rather than joined later:
    #: the question "which ruleset were we worse at" has to survive the
    #: character being edited or deleted.
    ruleset: str = ""

    #: Nullable: a proposal made outside a chat is still a proposal. Kept as
    #: a plain id, not a foreign key, so deleting a chat does not delete the
    #: record of what was offered in it.
    message_id: int | None = Field(default=None, index=True)

    path: str
    section: str = ""
    #: Whether the model's own arithmetic checked out against the sheet.
    #: Unverified proposals are expected to be accepted less often, and
    #: that difference is the reason to keep the flag here.
    verified: bool = False

    outcome: str = OUTCOME_PROPOSED
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None
