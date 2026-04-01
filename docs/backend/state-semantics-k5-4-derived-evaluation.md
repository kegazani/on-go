# K5.4: Offline and Replay Evaluation for Derived States

Дата: `2026-03-28`.

## Цель

Проверить поведение semantic layer (`derived_state`) на offline prediction artifacts и session-ordered replay эмуляции:

1. coverage состояний;
2. `unknown-rate` (`uncertain_state`);
3. false-claim risk для claimable состояний.

## Что выполнено

1. Добавлен evaluation скрипт:
   - `scripts/ml/state_k5_4_derived_state_evaluation.py`.
2. Выполнен прогон на `WESAD` artifacts:
   - `watch-only-baseline/predictions-test.csv`,
   - `fusion-baseline/predictions-test.csv`.
3. Сформирован research-grade bundle:
   - `evaluation-report.json`,
   - `predictions-test.csv`,
   - `per-subject-metrics.csv`,
   - `model-comparison.csv`,
   - `replay-session-metrics.csv`,
   - `plots/`,
   - `research-report.md`.

## Headline metrics

Из `k5-4-derived-state-evaluation/evaluation-report.json`:

1. `samples_total`: `75`
2. `unknown_rate`: `0.4133`
3. `false_claim_rate`: `0.0667`
4. `claimable_rate`: `0.5867`
5. `status`: `baseline`

## Comparative summary

1. `watch-only-baseline`:
   - `uncertain_rate=0.2667`
   - `false_claim_rate=0.1333`
2. `fusion-baseline`:
   - `uncertain_rate=0.4500`
   - `false_claim_rate=0.0500`

Интерпретация:

1. `fusion` вариант более консервативен (выше `uncertain_rate`) и дает ниже false-claim risk.
2. `watch-only` вариант чаще выдает claimable состояния и имеет выше false-claim risk на части сессий.

## Replay-oriented findings

Session-ordered replay эмуляция (`replay-session-metrics.csv`) показывает, что worst-case риск концентрируется в отдельных сессиях, а не равномерно по корпусу. Это подтверждает необходимость `K5.5` policy-слоя с ограничением wording для `guarded` и `no_claim`.

## Артефакты

Папка:

`data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/`

Ключевые файлы:

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `replay-session-metrics.csv`
4. `plots/derived-state-coverage.png`
5. `plots/risk-rates.png`
6. `plots/per-subject-false-claim.png`
7. `research-report.md`

## Следующий шаг

`K5.5 - Product wording and exposure policy`:

1. зафиксировать user-facing wording по `claim_level`;
2. определить exposure matrix (`safe/guarded/internal_only/no_claim`);
3. закрепить forbidden phrasing и fallback copy для `uncertain_state`.
