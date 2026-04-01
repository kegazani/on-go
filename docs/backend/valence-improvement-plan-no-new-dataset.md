# Valence Improvement Plan (без собственного нового датасета)

## Контекст

После `E2.3` и `E2.4`:

1. `valence` показывает полезный сигнал, но нестабилен для claim-safe production.
2. Нужен план повышения устойчивости без сбора собственного нового датасета.

## Ограничения

1. Не создаем новый датасет с нуля.
2. Используем только доступные источники (`WESAD`, `G-REx`, `EmoWear`) и текущий capture/pipeline.
3. Synthetic-данные допускаются только как `augmentation_only`, не как primary supervision.

## Цели

1. Повысить устойчивость `valence` на subject-wise / LOSO.
2. Снизить риск shortcut/leakage и переобучения на отдельных фолдах.
3. Подготовить claim-safe границы для `valence` (или формально закрепить exploratory-only policy до выполнения gate-условий).

## Фазы выполнения

## V1. Error Anatomy и стабильность

1. Разложить `valence` ошибки по:
   - subject;
   - классу (`negative/neutral/positive`);
   - сессии и source_label_value.
2. Вычислить:
   - mean/std/CI `macro_f1` по LOSO;
   - worst-subject `macro_f1`;
   - пер-класс recall/precision и confusion drift.
3. Артефакты:
   - `valence-error-analysis.csv`
   - `valence-subject-stability.csv`
   - `valence-confusion-by-fold.csv`

Gate V1:
1. Есть формальный список failure modes (минимум 3).
2. Определены худшие субъекты/классы для целевой оптимизации.

## V2. Label Quality Hardening (без новых разметок)

1. Ввести quality-tiers для `valence`:
   - `tier_a` (high confidence);
   - `tier_b` (medium);
   - `tier_c` (noisy/auxiliary).
2. Добавить weighted training policy:
   - основной вес для `tier_a`;
   - пониженный вес для `tier_b`;
   - исключение или минимальный вес `tier_c`.
3. Проверить sensitivity к порогу confidence/quality.

Gate V2:
1. Noisy-сегменты уменьшают вклад в обучение.
2. Нет деградации `arousal` при введении quality weights.

## V3. Feature Stabilization для valence

1. Добавить baseline-normalized признаки:
   - отклонения от subject/session baseline;
   - delta-признаки в temporal контексте.
2. Добавить interaction-блоки:
   - watch context x polar HRV;
   - motion intensity x cardio recovery proxies.
3. Сделать ablation:
   - `watch_only`;
   - `polar_rr_acc`;
   - `fusion`;
   - `fusion + normalized`;
   - `fusion + normalized + interactions`.

Gate V3:
1. Минимум 2 из 3 LOSO-run показывают прирост против текущего valence baseline.
2. Нет single-feature shortcut alert в safety audit.

## V4. Ordinal-first Modeling

1. Обучать `valence` не только как coarse-классы, но и как ordinal target.
2. Сравнить family-кандидаты:
   - `catboost`;
   - `xgboost`;
   - `lightgbm`;
   - `gaussian_nb` (baseline).
3. Репортить одновременно:
   - coarse: `macro_f1`, `balanced_accuracy`;
   - ordinal: `mae`, `spearman_rho`, `qwk`.

Gate V4:
1. Winner определяется по совместному критерию coarse + ordinal stability.
2. Модель не может быть promoted, если есть сильная деградация на worst-subject.

## V5. Cross-dataset transfer без нового датасета

1. Использовать `G-REx` как real-label reinforcement для `valence`.
2. Использовать `EmoWear` только как auxiliary/proxy pretraining.
3. Выполнить transfer protocol:
   - pretrain on auxiliary;
   - fine-tune on real-label subset;
   - validate on WESAD claim subset.

Gate V5:
1. Перенос дает прирост стабильности, а не только локальный фолд-спайк.
2. Claim-grade решение принимается только по real-label evaluation.

## V6. Claim-safe decision

1. Если выполнены stability-gates:
   - продвинуть `valence` в `limited-production` scope.
2. Если не выполнены:
   - оставить `valence` в `exploratory` policy с явными ограничениями.
3. Зафиксировать deployment boundaries:
   - confidence gating;
   - fallback behavior;
   - monitoring KPIs.

## Обязательные метрики и пороги (минимум)

1. `valence_coarse macro_f1` (LOSO mean, CI, worst-subject).
2. `balanced_accuracy` (LOSO mean).
3. `QWK`, `Spearman`, `MAE` для ordinal track.
4. `single_feature_probe top_macro_f1` < `0.95`.
5. `permutation sanity`: baseline существенно выше permutation distribution (`p < 0.05`).

## Порядок выполнения (execution order)

1. `V1` Error anatomy.
2. `V2` Label quality hardening.
3. `V3` Feature stabilization + ablation.
4. `V4` Ordinal-first model sweep.
5. `V5` Cross-dataset transfer.
6. `V6` Claim-safe decision и freeze policy.

## Артефакт-пакет на каждом этапе

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `per-subject-metrics.csv`
4. `research-report.md`
5. `plots/`:
   - metric bars;
   - delta bars;
   - confusion matrices;
   - subject-level distribution;
   - ordinal scatter.
