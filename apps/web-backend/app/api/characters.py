from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.character import Character
from app.models.chat import Chat
from app.models.user import User
from app.schemas.character import CharacterCreate, CharacterResponse, CharacterUpdate

router = APIRouter(prefix="/characters", tags=["characters"])


def _get_owned_character(character_id: int, owner: User, session: Session) -> Character:
    character = session.get(Character, character_id)
    if character is None or character.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character


@router.get("", response_model=list[CharacterResponse])
def list_characters(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Character]:
    return list(session.exec(select(Character).where(Character.owner_id == current_user.id)))


@router.post("", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def create_character(
    payload: CharacterCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Character:
    character = Character(owner_id=current_user.id, **payload.model_dump())
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterResponse)
def get_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Character:
    return _get_owned_character(character_id, current_user, session)


@router.patch("/{character_id}", response_model=CharacterResponse)
def update_character(
    character_id: int,
    payload: CharacterUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Character:
    character = _get_owned_character(character_id, current_user, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    character = _get_owned_character(character_id, current_user, session)

    # Chats outlive the characters they were about: the rules discussion in
    # them is still worth reading. Postgres would refuse the delete outright
    # while a chat still points here, so the link is cleared first.
    for chat in session.exec(select(Chat).where(Chat.character_id == character.id)):
        chat.character_id = None
        session.add(chat)

    session.delete(character)
    session.commit()
