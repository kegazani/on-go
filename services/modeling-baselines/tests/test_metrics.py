from modeling_baselines.metrics import (
    compute_classification_metrics,
    compute_mae,
    compute_quadratic_weighted_kappa,
    compute_spearman_rho,
)


def test_classification_metrics_shape_and_support() -> None:
    metrics = compute_classification_metrics(
        y_true=["a", "a", "b", "c"],
        y_pred=["a", "b", "b", "c"],
    )
    assert metrics.labels == ["a", "b", "c"]
    assert metrics.per_class_support == {"a": 2, "b": 1, "c": 1}
    assert len(metrics.confusion_matrix) == 3
    assert metrics.macro_f1 > 0.0


def test_ordinal_metrics_perfect_prediction() -> None:
    y_true = [1, 3, 5, 7, 9]
    y_pred = [1, 3, 5, 7, 9]
    assert compute_mae(y_true, y_pred) == 0.0
    assert compute_spearman_rho(y_true, y_pred) == 1.0
    assert compute_quadratic_weighted_kappa(y_true, y_pred, min_rating=1, max_rating=9) == 1.0
