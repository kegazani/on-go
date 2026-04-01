# H4 - Personalization methodology redesign

## Статус

- Step ID: `H4`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Зафиксировать методику персонализации как основной научный вклад: формальный `research objective`, гипотезы, strategy matrix для `watch-only/fusion` и `arousal/valence`, а также границы claim-grade интерпретации перед `H5/H6`.

## Что сделано

1. Подготовлен методологический документ:
   - `docs/research/personalization-methodology-redesign.md`.
2. Зафиксированы исследовательские гипотезы `H4-HYP-1..H4-HYP-4` с акцентом на:
   - устойчивый subject-level gain;
   - контроль `worst-case degradation`;
   - отдельные правила интерпретации для `valence`.
3. Зафиксирована обязательная strategy matrix:
   - `watch-only/fusion` x `arousal_coarse/valence`;
   - label-efficient и label-free strategy families для каждого cell.
4. Собран research-grade H4 пакет:
   - `evaluation-report.json`;
   - `model-comparison.csv`;
   - `per-subject-metrics.csv`;
   - `research-report.md`;
   - `plots/`.
5. Зафиксированы readiness criteria для перехода к `H5`.

## Ключевой результат

`H4` завершен: personalization track формализован как отдельная методика с четкими hypothesis-driven стратегиями, claim-границами и проверяемыми критериями перехода к benchmark шагу `H5`.

## Следующий шаг

`H5 - Weak-label / label-free personalization benchmark`
