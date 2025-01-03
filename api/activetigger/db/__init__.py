import logging
from pathlib import Path

from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from activetigger.functions import get_hash, get_root_pwd

db_url = f"sqlite:///{path_db}"


class DBException(Exception):
    pass


class Base(DeclarativeBase):
    pass


def create_db(db_url: str) -> None:
    logging.debug("Create database")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def create_root_session() -> None:
    """
    Create root session
    :return: None
    """
    pwd: str = get_root_pwd()
    hash_pwd: bytes = get_hash(pwd)
    self.add_user("root", hash_pwd, "root", "system")


# test if the db exists, else create it
if not Path(path_db).exists():
    create_db(db_url)

# connect the session
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
default_user = "server"

# check if there is a root user, add it
with Session() as session:
    if not session.query(Users).filter_by(user="root").first():
        create_root_session()
