# I1 - Research report и production scope decision

## Статус

- Step ID: `I1`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

После завершения `H3` свести результаты `G1-G3` и `H1-H3` в единый decision-oriented пакет, чтобы закрыть research gate и зафиксировать production scope.

## Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Собран единый machine-readable пакет `I1`:
   - `data/artifacts/research-gate/i1-production-scope-decision/evaluation-report.json`
   - `model-comparison.csv`
   - `per-subject-metrics.csv`
   - `research-report.md`
   - `plots/`
3. В сравнительную таблицу `I1` включены:
   - top `G3.1` model-zoo кандидаты (`activity`, `arousal_coarse`);
   - winners `G3.2` per dataset/track;
   - `H3` mode-level сравнение (`global/light/full`) по всем personalization variants.
4. Сформированы presentation-ready визуализации:
   - aggregated top-by-step графики по `activity` и `arousal_coarse`;
   - histogram `full vs light` subject-level gain;
   - добавлены reference plots по feature-importance, multi-dataset winners и worst-case degradation.
5. В `research-report.md` зафиксировано production scope decision:
   - `in-scope`: strongest global watch/fusion candidates + guarded full personalization path;
   - `out-of-scope`: claim-grade выводы по proxy-label datasets, default light personalization, valence product commitments без дополнительных labels.

## Артефакты

Итоговый пакет:

`/Users/kgz/Desktop/p/on-go/data/artifacts/research-gate/i1-production-scope-decision/`

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `per-subject-metrics.csv`
4. `research-report.md`
5. `plots/`

## Ключевой результат

`I1` закрыт: сформирован единый decision-oriented research пакет, после которого можно переходить к `J1` и формализовать experiment tracking/model registry как обязательный foundation перед production inference.

## Следующий шаг

`J1 - Experiment tracking и model registry`
