from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any

from .config import PaperAgentConfig
from .repository import PaperRepository
from .schemas import FigureAsset, RetrievedChunk, ToolCallRecord


NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(slots=True)
class PaperToolkit:
    """面向 Agent 的工具层。

    `LangGraph` 仍然负责宏观编排，但这里的方法会被包装成 LangChain tools，
    供 `create_agent(...)` 创建出来的节点级 Agent 自主决定何时检索、读图、
    或执行轻量分析。
    """

    config: PaperAgentConfig
    repository: PaperRepository

    def retrieve_paper_chunks(self, query: str, paper_ids: list[str], top_k: int | None = None) -> list[RetrievedChunk]:
        return self.repository.retrieve_chunks(query=query, paper_ids=paper_ids, top_k=top_k)

    def read_figure_by_id(self, paper_id: str, figure_id: int) -> FigureAsset | None:
        return self.repository.get_figure(paper_id=paper_id, img_id=figure_id)

    def compare_papers(self, query: str, paper_ids: list[str], top_k_per_paper: int = 2) -> dict[str, list[RetrievedChunk]]:
        return self.repository.compare_papers(query=query, paper_ids=paper_ids, top_k_per_paper=top_k_per_paper)

    def run_python_stats(self, text: str) -> ToolCallRecord:
        if not self.config.enable_python_tool:
            return ToolCallRecord(
                tool_name="run_python_stats",
                status="skipped",
                summary="Python analysis is disabled by configuration.",
            )

        numbers = [float(match) for match in NUMBER_RE.findall(text)]
        if not numbers:
            return ToolCallRecord(
                tool_name="run_python_stats",
                status="skipped",
                summary="No numeric values were found in the available evidence.",
            )

        payload = {
            "count": len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "mean": statistics.fmean(numbers),
        }
        summary = (
            f"Parsed {payload['count']} numeric values "
            f"(min={payload['min']:.4g}, max={payload['max']:.4g}, mean={payload['mean']:.4g})."
        )
        return ToolCallRecord(
            tool_name="run_python_stats",
            status="ok",
            summary=summary,
            payload=payload,
        )

    def search_web(self, query: str) -> ToolCallRecord:
        if not self.config.enable_web_search:
            return ToolCallRecord(
                tool_name="search_web",
                status="skipped",
                summary="Web search is disabled. Configure a search provider before enabling this tool.",
                payload={"query": query},
            )

        return ToolCallRecord(
            tool_name="search_web",
            status="skipped",
            summary="Web search capability is scaffolded but no provider adapter is configured yet.",
            payload={"query": query},
        )

    def retrieve_paper_chunks_tool(self, query: str, paper_ids: list[str], top_k: int | None = None) -> dict[str, Any]:
        """给 LangChain 工具调用使用的可序列化包装器。"""
        chunks = self.retrieve_paper_chunks(query=query, paper_ids=paper_ids, top_k=top_k)
        return {
            "query": query,
            "paper_ids": paper_ids,
            "chunks": [chunk.model_dump() for chunk in chunks],
        }

    def read_figure_by_id_tool(self, paper_id: str, figure_id: int) -> dict[str, Any] | None:
        """给 LangChain 工具调用使用的可序列化包装器。"""
        figure = self.read_figure_by_id(paper_id=paper_id, figure_id=figure_id)
        return None if figure is None else figure.model_dump()

    def compare_papers_tool(self, query: str, paper_ids: list[str], top_k_per_paper: int = 2) -> dict[str, Any]:
        """给 LangChain 工具调用使用的可序列化包装器。"""
        comparison = self.compare_papers(query=query, paper_ids=paper_ids, top_k_per_paper=top_k_per_paper)
        return {
            paper_id: [chunk.model_dump() for chunk in chunks]
            for paper_id, chunks in comparison.items()
        }

    def run_python_stats_tool(self, text: str) -> dict[str, Any]:
        """给 LangChain 工具调用使用的可序列化包装器。"""
        return self.run_python_stats(text).model_dump()

    def search_web_tool(self, query: str) -> dict[str, Any]:
        """给 LangChain 工具调用使用的可序列化包装器。"""
        return self.search_web(query).model_dump()

    def to_langchain_tools(self) -> list[Any]:
        """导出给 `create_agent(...)` 使用的 LangChain tools。"""
        try:
            from langchain_core.tools import StructuredTool
        except Exception:
            return []

        return [
            StructuredTool.from_function(
                func=self.retrieve_paper_chunks_tool,
                name="retrieve_paper_chunks",
                description="Retrieve the most relevant markdown chunks for one or more paper ids.",
            ),
            StructuredTool.from_function(
                func=self.read_figure_by_id_tool,
                name="read_figure_by_id",
                description="Read one figure asset by integer image id for a specific paper.",
            ),
            StructuredTool.from_function(
                func=self.compare_papers_tool,
                name="compare_papers",
                description="Retrieve supporting chunks for each paper in a comparison question.",
            ),
            StructuredTool.from_function(
                func=self.run_python_stats_tool,
                name="run_python_stats",
                description="Extract numeric values from text and compute simple descriptive statistics.",
            ),
            StructuredTool.from_function(
                func=self.search_web_tool,
                name="search_web",
                description="Search the web using an external provider when configured.",
            ),
        ]
