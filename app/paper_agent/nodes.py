from __future__ import annotations

import re
from dataclasses import dataclass

from .config import PaperAgentConfig
from .llm import LLMClient
from .prompts import (
    CONSENSUS_SYSTEM_PROMPT,
    CRITIC_REVIEW_SYSTEM_PROMPT,
    DRAFT_SYSTEM_PROMPT,
    EXPERIMENT_REVIEW_SYSTEM_PROMPT,
    METHODOLOGY_REVIEW_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    QUALITY_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    consensus_user_prompt,
    draft_user_prompt,
    history_summary_prompt,
    planner_user_prompt,
    quality_user_prompt,
    review_user_prompt,
)
from .repository import PaperRepository
from .schemas import AgentResponse, FigureAsset, PlannerDecision, QualityReport, ReviewNote, ToolCallRecord
from .state import PaperAgentState
from .tools import PaperToolkit


FIGURE_QUERY_RE = re.compile(r"(figure|fig\.?|image|chart|plot)", re.IGNORECASE)
COMPARE_QUERY_RE = re.compile(r"(compare|comparison|versus|vs\.?)", re.IGNORECASE)
PYTHON_QUERY_RE = re.compile(r"(stat|statistics|metric|number|mean|variance)", re.IGNORECASE)
WEB_QUERY_RE = re.compile(r"(latest|recent|today|news|web)", re.IGNORECASE)


@dataclass(slots=True)
class PaperAgentNodes:
    """LangGraph 节点实现。

    图负责宏观路由，这个类中的部分节点会调用 `create_agent(...)`，
    让模型在节点内部自行决定是否使用检索、读图或分析工具。
    """

    config: PaperAgentConfig
    repository: PaperRepository
    toolkit: PaperToolkit
    llm: LLMClient

    def initialize(self, state: PaperAgentState) -> PaperAgentState:
        """初始化本轮状态。"""
        query = state["user_query"].strip()
        self.llm.reset_call_budget(self.config.max_model_calls)
        self._progress("initialize", f"Starting request: {query[:120]}", state)
        messages = state.get("messages", [])
        if not messages:
            messages = [{"role": "user", "content": query}]

        paper_inputs = state.get("paper_inputs") or []
        self._progress(
            "initialize",
            f"Prepared {len(paper_inputs)} paper input(s).",
            state,
        )
        return {
            "messages": messages,
            "paper_inputs": paper_inputs,
            "user_preferences": state.get("user_preferences", {}),
        }

    def planner(self, state: PaperAgentState) -> PaperAgentState:
        """运行规划节点，输出下一步动作。"""
        self._progress("planner", "Planning next action.", state)
        decision = self._plan_next_action(state)
        budget_snapshot = self._runtime_budget_snapshot(state)
        self._progress("planner", f"Decision => {decision.next_action}. {decision.reasoning}", state)
        return {
            "planner_decision": decision,
            "tool_results": {
                "planner": ToolCallRecord(
                    tool_name="planner",
                    status="ok",
                    summary=(
                        f"Planner selected `{decision.next_action}`: {decision.reasoning} "
                        f"(llm={budget_snapshot['llm_calls_used']}/{budget_snapshot['max_model_calls']})"
                    ),
                    payload={
                        **decision.model_dump(),
                        "budget": budget_snapshot,
                    },
                )
            },
        }

    def route_after_planner(self, state: PaperAgentState) -> str:
        if self._is_llm_cap_reached():
            self._progress("planner_route", "LLM call cap reached -> finalize immediately.", state)
            return "finalize"

        decision = state["planner_decision"]
        if decision.next_action == "review":
            return "review_input"
        if decision.next_action == "finalize":
            return "draft"
        return decision.next_action

    def retrieve(self, state: PaperAgentState) -> PaperAgentState:
        """显式检索节点：把检索结果写回共享状态。"""
        decision = state["planner_decision"]
        paper_ids = [item.paper_id for item in state["paper_inputs"]]
        planned_query = decision.retrieval_query.strip() if decision.retrieval_query else ""
        query = planned_query or self._build_contextual_retrieval_query(state)
        chunks = self.toolkit.retrieve_paper_chunks(query=query, paper_ids=paper_ids, top_k=self.config.retrieval_top_k)

        existing_ids = {chunk.chunk_id for chunk in state.get("retrieved_chunks", [])}
        new_chunks = [chunk for chunk in chunks if chunk.chunk_id not in existing_ids]
        self._progress("retrieve", f"query=`{query}` -> {len(chunks)} chunk(s), {len(new_chunks)} new.", state)
        return {
            "retrieved_chunks": new_chunks,
            "tool_results": {
                "retrieve_paper_chunks": ToolCallRecord(
                    tool_name="retrieve_paper_chunks",
                    status="ok",
                    summary=f"Retrieved {len(chunks)} chunks for query `{query}`.",
                    payload={
                        "query": query,
                        "paper_ids": paper_ids,
                        "chunk_ids": [chunk.chunk_id for chunk in chunks],
                    },
                )
            },
        }

    def vision(self, state: PaperAgentState) -> PaperAgentState:
        """显式读图节点：把选中的 figure 资产写回共享状态。"""
        decision = state["planner_decision"]
        figure_map: dict[str, list[FigureAsset]] = {}
        figure_ids = decision.focus_figure_ids

        for paper_input in state["paper_inputs"]:
            if figure_ids:
                figures = [
                    figure
                    for figure_id in figure_ids
                    if (figure := self.toolkit.read_figure_by_id(paper_input.paper_id, figure_id)) is not None
                ]
            else:
                figures = self.repository.build_figure_map(paper_input.paper_id)[:3]
            if figures:
                figure_map[paper_input.paper_id] = figures

        loaded_count = sum(len(figures) for figures in figure_map.values())
        status = "ok" if loaded_count else "skipped"
        self._progress("vision", f"Loaded {loaded_count} figure(s).", state)
        return {
            "figure_map": figure_map,
            "tool_results": {
                "read_figure_by_id": ToolCallRecord(
                    tool_name="read_figure_by_id",
                    status=status,
                    summary=f"Loaded {loaded_count} figures for the current step.",
                    payload={
                        "requested_ids": figure_ids,
                        "paper_ids": list(figure_map),
                    },
                )
            },
        }

    def python(self, state: PaperAgentState) -> PaperAgentState:
        """显式分析节点：对已有证据做轻量数值统计。"""
        text = "\n\n".join(chunk.content for chunk in state.get("retrieved_chunks", []))
        result = self.toolkit.run_python_stats(text)
        self._progress("python", f"{result.status}: {result.summary}", state)
        return {"tool_results": {"run_python_stats": result}}

    def web(self, state: PaperAgentState) -> PaperAgentState:
        """显式联网节点：调用外部搜索工具并记录结果。"""
        decision = state.get("planner_decision")
        planned_query = decision.retrieval_query.strip() if decision and decision.retrieval_query else ""
        query = planned_query or self._build_contextual_web_query(state)
        result = self.toolkit.search_web(query)
        self._progress("web", f"query=`{query}` | {result.status}: {result.summary}", state)
        return {"tool_results": {"search_web": result}}

    def review_input(self, state: PaperAgentState) -> PaperAgentState:
        """记录当前进入哪种审阅模式。"""
        decision = state["planner_decision"]
        self._progress("review_input", f"Entering `{decision.mode}` review mode.", state)
        return {
            "tool_results": {
                "review_input": ToolCallRecord(
                    tool_name="review_input",
                    status="ok",
                    summary=f"Prepared review context in `{decision.mode}` mode.",
                    payload={"mode": decision.mode},
                )
            }
        }

    def methodology_review(self, state: PaperAgentState) -> PaperAgentState:
        """方法论评审 Agent。"""
        note = self._review("methodology", METHODOLOGY_REVIEW_SYSTEM_PROMPT, state)
        self._progress("methodology_review", note.summary[:160], state)
        return {"review_notes": {"methodology": note}}

    def experiment_review(self, state: PaperAgentState) -> PaperAgentState:
        """实验评审 Agent。"""
        note = self._review("experiment", EXPERIMENT_REVIEW_SYSTEM_PROMPT, state)
        self._progress("experiment_review", note.summary[:160], state)
        return {"review_notes": {"experiment": note}}

    def critical_review(self, state: PaperAgentState) -> PaperAgentState:
        """批判性评审 Agent。"""
        note = self._review("critic", CRITIC_REVIEW_SYSTEM_PROMPT, state)
        self._progress("critical_review", note.summary[:160], state)
        return {"review_notes": {"critic": note}}

    def consensus(self, state: PaperAgentState) -> PaperAgentState:
        """共识 Agent：汇总多个 reviewer 的意见。"""
        notes = list(state.get("review_notes", {}).values())
        budget_prompt = self._runtime_budget_prompt(state, stage="consensus")
        prompt = f"{budget_prompt}\n\n{consensus_user_prompt(notes)}"
        llm_note = self.llm.invoke_structured(
            CONSENSUS_SYSTEM_PROMPT,
            prompt,
            ReviewNote,
            tools=self._analysis_tools(),
            agent_name="consensus_agent",
        )
        if llm_note is not None:
            llm_note.reviewer = "consensus"
            note = llm_note
        else:
            llm_error = self.llm.consume_last_error()
            if llm_error:
                self._progress("consensus", f"Fallback due to LLM issue: {llm_error}", state)
            strengths: list[str] = []
            weaknesses: list[str] = []
            evidence: list[str] = []
            for item in notes:
                strengths.extend(item.strengths)
                weaknesses.extend(item.weaknesses)
                evidence.extend(item.evidence)
            note = ReviewNote(
                reviewer="consensus",
                summary="Consensus review combining methodology, experiment, and critical perspectives.",
                strengths=self._unique(strengths)[:4],
                weaknesses=self._unique(weaknesses)[:4],
                evidence=self._unique(evidence)[:6],
            )

        self._progress("consensus", note.summary[:160], state)

        return {
            "review_notes": {"consensus": note},
            "tool_results": {
                "consensus": ToolCallRecord(
                    tool_name="consensus",
                    status="ok",
                    summary="Merged reviewer outputs into a consensus note.",
                    payload=note.model_dump(),
                )
            },
        }

    def draft(self, state: PaperAgentState) -> PaperAgentState:
        """回答起草 Agent，可在需要时再次调用工具补证据。"""
        figures = self._all_figures(state)
        reviews = list(state.get("review_notes", {}).values())
        budget_prompt = self._runtime_budget_prompt(state, stage="draft")
        prompt = budget_prompt + "\n\n" + draft_user_prompt(
            user_query=state["user_query"],
            chunks=state.get("retrieved_chunks", []),
            reviews=reviews,
            figures=figures,
            user_preferences=state.get("user_preferences", {}),
        )
        draft_answer = self.llm.invoke_text(
            DRAFT_SYSTEM_PROMPT,
            prompt,
            tools=self._analysis_tools(),
            agent_name="draft_agent",
        )
        if not draft_answer:
            llm_error = self.llm.consume_last_error()
            if llm_error:
                self._progress("draft", f"Fallback due to LLM issue: {llm_error}", state)
            draft_answer = self._fallback_draft(state)

        self._progress("draft", f"Draft ready ({len(draft_answer)} chars).", state)

        return {
            "draft_answer": draft_answer,
            "tool_results": {
                "draft_answer": ToolCallRecord(
                    tool_name="draft_answer",
                    status="ok",
                    summary="Generated answer draft.",
                )
            },
        }

    def route_after_draft(self, state: PaperAgentState) -> str:
        """当 LLM 预算已到上限时，草稿后立即终结，避免再进入 QA 消耗回合。"""
        if self._is_llm_cap_reached():
            self._progress("draft_route", "LLM call cap reached -> finalize immediately.", state)
            return "finalize"
        return "qa"

    def qa(self, state: PaperAgentState) -> PaperAgentState:
        """质量评估 Agent，判断是否需要补信息或重写。"""
        reviews = list(state.get("review_notes", {}).values())
        budget_prompt = self._runtime_budget_prompt(state, stage="qa")
        prompt = budget_prompt + "\n\n" + quality_user_prompt(
            user_query=state["user_query"],
            draft_answer=state.get("draft_answer", ""),
            reviews=reviews,
            preferences=state.get("user_preferences", {}),
        )
        report = self.llm.invoke_structured(
            QUALITY_SYSTEM_PROMPT,
            prompt,
            QualityReport,
            tools=self._analysis_tools(),
            agent_name="qa_agent",
        )
        if report is None:
            llm_error = self.llm.consume_last_error()
            if llm_error:
                self._progress("qa", f"Fallback due to LLM issue: {llm_error}", state)
            report = self._fallback_quality_report(state)

        self._progress("qa", f"verdict={report.verdict}, score={report.quality_score:.2f}", state)

        return {
            "quality_report": report,
            "quality_score": report.quality_score,
            "tool_results": {
                "quality_review": ToolCallRecord(
                    tool_name="quality_review",
                    status="ok",
                    summary=f"Quality review verdict: {report.verdict}",
                    payload=report.model_dump(),
                )
            },
        }

    def route_after_qa(self, state: PaperAgentState) -> str:
        if self._is_llm_cap_reached():
            self._progress("qa_route", "LLM call cap reached -> finalize immediately.", state)
            return "finalize"

        report = state["quality_report"]
        if report.verdict == "pass":
            self._progress("qa_route", "Quality pass -> finalize.", state)
            return "finalize"

        if report.verdict == "rewrite":
            self._progress("qa_route", "QA requested rewrite.", state)
            return "rewrite"

        self._progress("qa_route", "QA requested more info -> planner.", state)
        return "planner"

    def rewrite(self, state: PaperAgentState) -> PaperAgentState:
        """按 QA 反馈重写答案。"""
        report = state["quality_report"]
        base_draft = state.get("draft_answer", "")
        rewritten: str | None = None
        if self.llm.is_available():
            budget_prompt = self._runtime_budget_prompt(state, stage="rewrite")
            prompt = (
                f"{budget_prompt}\n\n"
                f"Current draft:\n{base_draft}\n\n"
                f"Rewrite instructions:\n{report.rewrite_instructions or report.missing_points}\n\n"
                "Rewrite the answer so it directly addresses the missing points."
            )
            rewritten = self.llm.invoke_text(
                DRAFT_SYSTEM_PROMPT,
                prompt,
                tools=self._analysis_tools(),
                agent_name="rewrite_agent",
            )
            if not rewritten:
                llm_error = self.llm.consume_last_error()
                if llm_error:
                    self._progress("rewrite", f"Fallback due to LLM issue: {llm_error}", state)
        if not rewritten:
            additions = "\n".join(f"- {item}" for item in (report.rewrite_instructions or report.missing_points))
            rewritten = f"{base_draft}\n\nRevision notes:\n{additions}" if additions else base_draft

        self._progress("rewrite", f"Rewritten draft ({len(rewritten)} chars).", state)

        return {
            "draft_answer": rewritten or base_draft,
            "tool_results": {
                "rewrite": ToolCallRecord(
                    tool_name="rewrite",
                    status="ok",
                    summary="Rewrote draft after QA feedback.",
                    payload={"instructions": report.rewrite_instructions or report.missing_points},
                )
            },
        }

    def finalize(self, state: PaperAgentState) -> PaperAgentState:
        """写入最终答案。"""
        final_answer = state.get("draft_answer") or self._fallback_draft(state)
        calls, budget = self.llm.get_call_stats()
        budget_cap_reached = calls >= budget
        budget_exhausted = self.llm.is_budget_exhausted() or budget_cap_reached
        self._progress("finalize", f"Final answer prepared ({len(final_answer)} chars).", state)
        return {
            "final_answer": final_answer,
            "messages": [{"role": "assistant", "content": final_answer}],
            "tool_results": {
                "llm_budget": ToolCallRecord(
                    tool_name="llm_budget",
                    status="error" if budget_exhausted else "ok",
                    summary=(
                        f"Model calls used: {calls}/{budget}."
                        + (
                            " LLM call cap reached; workflow finalized immediately with available evidence."
                            if budget_cap_reached
                            else (" Budget exhausted; workflow switched to fallback behavior." if budget_exhausted else "")
                        )
                    ),
                    payload={
                        "model_call_count": calls,
                        "max_model_calls": budget,
                        "budget_cap_reached": budget_cap_reached,
                        "budget_exhausted": budget_exhausted,
                    },
                )
            },
        }

    def compress_history(self, state: PaperAgentState) -> PaperAgentState:
        """压缩过长历史，保留后续轮次可复用的摘要。"""
        messages = state.get("messages", [])
        if len(messages) <= self.config.keep_recent_messages:
            self._progress("compress_history", "History short enough, skip compression.", state)
            return {"history_summary": state.get("history_summary", "")}

        history_slice = messages[:-self.config.keep_recent_messages]
        prompt = history_summary_prompt(history_slice)
        summary = self.llm.invoke_text(
            SUMMARY_SYSTEM_PROMPT,
            prompt,
            agent_name="history_summary_agent",
        )
        if not summary:
            llm_error = self.llm.consume_last_error()
            if llm_error:
                self._progress("compress_history", f"Fallback summary due to LLM issue: {llm_error}", state)
            summary = " | ".join(message.get("content", "")[:120] for message in history_slice)

        self._progress("compress_history", "Conversation history compressed.", state)

        return {"history_summary": summary}

    def build_response(self, state: PaperAgentState) -> AgentResponse:
        """把最终 graph state 转成对外返回对象。"""
        return AgentResponse(
            final_answer=state.get("final_answer", ""),
            quality_score=state.get("quality_score", 0.0),
            tool_results=state.get("tool_results", {}),
            review_notes=state.get("review_notes", {}),
        )

    def _plan_next_action(self, state: PaperAgentState) -> PlannerDecision:
        """planner 使用 `create_agent(...)` 决定下一步，并允许其内部调用工具。"""
        paper_ids = [item.paper_id for item in state.get("paper_inputs", [])]
        retrieved_chunks = state.get("retrieved_chunks", [])
        has_figures = any(state.get("figure_map", {}).values())
        has_reviews = "consensus" in state.get("review_notes", {})
        query = state["user_query"]
        mode = "multi_paper" if len(paper_ids) > 1 or COMPARE_QUERY_RE.search(query) else "single_paper"
        budget_snapshot = self._runtime_budget_snapshot(state)

        if self._is_llm_cap_reached():
            return PlannerDecision(
                next_action="finalize",
                reasoning=(
                    "LLM call cap reached "
                    f"({budget_snapshot['llm_calls_used']}/{budget_snapshot['max_model_calls']}); "
                    "finalize immediately with current evidence."
                ),
                retrieval_query=self._build_contextual_retrieval_query(state),
                mode=mode,
            )

        prompt = planner_user_prompt(
            user_query=query,
            paper_ids=paper_ids,
            retrieved_chunks=retrieved_chunks,
            has_figures=has_figures,
            has_reviews=has_reviews,
            llm_calls_used=budget_snapshot["llm_calls_used"],
            max_model_calls=budget_snapshot["max_model_calls"],
            llm_calls_remaining=budget_snapshot["llm_calls_remaining"],
            context_summary=self._build_query_subject_summary(state),
        )
        decision = self.llm.invoke_structured(
            PLANNER_SYSTEM_PROMPT,
            prompt,
            PlannerDecision,
            tools=self._planner_tools(),
            agent_name="planner_agent",
        )
        if decision is not None:
            return decision

        llm_error = self.llm.consume_last_error()
        if llm_error:
            self._progress("planner", f"LLM planner unavailable, using fallback policy: {llm_error}", state)
            if self._is_llm_cap_reached():
                return PlannerDecision(
                    next_action="finalize",
                    reasoning=(
                        "Model call budget has reached the configured cap; "
                        "stop planning and finalize using currently available evidence."
                    ),
                    retrieval_query=self._build_contextual_retrieval_query(state),
                    mode=mode,
                )

        if not retrieved_chunks:
            return PlannerDecision(
                next_action="retrieve",
                reasoning="No evidence has been retrieved yet.",
                retrieval_query=self._build_contextual_retrieval_query(state),
                mode=mode,
            )
        if FIGURE_QUERY_RE.search(query) and not has_figures:
            return PlannerDecision(
                next_action="vision",
                reasoning="The user is asking about figures or images.",
                retrieval_query=query,
                focus_figure_ids=self._extract_figure_ids(query),
                mode=mode,
            )
        if PYTHON_QUERY_RE.search(query) and "run_python_stats" not in state.get("tool_results", {}):
            return PlannerDecision(
                next_action="python",
                reasoning="The query appears to require numeric analysis.",
                retrieval_query=query,
                mode=mode,
            )
        if WEB_QUERY_RE.search(query) and self.config.enable_web_search and "search_web" not in state.get("tool_results", {}):
            return PlannerDecision(
                next_action="web",
                reasoning="The user is explicitly asking for recent or external information.",
                retrieval_query=self._build_contextual_web_query(state),
                mode=mode,
            )
        if not has_reviews:
            return PlannerDecision(
                next_action="review",
                reasoning="Evidence is available and reviewer notes have not been generated yet.",
                retrieval_query=query,
                mode=mode,
            )
        return PlannerDecision(
            next_action="finalize",
            reasoning="The system has enough evidence to draft an answer.",
            retrieval_query=query,
            mode=mode,
        )

    def _review(self, reviewer: str, system_prompt: str, state: PaperAgentState) -> ReviewNote:
        """单个 reviewer 节点，允许在节点内部自主补检索或读图。"""
        figures = self._all_figures(state)
        budget_prompt = self._runtime_budget_prompt(state, stage=f"{reviewer}_review")
        prompt = budget_prompt + "\n\n" + review_user_prompt(
            user_query=state["user_query"],
            chunks=state.get("retrieved_chunks", []),
            figures=figures,
        )
        note = self.llm.invoke_structured(
            system_prompt,
            prompt,
            ReviewNote,
            tools=self._analysis_tools(),
            agent_name=f"{reviewer}_review_agent",
        )
        if note is not None:
            note.reviewer = reviewer  # type: ignore[assignment]
            return note

        llm_error = self.llm.consume_last_error()
        if llm_error:
            self._progress(f"{reviewer}_review", f"Using fallback note: {llm_error}", state)

        evidence = [f"{chunk.paper_id}:{chunk.chunk_id}" for chunk in state.get("retrieved_chunks", [])[:4]]
        figure_refs = [f"{figure.paper_id}:Figure {figure.img_id}" for figure in figures[:3]]
        strengths = {
            "methodology": [
                "The retrieved chunks describe the proposed approach in concrete technical terms.",
                "The answer can ground claims in paper-specific passages.",
            ],
            "experiment": [
                "The retrieved evidence includes experimental sections or result descriptions.",
                "The framework preserves chunk-level citations for later drafting.",
            ],
            "critic": [
                "The framework can explicitly track limitations through a dedicated reviewer.",
                "Consensus synthesis helps avoid single-agent overclaiming.",
            ],
        }
        weaknesses = {
            "methodology": [
                "Method details may still be incomplete if the retrieved chunks miss algorithm sections.",
            ],
            "experiment": [
                "Quantitative evidence may remain thin without table-specific retrieval or figure inspection.",
            ],
            "critic": [
                "The current evidence may not fully expose negative results or failure cases.",
            ],
        }

        return ReviewNote(
            reviewer=reviewer,  # type: ignore[arg-type]
            summary=f"{reviewer.capitalize()} review based on retrieved chunks and available figures.",
            strengths=strengths.get(reviewer, []),
            weaknesses=weaknesses.get(reviewer, []),
            evidence=self._unique(evidence + figure_refs)[:6],
        )

    def _fallback_draft(self, state: PaperAgentState) -> str:
        paper_ids = [item.paper_id for item in state.get("paper_inputs", [])]
        consensus = state.get("review_notes", {}).get("consensus")
        chunks = state.get("retrieved_chunks", [])
        figures = self._all_figures(state)
        lines = [
            f"Question: {state['user_query']}",
            f"Paper scope: {', '.join(paper_ids) if paper_ids else 'unspecified'}",
        ]
        if consensus is not None:
            lines.append(f"Overall assessment: {consensus.summary}")
            if consensus.strengths:
                lines.append("Key strengths: " + "; ".join(consensus.strengths[:3]))
            if consensus.weaknesses:
                lines.append("Limitations and risks: " + "; ".join(consensus.weaknesses[:3]))
        if chunks:
            lines.append("Evidence excerpts:")
            for chunk in chunks[:3]:
                lines.append(f"- [{chunk.paper_id}:{chunk.chunk_id}] {chunk.content[:220].strip()}")
        if figures:
            lines.append("Relevant figures:")
            for figure in figures[:3]:
                lines.append(f"- Figure {figure.img_id} ({figure.paper_id}): {figure.caption or figure.img_path}")
        return "\n".join(lines)

    def _fallback_quality_report(self, state: PaperAgentState) -> QualityReport:
        draft = state.get("draft_answer", "")
        missing_points: list[str] = []
        lowered = draft.lower()
        if not draft.strip():
            missing_points.append("No draft answer exists yet.")
        if state.get("retrieved_chunks") and "evidence" not in lowered:
            missing_points.append("The answer should reference supporting evidence from the paper.")
        if state.get("review_notes") and "limitation" not in lowered and "risk" not in lowered:
            missing_points.append("The answer should mention at least one limitation or open risk.")

        if not missing_points:
            return QualityReport(
                verdict="pass",
                quality_score=0.82,
                reasoning="The draft covers the expected areas with paper-backed content.",
            )

        verdict = "rewrite" if draft.strip() else "need_more_info"
        return QualityReport(
            verdict=verdict,  # type: ignore[arg-type]
            quality_score=0.52 if draft.strip() else 0.34,
            missing_points=missing_points,
            rewrite_instructions=missing_points,
            reasoning="The draft is missing required coverage.",
        )

    def _all_figures(self, state: PaperAgentState) -> list[FigureAsset]:
        figures: list[FigureAsset] = []
        for items in state.get("figure_map", {}).values():
            figures.extend(items)
        return figures

    def _extract_figure_ids(self, text: str) -> list[int]:
        return [int(match) for match in re.findall(r"(?:figure|fig\.?)\s*(\d+)", text, flags=re.IGNORECASE)]

    def _build_query_subject_summary(self, state: PaperAgentState) -> str:
        """构建主题摘要，供检索 query 生成使用。"""
        paper_title = next((item.title for item in state.get("paper_inputs", []) if item.title), None)
        if paper_title:
            return paper_title.strip()

        for chunk in state.get("retrieved_chunks", [])[:4]:
            for raw_line in chunk.content.splitlines()[:4]:
                line = raw_line.strip().lstrip("#").strip()
                if len(line) >= 8:
                    return line[:120]

        user_query = re.sub(r"\s+", " ", state.get("user_query", "")).strip()
        if user_query:
            return user_query[:120]
        return "paper topic"

    def _extract_requested_facets(self, user_query: str, is_chinese: bool) -> list[str]:
        """从用户需求中提取本轮检索关注点。"""
        lowered = user_query.lower()
        facets: list[str] = []

        if is_chinese:
            if "核心" in user_query or "问题" in user_query:
                facets.append("核心问题")
            if "方法" in user_query:
                facets.append("方法")
            if "实验" in user_query:
                facets.append("实验")
            if "局限" in user_query or "限制" in user_query:
                facets.append("局限")
            if "贡献" in user_query:
                facets.append("贡献")
            if "新" in user_query or "最新" in user_query or "技术" in user_query:
                facets.append("最新技术进展")
        else:
            if "problem" in lowered:
                facets.append("core problem")
            if "method" in lowered:
                facets.append("method")
            if "experiment" in lowered or "result" in lowered:
                facets.append("experiments and results")
            if "limitation" in lowered or "weakness" in lowered:
                facets.append("limitations")
            if "contribution" in lowered:
                facets.append("contributions")
            if "latest" in lowered or "recent" in lowered or "new" in lowered:
                facets.append("latest advances")

        if not facets:
            facets = ["核心问题", "方法", "实验", "局限"] if is_chinese else [
                "core problem",
                "method",
                "experiments",
                "limitations",
            ]
        return facets

    def _build_contextual_retrieval_query(self, state: PaperAgentState) -> str:
        """构建可脱离对话上下文独立执行的本地检索 query。"""
        user_query = state.get("user_query", "").strip()
        is_chinese = bool(re.search(r"[\u4e00-\u9fff]", user_query))
        subject = self._build_query_subject_summary(state)
        facets = self._extract_requested_facets(user_query, is_chinese)

        if is_chinese:
            facet_part = "、".join(facets)
            return f"主题：{subject}；检索目标：{facet_part}；关键词：摘要 引言 方法 实验 结果 局限 贡献"

        facet_part = ", ".join(facets)
        return (
            f"Topic: {subject}; Retrieval objective: {facet_part}; "
            "Keywords: abstract introduction method experiments results limitations contributions"
        )

    def _build_contextual_web_query(self, state: PaperAgentState) -> str:
        """根据当前上下文构造联网检索 query，避免直接复用原始用户句子。"""
        user_query = state.get("user_query", "").strip()
        is_chinese = bool(re.search(r"[\u4e00-\u9fff]", user_query))
        subject = self._build_query_subject_summary(state)
        facets = self._extract_requested_facets(user_query, is_chinese)

        if is_chinese:
            facet_part = "、".join(facets)
            return (
                f"主题：{subject}；查询目标：{facet_part}；"
                "查询范围：2025 2026 最新研究；输出：代表性方法、关键改进、可比基线"
            )

        facet_part = ", ".join(facets)
        return (
            f"Topic: {subject}; Search objective: {facet_part}; "
            "Scope: latest advances in 2025 and 2026; Output: representative methods, key improvements, comparable baselines"
        )

    def _runtime_budget_snapshot(self, state: PaperAgentState | None = None) -> dict[str, int]:
        """返回当前轮次可见的预算快照。"""
        llm_calls_used, max_model_calls = self.llm.get_call_stats()

        return {
            "llm_calls_used": llm_calls_used,
            "max_model_calls": max_model_calls,
            "llm_calls_remaining": max(0, max_model_calls - llm_calls_used),
        }

    def _runtime_budget_prompt(self, state: PaperAgentState, *, stage: str) -> str:
        """构造注入到各 Agent 的预算提示，确保每轮变化可见。"""
        snapshot = self._runtime_budget_snapshot(state)
        return (
            f"Runtime budget snapshot (stage={stage}):\n"
            f"- LLM calls: {snapshot['llm_calls_used']}/{snapshot['max_model_calls']} "
            f"(remaining={snapshot['llm_calls_remaining']})\n"
            "If remaining budget is near zero, prioritize producing the best possible final answer immediately."
        )

    def _is_llm_cap_reached(self) -> bool:
        """判断是否达到（或触发）LLM 调用上限。"""
        calls, budget = self.llm.get_call_stats()
        return calls >= budget or self.llm.is_budget_exhausted()

    def _planner_tools(self) -> list:
        """planner 可见的工具集合。"""
        return self.toolkit.to_langchain_tools()

    def _analysis_tools(self) -> list:
        """review/draft/qa 可见的工具集合。"""
        return self.toolkit.to_langchain_tools()

    def _progress(self, stage: str, message: str, state: PaperAgentState | None = None) -> None:
        """按配置输出中间进度日志。"""
        if not self.config.verbose_progress:
            return

        calls, budget = self.llm.get_call_stats()
        print(f"[paper-agent][{stage}] llm={calls}/{budget} | {message}", flush=True)

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen or not value:
                continue
            seen.add(value)
            result.append(value)
        return result
