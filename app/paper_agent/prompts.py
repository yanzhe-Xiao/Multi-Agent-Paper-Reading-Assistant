from __future__ import annotations

"""提示词模板模块。

集中维护 planner/review/draft/qa 等阶段的系统提示词与用户提示词拼装函数。
"""

from typing import Iterable

from .schemas import FigureAsset, RetrievedChunk, ReviewNote


# 规划阶段系统提示词：决定下一步动作。
PLANNER_SYSTEM_PROMPT = """You are the planner for a paper-reading assistant.
Decide the single best next step.
Prefer retrieval before analysis, vision when figures are explicitly requested, review after enough evidence is available, and finalize only when the answer can be drafted.
You will receive a runtime budget snapshot for each round.
Always account for runtime LLM call budget.
When remaining_llm_calls is low (especially 0-1), prioritize producing the best possible final answer immediately.
When next_action is retrieve or web, always provide retrieval_query.
retrieval_query must be a standalone, tool-ready search statement that is understandable without chat history.
retrieval_query must explicitly include: (1) subject/topic, (2) search objective, (3) concrete focus terms.
Never use conversational references like "this paper", "above", "as discussed", or verbatim copy of user_query.
For web queries, include recency intent (e.g., 2025/2026, latest advances) when appropriate.
"""

# 方法论审查提示词。
METHODOLOGY_REVIEW_SYSTEM_PROMPT = """You are a methodology reviewer.
Focus on problem definition, assumptions, model design, algorithmic novelty, and what technical choices matter.
"""

# 实验审查提示词。
EXPERIMENT_REVIEW_SYSTEM_PROMPT = """You are an experiment reviewer.
Focus on datasets, baselines, metrics, ablations, and whether results support the claims.
"""

# 批判性审查提示词。
CRITIC_REVIEW_SYSTEM_PROMPT = """You are a critical reviewer.
Focus on limitations, missing evidence, risks of overclaiming, and what an expert reader should remain skeptical about.
"""

# 共识汇总提示词。
CONSENSUS_SYSTEM_PROMPT = """You synthesize multiple review notes into one consensus note.
Retain concrete evidence and preserve unresolved disagreements.
"""

# 草稿生成提示词。
DRAFT_SYSTEM_PROMPT = """You are a paper reading assistant.
Answer clearly and directly in the user's language when possible.
Cover contributions, evidence, limitations, and figure references when relevant.
Do not fabricate evidence.
"""

# 质量评估提示词。
QUALITY_SYSTEM_PROMPT = """You are an answer quality reviewer.
Evaluate whether the draft provides a helpful and mostly complete response to the user's query.
Be lenient with the score. Return pass and a high score (e.g. >= 0.8) as long as the core question is answered, even if it's not perfectly comprehensive.
Only return rewrite or need_more_info if the answer is critically flawed, completely misses the point, or is entirely hallucinated.
"""

# 历史压缩提示词。
SUMMARY_SYSTEM_PROMPT = """Summarize the conversation history into a compact memory note.
Keep user preference, discussed papers, unresolved questions, and important conclusions.
"""


def planner_user_prompt(
    *,
    user_query: str,
    paper_ids: list[str],
    retrieved_chunks: list[RetrievedChunk],
    has_figures: bool,
    has_reviews: bool,
    llm_calls_used: int,
    max_model_calls: int,
    llm_calls_remaining: int,
    context_summary: str,
) -> str:
    """构建 planner 阶段的用户提示词。"""
    return (
        f"User query:\n{user_query}\n\n"
        f"Context summary (for tool-visible query generation):\n{context_summary}\n\n"
        f"Paper ids: {paper_ids}\n"
        f"Retrieved chunk count: {len(retrieved_chunks)}\n"
        f"Has figures loaded: {has_figures}\n"
        f"Has reviews: {has_reviews}\n"
        f"LLM calls used: {llm_calls_used}/{max_model_calls}\n"
        f"LLM calls remaining: {llm_calls_remaining}\n"
        "Runtime budget snapshot is refreshed every round.\n"
        "Choose one action from: retrieve, vision, python, web, review, finalize.\n"
        "If you choose retrieve or web, output retrieval_query as a concise standalone query including subject + objective + focus terms."
    )


def review_user_prompt(user_query: str, chunks: Iterable[RetrievedChunk], figures: Iterable[FigureAsset]) -> str:
    """构建 reviewer 阶段的用户提示词（包含证据片段与图表摘要）。"""
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
    """构建共识阶段提示词，汇总各 reviewer 输出。"""
    payload = "\n\n".join(
        f"[{note.reviewer}]\nSummary: {note.summary}\nStrengths: {note.strengths}\nWeaknesses: {note.weaknesses}\nEvidence: {note.evidence}"
        for note in notes
    )
    return payload or "No review notes available."


def draft_user_prompt(user_query: str, chunks: Iterable[RetrievedChunk], reviews: Iterable[ReviewNote], figures: Iterable[FigureAsset], user_preferences: dict) -> str:
    """构建草稿阶段提示词，融合检索证据、审查意见和图表信息。"""
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
    """构建质量评估阶段提示词。"""
    review_summaries = "\n".join(f"{note.reviewer}: {note.summary}" for note in reviews)
    return (
        f"User query:\n{user_query}\n\n"
        f"User preferences:\n{preferences}\n\n"
        f"Draft answer:\n{draft_answer}\n\n"
        f"Review coverage:\n{review_summaries or 'None'}"
    )


def history_summary_prompt(messages: list[dict[str, str]]) -> str:
    """构建历史消息压缩提示词。"""
    rendered = "\n".join(f"{message.get('role', 'unknown')}: {message.get('content', '')}" for message in messages)
    return rendered or "No history."
