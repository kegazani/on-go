# Migrations

Для шага `F2` registry реализован как filesystem JSONL (`registry/datasets.jsonl`),
поэтому DB-миграции пока не требуются.

При переходе на Postgres-backed registry в следующих шагах добавить SQL-миграции здесь.
