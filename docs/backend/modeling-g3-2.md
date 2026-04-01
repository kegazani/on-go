# G3.2 - Multi-dataset harmonization, protocol repair and phased training

## Статус

- Step ID: `G3.2`
- Status: `completed_with_followup_protocol`
- Date: `2026-03-27`

## Запрос

Расширить сравнение моделей за пределы `WESAD`, затем перевести multi-dataset линию из режима "сырая harmonization/comparison" в режим контролируемого обучения с разделением по качеству labels, readiness-gates и фазовому протоколу обучения.

## Что сделано

1. В `dataset-registry` добавлены реальные импортёры и CLI-команды для:
   - `EmoWear` (`import-emowear`);
   - `G-REx` (`import-grex`);
   - `DAPPER` (`import-dapper`).
2. Для `EmoWear`/`DAPPER` реализован временный proxy label mapping и явно помечен в данных как `source=proxy_mapping`.
3. Для `modeling-baselines` добавлен run-kind `g3-2-multi-dataset` с per-dataset benchmark на общем protocol.
4. В benchmark добавлены model families: `centroid`, `gaussian_nb`, `logistic_regression`, `random_forest`, `xgboost`, `lightgbm`, `catboost`.
5. Добавлен обязательный блок ограничений в `research-report.md` (`Interpretation Limits`) про proxy labels и ограничения claim-grade интерпретации.
6. Выполнен реальный запуск `g3-2-multi-dataset` по локальным unified artifacts.
7. После разбора результатов зафиксировано, что pooled benchmark на смешанных label tiers недостаточен для claim-grade выбора модели по `arousal`.
8. В `modeling-baselines` добавлен run-kind `g3-2-multi-dataset-strategy`, который:
   - классифицирует datasets как `real`, `protocol-mapped`, `proxy`;
   - назначает роль dataset-а (`primary_supervision`, `auxiliary_pretraining`, `protocol_transfer_or_eval`, `skip`);
   - строит рекомендуемые training phases;
   - фиксирует policy по synthetic data: только `augmentation_only`, не основной supervision source.
9. В `modeling-baselines` добавлен run-kind `g3-2-multi-dataset-protocol`, который:
   - исполняет readiness-checks перед фазовым обучением;
   - проверяет dataset coverage;
   - проверяет наличие harmonized non-label signal features;
   - строит `phase-execution` table со статусами `ready/blocked/skipped`.
10. Устранен блокер `harmonized_signal_features`:
   - добавлен harmonized signal feature extraction из raw data для `WESAD`, `G-REx`, `EmoWear`;
   - `DAPPER` сохранен как `skip` по coverage, но больше не блокирует весь протокол.
11. Прогнан реальный protocol execution run после исправлений; итоговый статус переведен в `ready`.

## Исторический comparison run

- `experiment_id`: `g3-2-multi-dataset-20260322T191834Z`
- Итог: `dataset_count=3`, `skipped_dataset_count=1`
- Benchmarked: `WESAD`, `G-REx`, `EmoWear`
- Skipped: `DAPPER` (причина: `insufficient train/test examples after filtering`)

## Артефакты

Результаты сохранены в:

`/Users/kgz/Desktop/p/on-go/data/external/multi-dataset/comparison/`

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `predictions-test.csv`
4. `per-subject-metrics.csv`
5. `failed-variants.csv`
6. `research-report.md`
7. `plots/`

## Strategy / protocol runs

### Training strategy

Артефакты:

`/Users/kgz/Desktop/p/on-go/data/external/multi-dataset/strategy/`

1. `training-strategy-report.json`
2. `dataset-strategy.csv`
3. `training-phases.csv`
4. `training-protocol.md`

Ключевые решения:

1. `grex-v1` -> `primary_supervision`
2. `emowear-v1` -> `auxiliary_pretraining`
3. `wesad-v1` -> `protocol_transfer_or_eval`
4. `dapper-v1` -> `skip`
5. AI/synthetic data policy -> `augmentation_only`

### Protocol execution

Артефакты:

`/Users/kgz/Desktop/p/on-go/data/external/multi-dataset/protocol-execution/`

1. `protocol-execution-report.json`
2. `readiness-checks.csv`
3. `phase-execution.csv`
4. `protocol-execution.md`

Итоговый статус на `2026-03-27`:

1. `overall_status = ready`
2. `blocking_check_count = 0`
3. `blocking_phase_count = 0`
4. harmonized signal features подтверждены:
   - `wesad = 80`
   - `grex = 16`
   - `emowear = 28`
5. `dapper` помечен как `skipped`, а не `failed`

## Ключевые результаты

1. `WESAD`: winner `activity=label_centroid (1.0)`, `arousal=label_gaussian_nb (1.0)`.
2. `G-REx`: winner `activity=label_random_forest (0.284418)`, `arousal=label_gaussian_nb (1.0)`.
3. `EmoWear`: winner `activity=label_gaussian_nb (1.0)`, `arousal=label_gaussian_nb (1.0)`.
4. Зафиксирован `LightGBM` fail-case на `EmoWear` (`arousal_coarse`) при вырожденном числе классов.
5. Эти near-perfect multi-dataset comparison numbers не используются как основание для model selection, потому что часть datasets опирается на `protocol-mapped/proxy` labels.
6. Новым каноническим входом в multi-dataset обучение считается не `g3-2-multi-dataset`, а связка:
   - `g3-2-multi-dataset-strategy`
   - `g3-2-multi-dataset-protocol`
   - phased training / self-training plan

## Ограничения и интерпретация

1. Для `EmoWear` и `DAPPER` используются proxy labels, поэтому их нельзя трактовать как claim-grade supervision source для итоговой `arousal` модели.
2. В `WESAD` `arousal` на текущем шаге является protocol-derived proxy, а не независимой сегментной affect annotation.
3. Из-за этого pooled comparison на `WESAD/G-REx/EmoWear` следует трактовать как harmonization/diagnostic step, а не как финальную валидацию generalized emotion model.
4. Канонический training order теперь такой:
   - proxy pretraining;
   - real-label finetuning;
   - protocol transfer/eval;
   - cross-dataset evaluation;
   - только затем controlled self-training.
5. `DAPPER` сохраняется в registry, но исключается из активного training loop до устранения coverage issue.

## Измененные файлы (ядро шага)

1. `services/dataset-registry/src/dataset_registry/external_imports.py`
2. `services/dataset-registry/src/dataset_registry/main.py`
3. `services/dataset-registry/README.md`
4. `services/modeling-baselines/src/modeling_baselines/multi_dataset.py`
5. `services/modeling-baselines/src/modeling_baselines/main.py`
6. `services/modeling-baselines/tests/test_multi_dataset.py`
7. `services/modeling-baselines/README.md`

## Вывод

`G3.2` больше не трактуется как "просто comparative benchmark". Шаг доведен до более строгого состояния:

1. datasets разделены по качеству supervision;
2. protocol gate теперь реально проверяет readiness;
3. harmonized signal features подтверждены на реальных raw datasets;
4. multi-dataset линия готова к фазовому обучению, но не к безусловному pooled fitting.
