from __future__ import annotations

from typing import Iterable

from .schemas import FigureAsset, RetrievedChunk, ReviewNote


PLANNER_SYSTEM_PROMPT = """You are the planner for a paper-reading assistant.
Decide the single best next step.
Prefer retrieval before analysis, vision when figures are explicitly requested, review after enough evidence is available, and finalize only when the answer can be drafted.
"""

METHODOLOGY_REVIEW_SYSTEM_PROMPT = """You are a methodology reviewer.
Focus on problem definition, assumptions, model design, algorithmic novelty, and what technical choices matter.
"""

EXPERIMENT_REVIEW_SYSTEM_PROMPT = """You are an experiment reviewer.
Focus on datasets, baselines, metrics, ablations, and whether results support the claims.
"""

CRITIC_REVIEW_SYSTEM_PROMPT = """You are a critical reviewer.
Focus on limitations, missing evidence, risks of overclaiming, and what an expert reader should remain skeptical about.
"""

CONSENSUS_SYSTEM_PROMPT = """You synthesize multiple review notes into one consensus note.
Retain concrete evidence and preserve unresolved disagreements.
"""

DRAFT_SYSTEM_PROMPT = """You are a paper reading assistant.
Answer clearly and directly in the user's language when possible.
Cover contributions, evidence, limitations, and figure references when relevant.
Do not fabricate evidence.
"""

QUALITY_SYSTEM_PROMPT = """You are a strict answer quality reviewer.
Judge whether the draft covers contribution, evidence, limitation, and user preferences.
Return pass only when the answer is specific and evidence-backed.
"""

SUMMARY_SYSTEM_PROMPT = """Summarize the conversation history into a compact memory note.
Keep user preference, discussed papers, unresolved questions, and important conclusions.
"""


def planner_user_prompt(*, user_query: str, paper_ids: list[str], retrieved_chunks: list[RetrievedChunk], has_figures: bool, has_reviews: bool, iteration_count: int, max_iterations: int) -> str:
    return (
        f"User query:\n{user_query}\n\n"
        f"Paper ids: {paper_ids}\n"
        f"Retrieved chunk count: {len(retrieved_chunks)}\n"
        f"Has figures loaded: {has_figures}\n"
        f"Has reviews: {has_reviews}\n"
        f"Iteration: {iteration_count}/{max_iterations}\n"
        "Choose one action from: retrieve, vision, python, web, review, finalize."
    )


def review_user_prompt(user_query: str, chunks: Iterable[RetrievedChunk], figures: Iterable[FigureAsset]) -> str:
    chunk_text = "\n\n".join(
        f"[{chunk.paper_id}::{chunk.chunk_id}] {chunk.content[:1200]}"
        for chunk in chunks
    )
    figure_text = "\n".join(
        f"[{figure.paper_id}::img_{figure.img_id}] {figure.caption or figure.img_path}"
        for figure in figures
    )
    return (
        f"User query:\n{user_query}\n\n"
        f"Evidence chunks:\n{chunk_text or 'None'}\n\n"
        f"Figures:\n{figure_text or 'None'}"
    )


def consensus_user_prompt(notes: Iterable[ReviewNote]) -> str:
    payload = "\n\n".join(
        f"[{note.reviewer}]\nSummary: {note.summary}\nStrengths: {note.strengths}\nWeaknesses: {note.weaknesses}\nEvidence: {note.evidence}"
        for note in notes
    )
    return payload or "No review notes available."


def draft_user_prompt(user_query: str, chunks: Iterable[RetrievedChunk], reviews: Iterable[ReviewNote], figures: Iterable[FigureAsset], user_preferences: dict) -> str:
    evidence = "\n\n".join(
        f"[{chunk.paper_id}::{chunk.chunk_id}] {chunk.content[:1200]}"
        for chunk in chunks
    )
    review_text = "\n\n".join(
        f"[{note.reviewer}] {note.summary}\nStrengths: {note.strengths}\nWeaknesses: {note.weaknesses}"
        for note in reviews
    )
    figure_text = "\n".join(
        f"Figure {figure.img_id} ({figure.paper_id}): {figure.caption or figure.img_path}"
        for figure in figures
    )
    return (
        f"User query:\n{user_query}\n\n"
        f"User preferences:\n{user_preferences}\n\n"
        f"Evidence chunks:\n{evidence or 'None'}\n\n"
        f"Review notes:\n{review_text or 'None'}\n\n"
        f"Figures:\n{figure_text or 'None'}"
    )


def quality_user_prompt(user_query: str, draft_answer: str, reviews: Iterable[ReviewNote], preferences: dict) -> str:
    review_summaries = "\n".join(f"{note.reviewer}: {note.summary}" for note in reviews)
    return (
        f"User query:\n{user_query}\n\n"
        f"User preferences:\n{preferences}\n\n"
        f"Draft answer:\n{draft_answer}\n\n"
        f"Review coverage:\n{review_summaries or 'None'}"
    )


def history_summary_prompt(messages: list[dict[str, str]]) -> str:
    rendered = "\n".join(f"{message.get('role', 'unknown')}: {message.get('content', '')}" for message in messages)
    return rendered or "No history."
