import datetime

from sqlalchemy import TIMESTAMP, delete, func, select, update
from sqlalchemy.orm import MappedColumn, mapped_column
from sqlalchemy.types import Integer, String, Text

from activetigger.db import Base, DBException, Session


class User(Base):
    __tablename__: str = "users"

    id: MappedColumn[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: MappedColumn[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp()
    )
    user: MappedColumn[str] = mapped_column(String)
    key: MappedColumn[str] = mapped_column(Text)
    description: MappedColumn[str] = mapped_column(Text)
    contact: MappedColumn[str] = mapped_column(Text)
    created_by: MappedColumn[str] = mapped_column(String)


def get_user(username: str) -> User:
    # Context manager (with) will automatically close the session outside of its scope
    with Session() as session:
        user = session.scalars(select(User).filter_by(user=username)).first()
        if user is None:
            raise DBException(f"User {username} not found")
        return user


def add_user(
    username: str,
    password: str,
    role: str,
    created_by: str,
    contact: str = "",
):
    # with .begin(), it also commit the transaction
    with Session.begin() as session:
        user = User(
            user=username,
            key=password,
            description=role,
            created_by=created_by,
            # time=datetime.datetime.now(), ← This is default value
            contact=contact,
        )
        session.add(user)


def get_users_created_by(username: str) -> list[str]:
    """
    get users created by *username*
    """
    with Session() as session:
        if username == "all":
            result = session.execute(select(User.user, User.contact).distinct()).all()
        else:
            result = session.scalars(
                select(User.user, User.contact).filter_by(created_by=username).distinct()
            ).all()
        return [row.contact for row in result]


def delete_user(username: str) -> None:
    with Session.begin() as session:
        session.execute(delete(User).filter_by(user=username))


def change_password(username: str, password: str) -> None:
    with Session.begin() as session:
        session.execute(update(User).filter_by(user=username).values(key=password))
