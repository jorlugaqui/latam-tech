"""SQLAlchemy Core table definitions; Alembic autogenerates revisions from this metadata.

Use portable column types only, so tables behave the same on PostgreSQL and SQLite.
"""

from sqlalchemy import MetaData

metadata = MetaData()
