# E2.11: Scoped Mode Runtime Integration

## Статус

- Parent track: `E2`
- Step: `E2.11`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Интегрировать scoped `valence` policy в runtime/inference контур и проверить переключение режимов `disabled <-> internal_scoped` в dry-run.

## Что сделано

1. Runtime policy integration в `inference-api`:
   - загрузка policy из `INFERENCE_VALENCE_SCOPED_POLICY_PATH`;
   - health-поля: `valence_policy_loaded`, `valence_mode`;
   - новый endpoint: `GET /v1/policy/valence-scoped`;
   - `POST /v1/predict` принимает `X-On-Go-Context` и возвращает `valence_scoped_status`.
2. Hard guardrails внедрены в response-level status:
   - context allowlist,
   - non-user-facing ограничения,
   - reason-code при блокировке/недоступности.
3. Обновлены контракты и docs:
   - `contracts/http/inference-api.openapi.yaml`,
   - `services/inference-api/README.md`.
4. Выполнен dry-run переключения режимов:
   - `scripts/ml/valence_e2_11_runtime_dryrun.py`,
   - артефакты в `e2-11-runtime-dryrun/`.

## Артефакты

Dry-run папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-11-runtime-dryrun/`

Файлы:

1. `dryrun-mode-matrix.csv`
2. `dryrun-report.json`
3. `dryrun-report.md`

## Ключевой результат

1. В режиме `disabled` все контексты блокируются (`policy_disabled`).
2. В `internal_scoped`:
   - `research_only/internal_dashboard/shadow_mode` разрешены;
   - `public_app` блокируется (`context_not_allowed`).
3. User-facing claims остаются запрещены.

## Следующий шаг

`E2.12` — Scoped mode shadow-cycle evaluation:

1. прогнать несколько циклов shadow/replay с runtime policy;
2. проверить rollback-триггеры на реальных метриках;
3. подтвердить или отменить scoped режим на операционном gate.
