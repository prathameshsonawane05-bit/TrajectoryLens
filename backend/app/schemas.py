from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError

StepType = Literal["command", "edit", "test_run", "message"]
FinalStatus = Literal["pass", "fail"]


def _value_error(loc: tuple[str | int, ...], message: str, value: object) -> InitErrorDetails:
    return InitErrorDetails(
        type=PydanticCustomError("value_error", message),
        loc=loc,
        input=value,
    )


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    type: StepType
    content: str
    file: str | None = None
    output: str
    exit_code: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    error_signature: str | None = None

    @model_validator(mode="after")
    def check_type_requirements(self) -> "StepIn":
        errors: list[InitErrorDetails] = []
        if self.type == "edit" and (self.file is None or self.file.strip() == ""):
            errors.append(
                _value_error(("file",), "edit steps must include a file", self.file),
            )
        if self.type == "test_run" and self.tests_passed is None:
            errors.append(
                _value_error(
                    ("tests_passed",),
                    "test_run steps must include tests_passed",
                    self.tests_passed,
                ),
            )
        if self.type == "test_run" and self.tests_failed is None:
            errors.append(
                _value_error(
                    ("tests_failed",),
                    "test_run steps must include tests_failed",
                    self.tests_failed,
                ),
            )
        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


class StepOut(BaseModel):
    index: int
    type: StepType
    content: str
    file: str | None
    output: str
    exit_code: int | None
    tests_passed: int | None
    tests_failed: int | None
    error_signature: str | None


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    model: str
    final_status: FinalStatus
    agent_claimed_success: bool
    steps: list[StepIn]

    @field_validator("run_id")
    @classmethod
    def run_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise PydanticCustomError("value_error", "run_id must be non-empty")
        return value

    @model_validator(mode="after")
    def check_steps(self) -> "RunCreate":
        errors: list[InitErrorDetails] = []
        if len(self.steps) == 0:
            errors.append(
                _value_error(("steps",), "steps must contain at least one step", self.steps),
            )
        else:
            # Indexes are 0-based and strictly increasing. Gaps are allowed.
            if self.steps[0].index != 0:
                errors.append(
                    _value_error(
                        ("steps", 0, "index"),
                        "step indexes must start at 0",
                        self.steps[0].index,
                    ),
                )
            for position in range(1, len(self.steps)):
                if self.steps[position].index <= self.steps[position - 1].index:
                    errors.append(
                        _value_error(
                            ("steps", position, "index"),
                            "step indexes must be strictly increasing",
                            self.steps[position].index,
                        ),
                    )
        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


class RunOut(BaseModel):
    run_id: str
    task_id: str
    model: str
    final_status: FinalStatus
    agent_claimed_success: bool
    created_at: datetime
    steps: list[StepOut]


class RunSummary(BaseModel):
    run_id: str
    task_id: str
    model: str
    final_status: FinalStatus
    agent_claimed_success: bool
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int
