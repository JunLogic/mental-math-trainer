from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.models.game import BaseOperation
from app.runtime import resolve_data_dir

SUPPORTED_FORWARD_OPERATIONS: tuple[BaseOperation, ...] = (
    "addition",
    "subtraction",
    "multiplication",
    "division",
)
SUPPORTED_FORWARD_FILTERS = {
    "base_operation",
    "used_missing_variable",
    "used_decimal",
    "requires_carry",
    "requires_borrow",
    "borrow_across_zero",
    "long_borrow_chain_length",
    "addition_crosses_decade",
    "addition_crosses_century",
    "sub_crosses_decade",
    "sub_crosses_century",
    "mult_one_digit_by_two_digit",
    "mult_two_digit_by_two_digit",
    "mult_units_product_ge_10",
    "div_exact",
    "quotient_is_integer",
    "division_result_terminating_decimal",
}
FEATURE_OPERATION_HINTS: dict[str, BaseOperation] = {
    "requires_carry": "addition",
    "addition_crosses_decade": "addition",
    "addition_crosses_century": "addition",
    "requires_borrow": "subtraction",
    "borrow_across_zero": "subtraction",
    "long_borrow_chain_length": "subtraction",
    "sub_crosses_decade": "subtraction",
    "sub_crosses_century": "subtraction",
    "mult_one_digit_by_two_digit": "multiplication",
    "mult_two_digit_by_two_digit": "multiplication",
    "mult_units_product_ge_10": "multiplication",
    "div_exact": "division",
    "quotient_is_integer": "division",
    "division_result_terminating_decimal": "division",
}


@dataclass(frozen=True)
class TrainingTarget:
    rank: int
    slice_key: str
    slice_description: str
    priority_score: float
    filters: tuple[tuple[str, Any], ...]
    base_operation: BaseOperation | None
    support_count: int
    why_it_matters: str
    view: str | None = None
    filter_expression: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "slice_key": self.slice_key,
            "slice_description": self.slice_description,
            "priority_score": self.priority_score,
            "base_operation": self.base_operation,
            "support_count": self.support_count,
            "filters": [
                {"feature": feature, "value": value}
                for feature, value in self.filters
            ],
            "view": self.view,
            "filter_expression": self.filter_expression,
            "why_it_matters": self.why_it_matters,
        }


@dataclass(frozen=True)
class WeaknessArtifactBundle:
    status: str
    artifact_path: str | None
    artifact_source: str | None
    weakness_weighting_applied: bool
    reverse_problems_excluded: bool
    missing_variable_allowed: bool
    selected_view: str | None
    available_views: tuple[str, ...]
    targets: tuple[TrainingTarget, ...]
    rejected_slice_keys: tuple[str, ...]

    def runtime_summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "artifact_path": self.artifact_path,
            "artifact_source": self.artifact_source,
            "weakness_weighting_applied": self.weakness_weighting_applied,
            "reverse_problems_excluded": self.reverse_problems_excluded,
            "missing_variable_allowed": self.missing_variable_allowed,
            "selected_view": self.selected_view,
            "available_views": list(self.available_views),
            "target_count": len(self.targets),
            "loaded_target_slice_keys": [target.slice_key for target in self.targets],
            "targets": [target.to_summary() for target in self.targets],
            "rejected_slice_keys": list(self.rejected_slice_keys),
        }


class WeaknessArtifactLoader:
    def __init__(self, artifacts_root: Path | None = None) -> None:
        self.artifacts_root = artifacts_root

    def load_forward_targets(
        self,
        *,
        allow_missing_variable: bool = False,
        included_operations: Iterable[BaseOperation] = SUPPORTED_FORWARD_OPERATIONS,
        preferred_view: str = "correct_only",
    ) -> WeaknessArtifactBundle:
        artifact_root = self.artifacts_root or (resolve_data_dir() / "ml_artifacts")
        enabled_operations = set(included_operations)
        for artifact_path, artifact_source in self._candidate_paths(artifact_root):
            raw_payload = self._read_json(artifact_path)
            if raw_payload is None:
                continue

            selected_view, available_views, raw_targets = self._extract_targets(
                raw_payload,
                artifact_source=artifact_source,
                preferred_view=preferred_view,
            )
            targets: list[TrainingTarget] = []
            rejected_slice_keys: list[str] = []
            for raw_target in raw_targets:
                target = self._normalize_target(
                    raw_target,
                    allow_missing_variable=allow_missing_variable,
                    included_operations=enabled_operations,
                    selected_view=selected_view,
                )
                if target is None:
                    slice_key = str(raw_target.get("slice_key") or raw_target.get("filter_expression") or "unknown")
                    rejected_slice_keys.append(slice_key)
                    continue
                targets.append(target)

            status = "loaded" if targets else "no_forward_targets"
            return WeaknessArtifactBundle(
                status=status,
                artifact_path=str(artifact_path),
                artifact_source=artifact_source,
                weakness_weighting_applied=bool(targets),
                reverse_problems_excluded=True,
                missing_variable_allowed=allow_missing_variable,
                selected_view=selected_view,
                available_views=tuple(available_views),
                targets=tuple(targets),
                rejected_slice_keys=tuple(rejected_slice_keys),
            )

        return WeaknessArtifactBundle(
            status="artifacts_missing",
            artifact_path=None,
            artifact_source=None,
            weakness_weighting_applied=False,
            reverse_problems_excluded=True,
            missing_variable_allowed=allow_missing_variable,
            selected_view=None,
            available_views=(),
            targets=(),
            rejected_slice_keys=(),
        )

    def _candidate_paths(self, artifact_root: Path) -> list[tuple[Path, str]]:
        if not artifact_root.exists():
            return []

        preferred_targets = artifact_root / "phase4_check" / "top_training_targets.json"
        preferred_priority = artifact_root / "phase4_check" / "weakness_priority.json"

        candidate_paths: list[tuple[Path, str]] = []
        seen_paths: set[Path] = set()

        def add_path(path: Path, source: str) -> None:
            resolved = path.resolve()
            if not path.exists() or resolved in seen_paths:
                return
            seen_paths.add(resolved)
            candidate_paths.append((path, source))

        add_path(preferred_targets, "top_training_targets")
        for path in sorted(
            artifact_root.glob("**/top_training_targets.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            add_path(path, "top_training_targets")

        add_path(preferred_priority, "weakness_priority")
        for path in sorted(
            artifact_root.glob("**/weakness_priority.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            add_path(path, "weakness_priority")

        return candidate_paths

    def _read_json(self, artifact_path: Path) -> dict[str, Any] | None:
        try:
            with artifact_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None
        return payload if isinstance(payload, dict) else None

    def _extract_targets(
        self,
        payload: dict[str, Any],
        *,
        artifact_source: str,
        preferred_view: str,
    ) -> tuple[str | None, list[str], list[dict[str, Any]]]:
        if artifact_source == "top_training_targets":
            selected_view = _string_or_none(payload.get("default_view"))
            available_views = [selected_view] if selected_view else []
            raw_targets = payload.get("targets", [])
            return selected_view, available_views, raw_targets if isinstance(raw_targets, list) else []

        available_views = [
            str(view_name)
            for view_name in payload.get("available_views", [])
            if isinstance(view_name, str)
        ]
        selected_view = preferred_view if preferred_view in available_views else _string_or_none(payload.get("default_view"))
        views = payload.get("views", {})
        view_payload = views.get(selected_view, {}) if isinstance(views, dict) and selected_view else {}
        raw_targets = view_payload.get("ranked_slices", [])
        if not isinstance(raw_targets, list):
            raw_targets = []
        return selected_view, available_views, raw_targets

    def _normalize_target(
        self,
        raw_target: dict[str, Any],
        *,
        allow_missing_variable: bool,
        included_operations: set[BaseOperation],
        selected_view: str | None,
    ) -> TrainingTarget | None:
        if not isinstance(raw_target, dict):
            return None

        filters = self._normalize_filters(raw_target)
        if not filters:
            return None

        if any(
            feature == "answer_role"
            for feature, _ in filters
        ):
            return None

        if any(
            feature == "used_missing_variable" and bool(value) and not allow_missing_variable
            for feature, value in filters
        ):
            return None

        if any(
            feature == "used_decimal" and bool(value)
            for feature, value in filters
        ):
            return None

        if any(feature not in SUPPORTED_FORWARD_FILTERS for feature, _ in filters):
            return None

        target_operation = _infer_target_operation(filters, slice_key=_string_or_none(raw_target.get("slice_key")))
        if target_operation is None or target_operation not in included_operations:
            return None

        return TrainingTarget(
            rank=int(raw_target.get("rank", 0)),
            slice_key=str(raw_target.get("slice_key") or raw_target.get("filter_expression") or "unknown"),
            slice_description=str(raw_target.get("slice_description") or raw_target.get("slice_key") or "unknown"),
            priority_score=float(raw_target.get("priority_score", 0.0)),
            filters=filters,
            base_operation=target_operation,
            support_count=int(raw_target.get("support_count", 0)),
            why_it_matters=str(raw_target.get("why_it_matters") or ""),
            view=selected_view,
            filter_expression=_string_or_none(raw_target.get("filter_expression")),
        )

    def _normalize_filters(self, raw_target: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        raw_filters = raw_target.get("filters")
        filters: list[tuple[str, Any]] = []
        if isinstance(raw_filters, list):
            for raw_filter in raw_filters:
                if not isinstance(raw_filter, dict):
                    continue
                feature = _string_or_none(raw_filter.get("feature"))
                if feature is None:
                    continue
                filters.append((feature, raw_filter.get("value")))
        else:
            feature = _string_or_none(raw_target.get("feature"))
            if feature is not None:
                filters.append((feature, raw_target.get("value")))
        return tuple(filters)


def _infer_target_operation(
    filters: tuple[tuple[str, Any], ...],
    *,
    slice_key: str | None,
) -> BaseOperation | None:
    for feature, value in filters:
        if feature == "base_operation" and value in SUPPORTED_FORWARD_OPERATIONS:
            return value

    hinted_operations = {
        FEATURE_OPERATION_HINTS[feature]
        for feature, _ in filters
        if feature in FEATURE_OPERATION_HINTS
    }
    if len(hinted_operations) == 1:
        return next(iter(hinted_operations))

    if slice_key:
        for operation in SUPPORTED_FORWARD_OPERATIONS:
            if slice_key.startswith(f"{operation}__"):
                return operation
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
