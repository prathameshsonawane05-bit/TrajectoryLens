from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.analyzer import run_analysis
from app.analyzer.registry import Finding as AnalyzedFinding
from app.db import get_db, init_db
from app.models import Finding, Run, Step
from app.schemas import (
    AnalyzeAllResponse,
    FinalStatus,
    FindingOut,
    ModelCount,
    RunCreate,
    RunListResponse,
    RunOut,
    RunSummary,
    StepOut,
    StepType,
    SummaryResponse,
    TypeCount,
)

DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="TrajectoryLens", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


runs_router = APIRouter()


def _final_status(value: str) -> FinalStatus:
    if value == "pass":
        return "pass"
    if value == "fail":
        return "fail"
    raise RuntimeError(f"stored final_status {value!r} is invalid")


def _step_type(value: str) -> StepType:
    if value == "command":
        return "command"
    if value == "edit":
        return "edit"
    if value == "test_run":
        return "test_run"
    if value == "message":
        return "message"
    raise RuntimeError(f"stored step type {value!r} is invalid")


def _step_out(step: Step) -> StepOut:
    return StepOut(
        index=step.index,
        type=_step_type(step.type),
        content=step.content,
        file=step.file,
        output=step.output,
        exit_code=step.exit_code,
        tests_passed=step.tests_passed,
        tests_failed=step.tests_failed,
        error_signature=step.error_signature,
    )


def _summary(run: Run) -> RunSummary:
    return RunSummary(
        run_id=run.run_id,
        task_id=run.task_id,
        model=run.model,
        final_status=_final_status(run.final_status),
        agent_claimed_success=run.agent_claimed_success,
        created_at=run.created_at,
    )


def _run_out(run: Run) -> RunOut:
    return RunOut(
        run_id=run.run_id,
        task_id=run.task_id,
        model=run.model,
        final_status=_final_status(run.final_status),
        agent_claimed_success=run.agent_claimed_success,
        created_at=run.created_at,
        steps=[_step_out(step) for step in run.steps],
    )


def _get_run(db: Session, run_id: str) -> Run:
    run = db.scalar(select(Run).where(Run.run_id == run_id).options(selectinload(Run.steps)))
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@runs_router.post("/runs", status_code=201)
def create_run(payload: RunCreate, db: DbSession) -> RunOut:
    run = Run(
        run_id=payload.run_id,
        task_id=payload.task_id,
        model=payload.model,
        final_status=payload.final_status,
        agent_claimed_success=payload.agent_claimed_success,
        created_at=datetime.now(UTC),
        steps=[
            Step(
                index=item.index,
                type=item.type,
                content=item.content,
                file=item.file,
                output=item.output,
                exit_code=item.exit_code,
                tests_passed=item.tests_passed,
                tests_failed=item.tests_failed,
                error_signature=item.error_signature,
            )
            for item in payload.steps
        ],
    )
    db.add(run)
    committed = False
    try:
        db.flush()
        _replace_findings(db, run, commit=False)
        db.commit()
        committed = True
    except IntegrityError:
        raise HTTPException(status_code=409, detail="run_id already exists") from None
    finally:
        if not committed:
            db.rollback()
    db.refresh(run)
    return _run_out(run)


@runs_router.get("/runs")
def list_runs(
    db: DbSession,
    status: Annotated[Literal["pass", "fail"] | None, Query()] = None,
    model: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunListResponse:
    filters = []
    if status is not None:
        filters.append(Run.final_status == status)
    if model is not None:
        filters.append(Run.model == model)

    total = db.scalar(select(func.count()).select_from(Run).where(*filters))
    runs = db.scalars(
        select(Run)
        .where(*filters)
        .order_by(Run.created_at.desc(), Run.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return RunListResponse(
        items=[_summary(run) for run in runs],
        total=0 if total is None else total,
        limit=limit,
        offset=offset,
    )


@runs_router.get("/summary")
def get_summary(db: DbSession) -> SummaryResponse:
    status_rows = db.execute(
        select(Run.final_status, func.count()).group_by(Run.final_status)
    ).all()
    status_counts = {str(status): int(count) for status, count in status_rows}
    type_rows = db.execute(
        select(Finding.type, func.count(Finding.id))
        .group_by(Finding.type)
        .order_by(func.count(Finding.id).desc(), Finding.type.asc()),
    ).all()
    by_type = [
        TypeCount(type=str(finding_type), count=int(count))
        for finding_type, count in type_rows
    ]
    model_rows = db.execute(
        select(Run.model, func.count(Finding.id))
        .outerjoin(Finding, Finding.run_id == Run.id)
        .group_by(Run.model)
        .order_by(func.count(Finding.id).desc(), Run.model.asc()),
    ).all()
    by_model = [ModelCount(model=str(model), count=int(count)) for model, count in model_rows]
    return SummaryResponse(
        pass_count=status_counts.get("pass", 0),
        fail_count=status_counts.get("fail", 0),
        by_type=by_type,
        by_model=by_model,
        top_failure_types=by_type[:5],
    )


@runs_router.get("/runs/{run_id}")
def get_run(run_id: str, db: DbSession) -> RunOut:
    return _run_out(_get_run(db, run_id))


@runs_router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, db: DbSession) -> Response:
    run = _get_run(db, run_id)
    db.delete(run)
    db.commit()
    return Response(status_code=204)


def _severity(value: str) -> Literal["low", "medium", "high"]:
    if value == "low":
        return "low"
    if value == "medium":
        return "medium"
    if value == "high":
        return "high"
    raise RuntimeError(f"stored severity {value!r} is invalid")


def _finding_out(item: AnalyzedFinding | Finding) -> FindingOut:
    return FindingOut(
        type=item.type,
        step_index=item.step_index,
        severity=_severity(item.severity),
        explanation=item.explanation,
    )


def _replace_findings(db: Session, run: Run, *, commit: bool = True) -> list[FindingOut]:
    analyzed = run_analysis(run)
    db.execute(delete(Finding).where(Finding.run_id == run.id))
    db.flush()
    for item in analyzed:
        db.add(
            Finding(
                run_id=run.id,
                type=item.type,
                step_index=item.step_index,
                severity=item.severity,
                explanation=item.explanation,
            ),
        )
    if commit:
        db.commit()
    else:
        db.flush()
    return [_finding_out(item) for item in analyzed]


@runs_router.post("/analyze-all")
def analyze_all(db: DbSession) -> AnalyzeAllResponse:
    runs = db.scalars(select(Run).options(selectinload(Run.steps)).order_by(Run.id)).all()
    total = 0
    for run in runs:
        total += len(_replace_findings(db, run, commit=False))
    db.commit()
    return AnalyzeAllResponse(runs_analyzed=len(runs), findings=total)


@runs_router.post("/runs/{run_id}/analyze")
def analyze_run(run_id: str, db: DbSession) -> list[FindingOut]:
    return _replace_findings(db, _get_run(db, run_id))


@runs_router.get("/runs/{run_id}/findings")
def get_findings(run_id: str, db: DbSession) -> list[FindingOut]:
    run = _get_run(db, run_id)
    rows = db.scalars(
        select(Finding)
        .where(Finding.run_id == run.id)
        .order_by(Finding.step_index, Finding.type, Finding.id),
    ).all()
    return [_finding_out(row) for row in rows]


app.include_router(runs_router)
