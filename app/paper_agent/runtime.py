from __future__ import annotations

from .config import PaperAgentConfig
from .llm import LLMClient
from .nodes import PaperAgentNodes
from .repository import PaperRepository
from .schemas import AgentResponse, PaperInput
from .tools import PaperToolkit


class PaperAssistant:
    def __init__(self, config: PaperAgentConfig | None = None):
        self.config = config or PaperAgentConfig.from_env()
        self.repository = PaperRepository(self.config)
        self._graph = None

    def available_papers(self) -> list[str]:
        return self.repository.list_paper_ids()

    def build(self):
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
        paper_ids = paper_ids or self.available_papers()
        paper_inputs = [
            PaperInput(paper_id=paper_id, title=self.repository.load_paper_title(paper_id))
            for paper_id in paper_ids
        ]
        graph = self.build()
        result = graph.invoke(
            {
                "user_query": user_query,
                "paper_inputs": paper_inputs,
                "user_preferences": user_preferences or {},
            },
            config={"configurable": {"thread_id": thread_id}},
        )

        helper = PaperAgentNodes(
            config=self.config,
            repository=self.repository,
            toolkit=PaperToolkit(config=self.config, repository=self.repository),
            llm=LLMClient(self.config),
        )
        return helper.build_response(result)
