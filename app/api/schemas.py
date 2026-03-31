from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GenerationSettingsOverride(BaseModel):
    addition_weight: Optional[float] = Field(default=None, ge=0)
    subtraction_weight: Optional[float] = Field(default=None, ge=0)
    multiplication_weight: Optional[float] = Field(default=None, ge=0)
    division_weight: Optional[float] = Field(default=None, ge=0)
    decimal_weight: Optional[float] = Field(default=None, ge=0)
    missing_variable_weight: Optional[float] = Field(default=None, ge=0)
    allow_negative_answers: Optional[bool] = None


class ZetamacOperationRangeOverride(BaseModel):
    left_min: Optional[int] = None
    left_max: Optional[int] = None
    right_min: Optional[int] = None
    right_max: Optional[int] = None


class ZetamacOperationsOverride(BaseModel):
    addition: Optional[bool] = None
    subtraction: Optional[bool] = None
    multiplication: Optional[bool] = None
    division: Optional[bool] = None


class ZetamacRangesOverride(BaseModel):
    addition: Optional[ZetamacOperationRangeOverride] = None
    subtraction: Optional[ZetamacOperationRangeOverride] = None
    multiplication: Optional[ZetamacOperationRangeOverride] = None
    division: Optional[ZetamacOperationRangeOverride] = None


class ZetamacSettingsOverride(BaseModel):
    duration_seconds: Optional[int] = None
    allow_negative_answers: Optional[bool] = None
    operations: Optional[ZetamacOperationsOverride] = None
    ranges: Optional[ZetamacRangesOverride] = None


class GameStartRequest(BaseModel):
    preset_name: Optional[str] = None
    mode: Optional[str] = None
    adaptive_enabled: Optional[bool] = None
    target_pace_seconds: Optional[float] = Field(default=None, ge=2.0, le=6.0)
    initial_difficulty: Optional[float] = Field(default=None, ge=0, le=100)
    settings: Optional[GenerationSettingsOverride] = None
    zetamac_settings: Optional[ZetamacSettingsOverride] = None


class GameAnswerRequest(BaseModel):
    session_id: str
    question_number: Optional[int] = Field(default=None, ge=1)
    selected_option_index: Optional[int] = Field(default=None, ge=0, le=3)
    answer: Optional[str] = None


class GameFinishRequest(BaseModel):
    session_id: str


class GameAbortRequest(BaseModel):
    session_id: str
