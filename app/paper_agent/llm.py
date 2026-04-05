from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from .config import PaperAgentConfig


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMClient:
    """基于 `create_agent(...)` 的节点级 Agent 执行器。

    这里刻意分成两层：
    1. `LangGraph` 负责显式工作流编排和状态流转。
    2. `create_agent(...)` 负责节点内部的工具选择与推理。

    这样既保留了可控的宏观流程，也让单个节点具备真正的工具调用能力。
    """

    def __init__(self, config: PaperAgentConfig):
        self.config = config

    def is_available(self) -> bool:
        if not self.config.has_llm_config:
            return False
        try:
            from langchain_openai import ChatOpenAI  # noqa: F401
        except Exception:
            return False
        return True

    def invoke_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        *,
        tools: list | None = None,
        agent_name: str | None = None,
    ) -> SchemaT | None:
        if not self.is_available():
            return None

        try:
            from langchain.agents import create_agent
            from langchain.agents.structured_output import ToolStrategy
            from langchain_openai import ChatOpenAI
        except Exception:
            return None

        llm = self._build_model(ChatOpenAI)
        try:
            response_format = ToolStrategy(schema) if tools else schema
            agent = create_agent(
                model=llm,
                tools=tools or [],
                system_prompt=system_prompt,
                response_format=response_format,
                name=agent_name,
            )
            result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
            structured = result.get("structured_response") if isinstance(result, dict) else None
            if isinstance(structured, schema):
                return structured
            if isinstance(structured, dict):
                return schema(**structured)
        except Exception:
            return None
        return None

    def invoke_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        tools: list | None = None,
        agent_name: str | None = None,
    ) -> str | None:
        if not self.is_available():
            return None

        try:
            from langchain.agents import create_agent
            from langchain_openai import ChatOpenAI
        except Exception:
            return None

        llm = self._build_model(ChatOpenAI)
        try:
            agent = create_agent(
                model=llm,
                tools=tools or [],
                system_prompt=system_prompt,
                name=agent_name,
            )
            result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
        except Exception:
            return None
        return self._extract_text_from_agent_result(result)

    def _build_model(self, chat_openai_cls):
        """创建节点级 Agent 复用的聊天模型实例。"""
        return chat_openai_cls(
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
        )

    def _extract_text_from_agent_result(self, result) -> str | None:
        """从 `create_agent(...).invoke(...)` 的结果中提取最终文本。"""
        if not isinstance(result, dict):
            return None

        messages = result.get("messages") or []
        for message in reversed(messages):
            message_type = getattr(message, "type", None)
            if message_type != "ai":
                continue

            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(str(block["text"]))
                return "\n".join(part for part in text_parts if part) or None

        return None
