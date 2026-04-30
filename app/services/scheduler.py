from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.pipeline import run_daily_pipeline


def lifecycle_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    hour, minute = settings.scrape_time_utc.split(":")
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id="daily_scrape",
        replace_existing=True,
    )
    return scheduler


def _run_job() -> None:
    with SessionLocal() as session:
        run_daily_pipeline(session)

