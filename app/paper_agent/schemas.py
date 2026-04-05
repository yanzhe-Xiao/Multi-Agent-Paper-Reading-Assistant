from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PlannerAction = Literal["retrieve", "vision", "python", "web", "review", "finalize"]
QualityVerdict = Literal["pass", "need_more_info", "rewrite"]
ReviewMode = Literal["single_paper", "multi_paper"]


class PaperInput(BaseModel):
    paper_id: str
    title: str | None = None


class RetrievedChunk(BaseModel):
    paper_id: str
    chunk_id: str
    content: str
    source_path: str
    score: float = 0.0
    title: str | None = None


class FigureAsset(BaseModel):
    paper_id: str
    img_id: int
    img_path: str
    absolute_path: str
    caption: str | None = None
    page_idx: int | None = None
    is_checked: bool = False


class ToolCallRecord(BaseModel):
    tool_name: str
    status: Literal["ok", "skipped", "error"]
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewNote(BaseModel):
    reviewer: Literal["methodology", "experiment", "critic", "consensus"]
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class PlannerDecision(BaseModel):
    next_action: PlannerAction
    reasoning: str
    retrieval_query: str | None = None
    focus_figure_ids: list[int] = Field(default_factory=list)
    mode: ReviewMode = "single_paper"


class QualityReport(BaseModel):
    verdict: QualityVerdict
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_points: list[str] = Field(default_factory=list)
    rewrite_instructions: list[str] = Field(default_factory=list)
    reasoning: str


class AgentResponse(BaseModel):
    final_answer: str
    quality_score: float
    iterations: int
    tool_results: dict[str, ToolCallRecord] = Field(default_factory=dict)
    review_notes: dict[str, ReviewNote] = Field(default_factory=dict)
