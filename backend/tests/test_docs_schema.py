from pathlib import Path

from app import models  # noqa: F401
from app.db import Base

SCHEMA_DOC = Path(__file__).resolve().parents[2] / "Docs" / "Schema.md"


def test_every_implemented_table_is_in_the_schema_doc() -> None:
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    missing = [name for name in Base.metadata.tables if f"`{name}`" not in text]
    assert not missing, f"Docs/Schema.md is missing tables: {missing}"
