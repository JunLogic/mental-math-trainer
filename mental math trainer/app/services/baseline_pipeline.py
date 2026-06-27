from __future__ import annotations

import csv
import math
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import ElasticNet, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from app.services.dataset_builder import (
    AttemptDataset,
    DEFAULT_EXCLUDED_MODEL_COLUMNS,
    build_attempt_dataset_from_storage,
    filter_answered,
    filter_correct_only,
    filter_parse_succeeded,
    save_dataset_csv,
)
from app.services.storage import SQLiteStorage

MODEL_RANDOM_STATE = 42
DEFAULT_TEST_SIZE = 0.25
TOP_FEATURE_COUNT = 12
DEFAULT_EXPECTED_TIME_MODEL = "gradient_boosting_regressor"
TOP_LOG_DELTA_ROW_COUNT = 25
RESIDUAL_SLICE_LIMIT = 12
RESIDUAL_SLICE_MIN_COUNT = 3
WEAKNESS_PRIORITY_MIN_SUPPORT = 6
WEAKNESS_PRIORITY_SUPPORT_SATURATION = 12
TOP_TRAINING_TARGET_COUNT = 10
WEAKNESS_PRIORITY_DEFAULT_VIEW = "correct_only"
RESIDUAL_BAND_THRESHOLDS: dict[str, float] = {
    "mildly_slow": 0.1,
    "slow": 0.25,
    "breakdown": 0.5,
}
RESIDUAL_EXPORT_COLUMNS: tuple[str, ...] = (
    "saved_question_id",
    "run_id",
    "question_index",
    "base_operation",
    "mode",
    "result_label",
    "response_time_ms",
    "actual_time_log",
    "expected_time_log",
    "log_delta",
    "residual_band",
    "analysis_model",
    "feature_set",
    "used_decimal",
    "used_missing_variable",
    "answer_role",
    "a_value_normalized",
    "b_value_normalized",
    "result_value_normalized",
    "requires_carry",
    "num_carries",
    "carry_in_units",
    "carry_in_tens",
    "carry_creates_new_digit",
    "requires_borrow",
    "num_borrows",
    "borrow_in_units",
    "borrow_in_tens",
    "borrow_across_zero",
    "long_borrow_chain_length",
    "borrow_changes_leading_digit",
    "addition_crosses_decade",
    "addition_crosses_century",
    "sub_crosses_decade",
    "sub_crosses_century",
)
WEAKNESS_PRIORITY_CATEGORICAL_COLUMNS: tuple[str, ...] = (
    "base_operation",
    "answer_role",
)
WEAKNESS_PRIORITY_TRUE_FLAG_COLUMNS: tuple[str, ...] = (
    "used_decimal",
    "used_missing_variable",
    "requires_carry",
    "carry_in_units",
    "carry_in_tens",
    "carry_creates_new_digit",
    "requires_borrow",
    "borrow_in_units",
    "borrow_in_tens",
    "borrow_across_zero",
    "borrow_changes_leading_digit",
    "addition_crosses_decade",
    "addition_crosses_century",
    "sub_crosses_decade",
    "sub_crosses_century",
    "mult_one_digit_by_one_digit",
    "mult_one_digit_by_two_digit",
    "mult_two_digit_by_two_digit",
    "mult_units_product_ge_10",
    "div_exact",
    "quotient_is_integer",
    "division_result_terminating_decimal",
)
WEAKNESS_PRIORITY_POSITIVE_COUNT_COLUMNS: tuple[str, ...] = (
    "num_carries",
    "num_borrows",
    "long_borrow_chain_length",
)
WEAKNESS_PRIORITY_CSV_COLUMNS: tuple[str, ...] = (
    "view",
    "rank",
    "slice_type",
    "slice_key",
    "slice_description",
    "feature",
    "value",
    "support_count",
    "support_rate",
    "mean_log_delta",
    "median_log_delta",
    "slow_or_worse_rate",
    "breakdown_rate",
    "priority_score",
    "filter_expression",
    "why_it_matters",
)
WEAKNESS_PRIORITY_COMBO_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slice_key": "addition__requires_carry",
        "description": "addition + requires carry",
        "filters": (("base_operation", "addition"), ("requires_carry", True)),
    },
    {
        "slice_key": "addition__crosses_decade",
        "description": "addition + crosses decade",
        "filters": (("base_operation", "addition"), ("addition_crosses_decade", True)),
    },
    {
        "slice_key": "subtraction__requires_borrow",
        "description": "subtraction + requires borrow",
        "filters": (("base_operation", "subtraction"), ("requires_borrow", True)),
    },
    {
        "slice_key": "subtraction__requires_borrow__used_missing_variable",
        "description": "subtraction + requires borrow + missing variable",
        "filters": (
            ("base_operation", "subtraction"),
            ("requires_borrow", True),
            ("used_missing_variable", True),
        ),
    },
    {
        "slice_key": "subtraction__borrow_across_zero",
        "description": "subtraction + borrow across zero",
        "filters": (("base_operation", "subtraction"), ("borrow_across_zero", True)),
    },
    {
        "slice_key": "multiplication__two_digit_by_two_digit",
        "description": "multiplication + two digit by two digit",
        "filters": (("base_operation", "multiplication"), ("mult_two_digit_by_two_digit", True)),
    },
    {
        "slice_key": "multiplication__used_decimal",
        "description": "multiplication + decimals",
        "filters": (("base_operation", "multiplication"), ("used_decimal", True)),
    },
    {
        "slice_key": "division__used_missing_variable",
        "description": "division + missing variable",
        "filters": (("base_operation", "division"), ("used_missing_variable", True)),
    },
    {
        "slice_key": "division__exact",
        "description": "division + exact quotient",
        "filters": (("base_operation", "division"), ("div_exact", True)),
    },
)
RESIDUAL_SLICE_COLUMNS: tuple[str, ...] = (
    "base_operation",
    "mode",
    "used_decimal",
    "used_missing_variable",
    "answer_role",
    "requires_carry",
    "num_carries",
    "carry_in_units",
    "carry_in_tens",
    "carry_creates_new_digit",
    "requires_borrow",
    "num_borrows",
    "borrow_in_units",
    "borrow_in_tens",
    "borrow_across_zero",
    "long_borrow_chain_length",
    "borrow_changes_leading_digit",
    "addition_crosses_decade",
    "addition_crosses_century",
    "sub_crosses_decade",
    "sub_crosses_century",
)


@dataclass(frozen=True)
class TrainingArtifacts:
    output_dir: Path
    dataset_path: Path
    metrics_path: Path
    summary_path: Path
    feature_columns_path: Path
    model_feature_manifests_path: Path
    model_summaries_path: Path
    ablations_path: Path
    residual_rows_path: Path
    residual_summary_path: Path
    top_log_delta_rows_path: Path
    weakness_priority_path: Path
    weakness_priority_csv_path: Path
    top_training_targets_path: Path


def run_baseline_pipeline(
    storage: SQLiteStorage,
    output_dir: Path,
    use_full_features: bool = False,
    test_size: float = DEFAULT_TEST_SIZE,
    random_seed: int = MODEL_RANDOM_STATE,
    time_correct_only: bool = True,
) -> dict[str, Any]:
    dataset = build_attempt_dataset_from_storage(storage, use_full_features=use_full_features)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = output_dir / "attempt_dataset.csv"
    metrics_path = output_dir / "metrics.json"
    summary_path = output_dir / "dataset_summary.json"
    feature_columns_path = output_dir / "feature_columns.json"
    model_feature_manifests_path = output_dir / "model_feature_manifests.json"
    model_summaries_path = output_dir / "model_summaries.json"
    ablations_path = output_dir / "ablations.json"
    residual_rows_path = output_dir / "residual_rows.csv"
    residual_summary_path = output_dir / "residual_summary.json"
    top_log_delta_rows_path = output_dir / "top_log_delta_rows.json"
    weakness_priority_path = output_dir / "weakness_priority.json"
    weakness_priority_csv_path = output_dir / "weakness_priority.csv"
    top_training_targets_path = output_dir / "top_training_targets.json"

    save_dataset_csv(dataset.rows, dataset_path)
    _write_json(
        feature_columns_path,
        {
            "feature_set": dataset.feature_set,
            "available_feature_columns": dataset.available_feature_columns,
            "model_feature_columns": dataset.feature_columns,
            "default_excluded_model_columns": sorted(DEFAULT_EXCLUDED_MODEL_COLUMNS),
            "pruned_uninformative_model_columns": dataset.pruned_uninformative_model_columns,
        },
    )
    dataset_summary = dataset.summary()
    _write_json(summary_path, dataset_summary)

    model_results = {
        "error_models": _train_error_models(
            dataset=dataset,
            output_dir=output_dir,
            test_size=test_size,
            random_seed=random_seed,
        ),
        "time_models": _train_time_models(
            dataset=dataset,
            output_dir=output_dir,
            test_size=test_size,
            random_seed=random_seed,
            correct_only=time_correct_only,
            residual_rows_path=residual_rows_path,
            residual_summary_path=residual_summary_path,
            top_log_delta_rows_path=top_log_delta_rows_path,
            weakness_priority_path=weakness_priority_path,
            weakness_priority_csv_path=weakness_priority_csv_path,
            top_training_targets_path=top_training_targets_path,
        ),
    }
    model_feature_manifests = _collect_model_feature_manifests(model_results)
    ablations = _build_ablation_summary(dataset_summary, model_results)
    _write_json(metrics_path, _metrics_only(model_results))
    _write_json(model_feature_manifests_path, model_feature_manifests)
    _write_json(model_summaries_path, model_results)
    _write_json(ablations_path, ablations)

    return {
        "artifacts": TrainingArtifacts(
            output_dir=output_dir,
            dataset_path=dataset_path,
            metrics_path=metrics_path,
            summary_path=summary_path,
            feature_columns_path=feature_columns_path,
            model_feature_manifests_path=model_feature_manifests_path,
            model_summaries_path=model_summaries_path,
            ablations_path=ablations_path,
            residual_rows_path=residual_rows_path,
            residual_summary_path=residual_summary_path,
            top_log_delta_rows_path=top_log_delta_rows_path,
            weakness_priority_path=weakness_priority_path,
            weakness_priority_csv_path=weakness_priority_csv_path,
            top_training_targets_path=top_training_targets_path,
        ),
        "dataset_summary": dataset_summary,
        "results": model_results,
        "model_feature_manifests": model_feature_manifests,
        "ablations": ablations,
    }


def _train_error_models(
    dataset: AttemptDataset,
    output_dir: Path,
    test_size: float,
    random_seed: int,
) -> dict[str, Any]:
    rows = filter_answered(filter_parse_succeeded(dataset.rows))
    rows = [row for row in rows if row.get("y_error") is not None]
    if len(rows) < 8:
        return {"status": "skipped", "reason": "Need at least 8 answered parse-succeeded rows for error modelling."}

    classes = {int(row["y_error"]) for row in rows}
    if len(classes) < 2:
        return {"status": "skipped", "reason": "Need both correct and incorrect rows for error modelling."}

    split = _grouped_train_test_rows(rows, "y_error", test_size=test_size, random_seed=random_seed)
    if split.get("status") != "ok":
        return split
    train_rows, test_rows = split["train_rows"], split["test_rows"]
    y_train = split["y_train"]
    y_test = split["y_test"]
    if len(set(y_train)) < 2:
        return {
            "status": "skipped",
            "reason": "Grouped train split does not contain both error classes.",
            "split": split["split"],
        }
    X_train_dicts = _vectorizable_rows(train_rows, dataset.feature_columns)
    X_test_dicts = _vectorizable_rows(test_rows, dataset.feature_columns)
    vectorizer = DictVectorizer(sparse=False)
    X_train = vectorizer.fit_transform(X_train_dicts)
    X_test = vectorizer.transform(X_test_dicts)
    feature_names = vectorizer.get_feature_names_out().tolist()

    logistic = LogisticRegression(max_iter=1000, random_state=random_seed, solver="liblinear")
    logistic.fit(X_train, y_train)
    logistic_predictions = logistic.predict(X_test)
    logistic_probabilities = logistic.predict_proba(X_test)[:, 1] if len(set(y_train)) > 1 else None

    tree = GradientBoostingClassifier(random_state=random_seed)
    tree.fit(X_train, y_train)
    tree_predictions = tree.predict(X_test)
    tree_probabilities = tree.predict_proba(X_test)[:, 1] if hasattr(tree, "predict_proba") else None

    logistic_path = output_dir / "error_logistic_regression.pkl"
    tree_path = output_dir / "error_gradient_boosting.pkl"
    _save_pickle(logistic_path, {"vectorizer": vectorizer, "model": logistic, "feature_names": feature_names})
    _save_pickle(tree_path, {"vectorizer": vectorizer, "model": tree, "feature_names": feature_names})

    return {
        "status": "ok",
        "rows": len(rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "feature_count": len(feature_names),
        "split": split["split"],
        "models": {
            "logistic_regression": {
                "metrics": _classification_metrics(y_test, logistic_predictions, logistic_probabilities),
                "artifacts": {"model_path": str(logistic_path)},
                "model_input_columns": list(dataset.feature_columns),
                "vectorized_feature_names": feature_names,
                "top_coefficients": _top_linear_weights(feature_names, logistic.coef_[0]),
                "by_operation": _classification_metrics_by_operation(test_rows, y_test, logistic_predictions),
            },
            "gradient_boosting_classifier": {
                "metrics": _classification_metrics(y_test, tree_predictions, tree_probabilities),
                "artifacts": {"model_path": str(tree_path)},
                "model_input_columns": list(dataset.feature_columns),
                "vectorized_feature_names": feature_names,
                "top_feature_importances": _top_feature_importances(feature_names, tree.feature_importances_),
                "by_operation": _classification_metrics_by_operation(test_rows, y_test, tree_predictions),
            },
        },
    }


def _train_time_models(
    dataset: AttemptDataset,
    output_dir: Path,
    test_size: float,
    random_seed: int,
    correct_only: bool,
    residual_rows_path: Path,
    residual_summary_path: Path,
    top_log_delta_rows_path: Path,
    weakness_priority_path: Path,
    weakness_priority_csv_path: Path,
    top_training_targets_path: Path,
) -> dict[str, Any]:
    rows = filter_answered(filter_parse_succeeded(dataset.rows))
    if correct_only:
        rows = filter_correct_only(rows)
    rows = [row for row in rows if row.get("y_time_log") is not None]
    if len(rows) < 8:
        return {"status": "skipped", "reason": "Need at least 8 answered parse-succeeded rows for time modelling."}

    split = _grouped_train_test_rows(rows, "y_time_log", test_size=test_size, random_seed=random_seed)
    if split.get("status") != "ok":
        return split
    train_rows, test_rows = split["train_rows"], split["test_rows"]
    y_train = split["y_train"]
    y_test = split["y_test"]
    X_train_dicts = _vectorizable_rows(train_rows, dataset.feature_columns)
    X_test_dicts = _vectorizable_rows(test_rows, dataset.feature_columns)
    vectorizer = DictVectorizer(sparse=False)
    X_train = vectorizer.fit_transform(X_train_dicts)
    X_test = vectorizer.transform(X_test_dicts)
    feature_names = vectorizer.get_feature_names_out().tolist()

    elastic_net = ElasticNet(alpha=0.2, l1_ratio=0.2, random_state=random_seed, max_iter=5000)
    elastic_net.fit(X_train, y_train)
    elastic_predictions = elastic_net.predict(X_test)

    tree = GradientBoostingRegressor(random_state=random_seed)
    tree.fit(X_train, y_train)
    tree_predictions = tree.predict(X_test)

    elastic_path = output_dir / "time_elastic_net.pkl"
    tree_path = output_dir / "time_gradient_boosting.pkl"
    _save_pickle(elastic_path, {"vectorizer": vectorizer, "model": elastic_net, "feature_names": feature_names})
    _save_pickle(tree_path, {"vectorizer": vectorizer, "model": tree, "feature_names": feature_names})

    residual_analysis = _build_time_residual_analysis(
        test_rows=test_rows,
        predictions_by_model={
            "elastic_net": elastic_predictions,
            "gradient_boosting_regressor": tree_predictions,
        },
        correct_only=correct_only,
        split=split["split"],
        residual_rows_path=residual_rows_path,
        residual_summary_path=residual_summary_path,
        top_log_delta_rows_path=top_log_delta_rows_path,
        weakness_priority_path=weakness_priority_path,
        weakness_priority_csv_path=weakness_priority_csv_path,
        top_training_targets_path=top_training_targets_path,
    )

    return {
        "status": "ok",
        "rows": len(rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "feature_count": len(feature_names),
        "correct_only": correct_only,
        "split": split["split"],
        "residual_analysis": residual_analysis,
        "models": {
            "elastic_net": {
                "metrics": _regression_metrics(y_test, elastic_predictions),
                "artifacts": {"model_path": str(elastic_path)},
                "model_input_columns": list(dataset.feature_columns),
                "vectorized_feature_names": feature_names,
                "top_coefficients": _top_linear_weights(feature_names, elastic_net.coef_),
                "by_operation": _regression_metrics_by_operation(test_rows, y_test, elastic_predictions),
            },
            "gradient_boosting_regressor": {
                "metrics": _regression_metrics(y_test, tree_predictions),
                "artifacts": {"model_path": str(tree_path)},
                "model_input_columns": list(dataset.feature_columns),
                "vectorized_feature_names": feature_names,
                "top_feature_importances": _top_feature_importances(feature_names, tree.feature_importances_),
                "by_operation": _regression_metrics_by_operation(test_rows, y_test, tree_predictions),
            },
        },
    }


def _grouped_train_test_rows(
    rows: list[dict[str, Any]],
    target_column: str,
    test_size: float,
    random_seed: int,
) -> dict[str, Any]:
    run_ids = [row.get("run_id") for row in rows if row.get("run_id") is not None]
    unique_run_ids = sorted({int(run_id) for run_id in run_ids})
    if len(unique_run_ids) < 2:
        return {
            "status": "skipped",
            "reason": "Need at least 2 runs for grouped train/test evaluation.",
            "split": {
                "strategy": "group_shuffle_split",
                "group_column": "run_id",
                "unique_runs": len(unique_run_ids),
                "train_run_ids": [],
                "test_run_ids": [],
                "warning": None,
            },
        }

    groups = [row.get("run_id") for row in rows]
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_seed)
    train_indices, test_indices = next(splitter.split(rows, groups=groups))
    train_rows = [rows[index] for index in train_indices]
    test_rows = [rows[index] for index in test_indices]
    if not train_rows or not test_rows:
        return {
            "status": "skipped",
            "reason": "Grouped split produced an empty train or test partition.",
            "split": {
                "strategy": "group_shuffle_split",
                "group_column": "run_id",
                "unique_runs": len(unique_run_ids),
                "train_run_ids": sorted({int(row.get("run_id")) for row in train_rows if row.get("run_id") is not None}),
                "test_run_ids": sorted({int(row.get("run_id")) for row in test_rows if row.get("run_id") is not None}),
                "warning": None,
            },
        }

    y_train = [row[target_column] for row in train_rows]
    y_test = [row[target_column] for row in test_rows]
    warning = None
    if len(unique_run_ids) < 4:
        warning = f"Only {len(unique_run_ids)} unique runs available; grouped split may be unstable."
    return {
        "status": "ok",
        "train_rows": train_rows,
        "test_rows": test_rows,
        "y_train": y_train,
        "y_test": y_test,
        "split": {
            "strategy": "group_shuffle_split",
            "group_column": "run_id",
            "unique_runs": len(unique_run_ids),
            "train_run_ids": sorted({int(row.get("run_id")) for row in train_rows if row.get("run_id") is not None}),
            "test_run_ids": sorted({int(row.get("run_id")) for row in test_rows if row.get("run_id") is not None}),
            "warning": warning,
        },
    }


def _vectorizable_rows(rows: Iterable[dict[str, Any]], feature_columns: Iterable[str]) -> list[dict[str, Any]]:
    selected_columns = list(feature_columns)
    vectorized_rows: list[dict[str, Any]] = []
    for row in rows:
        vectorized_row = {
            key: value
            for key, value in row.items()
            if key in selected_columns and value is not None
        }
        vectorized_rows.append(vectorized_row)
    return vectorized_rows


def _classification_metrics(
    y_true: list[int],
    predictions: list[int],
    probabilities: list[float] | None,
) -> dict[str, Any]:
    metrics = {
        "accuracy": round(float(accuracy_score(y_true, predictions)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, predictions)), 4),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "roc_auc": None,
    }
    if probabilities is not None and len(set(y_true)) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, probabilities)), 4)
    return metrics


def _regression_metrics(y_true: list[float], predictions: list[float]) -> dict[str, Any]:
    mse = float(mean_squared_error(y_true, predictions))
    return {
        "mae": round(float(mean_absolute_error(y_true, predictions)), 4),
        "rmse": round(math.sqrt(mse), 4),
        "r2": round(float(r2_score(y_true, predictions)), 4),
    }


def _top_linear_weights(feature_names: list[str], weights: Iterable[float]) -> list[dict[str, Any]]:
    feature_weight_pairs = list(zip(feature_names, weights))
    if len(feature_weight_pairs) != len(feature_names):
        raise ValueError("Linear model weights are out of sync with feature names.")
    weighted = [
        {"feature": feature_name, "weight": round(float(weight), 6)}
        for feature_name, weight in feature_weight_pairs
    ]
    weighted.sort(key=lambda item: abs(item["weight"]), reverse=True)
    return weighted[:TOP_FEATURE_COUNT]


def _top_feature_importances(feature_names: list[str], importances: Iterable[float]) -> list[dict[str, Any]]:
    feature_importance_pairs = list(zip(feature_names, importances))
    if len(feature_importance_pairs) != len(feature_names):
        raise ValueError("Tree-model importances are out of sync with feature names.")
    weighted = [
        {"feature": feature_name, "importance": round(float(importance), 6)}
        for feature_name, importance in feature_importance_pairs
    ]
    weighted.sort(key=lambda item: item["importance"], reverse=True)
    return weighted[:TOP_FEATURE_COUNT]


def _metrics_only(results: dict[str, Any]) -> dict[str, Any]:
    condensed: dict[str, Any] = {}
    for task_name, task_result in results.items():
        if task_result.get("status") != "ok":
            condensed[task_name] = task_result
            continue
        condensed[task_name] = {
            "rows": task_result["rows"],
            "train_rows": task_result["train_rows"],
            "test_rows": task_result["test_rows"],
            "split": task_result.get("split"),
            "models": {
                model_name: model_result["metrics"]
                for model_name, model_result in task_result["models"].items()
            },
        }
    return condensed


def _classification_metrics_by_operation(
    test_rows: list[dict[str, Any]],
    y_true: list[int],
    predictions: list[int],
) -> dict[str, Any]:
    metrics_by_operation: dict[str, Any] = {}
    grouped_indices: dict[str, list[int]] = {}
    for index, row in enumerate(test_rows):
        grouped_indices.setdefault(str(row.get("base_operation", "unknown")), []).append(index)
    for operation, indices in grouped_indices.items():
        subset_true = [y_true[index] for index in indices]
        subset_predictions = [predictions[index] for index in indices]
        metrics_by_operation[operation] = {
            "count": len(indices),
            "accuracy": round(float(accuracy_score(subset_true, subset_predictions)), 4),
            "balanced_accuracy": (
                round(float(balanced_accuracy_score(subset_true, subset_predictions)), 4)
                if len(set(subset_true)) > 1
                else None
            ),
        }
    return metrics_by_operation


def _regression_metrics_by_operation(
    test_rows: list[dict[str, Any]],
    y_true: list[float],
    predictions: list[float],
) -> dict[str, Any]:
    metrics_by_operation: dict[str, Any] = {}
    grouped_indices: dict[str, list[int]] = {}
    for index, row in enumerate(test_rows):
        grouped_indices.setdefault(str(row.get("base_operation", "unknown")), []).append(index)
    for operation, indices in grouped_indices.items():
        subset_true = [y_true[index] for index in indices]
        subset_predictions = [predictions[index] for index in indices]
        mse = float(mean_squared_error(subset_true, subset_predictions))
        metrics_by_operation[operation] = {
            "count": len(indices),
            "mae": round(float(mean_absolute_error(subset_true, subset_predictions)), 4),
            "rmse": round(math.sqrt(mse), 4),
        }
    return metrics_by_operation


def _collect_model_feature_manifests(results: dict[str, Any]) -> dict[str, Any]:
    manifests: dict[str, Any] = {}
    for task_name, task_result in results.items():
        if task_result.get("status") != "ok":
            manifests[task_name] = task_result
            continue
        manifests[task_name] = {
            "split": task_result.get("split"),
            "models": {
                model_name: {
                    "model_input_columns": model_result.get("model_input_columns", []),
                    "vectorized_feature_names": model_result.get("vectorized_feature_names", []),
                }
                for model_name, model_result in task_result["models"].items()
            },
        }
        if task_name == "time_models" and task_result.get("residual_analysis", {}).get("status") == "ok":
            manifests[task_name]["residual_analysis"] = {
                "analysis_model": task_result["residual_analysis"].get("analysis_model"),
                "artefacts": task_result["residual_analysis"].get("artefacts"),
            }
    return manifests


def _build_ablation_summary(dataset_summary: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    ablations: dict[str, Any] = {
        "dataset_counts": {
            "rows": dataset_summary["rows"],
            "answered_rows": dataset_summary["answered_rows"],
            "correct_rows": dataset_summary["correct_rows"],
            "incorrect_rows": dataset_summary["incorrect_rows"],
            "operation_counts": dataset_summary["operation_counts"],
            "mode_counts": dataset_summary["mode_counts"],
        }
    }
    for task_name, task_result in results.items():
        if task_result.get("status") != "ok":
            ablations[task_name] = task_result
            continue
        ablations[task_name] = {
            "split": task_result.get("split"),
            "models": {
                model_name: model_result.get("by_operation", {})
                for model_name, model_result in task_result["models"].items()
            },
        }
        if task_name == "time_models" and task_result.get("residual_analysis", {}).get("status") == "ok":
            ablations[task_name]["residual_analysis"] = {
                "analysis_model": task_result["residual_analysis"].get("analysis_model"),
                "by_operation": task_result["residual_analysis"].get("by_operation", {}),
            }
    return ablations


def _build_time_residual_analysis(
    test_rows: list[dict[str, Any]],
    predictions_by_model: dict[str, Any],
    correct_only: bool,
    split: dict[str, Any],
    residual_rows_path: Path,
    residual_summary_path: Path,
    top_log_delta_rows_path: Path,
    weakness_priority_path: Path,
    weakness_priority_csv_path: Path,
    top_training_targets_path: Path,
) -> dict[str, Any]:
    analysis_model = DEFAULT_EXPECTED_TIME_MODEL
    if analysis_model not in predictions_by_model:
        return {
            "status": "skipped",
            "reason": f"Expected-time analysis model {analysis_model} is unavailable.",
        }

    expected_time_predictions = [float(value) for value in predictions_by_model[analysis_model]]
    residual_rows = _build_residual_rows(
        test_rows=test_rows,
        expected_time_predictions=expected_time_predictions,
        analysis_model=analysis_model,
    )
    top_log_delta_rows = _top_log_delta_rows(residual_rows)
    residual_summary = _summarize_residual_rows(
        residual_rows=residual_rows,
        correct_only=correct_only,
        split=split,
        analysis_model=analysis_model,
    )
    weakness_priority = _build_weakness_priority_analysis(
        residual_rows=residual_rows,
        analysis_model=analysis_model,
        correct_only_source=correct_only,
        split=split,
    )
    weakness_priority_rows = _flatten_weakness_priority_rows(weakness_priority)

    _write_csv_rows(residual_rows_path, residual_rows, preferred_columns=RESIDUAL_EXPORT_COLUMNS)
    _write_json(residual_summary_path, residual_summary)
    _write_json(top_log_delta_rows_path, top_log_delta_rows)
    _write_json(weakness_priority_path, weakness_priority)
    _write_csv_rows(
        weakness_priority_csv_path,
        weakness_priority_rows,
        preferred_columns=WEAKNESS_PRIORITY_CSV_COLUMNS,
    )
    _write_json(top_training_targets_path, weakness_priority["top_training_targets"])

    return {
        "status": "ok",
        "analysis_model": analysis_model,
        "rows": len(residual_rows),
        "correct_only": correct_only,
        "definition": {
            "actual_time_log": "log1p(response_time_ms)",
            "expected_time_log": (
                "Held-out prediction from the grouped test split using the "
                f"{analysis_model} baseline time model."
            ),
            "log_delta": "actual_time_log - expected_time_log",
        },
        "band_definitions": {
            "on_band": f"log_delta < {RESIDUAL_BAND_THRESHOLDS['mildly_slow']}",
            "mildly_slow": (
                f"{RESIDUAL_BAND_THRESHOLDS['mildly_slow']} <= log_delta < "
                f"{RESIDUAL_BAND_THRESHOLDS['slow']}"
            ),
            "slow": (
                f"{RESIDUAL_BAND_THRESHOLDS['slow']} <= log_delta < "
                f"{RESIDUAL_BAND_THRESHOLDS['breakdown']}"
            ),
            "breakdown": f"log_delta >= {RESIDUAL_BAND_THRESHOLDS['breakdown']}",
        },
        "artefacts": {
            "residual_rows_path": str(residual_rows_path),
            "residual_summary_path": str(residual_summary_path),
            "top_log_delta_rows_path": str(top_log_delta_rows_path),
            "weakness_priority_path": str(weakness_priority_path),
            "weakness_priority_csv_path": str(weakness_priority_csv_path),
            "top_training_targets_path": str(top_training_targets_path),
        },
        "by_operation": residual_summary["by_operation"],
        "weakness_priority": {
            "default_view": weakness_priority["default_view"],
            "available_views": weakness_priority["available_views"],
            "minimum_support": weakness_priority["minimum_support"],
            "priority_scoring": weakness_priority["priority_scoring"],
        },
    }


def _build_residual_rows(
    test_rows: list[dict[str, Any]],
    expected_time_predictions: list[float],
    analysis_model: str,
) -> list[dict[str, Any]]:
    residual_rows: list[dict[str, Any]] = []
    for row, expected_time_log in zip(test_rows, expected_time_predictions):
        actual_time_log = float(row["y_time_log"])
        log_delta = actual_time_log - expected_time_log
        residual_row = dict(row)
        residual_row.update(
            {
                "actual_time_log": round(actual_time_log, 6),
                "expected_time_log": round(float(expected_time_log), 6),
                "log_delta": round(float(log_delta), 6),
                "residual_band": _residual_band(log_delta),
                "analysis_model": analysis_model,
            }
        )
        residual_rows.append(residual_row)
    return residual_rows


def _residual_band(log_delta: float) -> str:
    if log_delta >= RESIDUAL_BAND_THRESHOLDS["breakdown"]:
        return "breakdown"
    if log_delta >= RESIDUAL_BAND_THRESHOLDS["slow"]:
        return "slow"
    if log_delta >= RESIDUAL_BAND_THRESHOLDS["mildly_slow"]:
        return "mildly_slow"
    return "on_band"


def _top_log_delta_rows(residual_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_rows = sorted(residual_rows, key=lambda row: float(row["log_delta"]), reverse=True)
    top_rows = ranked_rows[:TOP_LOG_DELTA_ROW_COUNT]
    return [
        {
            key: row.get(key)
            for key in RESIDUAL_EXPORT_COLUMNS
            if key in row
        }
        for row in top_rows
    ]


def _summarize_residual_rows(
    residual_rows: list[dict[str, Any]],
    correct_only: bool,
    split: dict[str, Any],
    analysis_model: str,
) -> dict[str, Any]:
    log_deltas = [float(row["log_delta"]) for row in residual_rows]
    actual_logs = [float(row["actual_time_log"]) for row in residual_rows]
    expected_logs = [float(row["expected_time_log"]) for row in residual_rows]
    band_counts: dict[str, int] = {
        "on_band": 0,
        "mildly_slow": 0,
        "slow": 0,
        "breakdown": 0,
    }
    for row in residual_rows:
        band = str(row["residual_band"])
        band_counts[band] = band_counts.get(band, 0) + 1

    return {
        "analysis_model": analysis_model,
        "rows": len(residual_rows),
        "correct_only": correct_only,
        "split": split,
        "definitions": {
            "actual_time_log": "log1p(response_time_ms)",
            "expected_time_log": (
                "Held-out grouped test prediction from the baseline "
                f"{analysis_model} model."
            ),
            "log_delta": "actual_time_log - expected_time_log",
        },
        "band_definitions": {
            "on_band": f"log_delta < {RESIDUAL_BAND_THRESHOLDS['mildly_slow']}",
            "mildly_slow": (
                f"{RESIDUAL_BAND_THRESHOLDS['mildly_slow']} <= log_delta < "
                f"{RESIDUAL_BAND_THRESHOLDS['slow']}"
            ),
            "slow": (
                f"{RESIDUAL_BAND_THRESHOLDS['slow']} <= log_delta < "
                f"{RESIDUAL_BAND_THRESHOLDS['breakdown']}"
            ),
            "breakdown": f"log_delta >= {RESIDUAL_BAND_THRESHOLDS['breakdown']}",
        },
        "overall": {
            "mean_actual_time_log": _rounded_mean(actual_logs),
            "mean_expected_time_log": _rounded_mean(expected_logs),
            "mean_log_delta": _rounded_mean(log_deltas),
            "median_log_delta": _rounded_median(log_deltas),
            "max_log_delta": round(max(log_deltas), 6) if log_deltas else None,
            "min_log_delta": round(min(log_deltas), 6) if log_deltas else None,
        },
        "band_counts": band_counts,
        "band_rates": {
            band: round(count / len(residual_rows), 4)
            for band, count in sorted(band_counts.items())
        },
        "by_operation": _residual_summary_by_field(residual_rows, "base_operation"),
        "high_mean_log_delta_slices": _residual_slice_summary(residual_rows),
        "top_log_delta_rows": _top_log_delta_rows(residual_rows),
    }


def _residual_summary_by_field(
    residual_rows: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any]:
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    for row in residual_rows:
        field_value = row.get(field_name)
        if field_value is None:
            continue
        grouped_rows.setdefault(str(field_value), []).append(row)

    summary: dict[str, Any] = {}
    for field_value, rows in sorted(grouped_rows.items()):
        log_deltas = [float(row["log_delta"]) for row in rows]
        slow_or_worse = sum(
            1
            for row in rows
            if row["residual_band"] in {"slow", "breakdown"}
        )
        summary[field_value] = {
            "count": len(rows),
            "mean_log_delta": _rounded_mean(log_deltas),
            "median_log_delta": _rounded_median(log_deltas),
            "slow_or_worse_rate": round(slow_or_worse / len(rows), 4),
        }
    return summary


def _residual_slice_summary(residual_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for column in RESIDUAL_SLICE_COLUMNS:
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        value_labels: dict[str, Any] = {}
        for row in residual_rows:
            raw_value = row.get(column)
            if raw_value is None:
                continue
            value_key = json.dumps(raw_value, sort_keys=True)
            grouped_rows.setdefault(value_key, []).append(row)
            value_labels[value_key] = raw_value

        for value_key, rows in grouped_rows.items():
            if len(rows) < RESIDUAL_SLICE_MIN_COUNT:
                continue
            log_deltas = [float(row["log_delta"]) for row in rows]
            mean_log_delta = _rounded_mean(log_deltas)
            if mean_log_delta is None or mean_log_delta <= 0:
                continue
            slices.append(
                {
                    "feature": column,
                    "value": value_labels[value_key],
                    "count": len(rows),
                    "mean_log_delta": mean_log_delta,
                    "median_log_delta": _rounded_median(log_deltas),
                }
            )

    slices.sort(key=lambda item: (item["mean_log_delta"], item["count"]), reverse=True)
    return slices[:RESIDUAL_SLICE_LIMIT]


def _build_weakness_priority_analysis(
    residual_rows: list[dict[str, Any]],
    analysis_model: str,
    correct_only_source: bool,
    split: dict[str, Any],
) -> dict[str, Any]:
    views: dict[str, Any] = {}
    unavailable_views: dict[str, str] = {}
    correct_rows = [row for row in residual_rows if str(row.get("result_label")) == "correct"]

    if correct_rows:
        views["correct_only"] = _build_weakness_priority_view(correct_rows, view_name="correct_only")
    else:
        unavailable_views["correct_only"] = "No correct rows were present in the residual analysis source."

    if correct_only_source:
        unavailable_views["all_answered"] = (
            "Residual rows were generated from a correct-only time-model dataset. "
            "Rerun with time_correct_only=False to rank all answered attempts."
        )
    elif residual_rows:
        views["all_answered"] = _build_weakness_priority_view(residual_rows, view_name="all_answered")
    else:
        unavailable_views["all_answered"] = "No answered rows were present in the residual analysis source."

    default_view = _default_weakness_priority_view(views)
    top_training_targets = {
        "default_view": default_view,
        "target_count": 0,
        "targets": [],
    }
    if default_view in views:
        targets = views[default_view]["ranked_slices"][:TOP_TRAINING_TARGET_COUNT]
        top_training_targets = {
            "analysis_model": analysis_model,
            "default_view": default_view,
            "row_filter": views[default_view]["row_filter"],
            "rows": views[default_view]["rows"],
            "target_count": len(targets),
            "targets": targets,
        }

    return {
        "analysis_model": analysis_model,
        "source_residual_rows": {
            "rows": len(residual_rows),
            "correct_only_source": correct_only_source,
            "split": split,
        },
        "default_view": default_view,
        "available_views": sorted(views.keys()),
        "unavailable_views": unavailable_views,
        "definitions": {
            "log_delta": "actual_time_log - expected_time_log",
            "slow_or_worse_rate": "share of rows where residual_band is slow or breakdown",
            "breakdown_rate": "share of rows where residual_band is breakdown",
        },
        "minimum_support": {
            "count": WEAKNESS_PRIORITY_MIN_SUPPORT,
            "rule": (
                "Only slices with support_count >= "
                f"{WEAKNESS_PRIORITY_MIN_SUPPORT} are eligible for ranking."
            ),
        },
        "priority_scoring": {
            "rule": (
                "priority_score = (max(mean_log_delta, 0) + 0.5 * max(median_log_delta, 0)) "
                f"* min(1.0, support_count / {WEAKNESS_PRIORITY_SUPPORT_SATURATION}) "
                "* (1.0 + slow_or_worse_rate + 1.5 * breakdown_rate)"
            ),
            "support_saturation_count": WEAKNESS_PRIORITY_SUPPORT_SATURATION,
            "notes": (
                "The score rewards slices that are meaningfully slower than expected, "
                "have enough examples, and frequently land in the slow/breakdown bands."
            ),
        },
        "slice_types_considered": {
            "single_feature_categorical": list(WEAKNESS_PRIORITY_CATEGORICAL_COLUMNS),
            "single_feature_true_flags": list(WEAKNESS_PRIORITY_TRUE_FLAG_COLUMNS),
            "single_feature_positive_counts": list(WEAKNESS_PRIORITY_POSITIVE_COUNT_COLUMNS),
            "structured_combinations": [
                {
                    "slice_key": spec["slice_key"],
                    "description": spec["description"],
                    "filter_expression": _filter_expression(spec["filters"]),
                }
                for spec in WEAKNESS_PRIORITY_COMBO_SPECS
            ],
        },
        "views": views,
        "top_training_targets": top_training_targets,
    }


def _build_weakness_priority_view(
    residual_rows: list[dict[str, Any]],
    view_name: str,
) -> dict[str, Any]:
    ranked_slices, candidate_slice_count = _rank_weakness_slices(residual_rows, view_name=view_name)
    row_filter = "result_label == 'correct'" if view_name == "correct_only" else "all answered rows"
    return {
        "row_filter": row_filter,
        "rows": len(residual_rows),
        "candidate_slice_count": candidate_slice_count,
        "ranked_slice_count": len(ranked_slices),
        "ranked_slices": ranked_slices,
    }


def _rank_weakness_slices(
    residual_rows: list[dict[str, Any]],
    view_name: str,
) -> tuple[list[dict[str, Any]], int]:
    candidate_slice_count = 0
    ranked_slices: list[dict[str, Any]] = []
    total_rows = len(residual_rows)

    for column in WEAKNESS_PRIORITY_CATEGORICAL_COLUMNS:
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        value_labels: dict[str, Any] = {}
        for row in residual_rows:
            raw_value = row.get(column)
            if raw_value is None:
                continue
            value_key = json.dumps(raw_value, sort_keys=True)
            grouped_rows.setdefault(value_key, []).append(row)
            value_labels[value_key] = raw_value
        for value_key, rows in grouped_rows.items():
            candidate_slice_count += 1
            entry = _build_weakness_slice_entry(
                rows=rows,
                total_rows=total_rows,
                view_name=view_name,
                slice_type="single_feature",
                slice_key=f"{column}={_slice_value_token(value_labels[value_key])}",
                slice_description=_describe_single_feature_slice(column, value_labels[value_key]),
                filters=((column, value_labels[value_key]),),
                feature=column,
                value=value_labels[value_key],
            )
            if entry is not None:
                ranked_slices.append(entry)

    for column in WEAKNESS_PRIORITY_TRUE_FLAG_COLUMNS:
        rows = [row for row in residual_rows if row.get(column) is True]
        if not rows:
            continue
        candidate_slice_count += 1
        entry = _build_weakness_slice_entry(
            rows=rows,
            total_rows=total_rows,
            view_name=view_name,
            slice_type="single_feature",
            slice_key=f"{column}=true",
            slice_description=_describe_single_feature_slice(column, True),
            filters=((column, True),),
            feature=column,
            value=True,
        )
        if entry is not None:
            ranked_slices.append(entry)

    for column in WEAKNESS_PRIORITY_POSITIVE_COUNT_COLUMNS:
        grouped_rows: dict[int, list[dict[str, Any]]] = {}
        for row in residual_rows:
            raw_value = row.get(column)
            if raw_value is None or raw_value <= 0:
                continue
            grouped_rows.setdefault(int(raw_value), []).append(row)
        for value, rows in sorted(grouped_rows.items()):
            candidate_slice_count += 1
            entry = _build_weakness_slice_entry(
                rows=rows,
                total_rows=total_rows,
                view_name=view_name,
                slice_type="single_feature",
                slice_key=f"{column}={value}",
                slice_description=_describe_single_feature_slice(column, value),
                filters=((column, value),),
                feature=column,
                value=value,
            )
            if entry is not None:
                ranked_slices.append(entry)

    for combo_spec in WEAKNESS_PRIORITY_COMBO_SPECS:
        rows = [row for row in residual_rows if _row_matches_filters(row, combo_spec["filters"])]
        if not rows:
            continue
        candidate_slice_count += 1
        entry = _build_weakness_slice_entry(
            rows=rows,
            total_rows=total_rows,
            view_name=view_name,
            slice_type="structured_combo",
            slice_key=str(combo_spec["slice_key"]),
            slice_description=str(combo_spec["description"]),
            filters=combo_spec["filters"],
            feature=None,
            value=None,
        )
        if entry is not None:
            ranked_slices.append(entry)

    ranked_slices = _deduplicate_weakness_slices(ranked_slices)
    ranked_slices.sort(
        key=lambda item: (
            float(item["priority_score"]),
            float(item["mean_log_delta"]),
            float(item["median_log_delta"]),
            int(item["support_count"]),
            str(item["slice_description"]),
        ),
        reverse=True,
    )
    for rank, item in enumerate(ranked_slices, start=1):
        item.pop("_filter_count", None)
        item.pop("_row_signature", None)
        item["rank"] = rank
    return ranked_slices, candidate_slice_count


def _build_weakness_slice_entry(
    rows: list[dict[str, Any]],
    total_rows: int,
    view_name: str,
    slice_type: str,
    slice_key: str,
    slice_description: str,
    filters: tuple[tuple[str, Any], ...],
    feature: str | None,
    value: Any,
) -> dict[str, Any] | None:
    support_count = len(rows)
    if support_count < WEAKNESS_PRIORITY_MIN_SUPPORT:
        return None

    log_deltas = [float(row["log_delta"]) for row in rows]
    mean_log_delta = _rounded_mean(log_deltas)
    if mean_log_delta is None or mean_log_delta <= 0:
        return None

    median_log_delta = _rounded_median(log_deltas) or 0.0
    slow_or_worse_count = sum(
        1
        for row in rows
        if row.get("residual_band") in {"slow", "breakdown"}
    )
    breakdown_count = sum(1 for row in rows if row.get("residual_band") == "breakdown")
    slow_or_worse_rate = round(slow_or_worse_count / support_count, 4)
    breakdown_rate = round(breakdown_count / support_count, 4)
    support_factor = min(1.0, support_count / WEAKNESS_PRIORITY_SUPPORT_SATURATION)
    severity = max(mean_log_delta, 0.0) + (0.5 * max(median_log_delta, 0.0))
    frequency_factor = 1.0 + slow_or_worse_rate + (1.5 * breakdown_rate)
    priority_score = round(severity * support_factor * frequency_factor, 6)
    if priority_score <= 0:
        return None

    return {
        "view": view_name,
        "slice_type": slice_type,
        "slice_key": slice_key,
        "slice_description": slice_description,
        "feature": feature,
        "value": value,
        "filters": [
            {"feature": field_name, "value": field_value}
            for field_name, field_value in filters
        ],
        "filter_expression": _filter_expression(filters),
        "support_count": support_count,
        "support_rate": round(support_count / total_rows, 4) if total_rows else None,
        "mean_log_delta": mean_log_delta,
        "median_log_delta": round(median_log_delta, 6),
        "slow_or_worse_rate": slow_or_worse_rate,
        "breakdown_rate": breakdown_rate,
        "priority_score": priority_score,
        "why_it_matters": _build_weakness_reason(
            slice_description=slice_description,
            support_count=support_count,
            mean_log_delta=mean_log_delta,
            median_log_delta=median_log_delta,
            slow_or_worse_rate=slow_or_worse_rate,
            breakdown_rate=breakdown_rate,
            view_name=view_name,
        ),
        "_filter_count": len(filters),
        "_row_signature": tuple(sorted(_slice_row_identifier(row) for row in rows)),
    }


def _default_weakness_priority_view(views: dict[str, Any]) -> str:
    if (
        WEAKNESS_PRIORITY_DEFAULT_VIEW in views
        and views[WEAKNESS_PRIORITY_DEFAULT_VIEW]["ranked_slices"]
    ):
        return WEAKNESS_PRIORITY_DEFAULT_VIEW
    if "all_answered" in views and views["all_answered"]["ranked_slices"]:
        return "all_answered"
    if WEAKNESS_PRIORITY_DEFAULT_VIEW in views:
        return WEAKNESS_PRIORITY_DEFAULT_VIEW
    if "all_answered" in views:
        return "all_answered"
    return WEAKNESS_PRIORITY_DEFAULT_VIEW


def _deduplicate_weakness_slices(ranked_slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, ...], dict[str, Any]] = {}
    for entry in ranked_slices:
        signature = tuple(entry.get("_row_signature", ()))
        existing = deduped.get(signature)
        if existing is None or _prefer_weakness_slice(entry, existing):
            deduped[signature] = entry
    return list(deduped.values())


def _prefer_weakness_slice(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    candidate_score = (
        float(candidate["priority_score"]),
        int(candidate.get("_filter_count", 0)),
        1 if candidate.get("slice_type") == "structured_combo" else 0,
        str(candidate.get("slice_description", "")),
    )
    existing_score = (
        float(existing["priority_score"]),
        int(existing.get("_filter_count", 0)),
        1 if existing.get("slice_type") == "structured_combo" else 0,
        str(existing.get("slice_description", "")),
    )
    return candidate_score > existing_score


def _flatten_weakness_priority_rows(weakness_priority: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view_name in weakness_priority.get("available_views", []):
        for entry in weakness_priority.get("views", {}).get(view_name, {}).get("ranked_slices", []):
            rows.append(
                {
                    "view": view_name,
                    "rank": entry.get("rank"),
                    "slice_type": entry.get("slice_type"),
                    "slice_key": entry.get("slice_key"),
                    "slice_description": entry.get("slice_description"),
                    "feature": entry.get("feature"),
                    "value": entry.get("value"),
                    "support_count": entry.get("support_count"),
                    "support_rate": entry.get("support_rate"),
                    "mean_log_delta": entry.get("mean_log_delta"),
                    "median_log_delta": entry.get("median_log_delta"),
                    "slow_or_worse_rate": entry.get("slow_or_worse_rate"),
                    "breakdown_rate": entry.get("breakdown_rate"),
                    "priority_score": entry.get("priority_score"),
                    "filter_expression": entry.get("filter_expression"),
                    "why_it_matters": entry.get("why_it_matters"),
                }
            )
    return rows


def _row_matches_filters(
    row: dict[str, Any],
    filters: tuple[tuple[str, Any], ...],
) -> bool:
    return all(row.get(field_name) == field_value for field_name, field_value in filters)


def _filter_expression(filters: tuple[tuple[str, Any], ...]) -> str:
    return " & ".join(
        f"{field_name}={_slice_value_token(field_value)}"
        for field_name, field_value in filters
    )


def _slice_value_token(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _slice_row_identifier(row: dict[str, Any]) -> str:
    if row.get("saved_question_id") is not None:
        return f"id:{row['saved_question_id']}"
    return (
        "row:"
        f"{row.get('run_id')}|{row.get('question_index')}|{row.get('base_operation')}|"
        f"{row.get('result_label')}|{row.get('log_delta')}"
    )


def _describe_single_feature_slice(field_name: str, value: Any) -> str:
    if field_name == "base_operation":
        return str(value)
    if field_name == "answer_role":
        answer_role_labels = {
            "left": "solve for left operand",
            "right": "solve for right operand",
            "result": "solve for result",
        }
        return answer_role_labels.get(str(value), f"answer role = {value}")
    if field_name == "used_decimal":
        return "decimal problems"
    if field_name == "used_missing_variable":
        return "missing-variable problems"
    if field_name == "requires_carry":
        return "requires carry"
    if field_name == "carry_in_units":
        return "carry in units column"
    if field_name == "carry_in_tens":
        return "carry in tens column"
    if field_name == "carry_creates_new_digit":
        return "carry creates new digit"
    if field_name == "requires_borrow":
        return "requires borrow"
    if field_name == "borrow_in_units":
        return "borrow in units column"
    if field_name == "borrow_in_tens":
        return "borrow in tens column"
    if field_name == "borrow_across_zero":
        return "borrow across zero"
    if field_name == "borrow_changes_leading_digit":
        return "borrow changes leading digit"
    if field_name == "addition_crosses_decade":
        return "addition crosses decade"
    if field_name == "addition_crosses_century":
        return "addition crosses century"
    if field_name == "sub_crosses_decade":
        return "subtraction crosses decade"
    if field_name == "sub_crosses_century":
        return "subtraction crosses century"
    if field_name == "mult_one_digit_by_one_digit":
        return "one digit by one digit multiplication"
    if field_name == "mult_one_digit_by_two_digit":
        return "one digit by two digit multiplication"
    if field_name == "mult_two_digit_by_two_digit":
        return "two digit by two digit multiplication"
    if field_name == "mult_units_product_ge_10":
        return "multiplication with units product >= 10"
    if field_name == "div_exact":
        return "exact division"
    if field_name == "quotient_is_integer":
        return "integer-quotient division"
    if field_name == "division_result_terminating_decimal":
        return "terminating-decimal division"
    if field_name == "num_carries":
        label = "carry" if int(value) == 1 else "carries"
        return f"{value} {label}"
    if field_name == "num_borrows":
        label = "borrow" if int(value) == 1 else "borrows"
        return f"{value} {label}"
    if field_name == "long_borrow_chain_length":
        return f"borrow chain length {value}"
    return f"{field_name} = {value}"


def _build_weakness_reason(
    slice_description: str,
    support_count: int,
    mean_log_delta: float,
    median_log_delta: float,
    slow_or_worse_rate: float,
    breakdown_rate: float,
    view_name: str,
) -> str:
    scope_label = "Correct rows" if view_name == "correct_only" else "Answered rows"
    return (
        f"{scope_label} in {slice_description} average {_format_signed(mean_log_delta)} log slower than expected "
        f"(median {_format_signed(median_log_delta)}) across {support_count} rows; "
        f"{_format_percentage(slow_or_worse_rate)} are slow/breakdown and "
        f"{_format_percentage(breakdown_rate)} hit breakdown."
    )


def _format_signed(value: float) -> str:
    return f"{value:+.3f}"


def _format_percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def _rounded_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _rounded_median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return round(sorted_values[middle], 6)
    return round((sorted_values[middle - 1] + sorted_values[middle]) / 2.0, 6)


def _write_csv_rows(path: Path, rows: list[dict[str, Any]], preferred_columns: Iterable[str]) -> None:
    preferred = [column for column in preferred_columns if any(column in row for row in rows)]
    remaining = sorted(
        {
            key
            for row in rows
            for key in row.keys()
            if key not in preferred
        }
    )
    fieldnames = preferred + remaining
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _save_pickle(path: Path, payload: Any) -> None:
    with path.open("wb") as handle:
        pickle.dump(payload, handle)


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
