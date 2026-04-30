from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.domain import (
    AgentTrajectoryRead,
    CompanyCreate,
    CompanyRead,
    DailyRunResponse,
    NicheBootstrapCreate,
    NicheBootstrapResponse,
    HealthResponse,
    NicheCreate,
    NicheRead,
    ResearchTaskCreate,
    ResearchTaskRead,
    SourceCreate,
    SourceRead,
    TrainingExportResponse,
)
from app.services.reports import (
    create_basic_report,
    create_research_task,
    create_detailed_report,
    export_training_examples,
    list_tasks,
    list_reports,
)
from app.services.intake import bootstrap_niche_scan
from app.services.pipeline import run_daily_pipeline
from app.services.store import (
    create_company,
    create_niche,
    create_source,
    list_niches,
)

api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/niches", response_model=list[NicheRead])
def get_niches(db: Session = Depends(get_db)) -> list[NicheRead]:
    return list_niches(db)


@api_router.post("/niches", response_model=NicheRead, status_code=201)
def post_niche(payload: NicheCreate, db: Session = Depends(get_db)) -> NicheRead:
    return create_niche(db, payload)


@api_router.post("/niches/bootstrap", response_model=NicheBootstrapResponse, status_code=201)
def post_niche_bootstrap(
    payload: NicheBootstrapCreate, db: Session = Depends(get_db)
) -> NicheBootstrapResponse:
    return NicheBootstrapResponse(**bootstrap_niche_scan(db, payload.name, payload.description))


@api_router.post("/niches/{niche_id}/companies", response_model=CompanyRead, status_code=201)
def post_company(
    niche_id: int, payload: CompanyCreate, db: Session = Depends(get_db)
) -> CompanyRead:
    try:
        return create_company(db, niche_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/companies/{company_id}/sources", response_model=SourceRead, status_code=201)
def post_source(
    company_id: int, payload: SourceCreate, db: Session = Depends(get_db)
) -> SourceRead:
    try:
        return create_source(db, company_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/jobs/run-daily", response_model=DailyRunResponse)
def run_daily(db: Session = Depends(get_db)) -> DailyRunResponse:
    result = run_daily_pipeline(db)
    return DailyRunResponse(
        run_id=result["run_id"],
        pages_scraped=result["pages_scraped"],
        insights_created=result["insights_created"],
    )


@api_router.get("/tasks", response_model=list[ResearchTaskRead])
def get_tasks(
    niche_id: int | None = None, db: Session = Depends(get_db)
) -> list[ResearchTaskRead]:
    return list_tasks(db, niche_id=niche_id)


@api_router.post("/niches/{niche_id}/tasks", response_model=ResearchTaskRead, status_code=201)
def post_task(
    niche_id: int, payload: ResearchTaskCreate, db: Session = Depends(get_db)
) -> ResearchTaskRead:
    try:
        return create_research_task(
            db,
            niche_id=niche_id,
            name=payload.name,
            prompt=payload.prompt,
            evaluation_type=payload.evaluation_type,
            reward_definition=payload.reward_definition,
            company_id=payload.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/reports", response_model=list[AgentTrajectoryRead])
@api_router.get("/trajectories", response_model=list[AgentTrajectoryRead], include_in_schema=False)
def get_reports(
    task_id: int | None = None, db: Session = Depends(get_db)
) -> list[AgentTrajectoryRead]:
    return list_reports(db, task_id=task_id)


@api_router.post("/tasks/{task_id}/run-basic-report", response_model=AgentTrajectoryRead, status_code=201)
@api_router.post("/tasks/{task_id}/run-baseline", response_model=AgentTrajectoryRead, status_code=201, include_in_schema=False)
def post_basic_report(
    task_id: int, db: Session = Depends(get_db)
) -> AgentTrajectoryRead:
    try:
        return create_basic_report(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/tasks/{task_id}/run-detailed-report", response_model=AgentTrajectoryRead, status_code=201)
@api_router.post("/tasks/{task_id}/run-tree-grpo", response_model=AgentTrajectoryRead, status_code=201, include_in_schema=False)
def post_detailed_report(
    task_id: int, db: Session = Depends(get_db)
) -> AgentTrajectoryRead:
    try:
        return create_detailed_report(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/niches/{niche_id}/training-export", response_model=TrainingExportResponse)
def get_training_export(
    niche_id: int, db: Session = Depends(get_db)
) -> TrainingExportResponse:
    return TrainingExportResponse(
        niche_id=niche_id,
        examples=export_training_examples(db, niche_id=niche_id),
    )
