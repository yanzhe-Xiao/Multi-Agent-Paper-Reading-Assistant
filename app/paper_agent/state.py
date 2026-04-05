from __future__ import annotations

import operator
from typing import Any
from typing_extensions import Annotated, TypedDict

from .schemas import FigureAsset, PaperInput, PlannerDecision, QualityReport, RetrievedChunk, ReviewNote, ToolCallRecord


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def merge_lists(left: list[Any], right: list[Any]) -> list[Any]:
    return list(left or []) + list(right or [])


class PaperAgentState(TypedDict, total=False):
    messages: Annotated[list[dict[str, str]], operator.add]
    user_query: str
    paper_inputs: list[PaperInput]
    retrieved_chunks: Annotated[list[RetrievedChunk], merge_lists]
    figure_map: Annotated[dict[str, list[FigureAsset]], merge_dicts]
    tool_results: Annotated[dict[str, ToolCallRecord], merge_dicts]
    review_notes: Annotated[dict[str, ReviewNote], merge_dicts]
    draft_answer: str
    quality_score: float
    user_preferences: dict[str, Any]
    iteration_count: int
    max_iterations: int
    planner_decision: PlannerDecision
    quality_report: QualityReport
    final_answer: str
    history_summary: str
