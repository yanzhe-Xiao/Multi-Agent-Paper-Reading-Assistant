from __future__ import annotations

"""运行时封装模块。

对外提供 `PaperAssistant` 统一入口，屏蔽图构建与状态转换细节。
"""

from .config import PaperAgentConfig
from .llm import LLMClient, ModelRetryExhaustedError
from .nodes import PaperAgentNodes
from .repository import PaperRepository
from .schemas import AgentResponse, PaperInput, ToolCallRecord
from .tools import PaperToolkit


class PaperAssistant:
    """论文阅读助手运行时对象。"""

    def __init__(self, config: PaperAgentConfig | None = None):
        """初始化运行时依赖（配置、仓库、图缓存）。"""
        self.config = config or PaperAgentConfig.from_env()
        self.repository = PaperRepository(self.config)
        self._graph = None

    def available_papers(self) -> list[str]:
        """列出当前可用的论文 ID。"""
        return self.repository.list_paper_ids()

    def build(self):
        """延迟构建并缓存 LangGraph 工作流。"""
        if self._graph is None:
            from .graph import build_graph

            self._graph = build_graph(self.config)
        return self._graph

    def invoke(
        self,
        user_query: str,
        paper_ids: list[str] | None = None,
        thread_id: str = "default-thread",
        user_preferences: dict | None = None,
    ) -> AgentResponse:
        """执行一次问答请求并返回结构化响应对象。"""
        resolved_paper_ids = self._resolve_paper_ids(paper_ids)
        paper_inputs = [
            PaperInput(paper_id=paper_id, title=self.repository.load_paper_title(paper_id))
            for paper_id in resolved_paper_ids
        ]
        graph = self.build()
        try:
            result = graph.invoke(
                {
                    "user_query": user_query,
                    "paper_inputs": paper_inputs,
                    "user_preferences": user_preferences or {},
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        except ModelRetryExhaustedError as exc:
            timeout_seconds = int(max(1.0, float(self.config.model_request_timeout_seconds)))
            retry_count = max(0, int(self.config.model_retry_max_retries))
            fail_message = (
                f"抱歉，模型请求触发了超时类错误（单次超时配置 {timeout_seconds} 秒），已重试 {retry_count} 次仍失败。"
                "本次会话已自动结束，请稍后重试。"
            )
            return AgentResponse(
                final_answer=fail_message,
                quality_score=0.0,
                tool_results={
                    "session_timeout_failure": ToolCallRecord(
                        tool_name="session_timeout_failure",
                        status="error",
                        summary="Model timeout retries exhausted; session terminated.",
                        payload={
                            "thread_id": thread_id,
                            "timeout_seconds": timeout_seconds,
                            "retry_count": retry_count,
                            "error": str(exc),
                        },
                    )
                },
                review_notes={},
            )

        helper = PaperAgentNodes(
            config=self.config,
            repository=self.repository,
            toolkit=PaperToolkit(config=self.config, repository=self.repository),
            llm=LLMClient(self.config),
        )
        return helper.build_response(result)

    def _resolve_paper_ids(self, paper_ids: list[str] | None) -> list[str]:
        """解析本轮生效的论文范围。"""
        if paper_ids:
            return paper_ids

        available = self.available_papers()
        if not available:
            raise ValueError("No parsed papers were found. Please upload or parse at least one paper first.")

        if len(available) == 1:
            return available

        raise ValueError(
            "Multiple papers are available. Please pass `paper_ids` explicitly, "
            "or opt in to all papers from the caller."
        )
