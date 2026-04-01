# E2.19: Long-Horizon Canary Monitoring Pack

## Статус

- Parent track: `E2`
- Step: `E2.19`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Подготовить операционный пакет для длительного мониторинга valence canary-контура после успешного `burnin_passed` gate.

## Что сделано

1. Зафиксирован weekly summary template:
   - `docs/operations/valence-canary-weekly-summary.md`.
2. Зафиксирован incident template для `auto_disable` и rollback-сценариев:
   - `docs/operations/valence-canary-incident-template.md`.
3. Зафиксирован handoff pack с owner/ритмом/checklist:
   - `docs/operations/valence-canary-handoff-pack.md`.
4. Определены минимальные weekly KPI для continuous monitoring:
   - `cycles_total`,
   - `cycles_pass_rate`,
   - `alerts_total`,
   - `auto_disable_events`,
   - `freshness_slo_violations`,
   - `effective_mode_drift_events`.
5. Определен escalation path:
   - `warn` -> owner on-call,
   - `critical` -> immediate mode freeze (`disabled`) + incident runbook.

## Acceptance Criteria

`E2.19` считается завершенным, если:

1. Weekly summary заполняется из canary/dashboard артефактов за последние `7` дней.
2. Incident template содержит обязательные поля timeline/root-cause/rollback.
3. Handoff pack фиксирует ownership, ритм review и triage правила.
4. Следующий шаг переведен в `next` для операционной проверки реального weekly цикла.

## Ключевой результат

Canary-контур получил готовый к эксплуатации monitoring pack для длительного режима: единый weekly формат отчета, стандарт реагирования на инциденты и handoff-правила между командами.

## Следующий шаг

`E2.20` — Weekly canary monitoring dry-run:

1. выполнить один полный weekly summary цикл на актуальных артефактах;
2. смоделировать `warn` и `critical` triage по incident template;
3. зафиксировать readiness decision для регулярного weekly handoff.
