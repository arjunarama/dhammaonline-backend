import os
import re

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///dhammaonline.db"
)

engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    migrate_teaching_table()


def make_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "teaching"


def migrate_teaching_table():
    inspector = inspect(engine)

    if "teaching" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("teaching")
    }

    columns_to_add = {
        "slug": "VARCHAR",
        "short_description": "TEXT",
        "full_content": "TEXT",
        "thumbnail_image_url": "VARCHAR",
        "banner_image_url": "VARCHAR",
        "featured_image_url": "VARCHAR",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE teaching ADD COLUMN {column_name} {column_type}"
                    )
                )

        rows = list(
            connection.execute(
                text(
                    """
                    SELECT id, title
                    FROM teaching
                    WHERE slug IS NULL OR slug = ''
                    """
                )
            ).mappings()
        )

        used_slugs = {
            row["slug"]
            for row in connection.execute(
                text(
                    """
                    SELECT slug
                    FROM teaching
                    WHERE slug IS NOT NULL AND slug != ''
                    """
                )
            ).mappings()
        }

        for row in rows:
            base_slug = make_slug(row["title"])
            slug = base_slug
            suffix = 2

            while slug in used_slugs:
                slug = f"{base_slug}-{suffix}"
                suffix += 1

            used_slugs.add(slug)

            connection.execute(
                text(
                    """
                    UPDATE teaching
                    SET slug = :slug,
                        short_description = COALESCE(short_description, category),
                        full_content = COALESCE(full_content, category)
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "slug": slug,
                },
            )
