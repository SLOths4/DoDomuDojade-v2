from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.users.models import User
from app.users.schemas import UserCreate, UserUpdate

# Verifying against a real hash keeps login timing the same whether or not the user exists.
_DUMMY_HASH = hash_password("timing-equaliser")


def find_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", 404)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = find_by_username(db, username)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def _ensure_username_free(db: Session, username: str, except_id: int | None = None) -> None:
    existing = find_by_username(db, username)
    if existing is not None and existing.id != except_id:
        raise AppError("USERNAME_TAKEN", 409, username=username)


def create_user(db: Session, data: UserCreate) -> User:
    _ensure_username_free(db, data.username)
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    return user


def update_user(db: Session, actor: User, user: User, data: UserUpdate) -> User:
    if user.id == actor.id and (
        (data.role is not None and data.role != user.role) or data.is_active is False
    ):
        raise AppError("CANNOT_CHANGE_OWN_ACCESS", 409)
    if data.username is not None:
        _ensure_username_free(db, data.username, except_id=user.id)
        user.username = data.username
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        user.session_version += 1
    db.commit()
    return user


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    user.session_version += 1
    db.commit()


def change_own_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AppError("INVALID_PASSWORD", 400)
    if current == new:
        raise AppError("PASSWORD_UNCHANGED", 400)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.session_version += 1
    db.commit()


def delete_user(db: Session, actor: User, user: User) -> None:
    if user.id == actor.id:
        raise AppError("CANNOT_DELETE_SELF", 409)
    db.delete(user)
    db.commit()
