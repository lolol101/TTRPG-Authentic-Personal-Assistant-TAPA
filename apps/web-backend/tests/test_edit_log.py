"""The share of proposals a player takes is the point of this table.

So the tests are about the number surviving the ways it could be spoiled:
proposals that never get a denominator, sections applied one at a time, and
the same section applied twice.
"""

from sqlmodel import Session, select

from app.core.edit_log import mark_applied, outcome_counts, record_proposals
from app.models.character import Character
from app.models.sheet_edit import OUTCOME_APPLIED, OUTCOME_PROPOSED, SheetEditOutcome
from app.models.user import User


def _character(session: Session, ruleset: str = "pf2e") -> Character:
    user = User(email="alice@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)

    character = Character(owner_id=user.id, name="Рэм Байер", ruleset=ruleset)
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def _changes() -> list[dict]:
    return [
        {"path": "hp_current", "section": "Основное", "verified": True},
        {"path": "sheet_data.conditions.frightened", "section": "Состояния", "verified": False},
    ]


def test_a_proposal_is_recorded_before_anyone_acts_on_it(session_factory) -> None:
    with session_factory() as session:
        character = _character(session)

        record_proposals(session, character=character, changes=_changes(), message_id=7)

        rows = session.exec(select(SheetEditOutcome)).all()
        assert [row.path for row in rows] == [
            "hp_current",
            "sheet_data.conditions.frightened",
        ]
        assert {row.outcome for row in rows} == {OUTCOME_PROPOSED}
        assert [row.verified for row in rows] == [True, False]
        assert [row.section for row in rows] == ["Основное", "Состояния"]
        assert {row.ruleset for row in rows} == {"pf2e"}
        assert all(row.resolved_at is None for row in rows)


def test_a_question_without_a_character_records_nothing(session_factory) -> None:
    with session_factory() as session:
        assert record_proposals(session, character=None, changes=_changes(), message_id=None) == []
        assert session.exec(select(SheetEditOutcome)).all() == []


def test_a_proposal_outside_a_chat_still_counts(session_factory) -> None:
    """There is no message to hang it on, but the offer was still made."""
    with session_factory() as session:
        character = _character(session)

        record_proposals(session, character=character, changes=_changes()[:1], message_id=None)

        stored = session.exec(select(SheetEditOutcome)).one()
        assert stored.message_id is None
        assert stored.outcome == OUTCOME_PROPOSED


def test_applying_one_section_leaves_the_other_waiting(session_factory) -> None:
    with session_factory() as session:
        character = _character(session)
        record_proposals(session, character=character, changes=_changes(), message_id=7)

        moved = mark_applied(
            session,
            character_id=character.id,
            message_id=7,
            paths=["hp_current"],
        )

        assert moved == 1
        assert outcome_counts(session) == {"proposed": 2, "applied": 1, "waiting": 1}


def test_applying_the_same_section_twice_is_counted_once(session_factory) -> None:
    """A double click must not make the assistant look better than it is."""
    with session_factory() as session:
        character = _character(session)
        record_proposals(session, character=character, changes=_changes(), message_id=7)

        first = mark_applied(session, character_id=character.id, message_id=7, paths=["hp_current"])
        second = mark_applied(
            session, character_id=character.id, message_id=7, paths=["hp_current"]
        )

        assert (first, second) == (1, 0)
        assert outcome_counts(session)["applied"] == 1


def test_applying_does_not_reach_another_turn_or_another_character(session_factory) -> None:
    with session_factory() as session:
        character = _character(session)
        record_proposals(session, character=character, changes=_changes()[:1], message_id=7)
        record_proposals(session, character=character, changes=_changes()[:1], message_id=8)

        mark_applied(session, character_id=character.id, message_id=7, paths=["hp_current"])

        by_message = {
            row.message_id: row.outcome for row in session.exec(select(SheetEditOutcome)).all()
        }
        assert by_message == {7: OUTCOME_APPLIED, 8: OUTCOME_PROPOSED}


def test_counts_can_be_read_for_one_ruleset(session_factory) -> None:
    with session_factory() as session:
        pf2e = _character(session)
        record_proposals(session, character=pf2e, changes=_changes(), message_id=7)
        mark_applied(session, character_id=pf2e.id, message_id=7, paths=["hp_current"])

        assert outcome_counts(session, ruleset="pf2e")["applied"] == 1
        assert outcome_counts(session, ruleset="dnd5e") == {
            "proposed": 0,
            "applied": 0,
            "waiting": 0,
        }
