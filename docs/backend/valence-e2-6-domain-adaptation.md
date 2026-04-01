# E2.6: Valence Domain Adaptation + Calibration

## Статус

- Parent track: `E2` (`valence improvement continuation after E2.5`)
- Step: `E2.6`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Снизить `domain shift` для `valence` без нового датасета через:

1. `CORAL`-адаптацию признакового пространства;
2. калибровку confidence (`temperature scaling`);
3. повторный cross-dataset gate на тех же источниках (`WESAD`, `G-REx`, `EmoWear`).

## Что сделано

1. Добавлен воспроизводимый скрипт:
   - `scripts/ml/valence_e2_6_domain_adaptation.py`.
2. Реализованы режимы сравнения:
   - `baseline`;
   - `coral`;
   - `coral_temp`;
   - `coral_temp_gate`.
3. Для каждой пары `source -> target` и модели (`ridge_classifier`, `catboost`, `xgboost`) посчитаны:
   - `macro_f1`,
   - `balanced_accuracy`,
   - `qwk`,
   - subject-level breakdown.
4. Собраны calibration artifacts:
   - temperature;
   - threshold selection.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/`

Файлы:

1. `adaptation-matrix.csv`
2. `adaptation-summary.csv`
3. `adaptation-subject-metrics.csv`
4. `calibration-summary.csv`
5. `e2-6-report.json`
6. `research-report.md`
7. `plots/e2-6-transfer-baseline-vs-coral-temp.png`

## Ключевые результаты

1. Перенос `WESAD -> G-REx` улучшился для всех трех моделей:
   - `catboost`: `0.292029 -> 0.428391` (`+0.136362`)
   - `ridge`: `0.294289 -> 0.381734` (`+0.087445`)
   - `xgboost`: `0.282956 -> 0.428631` (`+0.145675`)
2. Перенос `G-REx -> WESAD` тоже улучшился:
   - `catboost`: `0.233333 -> 0.519943`
   - `ridge`: `0.250000 -> 0.804678`
   - `xgboost`: `0.233333 -> 0.434921`
3. Для `WESAD -> EmoWear` прирост не подтвержден (лучшим остается baseline).

## Вывод

1. `E2.6` дал практический прирост cross-dataset устойчивости и подтвердил, что domain adaptation работает.
2. При этом единый promotion floor для всех ключевых transfer-направлений еще не закрыт (`WESAD -> G-REx` остается ниже `0.45`).
3. `valence` остается в `exploratory` policy; нужен следующий инкремент стабилизации.

## Следующий шаг

`E2.7` — усиление domain-invariant feature strategy + re-gate:

1. добавить робастный feature filtering для transfer-only режима;
2. зафиксировать trusted model subset для `valence`;
3. повторить cross-dataset gate и пересмотреть promotion boundary.
