"""Typed handoffs for one coordinator and six bounded business agents."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class TypedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(TypedModel):
    label: str
    evidence: str
    location: str
    confidence: Annotated[float, Field(ge=0, le=1)] | Literal["insufficient_data"]
    kind: Literal["直接观察", "数据支持", "推测/建议"] = "直接观察"


class Report(TypedModel):
    summary: str = Field(min_length=1)
    findings: list[Finding] = Field(min_length=1)
    titles: list[str] = Field(min_length=3)
    hooks: list[str] = Field(min_length=3, max_length=3)
    script: str = Field(min_length=1)
    tasks: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    source: Literal["local", "mimo"]
    image_structure: list[str] = Field(default_factory=list)
    experiments: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reason: str = ""


class COOInput(TypedModel):
    content: dict
    mode: Literal["local", "ai"]
    budget: float


class COOOutput(TypedModel):
    stages: list[str]
    source_snapshot: dict
    paid_consent: bool
    budget: float
    limitations: list[str]


class ContentInput(TypedModel):
    content: dict
    assets: list[dict]


class ContentOutput(TypedModel):
    topic: str
    audience: str
    opening_hook: str
    narrative: list[str]
    visual_observations: list[str]
    findings: list[Finding]
    limitations: list[str]
    requires_human_review: bool = False
    review_reason: str = ""


class DataInput(TypedModel):
    snapshots: list[dict]


class DataOutput(TypedModel):
    sample_count: int
    latest_metrics: dict
    source: list[str]
    findings: list[Finding]
    limitations: list[str]


class RetrievalInput(TypedModel):
    query: str
    candidates: list[dict]


class RetrievalOutput(TypedModel):
    matches: list[dict]
    limitations: list[str]


class StrategyInput(TypedModel):
    content: dict
    breakdown: ContentOutput
    data: DataOutput
    retrieval: RetrievalOutput


class StrategyDraft(BaseModel):
    """Provider creates suggestions; the worker supplies evidence and provenance."""
    model_config = ConfigDict(extra='ignore')
    titles: list[str] = Field(min_length=3)
    hooks: list[str] = Field(min_length=3, max_length=3)
    script: str = Field(min_length=1)
    tasks: list[str] = Field(min_length=1)
    image_structure: list[str] = Field(default_factory=list)
    experiments: list[str] = Field(default_factory=list)


class StrategyOutput(Report):
    pass


class QualityInput(TypedModel):
    report: Report
    allowed_urls: list[str]
    media_received: bool


class QualityOutput(TypedModel):
    passed: bool
    checks: list[str]
    issues: list[str]
    report: Report
    rework_count: int = 0


class BusinessInput(TypedModel):
    analysis_id: str
    report: Report


class BusinessOutput(TypedModel):
    delivery_ready: bool
    follow_up: str
    quote_draft: dict
    required_approvals: list[str]
    external_actions_executed: bool = False


SCHEMAS = {
    "COO": (COOInput, COOOutput), "content": (ContentInput, ContentOutput),
    "data": (DataInput, DataOutput), "retrieval": (RetrievalInput, RetrievalOutput),
    "strategy": (StrategyInput, StrategyOutput), "quality": (QualityInput, QualityOutput),
    "business": (BusinessInput, BusinessOutput),
}
