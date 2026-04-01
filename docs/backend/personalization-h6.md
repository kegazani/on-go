# H6 - Realtime personalization evaluation plan

## Статус

- Step ID: `H6`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Зафиксировать, как валидировать personalized `activity/arousal/valence` в `replay/live` контуре и какие ограничения должны быть закрыты до перехода в `J1`.

## Что сделано

1. Подготовлен канонический H6 документ:
   - `docs/research/personalization-realtime-evaluation-plan.md`.
2. Зафиксированы режимы проверки:
   - `offline_baseline_reference`;
   - `replay_streaming_validation`;
   - `live_shadow_validation`.
3. Зафиксирована обязательная scenario matrix (`H6-S1..H6-S8`) по:
   - `watch-only/fusion`;
   - `global/weak_label/label_free`;
   - `activity/arousal/valence`.
4. Зафиксированы runtime KPI, guardrails и fallback правила:
   - latency/drop/sync thresholds;
   - `worst_subject_delta` guard;
   - automatic fallback на `global` при нарушениях.
5. Подготовлен H6 artifact bundle:
   - `evaluation-report.json`;
   - `model-comparison.csv`;
   - `per-subject-metrics.csv`;
   - `research-report.md`;
   - `plots/*`.

## Ключевой результат

`H6` завершен: определен формальный gate между personalization research и ML platform (`J1`) с проверяемыми replay/live KPI, fallback-политикой и явными claim-boundaries для `valence`.

## Следующий шаг

`J1 - Experiment tracking и model registry`
