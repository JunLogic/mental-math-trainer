from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.services.feature_extraction import (
    core_feature_names,
    extract_core_saved_question_feature_rows,
    extract_saved_question_feature_rows,
)
from app.services.storage import SQLiteStorage

DATASET_METADATA_COLUMNS: tuple[str, ...] = (
    "run_id",
    "question_index",
    "mode",
    "base_operation",
    "result_label",
    "response_time_ms",
    "difficulty_at_question",
    "parse_succeeded",
    "is_answered",
    "is_correct",
    "is_incorrect",
    "y_error",
    "y_time_log",
    "feature_set",
)
DEFAULT_EXCLUDED_MODEL_COLUMNS: frozenset[str] = frozenset(
    {
        "a_value_normalized",
        "b_value_normalized",
        "result_value_normalized",
    }
)
NON_MODEL_COLUMNS: frozenset[str] = frozenset(
    {
        "feature_version",
        "saved_question_id",
        "run_id",
        "question_index",
        "result_label",
        "response_time_ms",
        "difficulty_at_question",
        "parse_succeeded",
        "is_answered",
        "is_correct",
        "is_incorrect",
        "y_error",
        "y_time_log",
        "feature_set",
    }
)


@dataclass(frozen=True)
class AttemptDataset:
    rows: list[dict[str, Any]]
    feature_columns: list[str]
    available_feature_columns: list[str]
    feature_set: str
    pruned_uninformative_model_columns: list[str]

    def summary(self) -> dict[str, Any]:
        operation_counts: dict[str, int] = {}
        mode_counts: dict[str, int] = {}
        result_counts: dict[str, int] = {}
        for row in self.rows:
            operation = str(row.get("base_operation", ""))
            mode = str(row.get("mode", ""))
            result_label = str(row.get("result_label", ""))
            operation_counts[operation] = operation_counts.get(operation, 0) + 1
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            result_counts[result_label] = result_counts.get(result_label, 0) + 1
        return {
            "feature_set": self.feature_set,
            "rows": len(self.rows),
            "feature_columns": len(self.feature_columns),
            "available_feature_columns": len(self.available_feature_columns),
            "excluded_default_model_columns": sorted(DEFAULT_EXCLUDED_MODEL_COLUMNS),
            "pruned_uninformative_model_columns": list(self.pruned_uninformative_model_columns),
            "operation_counts": operation_counts,
            "mode_counts": mode_counts,
            "result_counts": result_counts,
            "parse_succeeded_rows": len(filter_parse_succeeded(self.rows)),
            "answered_rows": len(filter_answered(self.rows)),
            "correct_rows": len(filter_correct_only(self.rows)),
            "incorrect_rows": len(filter_incorrect_only(self.rows)),
        }


def build_attempt_dataset_from_storage(
    storage: SQLiteStorage,
    use_full_features: bool = False,
    run_ids: Sequence[int] | None = None,
) -> AttemptDataset:
    selected_run_ids = list(run_ids) if run_ids is not None else storage.list_saved_run_ids()
    rows: list[dict[str, Any]] = []
    for run_id in selected_run_ids:
        saved_questions = storage.list_saved_questions(run_id)
        rows.extend(
            build_dataset_rows_from_saved_questions(
                saved_questions,
                use_full_features=use_full_features,
            )
        )
    available_feature_columns = _infer_available_feature_columns(rows)
    feature_columns, pruned_uninformative_model_columns = _infer_model_feature_columns(
        rows,
        feature_set="full" if use_full_features else "core",
    )
    return AttemptDataset(
        rows=rows,
        feature_columns=feature_columns,
        available_feature_columns=available_feature_columns,
        feature_set="full" if use_full_features else "core",
        pruned_uninformative_model_columns=pruned_uninformative_model_columns,
    )


def build_dataset_rows_from_saved_questions(
    saved_question_rows: Sequence[dict[str, Any]],
    use_full_features: bool = False,
) -> list[dict[str, Any]]:
    extracted_rows = (
        extract_saved_question_feature_rows(saved_question_rows)
        if use_full_features
        else extract_core_saved_question_feature_rows(saved_question_rows)
    )
    if len(saved_question_rows) != len(extracted_rows):
        raise ValueError("Saved question rows and extracted feature rows are out of sync.")
    dataset_rows: list[dict[str, Any]] = []
    for saved_row, feature_row in zip(saved_question_rows, extracted_rows):
        response_time_ms = saved_row.get("response_time_ms")
        result_label = saved_row.get("result_label")
        answered = result_label in {"correct", "incorrect"}
        is_correct = result_label == "correct"
        is_incorrect = result_label == "incorrect"
        dataset_row: dict[str, Any] = {
            "run_id": saved_row.get("run_id"),
            "question_index": saved_row.get("question_index"),
            "mode": saved_row.get("mode"),
            "base_operation": saved_row.get("base_operation") or feature_row.get("operation"),
            "result_label": result_label,
            "response_time_ms": response_time_ms,
            "difficulty_at_question": saved_row.get("difficulty_at_question"),
            "parse_succeeded": bool(feature_row.get("parse_succeeded", False)),
            "is_answered": answered,
            "is_correct": is_correct,
            "is_incorrect": is_incorrect,
            "y_error": (1 if is_incorrect else 0) if answered else None,
            "y_time_log": math.log1p(response_time_ms) if answered and response_time_ms is not None else None,
            "feature_set": "full" if use_full_features else "core",
        }
        for key, value in feature_row.items():
            if key in {"run_id", "question_index", "mode", "operation", "result_label", "response_time_ms"}:
                continue
            dataset_row[key] = value
        dataset_rows.append(dataset_row)
    return dataset_rows


def filter_parse_succeeded(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if bool(row.get("parse_succeeded"))]


def filter_answered(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if bool(row.get("is_answered"))]


def filter_correct_only(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if bool(row.get("is_correct"))]


def filter_incorrect_only(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if bool(row.get("is_incorrect"))]


def filter_by_operation(rows: Iterable[dict[str, Any]], operations: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("base_operation") in operations]


def save_dataset_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def default_model_feature_columns(feature_set: str = "core") -> list[str]:
    if feature_set == "core":
        return sorted(
            feature_name
            for feature_name in core_feature_names()
            if feature_name not in NON_MODEL_COLUMNS and feature_name not in DEFAULT_EXCLUDED_MODEL_COLUMNS
        ) + ["base_operation"]
    if feature_set == "full":
        raise ValueError("Full-feature modelling columns depend on the built dataset rows.")
    raise ValueError(f"Unsupported feature set: {feature_set}")


def _infer_available_feature_columns(rows: Sequence[dict[str, Any]]) -> list[str]:
    candidate_columns = {
        key
        for row in rows
        for key in row.keys()
        if key not in NON_MODEL_COLUMNS
    }
    feature_columns = sorted(candidate_columns)
    if "base_operation" not in feature_columns and any("base_operation" in row for row in rows):
        feature_columns.append("base_operation")
    if "mode" not in feature_columns and any("mode" in row for row in rows):
        feature_columns.append("mode")
    return feature_columns


def _infer_model_feature_columns(rows: Sequence[dict[str, Any]], feature_set: str) -> tuple[list[str], list[str]]:
    feature_columns = _infer_available_feature_columns(rows)
    if feature_set == "core":
        candidate_columns = [column for column in feature_columns if column not in DEFAULT_EXCLUDED_MODEL_COLUMNS]
        return _prune_uninformative_model_columns(rows, candidate_columns)
    if feature_set == "full":
        candidate_columns = [column for column in feature_columns if column not in DEFAULT_EXCLUDED_MODEL_COLUMNS]
        return _prune_uninformative_model_columns(rows, candidate_columns)
    raise ValueError(f"Unsupported feature set: {feature_set}")


def _prune_uninformative_model_columns(
    rows: Sequence[dict[str, Any]],
    candidate_columns: Sequence[str],
) -> tuple[list[str], list[str]]:
    kept_columns: list[str] = []
    pruned_columns: list[str] = []
    for column in candidate_columns:
        distinct_values = {
            _hashable_feature_value(row.get(column))
            for row in rows
        }
        if len(distinct_values) <= 1:
            pruned_columns.append(column)
            continue
        kept_columns.append(column)
    return kept_columns, pruned_columns


def _hashable_feature_value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, dict):
        return tuple(sorted(value.items()))
    return value
