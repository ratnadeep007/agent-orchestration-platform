from pathlib import Path

from psycopg import connect

from app.config import settings

MIGRATIONS_DIR = Path(__file__).parent


def run_migrations() -> None:
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )

            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = path.stem
                cursor.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s",
                    (version,),
                )
                if cursor.fetchone():
                    continue

                cursor.execute(path.read_text())
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )

        connection.commit()


if __name__ == "__main__":
    run_migrations()
