from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str


class NicheCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    domain: str | None = None
    notes: str | None = None


class SourceCreate(BaseModel):
    page_type: str = Field(min_length=2, max_length=64)
    url: str


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_type: str
    url: str
    is_active: bool
    created_at: datetime


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str | None
    notes: str | None
    created_at: datetime
    sources: list[SourceRead] = []


class NicheRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime
    companies: list[CompanyRead] = []


class DailyRunResponse(BaseModel):
    run_id: int
    pages_scraped: int
    insights_created: int


class ResearchTaskCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    prompt: str = Field(min_length=8)
    evaluation_type: str = Field(default="heuristic", min_length=2, max_length=64)
    reward_definition: str | None = None
    company_id: int | None = None


class ResearchTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    company_id: int | None
    name: str
    prompt: str
    evaluation_type: str
    reward_definition: str | None
    is_active: bool
    created_at: datetime


class TrajectoryStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_key: str
    step_index: int
    action_type: str
    action_input: str
    observation: str | None
    branch_score: float | None


class RewardRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reward_name: str
    reward_value: float
    reason: str | None


class AgentTrajectoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    policy_name: str
    root_question: str
    final_answer: str | None
    status: str
    total_reward: float | None
    created_at: datetime
    steps: list[TrajectoryStepRead] = []
    rewards: list[RewardRecordRead] = []


class TrainingExportResponse(BaseModel):
    niche_id: int
    examples: list[dict[str, object]]


class NicheBootstrapCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class DiscoveredSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_name: str
    domain: str
    page_type: str
    url: str
    rationale: str
    score: float


class NicheBootstrapResponse(BaseModel):
    niche: NicheRead
    discovered_sources: list[DiscoveredSourceRead]
    run_id: int
    pages_scraped: int
    insights_created: int
    task_id: int
    trajectory_id: int
