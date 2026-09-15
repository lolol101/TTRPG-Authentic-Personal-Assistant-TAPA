"""Saving a sheet and coming back to it.

Hangs off the characters route rather than standing on its own: a snapshot
has no meaning apart from the character it belongs to, and ownership is
decided in exactly one place that way.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.models.character import Character
from app.models.snapshot import CharacterSnapshot
from app.models.user import User
from app.schemas.snapshot import SnapshotCreate, SnapshotResponse

router = APIRouter(prefix="/characters/{character_id}/snapshots", tags=["snapshots"])

#: Copied into a snapshot and written back on restore. Identity and ownership
#: are deliberately absent: restoring a sheet must not move it to another
#: player or resurrect it under a new id.
SAVED_FIELDS = (
    "name",
    "ancestry",
    "background",
    "class_name",
    "level",
    "str_mod",
    "dex_mod",
    "con_mod",
    "int_mod",
    "wis_mod",
    "cha_mod",
    "hp_max",
    "hp_current",
    "ac",
    "speed",
    "sheet_data",
)


def _owned_character(character_id: int, owner: User, session: Session) -> Character:
    character = session.get(Character, character_id)
    if character is None or character.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character


def _owned_snapshot(snapshot_id: int, character: Character, session: Session) -> CharacterSnapshot:
    snapshot = session.get(CharacterSnapshot, snapshot_id)
    if snapshot is None or snapshot.character_id != character.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return snapshot


def capture(character: Character) -> dict:
    """The fields a restore will write back, copied out of the character."""
    return {field: getattr(character, field) for field in SAVED_FIELDS}


def _default_name() -> str:
    return datetime.now(UTC).strftime("%d.%m %H:%M")


@router.get("", response_model=list[SnapshotResponse])
def list_snapshots(
    character_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[CharacterSnapshot]:
    """Newest first — the most likely one to want back is the last one saved."""
    character = _owned_character(character_id, current_user, session)
    return list(
        session.exec(
            select(CharacterSnapshot)
            .where(CharacterSnapshot.character_id == character.id)
            .order_by(CharacterSnapshot.id.desc())  # type: ignore[attr-defined]
        )
    )


@router.post("", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    character_id: int,
    payload: SnapshotCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CharacterSnapshot:
    character = _owned_character(character_id, current_user, session)

    saved = int(
        session.exec(
            select(func.count())
            .select_from(CharacterSnapshot)
            .where(CharacterSnapshot.character_id == character.id)
        ).one()
    )
    if saved >= settings.max_snapshots_per_character:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Сохранений уже {settings.max_snapshots_per_character} — это предел. "
                "Удали ненужные, чтобы сохранить ещё одно."
            ),
        )

    snapshot = CharacterSnapshot(
        character_id=character.id,
        name=payload.name.strip() or _default_name(),
        data=capture(character),
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


@router.post("/{snapshot_id}/restore", response_model=SnapshotResponse)
def restore_snapshot(
    character_id: int,
    snapshot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CharacterSnapshot:
    """Writes a saved copy back over the sheet.

    Only the fields that were saved are touched, and only ones the sheet
    still has: a snapshot taken before a field existed must not resurrect
    stale shapes, and one taken after must not write fields away.
    """
    character = _owned_character(character_id, current_user, session)
    snapshot = _owned_snapshot(snapshot_id, character, session)

    for field in SAVED_FIELDS:
        if field in snapshot.data:
            setattr(character, field, snapshot.data[field])

    session.add(character)
    session.commit()
    session.refresh(snapshot)
    return snapshot


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    character_id: int,
    snapshot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    character = _owned_character(character_id, current_user, session)
    session.delete(_owned_snapshot(snapshot_id, character, session))
    session.commit()
