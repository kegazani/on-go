# E2.3: Fusion-ready benchmark (`arousal + valence`)

## Статус

- Step ID: `E2.3`
- Status: `completed`
- Date: `2026-03-27`

## Запрос

Проверить новый feature stack после `E2.2` на трех постановках:

1. `polar_rr_only`
2. `polar_rr_acc`
3. `watch_plus_polar_fusion`

и собрать comparative report для `arousal + valence`.

## Что реализовано

1. В `modeling-baselines` добавлен run-kind:
   - `e2-3-wesad-polar-watch-benchmark`.
2. Добавлены E2.3-specific evaluation tracks:
   - `arousal_coarse`
   - `arousal_ordinal`
   - `valence_coarse`
   - `valence_ordinal` (exploratory)
3. Обновлен pipeline parsing:
   - `SegmentExample` теперь включает `valence_score` и `valence_coarse`.
4. Добавлен полный набор артефактов в standard формате:
   - `evaluation-report.json`
   - `predictions-test.csv`
   - `per-subject-metrics.csv`
   - `model-comparison.csv`
   - `research-report.md`
   - `plots/`

## Реальный запуск

- `experiment_id`: `e2-3-polar-watch-benchmark-20260327T195906Z`
- output root:
  - `data/external/wesad/artifacts/wesad/wesad-v1/e2-3-polar-watch-benchmark/`

Ключевые результаты (`macro_f1`, test):

1. `arousal_coarse`:
   - `polar_rr_only`: `0.275058`
   - `polar_rr_acc`: `0.390476` (`delta=+0.115418`, `supported`)
   - `watch_plus_polar_fusion`: `0.798319` (`delta=+0.523261`, `supported`)
2. `valence_coarse` (exploratory):
   - `polar_rr_only`: `0.477656`
   - `polar_rr_acc`: `0.343434` (`delta=-0.134222`, `inconclusive_negative`)
   - `watch_plus_polar_fusion`: `1.000000` (`delta=+0.522344`, `supported`)

## Ограничения

1. В текущем E2.3 `polar_*` представлены через `WESAD chest` proxy-модальности (`ECG/ACC`), а не через live `on-go` capture пакеты.
2. Слишком высокий `valence` результат у fusion-варианта требует дополнительного anti-leakage/stress gate перед любым сильным claim.
3. Следующий шаг должен быть направлен на устойчивость и safety:
   - LOSO sanity-check,
   - пер-субъектная стабильность,
   - проверка shortcut/leakage эффектов.

## Измененные файлы шага

1. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/README.md`
4. `services/modeling-baselines/tests/test_pipeline.py`
5. `services/modeling-baselines/tests/test_audit.py`

## Следующий рекомендуемый шаг

`E2.4` — stress-test и anti-leakage validation для E2.3.
