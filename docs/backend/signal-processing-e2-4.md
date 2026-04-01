# E2.4: Stress-test и anti-leakage validation для E2.3

## Статус

- Step ID: `E2.4`
- Status: `completed`
- Date: `2026-03-27`

## Цель шага

Проверить, что результат `E2.3` не является артефактом shortcut/leakage и устойчив при более строгом сценарии валидации.

## Что проверено

1. Обновлен `audit-wesad`:
   - добавлен `valence_coarse` в `single_feature_probe`, split coverage и alerts.
2. Выполнен реальный safety audit:
   - run id: `audit-wesad-20260327T202858Z`
   - status: `passed`
   - blocking findings: `[]`.
3. Выполнен LOSO stress-test для E2.3 вариантов:
   - `polar_rr_only`
   - `polar_rr_acc`
   - `watch_plus_polar_fusion`
4. Выполнен permutation sanity-check для `watch_plus_polar_fusion` по `valence_coarse`:
   - baseline model обучается на оригинальных train-labels;
   - далее `40` запусков с перестановкой train `valence` labels;
   - сравнение baseline против permutation distribution.

## Артефакты

1. `data/external/wesad/artifacts/wesad/wesad-v1/safety-audit/evaluation-report.json`
2. `data/external/wesad/artifacts/wesad/wesad-v1/safety-audit/leakage-audit.json`
3. `data/external/wesad/artifacts/wesad/wesad-v1/e2-4-safety-gate/e2-4-report.json`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-4-safety-gate/loso-fold-metrics.csv`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-4-safety-gate/loso-summary.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-4-safety-gate/valence-permutation.csv`

## Ключевые результаты

### Safety audit

1. `status=passed`, blocking findings отсутствуют.
2. `top_single_feature_valence_macro_f1 = 0.885714` (< `0.95` threshold), поэтому shortcut-alert не сработал.

### LOSO summary (macro_f1 mean)

1. `arousal_coarse`:
   - `polar_rr_only`: `0.349048`
   - `polar_rr_acc`: `0.369365`
   - `watch_plus_polar_fusion`: `0.634868`
2. `valence_coarse` (exploratory):
   - `polar_rr_only`: `0.321058`
   - `polar_rr_acc`: `0.416085`
   - `watch_plus_polar_fusion`: `0.742540`

### Permutation sanity-check (valence, fusion)

1. baseline `valence_coarse macro_f1`: `1.000000`
2. permutation mean macro_f1 (`n=40`): `0.291319`
3. permutation max macro_f1: `0.750000`
4. empirical `p_value`: `0.0`

## Вывод

1. Явных leakage-blockers шаг `E2.4` не обнаружил.
2. Результат `valence=1.0` из `E2.3` не воспроизводится как стабильный claim-safe уровень при более строгом stress-сценарии.
3. `valence` должен оставаться `exploratory` до дополнительной стабилизации (больше данных/строже протоколы/дополнительные guardrails).

## Следующий рекомендуемый шаг

`E2.5` — зафиксировать claim-safe winner selection:

1. выбрать production-safe winner по `arousal`;
2. оставить `valence` в exploratory policy;
3. подготовить freeze-кандидаты и deployment boundaries.
