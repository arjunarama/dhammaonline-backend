from typing import Optional
from sqlmodel import Field, SQLModel


class Teaching(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    category: str
    slug: str
    short_description: str
    full_content: str
    thumbnail_image_url: str | None = None
    banner_image_url: str | None = None
    featured_image_url: str | None = None

class Admin(SQLModel, table=True):
    id: int | None = Field(
        default=None,
        primary_key=True
    )

    username: str
    password: str
    role: str
