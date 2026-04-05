from __future__ import annotations

"""工具层模块。

对外提供可被节点或 Agent 调用的工具函数，并负责与 LangChain Tool 进行适配。
"""

import json
import os
import re
import statistics
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import PaperAgentConfig
from .repository import PaperRepository
from .schemas import FigureAsset, RetrievedChunk, ToolCallRecord


NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_WEB_TOP_K = 5


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
        """检索论文相关文本块。"""
        return self.repository.retrieve_chunks(query=query, paper_ids=paper_ids, top_k=top_k)

    def read_figure_by_id(self, paper_id: str, figure_id: int) -> FigureAsset | None:
        """读取指定论文中的单个图表资源。"""
        return self.repository.get_figure(paper_id=paper_id, img_id=figure_id)

    def compare_papers(self, query: str, paper_ids: list[str], top_k_per_paper: int = 2) -> dict[str, list[RetrievedChunk]]:
        """在多篇论文上执行对比检索。"""
        return self.repository.compare_papers(query=query, paper_ids=paper_ids, top_k_per_paper=top_k_per_paper)

    def run_python_stats(self, text: str) -> ToolCallRecord:
        """提取文本中的数字并计算基础统计量。"""
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
        """执行联网检索（当前实现为 Tavily 适配器）。"""
        if not self.config.enable_web_search:
            return ToolCallRecord(
                tool_name="search_web",
                status="skipped",
                summary="Web search is disabled. Configure a search provider before enabling this tool.",
                payload={"query": query},
            )

        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            return ToolCallRecord(
                tool_name="search_web",
                status="skipped",
                summary="Web search is enabled, but TAVILY_API_KEY is missing.",
                payload={"query": query},
            )

        raw_top_k = os.getenv("PAPER_AGENT_WEB_TOP_K", str(DEFAULT_WEB_TOP_K))
        try:
            top_k = max(1, min(10, int(raw_top_k)))
        except ValueError:
            top_k = DEFAULT_WEB_TOP_K

        request_payload = {
            "api_key": tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": top_k,
            "include_answer": True,
            "include_raw_content": False,
        }

        try:
            request = Request(
                TAVILY_SEARCH_ENDPOINT,
                data=json.dumps(request_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                response_text = response.read().decode("utf-8")

            body = json.loads(response_text)
            results = []
            for item in body.get("results", []):
                results.append(
                    {
                        "title": str(item.get("title", "") or ""),
                        "url": str(item.get("url", "") or ""),
                        "content": str(item.get("content", "") or ""),
                        "score": item.get("score"),
                    }
                )

            answer = str(body.get("answer", "") or "")
            if not results and not answer:
                return ToolCallRecord(
                    tool_name="search_web",
                    status="skipped",
                    summary="Web search returned no usable results.",
                    payload={"query": query},
                )

            summary = f"Web search returned {len(results)} result(s)."
            if answer:
                summary += " Included synthesized answer from provider."

            return ToolCallRecord(
                tool_name="search_web",
                status="ok",
                summary=summary,
                payload={
                    "query": query,
                    "answer": answer,
                    "results": results,
                },
            )
        except HTTPError as exc:
            return ToolCallRecord(
                tool_name="search_web",
                status="error",
                summary=f"Web search HTTP error: {exc.code}",
                payload={"query": query, "error": str(exc)},
            )
        except URLError as exc:
            return ToolCallRecord(
                tool_name="search_web",
                status="error",
                summary="Web search network error.",
                payload={"query": query, "error": str(exc)},
            )
        except Exception as exc:
            return ToolCallRecord(
                tool_name="search_web",
                status="error",
                summary="Web search failed unexpectedly.",
                payload={"query": query, "error": f"{type(exc).__name__}: {exc}"},
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

        retrieve_desc = (
            "Purpose: Retrieve the most relevant markdown chunks from already parsed local papers.\n"
            "Required args: query (standalone retrieval query), paper_ids (list[str] of exact paper ids), optional top_k (int).\n"
            "CRITICAL paper_id rule: paper_ids MUST be the exact long id string(s) provided to this run (for example: "
            "3798ba97-6dfc-4e6c-850b-435869ef2959). Do NOT infer, guess, summarize, or generate paper ids from title/content.\n"
            "When to use: extracting equations, definitions, methods, experiments, and evidence from known paper ids.\n"
            "Do NOT use when paper_ids are unknown; first rely on the caller-provided ids in context.\n"
            "Return shape: {query, paper_ids, chunks:[{paper_id, chunk_id, content, source_path, score, title}]}.\n"
            "Good example args: {\"query\": \"List all equations and explain symbols\", "
            "\"paper_ids\": [\"3798ba97-6dfc-4e6c-850b-435869ef2959\"], \"top_k\": 6}.\n"
            "Bad example args: {\"query\": \"...\", \"paper_ids\": [\"Think Global, Act Local\"]}  # title is NOT a paper_id."
        )

        read_figure_desc = (
            "Purpose: Read one figure asset for a specific paper by integer figure id.\n"
            "Required args: paper_id (exact long id string from caller context), figure_id (integer).\n"
            "CRITICAL paper_id rule: paper_id is the caller-provided UUID-like string, not a title and not inferred from text.\n"
            "When to use: user asks about Fig./Figure N, image caption details, or visual evidence.\n"
            "Return shape: figure object dict, or null if not found.\n"
            "Good example args: {\"paper_id\": \"3798ba97-6dfc-4e6c-850b-435869ef2959\", \"figure_id\": 4}.\n"
            "Bad example args: {\"paper_id\": \"the VLN paper\", \"figure_id\": \"Fig.4\"}  # wrong id type and figure type."
        )

        compare_desc = (
            "Purpose: Retrieve supporting chunks per paper for side-by-side comparison tasks.\n"
            "Required args: query (explicit comparison objective), paper_ids (list of exact caller-provided ids), "
            "optional top_k_per_paper (int).\n"
            "CRITICAL paper_id rule: all ids must come from runtime context; never invent ids from titles or prior sessions.\n"
            "When to use: compare methods, losses, datasets, metrics, limitations across multiple known papers.\n"
            "Return shape: {paper_id_1:[chunks...], paper_id_2:[chunks...], ...}.\n"
            "Good example args: {\"query\": \"Compare training objectives and ablations\", "
            "\"paper_ids\": [\"idA\", \"idB\"], \"top_k_per_paper\": 3}."
        )

        python_stats_desc = (
            "Purpose: Extract numeric values from text and compute descriptive statistics (count/min/max/mean).\n"
            "Required args: text (string containing evidence snippets with numbers).\n"
            "When to use: quick quantitative summary from retrieved passages/tables/captions.\n"
            "Not for symbolic derivation or exact theorem proving; this is lightweight numeric parsing only.\n"
            "Return shape: ToolCallRecord dict with status in {ok, skipped, error} and payload stats when available.\n"
            "Good example args: {\"text\": \"SPL 52.3, SR 61.0, loss 0.84\"}."
        )

        web_desc = (
            "Purpose: Search external web sources via configured Tavily provider.\n"
            "Required args: query (self-contained web search statement with topic + objective + focus terms).\n"
            "When to use: latest/recent/external context not present in local paper chunks.\n"
            "Avoid using for paper-internal facts if local retrieve_paper_chunks already covers them.\n"
            "Operational notes: may return skipped if web search disabled or TAVILY_API_KEY missing.\n"
            "Return shape: ToolCallRecord dict; payload may include answer and results[{title,url,content,score}].\n"
            "Good example args: {\"query\": \"Latest 2025-2026 VLN dual-scale graph transformer advances and baselines\"}."
        )

        return [
            StructuredTool.from_function(
                func=self.retrieve_paper_chunks_tool,
                name="retrieve_paper_chunks",
                description=retrieve_desc,
            ),
            StructuredTool.from_function(
                func=self.read_figure_by_id_tool,
                name="read_figure_by_id",
                description=read_figure_desc,
            ),
            StructuredTool.from_function(
                func=self.compare_papers_tool,
                name="compare_papers",
                description=compare_desc,
            ),
            StructuredTool.from_function(
                func=self.run_python_stats_tool,
                name="run_python_stats",
                description=python_stats_desc,
            ),
            StructuredTool.from_function(
                func=self.search_web_tool,
                name="search_web",
                description=web_desc,
            ),
        ]
