# Personalization Methodology Redesign (H4)

## Статус

- Step ID: `H4`
- Date: `2026-03-22`
- Scope: redesign methodological track после `I1.1` перед запуском `H5/H6`

## 1. Research objective

Основной научный вклад фиксируется как воспроизводимая методика персонализации поверх уже обученного `WESAD` baseline, отдельно для:

1. `watch-only`
2. `fusion`

Основные personalization targets:

1. `arousal_coarse` (claim-grade первичный track)
2. `valence` (exploratory/ограниченный claim-grade track)

## 2. Core hypotheses

1. `H4-HYP-1`: для `arousal_coarse` персонализация c небольшим calibration budget (label-efficient) должна снижать worst-case degradation относительно `global` и давать положительный median subject-level gain.
2. `H4-HYP-2`: на `watch-only` линии label-efficient персонализация должна давать меньший gain, чем на `fusion`, но оставаться статистически различимой от нуля.
3. `H4-HYP-3`: для `valence` label-free и weak-label варианты могут улучшать subject-level stability, но пока не считаются достаточными для сильного clinical-grade claim без дополнительных датасетов/labels.
4. `H4-HYP-4`: методика считается жизнеспособной только если устойчиво ограничивает деградации (`worst_subject_delta >= -0.05` по headline metric для основного набора стратегий).

## 3. Strategy matrix (обязательные линии)

Матрица фиксирует, что в `H5` сравниваются как минимум две adaptation families на каждый cell:

| Modality | Target | Strategy family | Label budget mode | Purpose |
| --- | --- | --- | --- | --- |
| `watch-only` | `arousal_coarse` | `LE_CALIBRATION_HEAD` | label-efficient | subject calibration с малым бюджетом разметки |
| `watch-only` | `arousal_coarse` | `LF_TTA_CONSISTENCY` | label-free | test-time adaptation по стабильности предсказаний |
| `watch-only` | `valence` | `LE_ORDINAL_CALIBRATION` | label-efficient | калибровка ordinal шкалы на персональном подмножестве |
| `watch-only` | `valence` | `LF_DOMAIN_ALIGNMENT` | label-free | unsupervised alignment персонального распределения признаков |
| `fusion` | `arousal_coarse` | `LE_CALIBRATION_HEAD` | label-efficient | персональная калибровка поверх multimodal baseline |
| `fusion` | `arousal_coarse` | `LF_TTA_CONSISTENCY` | label-free | адаптация без новых labels в replay/live окне |
| `fusion` | `valence` | `LE_ORDINAL_CALIBRATION` | label-efficient | персональная ordinal-калибровка multimodal выхода |
| `fusion` | `valence` | `LF_DOMAIN_ALIGNMENT` | label-free | label-free стабилизация на межсессионном дрейфе |

## 4. Evaluation guardrails для H5/H6

1. Сравнение только на едином subject-wise протоколе.
2. Для каждого strategy-variant обязательны:
   - `global` reference;
   - `light` (если применимо);
   - новый variant.
3. Обязательные графики:
   - subject-level gain distribution;
   - budget sensitivity;
   - worst-case degradation.
4. Для `valence` все выводы маркируются как `exploratory`, если не выполнены claim-grade условия по coverage и устойчивости.
5. Любой label-free variant должен отдельно репортить drift/failure cases и частоту деградаций по субъектам.

## 5. Claim boundaries

1. `arousal_coarse`:
   - допускается claim о gain только при устойчивом улучшении по median субъектов и контроле worst-case degradation.
2. `valence`:
   - допускается только ограниченный exploratory claim до расширения label-quality и cross-dataset подтверждения.
3. `EmoWear`/`DAPPER` proxy labels не используются как единственный источник для финального personalization claim.

## 6. H5 readiness criteria

`H5` считается готовым к запуску, если:

1. strategy matrix из этого документа реализована в experiment config;
2. для каждой линии (`watch-only`, `fusion`) есть label-efficient и label-free кандидат;
3. заранее зафиксированы budget levels и правила остановки при деградации;
4. структура отчетности полностью соответствует `docs/research/model-reporting-standard.md`.

## 7. Next step

`H5 - Weak-label / label-free personalization benchmark`
