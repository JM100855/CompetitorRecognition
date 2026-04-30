from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    companies: Mapped[list["Company"]] = relationship(back_populates="niche")
    tasks: Mapped[list["ResearchTask"]] = relationship(back_populates="niche")
    insights: Mapped[list["Insight"]] = relationship(back_populates="niche")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    niche: Mapped["Niche"] = relationship(back_populates="companies")
    sources: Mapped[list["SourcePage"]] = relationship(back_populates="company")
    tasks: Mapped[list["ResearchTask"]] = relationship(back_populates="company")
    insights: Mapped[list["Insight"]] = relationship(back_populates="company")


class SourcePage(Base):
    __tablename__ = "source_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    page_type: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="sources")
    snapshots: Mapped[list["PageSnapshot"]] = relationship(back_populates="source")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    insights_created: Mapped[int] = mapped_column(Integer, default=0)
    trajectories: Mapped[list["AgentTrajectory"]] = relationship(back_populates="scrape_run")


class PageSnapshot(Base):
    __tablename__ = "page_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_pages.id"), index=True)
    scrape_run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["SourcePage"] = relationship(back_populates="snapshots")
    trajectory_steps: Mapped[list["TrajectoryStep"]] = relationship(back_populates="snapshot")


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    evaluation_type: Mapped[str] = mapped_column(String(64), default="heuristic")
    reward_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    niche: Mapped["Niche"] = relationship(back_populates="tasks")
    company: Mapped["Company | None"] = relationship(back_populates="tasks")
    trajectories: Mapped[list["AgentTrajectory"]] = relationship(back_populates="task")


class AgentTrajectory(Base):
    __tablename__ = "agent_trajectories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    policy_name: Mapped[str] = mapped_column(String(128), default="baseline")
    root_question: Mapped[str] = mapped_column(Text)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    total_reward: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["ResearchTask"] = relationship(back_populates="trajectories")
    scrape_run: Mapped["ScrapeRun | None"] = relationship(back_populates="trajectories")
    steps: Mapped[list["TrajectoryStep"]] = relationship(back_populates="trajectory")
    rewards: Mapped[list["RewardRecord"]] = relationship(back_populates="trajectory")


class TrajectoryStep(Base):
    __tablename__ = "trajectory_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trajectory_id: Mapped[int] = mapped_column(ForeignKey("agent_trajectories.id"), index=True)
    parent_step_id: Mapped[int | None] = mapped_column(ForeignKey("trajectory_steps.id"), nullable=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("page_snapshots.id"), nullable=True)
    node_key: Mapped[str] = mapped_column(String(128), index=True)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    action_type: Mapped[str] = mapped_column(String(64))
    action_input: Mapped[str] = mapped_column(Text)
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trajectory: Mapped["AgentTrajectory"] = relationship(back_populates="steps")
    snapshot: Mapped["PageSnapshot | None"] = relationship(back_populates="trajectory_steps")


class RewardRecord(Base):
    __tablename__ = "reward_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trajectory_id: Mapped[int] = mapped_column(ForeignKey("agent_trajectories.id"), index=True)
    step_id: Mapped[int | None] = mapped_column(ForeignKey("trajectory_steps.id"), nullable=True)
    reward_name: Mapped[str] = mapped_column(String(128))
    reward_value: Mapped[float] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trajectory: Mapped["AgentTrajectory"] = relationship(back_populates="rewards")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trajectory_id: Mapped[int | None] = mapped_column(ForeignKey("agent_trajectories.id"), nullable=True)

    niche: Mapped["Niche"] = relationship(back_populates="insights")
    company: Mapped["Company | None"] = relationship(back_populates="insights")
