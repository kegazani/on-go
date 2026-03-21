from __future__ import annotations

import os
from pathlib import Path

import psycopg

from ingest_api.config import Settings


def main() -> None:
    settings = Settings.from_env()
    if env_path := os.environ.get("INGEST_MIGRATIONS_DIR"):
        migrations_dir = Path(env_path)
    elif (fallback := Path("/app/migrations")).exists():
        migrations_dir = fallback
    else:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found.")
        return

    with psycopg.connect(settings.database_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.ingest_api_schema_migrations (
                    migration_name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            cur.execute("SELECT migration_name FROM public.ingest_api_schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

            for migration_path in migration_files:
                if migration_path.name in applied:
                    continue
                sql = migration_path.read_text(encoding="utf-8")
                print(f"Applying migration: {migration_path.name}")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO public.ingest_api_schema_migrations (migration_name) VALUES (%s)",
                    (migration_path.name,),
                )

        conn.commit()

    print("Migrations applied successfully.")


if __name__ == "__main__":
    main()
