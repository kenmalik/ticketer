from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, Field, SQLModel, create_engine


class Attendee(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(index=True)


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    fill_mock_data()


def fill_mock_data():
    with Session(engine) as session:
        attendee_1 = Attendee(name="Joe", email="Joe@email.com")
        attendee_2 = Attendee(name="Jane", email="Jane@email.com")
        attendee_3 = Attendee(name="Jacob", email="Jacob@email.com")
        attendee_4 = Attendee(name="John", email="John@email.com")
        attendee_5 = Attendee(name="Gerry", email="Gerry@email.com")

        session.add_all([attendee_1, attendee_2, attendee_3, attendee_4, attendee_5])
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def insert_attendee(name: str, email: str) -> Attendee:
    attendee = Attendee(name=name, email=email)

    with Session(engine) as session:
        session.add(attendee)
        session.commit()
        session.refresh(attendee)

    return attendee
