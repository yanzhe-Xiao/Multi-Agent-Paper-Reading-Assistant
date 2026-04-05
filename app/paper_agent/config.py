from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PaperAgentConfig:
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    max_iterations: int = 6
    retrieval_top_k: int = 4
    chunk_size: int = 1600
    chunk_overlap: int = 200
    docs_root: Path | None = None
    checkpointer_uri: str | None = None
    enable_web_search: bool = False
    enable_python_tool: bool = True
    keep_recent_messages: int = 4

    @classmethod
    def from_env(cls) -> "PaperAgentConfig":
        docs_root = os.getenv("PAPER_DOCS_ROOT")
        raw_temperature = os.getenv("PAPER_AGENT_TEMPERATURE")
        raw_max_iterations = os.getenv("PAPER_AGENT_MAX_ITERATIONS")
        raw_top_k = os.getenv("PAPER_AGENT_TOP_K")
        raw_chunk_size = os.getenv("PAPER_AGENT_CHUNK_SIZE")
        raw_chunk_overlap = os.getenv("PAPER_AGENT_CHUNK_OVERLAP")
        raw_keep_recent = os.getenv("PAPER_AGENT_KEEP_RECENT_MESSAGES")

        return cls(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=float(raw_temperature or 0.1),
            max_iterations=int(raw_max_iterations or 6),
            retrieval_top_k=int(raw_top_k or 4),
            chunk_size=int(raw_chunk_size or 1600),
            chunk_overlap=int(raw_chunk_overlap or 200),
            docs_root=Path(docs_root).resolve() if docs_root else None,
            checkpointer_uri=os.getenv("LANGGRAPH_CHECKPOINTER_URI"),
            enable_web_search=os.getenv("PAPER_AGENT_ENABLE_WEB", "false").lower() == "true",
            enable_python_tool=os.getenv("PAPER_AGENT_ENABLE_PYTHON", "true").lower() == "true",
            keep_recent_messages=int(raw_keep_recent or 4),
        )

    @property
    def has_llm_config(self) -> bool:
        return bool(self.api_key)
