# C3: Full package checksum policy hardening

## Что реализовано

Шаг `C3` усиливает валидацию целостности raw package на этапе `finalize`:

1. `checksum_file_path` в `FinalizeRawSessionRequest` ограничен каноническим путем `checksums/SHA256SUMS`.
2. Сервер валидирует `SHA256SUMS` как UTF-8 и проверяет формат строк `<sha256> <relative_path>`.
3. Добавлена проверка на:
   - дубликаты путей в checksum-файле;
   - невалидные hash/path значения;
   - `..` и non-posix path сегменты.
4. Добавлена full-package policy проверка:
   - `package_checksum_sha256` должен совпадать с checksum артефактом;
   - `SHA256SUMS` должен покрывать все не-checksum артефакты;
   - в `SHA256SUMS` не должно быть лишних путей;
   - hash из `SHA256SUMS` должен совпадать с hash артефакта из ingest manifest.
5. В `finalize` добавлена проверка, что все артефакты в статусе `uploaded/verified` перед итоговым переходом в `ingested`.
6. Детали policy-ошибок добавляются в audit payload (`checksum_policy_errors`).

## Измененные backend-компоненты

1. `services/ingest-api/src/ingest_api/models.py`
2. `services/ingest-api/src/ingest_api/repository.py`
3. `services/ingest-api/src/ingest_api/service.py`
4. `services/ingest-api/tests/test_checksum_policy.py`

## Верификация

Проверено в текущей среде:

1. `python3 -m compileall -q src tests` (успешно).

Ограничения среды:

1. `pytest` не установлен в системном Python окружении, поэтому unit-тесты не запускались (`python3 -m pytest` -> `No module named pytest`).

## Что остается следующим шагом

1. `C4` — интеграционные/контрактные тесты ingest lifecycle с test fixtures.
