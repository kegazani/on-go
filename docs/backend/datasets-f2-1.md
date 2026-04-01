# F2.1: Dataset onboarding instructions и обязательный validation run

## Цель шага

Закрыть операционный gap после `F2`:

1. дать пользователю конкретные инструкции по скачиванию каждого приоритетного датасета;
2. зафиксировать единый локальный layout хранения;
3. добавить обязательную команду проверки source-структуры перед импортом.

## Что реализовано

1. Добавлен onboarding runbook по `WESAD`, `EmoWear`, `G-REx`, `DAPPER`:
   - ссылки на скачивание;
   - путь размещения (`data/external/<dataset>/raw`);
   - обязательные команды `validate-source`.
2. Добавлен `dataset catalog` в `dataset-registry` с полями:
   - `dataset_id`, `title`, `download_urls`, `access_notes`.
3. Добавлена команда `validate-source` для `wesad/emowear/grex/dapper`.
4. Добавлены source-validation rules для каждого датасета и базовые unit-тесты.

## Команды шага

```bash
cd services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main dataset-catalog
PYTHONPATH=src python3 -m dataset_registry.main validate-source --dataset-id wesad --source-dir <path>
PYTHONPATH=src python3 -m dataset_registry.main validate-source --dataset-id emowear --source-dir <path>
PYTHONPATH=src python3 -m dataset_registry.main validate-source --dataset-id grex --source-dir <path>
PYTHONPATH=src python3 -m dataset_registry.main validate-source --dataset-id dapper --source-dir <path>
```

## Локальная верификация

1. `python3 -m compileall -q src tests` — успешно.
2. Smoke-run `dataset-catalog` — успешно.
3. Smoke-run `validate-source` выполнен для всех 4 датасетов на синтетических fixture layout — успешно.

## Ограничения

1. Для `EmoWear`, `G-REx`, `DAPPER` в `F2.1` добавлен validation/onboarding, но полноценные import-adapters еще не реализованы.
2. Реальные прогоны на полном объеме датасетов требуют их локального скачивания пользователем и могут потребовать ручного доступа/аккаунта (Zenodo/Synapse/EULA).
