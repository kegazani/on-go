from __future__ import annotations

import numpy as np

from modeling_baselines.estimators import build_estimator_classifier, supported_classifier_kinds


def test_supported_classifier_kinds_cover_requested_extended_model_zoo() -> None:
    kinds = set(supported_classifier_kinds())
    assert {"random_forest", "xgboost", "lightgbm", "catboost"}.issubset(kinds)
    assert len(kinds) >= 18


def test_logistic_regression_wrapper_predicts_expected_labels() -> None:
    classifier = build_estimator_classifier("logistic_regression")
    x_train = np.asarray(
        [
            [0.0, 0.1],
            [0.2, 0.0],
            [3.0, 3.1],
            [3.2, 2.9],
        ],
        dtype=float,
    )
    y_train = ["low", "low", "high", "high"]
    classifier.fit(x_train, y_train)

    predicted = classifier.predict(np.asarray([[0.1, 0.2], [3.1, 3.0]], dtype=float))
    assert predicted == ["low", "high"]


def test_logistic_regression_wrapper_exposes_feature_importance_rows() -> None:
    classifier = build_estimator_classifier("logistic_regression")
    x_train = np.asarray(
        [
            [0.0, 0.1, 0.2],
            [0.2, 0.0, 0.1],
            [3.0, 3.1, 2.8],
            [3.2, 2.9, 3.1],
        ],
        dtype=float,
    )
    y_train = ["low", "low", "high", "high"]
    classifier.fit(x_train, y_train)

    rows = classifier.feature_importance_rows(
        variant_name="watch_only_logistic_regression",
        track="activity",
        feature_names=["f0", "f1", "f2"],
    )
    assert rows
    assert rows[0]["importance_kind"] == "coef_abs_mean"
    assert {row["feature_name"] for row in rows} == {"f0", "f1", "f2"}


def test_predict_sanitizes_non_finite_inputs() -> None:
    classifier = build_estimator_classifier("logistic_regression")
    x_train = np.asarray(
        [
            [0.0, 0.1],
            [0.2, 0.0],
            [3.0, 3.1],
            [3.2, 2.9],
        ],
        dtype=float,
    )
    y_train = ["low", "low", "high", "high"]
    classifier.fit(x_train, y_train)

    x_test = np.asarray([[np.nan, np.inf], [-np.inf, 2.5]], dtype=float)
    predicted = classifier.predict(x_test)
    assert len(predicted) == 2
