# E2.13: Scoped Mode Canary Hardening

## Статус

- Parent track: `E2`
- Step: `E2.13`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Добавить автоматический canary-контур для scoped `valence`: периодические runtime-checks, alerting и auto-disable флаг по rollback-условиям.

## Что сделано

1. Добавлен canary job:
   - `scripts/ml/valence_e2_13_canary_hardening.py`
2. Реализован canary artifact bundle:
   - `canary-state.json` (auto-disable + next-check metadata),
   - `alerts.json`,
   - `canary-trigger-results.csv`,
   - `canary-readiness-checklist.csv`,
   - `evaluation-report.json`,
   - `research-report.md`.
3. Runtime-интеграция в `inference-api`:
   - добавлен env `INFERENCE_VALENCE_CANARY_STATE_PATH`,
   - учитывается `auto_disable/effective_mode_override`,
   - `/health` и `/v1/policy/valence-scoped` отдают canary-state признаки.
4. Обновлены контракт и service docs:
   - `contracts/http/inference-api.openapi.yaml`
   - `services/inference-api/README.md`
   - `docs/operations/valence-scoped-policy-runbook.md`

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/`

Файлы:

1. `evaluation-report.json`
2. `canary-state.json`
3. `alerts.json`
4. `canary-trigger-results.csv`
5. `canary-readiness-checklist.csv`
6. `research-report.md`

## Ключевой результат

Canary hardening готов: rollback-условия автоматизированы в периодическом check-job, alerts формируются автоматически, а runtime может принудительно выключить scoped режим через `auto_disable` без изменения основной policy.

## Следующий шаг

`E2.14` — Canary drill and rollback simulation:

1. провести контролируемый trigger drill (forced rollback event);
2. подтвердить переход runtime в `disabled` через canary-state;
3. зафиксировать recovery-процедуру и SLA по возврату в `internal_scoped`.
