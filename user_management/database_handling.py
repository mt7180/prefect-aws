import sqlalchemy as db
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session
from typing import List, Dict
from dotenv import load_dotenv
from contextlib import contextmanager
import logging

import pathlib
import os

DBBase = declarative_base()


load_dotenv(override=True)

# Set to True if local DB should be used, otherwise AWS RDS is used as specified in
# env variable AWS_POSTGRES_ENDPOINT
LOCAL_DB = False

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

DEBUG = int(os.getenv("DEBUG_APP2", 0))
logging_level = logging.DEBUG if DEBUG else logging.INFO
logger = logging.getLogger("shared_logger")
logger.setLevel(logging_level)


class User(DBBase):
    __tablename__ = "registered_users"
    id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column("name", db.String(50), nullable=False)
    email = db.Column("email", db.String(75), nullable=False)
    country_code = db.Column("country_code", db.String(25), nullable=False)

    def __repr__(self):
        return f"User(name={self.name}, email={self.email}, \
        country_code={self.country_code})"


def create_db_engine() -> db.Engine:
    if LOCAL_DB:
        db_file = pathlib.Path("sqlite:///users.sqlite")
        engine = db.create_engine(f"sqlite:///{db_file.name}")
    else:
        host = os.getenv("AWS_POSTGRES_ENDPOINT", "")
        logger.info(f"{host=}")
        password = os.getenv("AWS_POSTGRES_PASSWORD")
        db_name = os.getenv("AWS_POSTGRES_DB_NAME")
        engine = db.create_engine(
            f"postgresql://postgres:{password}@{host}:5432/{db_name}"
        )

    # if not db_file.is_file():
    if not db.inspect(engine).has_table("users"):
        DBBase.metadata.create_all(engine)
    return engine


@contextmanager
def get_session(engine):
    session = Session(engine)
    try:
        yield session
    except:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


def add_user_to_db(registered_user: User, engine: db.Engine) -> None:
    with get_session(engine) as session:
        session.add(registered_user)


def delete_all_users(engine: db.Engine) -> int:
    num_deleted_rows = 0
    with get_session(engine) as session:
        num_deleted_rows = session.query(User).delete()
        return num_deleted_rows


def delete_user(name: str, engine: db.engine) -> None:
    with get_session(engine) as session:
        session.query(User).filter(User.name == name).delete()


def get_all_users_from_database(engine=None) -> List[Dict]:
    """querys for all regitered users"""
    if not engine:
        engine = create_db_engine()
    with Session(engine) as session:
        users = session.query(User).all()
    return [
        {"name": user.name, "email": user.email, "country_code": user.country_code}
        for user in users
    ]


if __name__ == "__main__":
    import sys

    curr_db = "local" if LOCAL_DB else os.getenv("AWS_POSTGRES_ENDPOINT")

    engine = create_db_engine()

    menu_dict = {
        "g": get_all_users_from_database,
        "a": add_user_to_db,
        "d": delete_all_users,
        "d1": delete_user,
        "e": sys.exit,
    }

    while True:
        print(f"\nYou are using the {curr_db} database.")
        print("\nYour Options: ")
        print(*zip(menu_dict.keys(), [func.__name__ for func in menu_dict.values()]))
        choice = input("\nWhat would you like to do?: ")
        action = menu_dict.get(choice, None)
        args = []
        if choice == "a":
            name, email, cc = (
                entry.strip()
                for entry in input(
                    "Please enter user name, email and country code (seperator: ','): "
                ).split(",")
            )
            args.append(User(name=name, email=email, country_code=cc))
            # args.append(engine)
        elif choice == "d1":
            # naive approach: no differentiation for users with the same name
            args.append(input("Please give the name of the user to be deleted: "))

        if action:
            action() if choice == "e" else print(action(*args, engine))
        else:
            print(f"{choice} is not a valid choice")
