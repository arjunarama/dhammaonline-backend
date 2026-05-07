from typing import Optional
from sqlmodel import Field, SQLModel


class Teaching(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    category: str

class Admin(SQLModel, table=True):
    id: int | None = Field(
        default=None,
        primary_key=True
    )

    username: str
    password: str
    role: str
    