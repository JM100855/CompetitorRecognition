from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Company, Insight, Niche, PageSnapshot, ScrapeRun, SourcePage
from app.services.scraper import fetch_url
from app.services.extractors import extract_page_document


def run_daily_pipeline(db: Session) -> dict[str, int]:
    run = ScrapeRun()
    db.add(run)
    db.commit()
    db.refresh(run)

    pages_scraped = 0
    insights_created = 0
    sources = db.scalars(select(SourcePage).where(SourcePage.is_active.is_(True))).all()

    for source in sources:
        html = fetch_url(source.url)
        if html is None:
            continue

        extracted = extract_page_document(html)
        content_hash = sha256((extracted["title"] + extracted["summary_text"]).encode("utf-8")).hexdigest()
        latest_snapshot = db.scalars(
            select(PageSnapshot)
            .where(PageSnapshot.source_id == source.id)
            .order_by(PageSnapshot.fetched_at.desc())
            .limit(1)
        ).first()

        snapshot = PageSnapshot(
            source_id=source.id,
            scrape_run_id=run.id,
            title=extracted["title"] or None,
            summary_text=extracted["summary_text"] or None,
            raw_text=extracted["raw_text"] or None,
            content_hash=content_hash,
        )
        db.add(snapshot)
        pages_scraped += 1

        if latest_snapshot is None or latest_snapshot.content_hash != content_hash:
            company = db.get(Company, source.company_id)
            if company is not None:
                db.add(
                    Insight(
                        niche_id=company.niche_id,
                        company_id=company.id,
                        scrape_run_id=run.id,
                        title=f"{company.name} changed on {source.page_type}",
                        body=_build_change_summary(company.name, source.page_type, extracted["summary_text"]),
                        source_url=source.url,
                    )
                )
                insights_created += 1

    run.pages_scraped = pages_scraped
    run.insights_created = insights_created
    run.status = "completed"
    run.finished_at = datetime.utcnow()
    db.commit()

    return {
        "run_id": run.id,
        "pages_scraped": pages_scraped,
        "insights_created": insights_created,
    }


def _build_change_summary(company_name: str, page_type: str, summary_text: str) -> str:
    clipped_summary = summary_text[:240].strip()
    return (
        f"{company_name} has a detected change on its {page_type} page. "
        f"Latest visible text: {clipped_summary}"
    )

