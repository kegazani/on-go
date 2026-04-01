# Personalization Realtime Evaluation Plan (H6)

## Статус

- Step ID: `H6`
- Date: `2026-03-22`
- Scope: evaluation gating перед переходом в `J1`

## 1. Цель шага

Зафиксировать воспроизводимый план проверки personalized inference в `replay/live`-контуре для:

1. `watch-only`
2. `fusion`

с целями `activity`, `arousal` и ограниченным `valence` track.

## 2. Evaluation modes

План охватывает три режима:

1. `offline_baseline_reference`:
   - reference метрики из `H3/H5`.
2. `replay_streaming_validation`:
   - запуск по историческим сессиям через `replay-service` (`single_window/full_session`).
3. `live_shadow_validation`:
   - live inference без продуктового воздействия, только shadow telemetry.

## 3. Canonical scenario matrix

Обязательные сценарии:

| Scenario ID | Modality | Personalization mode | Runtime | Primary target |
| --- | --- | --- | --- | --- |
| `H6-S1` | `watch-only` | `global` | `replay` | `activity` |
| `H6-S2` | `watch-only` | `label_free` | `replay` | `arousal` |
| `H6-S3` | `fusion` | `global` | `replay` | `activity` |
| `H6-S4` | `fusion` | `weak_label` | `replay` | `arousal` |
| `H6-S5` | `watch-only` | `label_free` | `live_shadow` | `arousal` |
| `H6-S6` | `fusion` | `weak_label` | `live_shadow` | `arousal` |
| `H6-S7` | `watch-only` | `label_free` | `live_shadow` | `valence` (exploratory) |
| `H6-S8` | `fusion` | `weak_label` | `live_shadow` | `valence` (exploratory) |

## 4. Runtime KPIs and guards

### 4.1 Quality KPIs

1. `macro_f1` (`activity`, `arousal_coarse`) на replay holdout.
2. `subject-level gain distribution` против `global`.
3. `worst_subject_delta` с guardrail:
   - `>= -0.05` для primary claim tracks.

### 4.2 Runtime KPIs

1. `prediction_latency_p95_ms`:
   - `watch-only <= 300ms`
   - `fusion <= 500ms`
2. `window_drop_rate`:
   - `<= 1%`
3. `stream_sync_gap_p95_ms`:
   - `<= 250ms` для fusion replay/live.

### 4.3 Safety rules

1. Если `worst_subject_delta < -0.05`, personalized режим переводится в fallback `global`.
2. Если `prediction_latency_p95_ms` выше порога 3 последовательных окна, включается fallback `global`.
3. Для `valence` любые runtime выгоды трактуются как exploratory, без claim-grade conclusion.

## 5. Replay protocol

1. Использовать `replay-service` режимы:
   - `single_window` для latency/guard проверок;
   - `full_session` для end-to-end stability.
2. Для каждого сценария логировать:
   - run_id;
   - policy (`global/weak_label/label_free`);
   - per-window latency;
   - prediction payload + confidence;
   - fallback switches.
3. Формировать replay summary artifact:
   - `scenario_status`, `kpi_table`, `guard_violations`, `fallback_count`.

## 6. Live-shadow protocol

1. Live inference только в shadow-mode (без пользовательских product actions).
2. Контрольные метрики:
   - `latency`, `drop_rate`, `fallback_count`, `confidence drift`.
3. Минимальная длительность shadow validation:
   - `>= 7` календарных дней или `>= 20` сессий (что наступит позже).

## 7. Claim boundaries before J1

Перед переходом к `J1` должны быть выполнены:

1. Replay-прохождение `H6-S1..S4` без критических guard violations.
2. Live-shadow прохождение `H6-S5..S6` с устойчивыми runtime KPI.
3. Для `valence` (`H6-S7..S8`) остается exploratory статус, если нет независимого усиления label quality.

## 8. Артефакты H6

Обязательный пакет шага:

1. `evaluation-report.json`
2. `model-comparison.csv` (matrix of runtime scenarios)
3. `per-subject-metrics.csv` (guardrails and fallback thresholds)
4. `research-report.md`
5. `plots/` (gates, runtime KPI map, fallback policy flow)

## 9. Следующий шаг

`J1 - Experiment tracking и model registry`
