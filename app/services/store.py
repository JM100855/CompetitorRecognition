from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import SessionLocal
from app.models.domain import (
    AgentTrajectory,
    Company,
    Insight,
    Niche,
    ResearchTask,
    ScrapeRun,
    SourcePage,
)
from app.schemas.domain import CompanyCreate, NicheCreate, SourceCreate


def list_niches(db: Session) -> list[Niche]:
    return db.scalars(
        select(Niche).options(selectinload(Niche.companies).selectinload(Company.sources)).order_by(Niche.created_at.desc())
    ).all()


def create_niche(db: Session, payload: NicheCreate) -> Niche:
    niche = Niche(name=payload.name.strip(), description=payload.description)
    db.add(niche)
    db.commit()
    db.refresh(niche)
    return niche


def create_company(db: Session, niche_id: int, payload: CompanyCreate) -> Company:
    niche = db.get(Niche, niche_id)
    if niche is None:
        raise ValueError(f"Niche {niche_id} not found")
    company = Company(
        niche_id=niche_id,
        name=payload.name.strip(),
        domain=payload.domain,
        notes=payload.notes,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_source(db: Session, company_id: int, payload: SourceCreate) -> SourcePage:
    company = db.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found")
    source = SourcePage(company_id=company_id, page_type=payload.page_type.strip(), url=payload.url.strip())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@dataclass
class DashboardPayload:
    niches: list[Niche]
    insights: list[Insight]
    runs: list[ScrapeRun]
    trajectories: list[AgentTrajectory]


def fetch_dashboard() -> DashboardPayload:
    with SessionLocal() as db:
        niches = list_niches(db)
        insights = db.scalars(select(Insight).order_by(desc(Insight.created_at)).limit(20)).all()
        runs = db.scalars(select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(6)).all()
        trajectories = db.scalars(
            select(AgentTrajectory).order_by(desc(AgentTrajectory.created_at)).limit(6)
        ).all()
        return DashboardPayload(
            niches=niches,
            insights=insights,
            runs=runs,
            trajectories=trajectories,
        )


def get_task_with_relations(db: Session, task_id: int) -> ResearchTask | None:
    return db.scalars(
        select(ResearchTask)
        .where(ResearchTask.id == task_id)
        .options(
            selectinload(ResearchTask.trajectories).selectinload(AgentTrajectory.steps),
            selectinload(ResearchTask.trajectories).selectinload(AgentTrajectory.rewards),
        )
    ).first()
