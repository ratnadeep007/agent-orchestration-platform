from collections.abc import Iterator

from psycopg import Connection, connect
from psycopg.rows import dict_row

from app.config import settings


def get_connection() -> Iterator[Connection]:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        yield connection
