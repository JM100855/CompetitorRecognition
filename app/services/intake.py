from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Company, Niche
from app.schemas.domain import CompanyCreate, NicheCreate, SourceCreate
from app.services.reports import create_detailed_report, create_research_task
from app.services.discovery import DiscoveredSource, discover_sources_for_niche
from app.services.pipeline import run_daily_pipeline
from app.services.store import create_company, create_niche, create_source


def bootstrap_niche_scan(
    db: Session, name: str, description: str | None = None
) -> dict[str, object]:
    niche = db.scalars(select(Niche).where(Niche.name == name.strip())).first()
    if niche is None:
        niche = create_niche(
            db,
            NicheCreate(name=name.strip(), description=description),
        )

    discovered_sources = discover_sources_for_niche(name, description)
    _attach_sources(db, niche.id, discovered_sources)

    run_result = run_daily_pipeline(db)
    task = create_research_task(
        db,
        niche_id=niche.id,
        name=f"{niche.name} summary",
        prompt=(
            f"Review the latest public updates for the {niche.name} niche. "
            "Summarize the main changes, cite the strongest sources, "
            "and note what should be checked next."
        ),
        evaluation_type="detailed-summary",
        reward_definition=(
            "Prefer clear notes, broad source coverage, and repeated patterns across more than one source."
        ),
    )
    trajectory = create_detailed_report(db, task.id)

    db.refresh(niche)
    return {
        "niche": niche,
        "discovered_sources": discovered_sources,
        "run_id": run_result["run_id"],
        "pages_scraped": run_result["pages_scraped"],
        "insights_created": run_result["insights_created"],
        "task_id": task.id,
        "trajectory_id": trajectory.id,
    }


def _attach_sources(db: Session, niche_id: int, discovered_sources: list[DiscoveredSource]) -> None:
    companies = db.scalars(select(Company).where(Company.niche_id == niche_id)).all()
    by_name = {company.name.lower(): company for company in companies}

    for item in discovered_sources:
        company = by_name.get(item.company_name.lower())
        if company is None:
            company = create_company(
                db,
                niche_id,
                CompanyCreate(
                    name=item.company_name,
                    domain=item.domain,
                    notes=item.rationale,
                ),
            )
            by_name[company.name.lower()] = company

        existing_urls = {source.url for source in company.sources}
        if item.url in existing_urls:
            continue

        create_source(
            db,
            company.id,
            SourceCreate(page_type=item.page_type, url=item.url),
        )
