from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class ClassificationMetrics:
    macro_f1: float
    balanced_accuracy: float
    weighted_f1: float
    macro_recall: float
    confusion_matrix: list[list[int]]
    labels: list[str]
    per_class_support: dict[str, int]


def compute_classification_metrics(y_true: list[str], y_pred: list[str]) -> ClassificationMetrics:
    if not y_true:
        raise ValueError("classification metrics require non-empty y_true")
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have equal length")

    labels = sorted(set(y_true) | set(y_pred))
    index = {label: i for i, label in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for true_label, predicted_label in zip(y_true, y_pred):
        cm[index[true_label], index[predicted_label]] += 1

    supports = cm.sum(axis=1).astype(float)
    predicted = cm.sum(axis=0).astype(float)
    diagonal = np.diag(cm).astype(float)

    precision = np.divide(
        diagonal,
        predicted,
        out=np.zeros_like(diagonal, dtype=float),
        where=predicted > 0,
    )
    recall = np.divide(
        diagonal,
        supports,
        out=np.zeros_like(diagonal, dtype=float),
        where=supports > 0,
    )
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(diagonal, dtype=float),
        where=(precision + recall) > 0,
    )

    valid_class_mask = supports > 0
    macro_f1 = float(f1[valid_class_mask].mean()) if np.any(valid_class_mask) else 0.0
    macro_recall = float(recall[valid_class_mask].mean()) if np.any(valid_class_mask) else 0.0
    weighted_f1 = float(np.divide((f1 * supports).sum(), supports.sum(), out=np.array(0.0), where=supports.sum() > 0))

    return ClassificationMetrics(
        macro_f1=round(macro_f1, 6),
        balanced_accuracy=round(macro_recall, 6),
        weighted_f1=round(weighted_f1, 6),
        macro_recall=round(macro_recall, 6),
        confusion_matrix=cm.astype(int).tolist(),
        labels=labels,
        per_class_support={label: int(supports[index[label]]) for label in labels},
    )


def compute_mae(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    truth = np.asarray(list(y_true), dtype=float)
    pred = np.asarray(list(y_pred), dtype=float)
    if truth.size == 0:
        raise ValueError("mae requires non-empty vectors")
    if truth.size != pred.size:
        raise ValueError("mae requires same vector size")
    return round(float(np.abs(truth - pred).mean()), 6)


def compute_spearman_rho(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    truth = np.asarray(list(y_true), dtype=float)
    pred = np.asarray(list(y_pred), dtype=float)
    if truth.size == 0:
        raise ValueError("spearman requires non-empty vectors")
    if truth.size != pred.size:
        raise ValueError("spearman requires same vector size")

    truth_ranks = _rank_average_ties(truth)
    pred_ranks = _rank_average_ties(pred)

    truth_centered = truth_ranks - truth_ranks.mean()
    pred_centered = pred_ranks - pred_ranks.mean()
    denom = float(np.sqrt((truth_centered**2).sum() * (pred_centered**2).sum()))
    if denom == 0.0:
        return 0.0
    return round(float((truth_centered * pred_centered).sum() / denom), 6)


def compute_quadratic_weighted_kappa(y_true: Iterable[int], y_pred: Iterable[int], min_rating: int, max_rating: int) -> float:
    truth = np.asarray(list(y_true), dtype=int)
    pred = np.asarray(list(y_pred), dtype=int)
    if truth.size == 0:
        raise ValueError("quadratic weighted kappa requires non-empty vectors")
    if truth.size != pred.size:
        raise ValueError("quadratic weighted kappa requires same vector size")
    if min_rating >= max_rating:
        raise ValueError("min_rating must be less than max_rating")

    num_ratings = max_rating - min_rating + 1
    weights = np.zeros((num_ratings, num_ratings), dtype=float)
    denom = float((num_ratings - 1) ** 2)
    for i in range(num_ratings):
        for j in range(num_ratings):
            weights[i, j] = ((i - j) ** 2) / denom

    observed = np.zeros((num_ratings, num_ratings), dtype=float)
    for t, p in zip(truth, pred):
        if t < min_rating or t > max_rating or p < min_rating or p > max_rating:
            raise ValueError("ratings are out of bounds")
        observed[t - min_rating, p - min_rating] += 1.0
    observed /= observed.sum()

    truth_hist = observed.sum(axis=1)
    pred_hist = observed.sum(axis=0)
    expected = np.outer(truth_hist, pred_hist)

    weighted_observed = float((weights * observed).sum())
    weighted_expected = float((weights * expected).sum())
    if weighted_expected == 0.0:
        return 0.0
    return round(1.0 - (weighted_observed / weighted_expected), 6)


def _rank_average_ties(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.zeros_like(values, dtype=float)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1
    return ranks
