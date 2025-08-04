from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str


class Users:
    def __init__(self):
        self._users: dict[int, User] = {}
        self._users[0] = User("Joe", "test_email@email.com")
        self._current_id = 1

    def get(self, id: int):
        return self._users[id]

    def insert(self, name: str, email: str):
        self._users[self._current_id] = User(name, email)
        self._current_id += 1
