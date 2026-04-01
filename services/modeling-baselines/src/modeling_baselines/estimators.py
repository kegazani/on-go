from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ClassifierConfig:
    kind: str
    model_family: str
    standardize: bool
    hyperparameters: dict[str, Any]
    description: str


class EncodedEstimatorClassifier:
    def __init__(self, kind: str, standardize: bool) -> None:
        self.kind = kind
        self._standardize = standardize
        self._estimator: Any | None = None
        self._labels: list[str] = []
        self._label_to_index: dict[str, int] = {}
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    def fit(self, features: np.ndarray, labels: list[str]) -> None:
        if features.shape[0] == 0:
            raise ValueError("cannot fit classifier on empty features")
        if features.shape[0] != len(labels):
            raise ValueError("features row count must match labels count")

        self._labels = sorted(set(labels))
        self._label_to_index = {label: index for index, label in enumerate(self._labels)}
        y = np.asarray([self._label_to_index[label] for label in labels], dtype=int)
        x = self._prepare_features(features, fit=True)
        estimator = _build_estimator(self.kind, num_classes=len(self._labels))
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", message="The covariance matrix of class .* is not full rank.*")
            estimator.fit(x, y)
        self._estimator = estimator

    def predict(self, features: np.ndarray) -> list[str]:
        if self._estimator is None:
            raise ValueError("classifier is not fitted")
        if features.shape[0] == 0:
            return []
        x = self._prepare_features(features, fit=False)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")
            raw = np.asarray(self._estimator.predict(x))
        if raw.ndim > 1:
            raw = raw.reshape(-1)
        return [self._labels[int(index)] for index in raw.astype(int).tolist()]

    def feature_importance_rows(
        self,
        variant_name: str,
        track: str,
        feature_names: list[str],
    ) -> list[dict[str, Any]]:
        if self._estimator is None:
            return []
        importance_values, importance_kind = _extract_importances(self._estimator, feature_names)
        if importance_values is None:
            return []
        ordered = sorted(
            zip(feature_names, importance_values),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )
        rows = []
        for rank, (feature_name, importance) in enumerate(ordered, start=1):
            rows.append(
                {
                    "variant_name": variant_name,
                    "track": track,
                    "feature_name": feature_name,
                    "importance": round(float(importance), 6),
                    "importance_abs": round(abs(float(importance)), 6),
                    "importance_kind": importance_kind,
                    "rank": rank,
                }
            )
        return rows

    def _prepare_features(self, features: np.ndarray, fit: bool) -> np.ndarray:
        x = _sanitize_numeric_matrix(np.asarray(features, dtype=float))
        if not self._standardize:
            return x
        if fit:
            mean = x.mean(axis=0)
            std = x.std(axis=0)
            std = np.where(std == 0.0, 1.0, std)
            self._mean = mean
            self._std = std
        if self._mean is None or self._std is None:
            raise ValueError("standardization parameters are not fitted")
        standardized = (x - self._mean) / self._std
        return _sanitize_numeric_matrix(standardized)


def _sanitize_numeric_matrix(matrix: np.ndarray, clip_abs: float = 1e6) -> np.ndarray:
    clean = np.nan_to_num(matrix, nan=0.0, posinf=clip_abs, neginf=-clip_abs)
    if clip_abs > 0:
        clean = np.clip(clean, -clip_abs, clip_abs)
    return clean


def supported_classifier_kinds() -> list[str]:
    return sorted(_CLASSIFIER_CONFIGS.keys())


def get_classifier_config(kind: str) -> ClassifierConfig:
    config = _CLASSIFIER_CONFIGS.get(kind)
    if config is None:
        raise ValueError(f"unsupported classifier kind: {kind}")
    return config


def build_estimator_classifier(kind: str) -> EncodedEstimatorClassifier:
    config = get_classifier_config(kind)
    return EncodedEstimatorClassifier(kind=kind, standardize=config.standardize)


_CLASSIFIER_CONFIGS: dict[str, ClassifierConfig] = {
    "logistic_regression": ClassifierConfig(
        kind="logistic_regression",
        model_family="logistic_regression_linear",
        standardize=True,
        hyperparameters={"C": 1.0, "max_iter": 2000, "class_weight": "balanced", "solver": "lbfgs"},
        description="Balanced multinomial logistic regression on tabular segment features.",
    ),
    "ridge_classifier": ClassifierConfig(
        kind="ridge_classifier",
        model_family="ridge_classifier_linear",
        standardize=True,
        hyperparameters={"alpha": 1.0, "class_weight": "balanced", "solver": "auto"},
        description="Ridge classifier with class balancing on standardized features.",
    ),
    "lda": ClassifierConfig(
        kind="lda",
        model_family="linear_discriminant_analysis",
        standardize=True,
        hyperparameters={"solver": "lsqr", "shrinkage": "auto"},
        description="Regularized linear discriminant analysis on standardized features.",
    ),
    "qda": ClassifierConfig(
        kind="qda",
        model_family="quadratic_discriminant_analysis",
        standardize=True,
        hyperparameters={"reg_param": 0.1},
        description="Quadratic discriminant analysis with covariance regularization.",
    ),
    "linear_svm": ClassifierConfig(
        kind="linear_svm",
        model_family="linear_support_vector_machine",
        standardize=True,
        hyperparameters={"C": 1.0, "class_weight": "balanced", "max_iter": 20000},
        description="Linear support vector classifier with class balancing.",
    ),
    "rbf_svm": ClassifierConfig(
        kind="rbf_svm",
        model_family="rbf_support_vector_machine",
        standardize=True,
        hyperparameters={"C": 2.0, "gamma": "scale", "class_weight": "balanced"},
        description="Kernel SVM with RBF decision surface.",
    ),
    "knn": ClassifierConfig(
        kind="knn",
        model_family="k_nearest_neighbors",
        standardize=True,
        hyperparameters={"n_neighbors": 5, "weights": "distance", "metric": "minkowski"},
        description="Distance-weighted k-nearest neighbors on standardized features.",
    ),
    "decision_tree": ClassifierConfig(
        kind="decision_tree",
        model_family="decision_tree",
        standardize=False,
        hyperparameters={"max_depth": 8, "min_samples_leaf": 2, "class_weight": "balanced", "random_state": 42},
        description="Single CART decision tree with depth regularization.",
    ),
    "random_forest": ClassifierConfig(
        kind="random_forest",
        model_family="random_forest",
        standardize=False,
        hyperparameters={"n_estimators": 400, "max_depth": 10, "min_samples_leaf": 1, "class_weight": "balanced_subsample", "random_state": 42},
        description="Balanced random forest ensemble with moderate depth.",
    ),
    "extra_trees": ClassifierConfig(
        kind="extra_trees",
        model_family="extra_trees",
        standardize=False,
        hyperparameters={"n_estimators": 400, "max_depth": 10, "min_samples_leaf": 1, "class_weight": "balanced", "random_state": 42},
        description="Extremely randomized trees ensemble.",
    ),
    "bagging_tree": ClassifierConfig(
        kind="bagging_tree",
        model_family="bagging_tree_ensemble",
        standardize=False,
        hyperparameters={"n_estimators": 300, "base_max_depth": 6, "base_min_samples_leaf": 2, "random_state": 42},
        description="Bagging ensemble over shallow decision trees.",
    ),
    "ada_boost": ClassifierConfig(
        kind="ada_boost",
        model_family="adaboost",
        standardize=False,
        hyperparameters={"n_estimators": 300, "learning_rate": 0.05, "random_state": 42},
        description="AdaBoost ensemble on shallow trees.",
    ),
    "gradient_boosting": ClassifierConfig(
        kind="gradient_boosting",
        model_family="gradient_boosting",
        standardize=False,
        hyperparameters={"n_estimators": 300, "learning_rate": 0.05, "max_depth": 3, "random_state": 42},
        description="Gradient boosting classifier over shallow decision trees.",
    ),
    "hist_gradient_boosting": ClassifierConfig(
        kind="hist_gradient_boosting",
        model_family="hist_gradient_boosting",
        standardize=False,
        hyperparameters={"max_iter": 300, "learning_rate": 0.05, "max_depth": 6, "random_state": 42},
        description="Histogram-based gradient boosting classifier.",
    ),
    "mlp": ClassifierConfig(
        kind="mlp",
        model_family="multi_layer_perceptron",
        standardize=True,
        hyperparameters={"hidden_layer_sizes": [128, 64], "alpha": 0.0005, "max_iter": 1500, "early_stopping": True, "random_state": 42},
        description="Compact feed-forward neural baseline on standardized features.",
    ),
    "sgd_linear": ClassifierConfig(
        kind="sgd_linear",
        model_family="stochastic_gradient_linear_classifier",
        standardize=True,
        hyperparameters={"loss": "modified_huber", "alpha": 0.0005, "class_weight": "balanced", "max_iter": 3000, "random_state": 42},
        description="Linear large-margin classifier trained with SGD.",
    ),
    "xgboost": ClassifierConfig(
        kind="xgboost",
        model_family="xgboost_hist",
        standardize=False,
        hyperparameters={"n_estimators": 300, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9, "random_state": 42},
        description="XGBoost tree ensemble with histogram tree method.",
    ),
    "lightgbm": ClassifierConfig(
        kind="lightgbm",
        model_family="lightgbm_gbdt",
        standardize=False,
        hyperparameters={"n_estimators": 300, "num_leaves": 31, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9, "random_state": 42},
        description="LightGBM gradient boosting trees.",
    ),
    "catboost": ClassifierConfig(
        kind="catboost",
        model_family="catboost_multiclass",
        standardize=False,
        hyperparameters={"iterations": 300, "depth": 6, "learning_rate": 0.05, "auto_class_weights": "Balanced", "random_seed": 42},
        description="CatBoost multiclass gradient boosting ensemble.",
    ),
}


def _build_estimator(kind: str, num_classes: int) -> Any:
    if kind in {
        "logistic_regression",
        "ridge_classifier",
        "lda",
        "qda",
        "linear_svm",
        "rbf_svm",
        "knn",
        "decision_tree",
        "random_forest",
        "extra_trees",
        "bagging_tree",
        "ada_boost",
        "gradient_boosting",
        "hist_gradient_boosting",
        "mlp",
        "sgd_linear",
    }:
        return _build_sklearn_estimator(kind)
    if kind == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            objective="multi:softmax",
            num_class=num_classes,
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            min_child_weight=1.0,
            tree_method="hist",
            random_state=42,
            n_jobs=1,
            verbosity=0,
        )
    if kind == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            objective="multiclass",
            n_estimators=300,
            num_leaves=31,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            class_weight="balanced",
            random_state=42,
            n_jobs=1,
            verbosity=-1,
        )
    if kind == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            loss_function="MultiClass",
            iterations=300,
            depth=6,
            learning_rate=0.05,
            auto_class_weights="Balanced",
            random_seed=42,
            allow_writing_files=False,
            verbose=False,
            thread_count=1,
        )
    raise ValueError(f"unsupported classifier kind: {kind}")


def _build_sklearn_estimator(kind: str) -> Any:
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
    from sklearn.ensemble import (
        AdaBoostClassifier,
        BaggingClassifier,
        ExtraTreesClassifier,
        GradientBoostingClassifier,
        HistGradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.svm import LinearSVC, SVC
    from sklearn.tree import DecisionTreeClassifier

    if kind == "logistic_regression":
        return LogisticRegression(
            C=1.0,
            max_iter=2000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=42,
        )
    if kind == "ridge_classifier":
        return RidgeClassifier(alpha=1.0, class_weight="balanced")
    if kind == "lda":
        return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    if kind == "qda":
        return QuadraticDiscriminantAnalysis(reg_param=0.1)
    if kind == "linear_svm":
        return LinearSVC(C=1.0, class_weight="balanced", max_iter=20000, random_state=42)
    if kind == "rbf_svm":
        return SVC(C=2.0, kernel="rbf", gamma="scale", class_weight="balanced")
    if kind == "knn":
        return KNeighborsClassifier(n_neighbors=5, weights="distance")
    if kind == "decision_tree":
        return DecisionTreeClassifier(max_depth=8, min_samples_leaf=2, class_weight="balanced", random_state=42)
    if kind == "random_forest":
        return RandomForestClassifier(
            n_estimators=400,
            max_depth=10,
            min_samples_leaf=1,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=1,
        )
    if kind == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=400,
            max_depth=10,
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=1,
        )
    if kind == "bagging_tree":
        return BaggingClassifier(
            estimator=DecisionTreeClassifier(max_depth=6, min_samples_leaf=2, random_state=42),
            n_estimators=300,
            random_state=42,
            n_jobs=1,
        )
    if kind == "ada_boost":
        return AdaBoostClassifier(
            n_estimators=300,
            learning_rate=0.05,
            random_state=42,
        )
    if kind == "gradient_boosting":
        return GradientBoostingClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        )
    if kind == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            max_depth=6,
            random_state=42,
        )
    if kind == "mlp":
        return MLPClassifier(
            hidden_layer_sizes=(128, 64),
            alpha=0.0005,
            max_iter=1500,
            early_stopping=True,
            random_state=42,
        )
    if kind == "sgd_linear":
        return SGDClassifier(
            loss="modified_huber",
            alpha=0.0005,
            class_weight="balanced",
            max_iter=3000,
            tol=1e-3,
            random_state=42,
        )
    raise ValueError(f"unsupported sklearn classifier kind: {kind}")


def _extract_importances(estimator: Any, feature_names: list[str]) -> tuple[np.ndarray | None, str | None]:
    if hasattr(estimator, "get_feature_importance"):
        try:
            values = np.asarray(estimator.get_feature_importance(type="FeatureImportance"), dtype=float).reshape(-1)
            if values.size == len(feature_names):
                return values, "catboost_feature_importance"
        except Exception:
            pass
    if hasattr(estimator, "feature_importances_"):
        values = np.asarray(estimator.feature_importances_, dtype=float).reshape(-1)
        if values.size == len(feature_names):
            return values, "feature_importances_"
    if hasattr(estimator, "coef_"):
        values = np.asarray(estimator.coef_, dtype=float)
        if values.ndim == 2:
            values = np.abs(values).mean(axis=0)
        else:
            values = np.abs(values).reshape(-1)
        if values.size == len(feature_names):
            return values, "coef_abs_mean"
    return None, None
