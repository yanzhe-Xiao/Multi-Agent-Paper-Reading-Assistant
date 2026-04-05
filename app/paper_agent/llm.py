from __future__ import annotations

from langchain_openrouter import ChatOpenRouter

"""LLM 调用封装模块。

该模块负责为各节点提供统一的模型调用接口，并在失败时返回可追踪错误信息。
"""

import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from .config import PaperAgentConfig


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ModelRetryExhaustedError(RuntimeError):
    """模型请求超时且重试耗尽时抛出，用于上层结束当前会话。"""


class LLMClient:
    """基于 `create_agent(...)` 的节点级 Agent 执行器。

    这里刻意分成两层：
    1. `LangGraph` 负责显式工作流编排和状态流转。
    2. `create_agent(...)` 负责节点内部的工具选择与推理。

    这样既保留了可控的宏观流程，也让单个节点具备真正的工具调用能力。
    """

    def __init__(self, config: PaperAgentConfig):
        self.config = config
        self.last_error: str | None = None
        self.model_call_count: int = 0
        self.max_model_calls: int = max(1, config.max_model_calls)
        self.budget_exhausted: bool = False

        # 缓存并复用中间件，避免每次调用都重新构造。
        self._timeout_error_types_cache: tuple[type[BaseException], ...] | None = None
        self._agent_middleware = self._build_agent_middleware()

    def reset_call_budget(self, max_model_calls: int | None = None) -> None:
        """重置单次请求的模型调用预算。"""
        self.model_call_count = 0
        self.budget_exhausted = False
        if max_model_calls is not None:
            self.max_model_calls = max(1, int(max_model_calls))

    def get_call_stats(self) -> tuple[int, int]:
        """返回 (已调用次数, 预算上限)。"""
        return self.model_call_count, self.max_model_calls

    def is_budget_exhausted(self) -> bool:
        """当前请求是否触发过预算耗尽。"""
        return self.budget_exhausted

    def _consume_budget(self) -> bool:
        """消费一次模型调用预算；若超限则返回 False。"""
        if self.model_call_count >= self.max_model_calls:
            self.budget_exhausted = True
            self.last_error = (
                f"Model call budget exceeded: {self.model_call_count}/{self.max_model_calls}. "
                "Please reduce workflow complexity or increase PAPER_AGENT_MAX_MODEL_CALLS."
            )
            return False
        self.model_call_count += 1
        return True

    def is_available(self) -> bool:
        """检查当前 LLM 依赖与配置是否可用。"""
        if not self.config.has_llm_config:
            self.last_error = "OPENAI_API_KEY is not configured."
            return False
        try:
            from langchain_openai import ChatOpenAI  # noqa: F401
        except Exception as exc:
            self.last_error = f"Failed to import ChatOpenAI: {type(exc).__name__}: {exc}"
            return False
        self.last_error = None
        return True

    def consume_last_error(self) -> str | None:
        """读取并清空最近一次错误，避免重复消费同一错误。"""
        error = self.last_error
        self.last_error = None
        return error

    def _build_agent_middleware(self) -> list:
        """构建模型调用中间件（用于超时自动重发）。"""
        retry_count = max(0, int(self.config.model_retry_max_retries))
        if retry_count <= 0:
            return []

        built_in = self._build_builtin_model_retry_middleware(retry_count)
        if built_in is not None:
            return [built_in]

        custom = self._build_custom_model_retry_middleware(retry_count)
        return [custom] if custom is not None else []

    def _build_builtin_model_retry_middleware(self, retry_count: int):
        """优先使用 LangChain 内置 `ModelRetryMiddleware`。"""
        try:
            from langchain.agents.middleware import ModelRetryMiddleware
        except Exception:
            return None

        retry_on = self._should_retry_model_error if self.config.model_retry_timeout_only else (Exception,)
        return ModelRetryMiddleware(
            max_retries=retry_count,
            retry_on=retry_on,
            on_failure="error",
            backoff_factor=max(0.0, float(self.config.model_retry_backoff_factor)),
            initial_delay=max(0.0, float(self.config.model_retry_initial_delay_seconds)),
            max_delay=max(0.0, float(self.config.model_retry_max_delay_seconds)),
            jitter=False,
        )

    def _build_custom_model_retry_middleware(self, retry_count: int):
        """内置中间件不可用时，退回自定义 `wrap_model_call` 重试逻辑。"""
        try:
            from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
        except Exception:
            return None

        @wrap_model_call
        def retry_model_call(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
            last_error: Exception | None = None

            for attempt in range(retry_count + 1):
                try:
                    return handler(request)
                except Exception as exc:  # noqa: PERF203
                    last_error = exc
                    should_retry = (not self.config.model_retry_timeout_only) or self._should_retry_model_error(exc)
                    if (not should_retry) or attempt >= retry_count:
                        raise

                    self._emit_retry_progress(attempt + 1, retry_count, exc)
                    delay_seconds = self._compute_retry_delay_seconds(attempt)
                    if delay_seconds > 0:
                        time.sleep(delay_seconds)

            if last_error is not None:
                raise last_error
            raise RuntimeError("Unexpected retry middleware state: no response and no exception.")

        return retry_model_call

    def _compute_retry_delay_seconds(self, attempt: int) -> float:
        """计算当前重试轮次的等待时间。"""
        base_delay = max(0.0, float(self.config.model_retry_initial_delay_seconds))
        max_delay = max(0.0, float(self.config.model_retry_max_delay_seconds))
        backoff_factor = max(0.0, float(self.config.model_retry_backoff_factor))

        if backoff_factor == 0.0:
            delay = base_delay
        else:
            delay = base_delay * (backoff_factor**attempt)

        if max_delay > 0.0:
            delay = min(delay, max_delay)
        return max(0.0, delay)

    def _emit_retry_progress(self, retry_index: int, retry_limit: int, error: Exception) -> None:
        """在 verbose 模式下打印重试进度。"""
        if not self.config.verbose_progress:
            return

        message = str(error).replace("\n", " ").strip()
        if len(message) > 180:
            message = message[:177] + "..."
        print(
            f"[paper-agent][llm-retry] retry={retry_index}/{retry_limit} "
            f"error={type(error).__name__}: {message}",
            flush=True,
        )

    def _timeout_error_types(self) -> tuple[type[BaseException], ...]:
        """收集可识别为“请求超时/长时间无响应”的异常类型。"""
        if self._timeout_error_types_cache is not None:
            return self._timeout_error_types_cache

        timeout_types: list[type[BaseException]] = [TimeoutError]
        candidates = (
            ("httpx", "TimeoutException"),
            ("httpx", "ReadTimeout"),
            ("httpx", "ConnectTimeout"),
            ("httpcore", "TimeoutException"),
            ("openai", "APITimeoutError"),
            ("openai", "APIConnectionError"),
        )

        for module_name, type_name in candidates:
            try:
                module = __import__(module_name, fromlist=[type_name])
                candidate_type = getattr(module, type_name, None)
            except Exception:
                continue

            if isinstance(candidate_type, type) and issubclass(candidate_type, BaseException):
                timeout_types.append(candidate_type)

        deduplicated: list[type[BaseException]] = []
        for error_type in timeout_types:
            if error_type not in deduplicated:
                deduplicated.append(error_type)

        self._timeout_error_types_cache = tuple(deduplicated)
        return self._timeout_error_types_cache

    def _should_retry_model_error(self, error: Exception) -> bool:
        """判断当前异常是否属于“超时/长时间无响应”并应触发重试。"""
        if isinstance(error, self._timeout_error_types()):
            return True

        lowered = str(error).lower()
        non_timeout_hints = (
            "unexpected keyword argument 'timeout'",
            'unexpected keyword argument "timeout"',
            "invalid timeout parameter",
            "timeout must be",
        )
        if any(hint in lowered for hint in non_timeout_hints):
            return False

        timeout_signals = (
            "timed out",
            "read timeout",
            "connect timeout",
            "request timeout",
            "operation timed out",
            "deadline exceeded",
            "gateway timeout",
            "504 gateway",
            "status code: 504",
        )
        return any(signal in lowered for signal in timeout_signals)

    def _build_retry_exhausted_message(self, *, error: Exception | None = None, elapsed_seconds: float | None = None) -> str:
        """构建超时重试耗尽的用户可读错误信息。"""
        timeout_seconds = int(max(1.0, float(self.config.model_request_timeout_seconds)))
        retry_count = max(0, int(self.config.model_retry_max_retries))
        message_parts = [
            (
                "Model request encountered timeout-like failures "
                f"(configured per-attempt timeout={timeout_seconds}s) and failed after {retry_count} retry attempts."
            )
        ]

        if elapsed_seconds is not None:
            message_parts.append(f"Observed elapsed time before termination: {max(0.0, elapsed_seconds):.1f}s.")

        if error is not None:
            raw = str(error).replace("\n", " ").strip()
            compact = raw if len(raw) <= 220 else (raw[:217] + "...")
            message_parts.append(f"Last error: {type(error).__name__}: {compact}")

        message_parts.append("Session should be terminated and user notified.")
        return " ".join(message_parts)

    def _create_agent(self, create_agent_fn, **kwargs):
        """创建 agent，并兼容老版本不支持 middleware 参数的情况。"""
        if self._agent_middleware:
            kwargs["middleware"] = self._agent_middleware

        try:
            return create_agent_fn(**kwargs)
        except TypeError as exc:
            if "middleware" not in kwargs:
                raise
            # 兼容：较早版本 create_agent 可能尚不支持 middleware 参数
            kwargs.pop("middleware", None)
            if self.config.verbose_progress:
                print(
                    f"[paper-agent][llm-retry] Middleware unavailable in current create_agent signature: {exc}",
                    flush=True,
                )
            return create_agent_fn(**kwargs)

    def invoke_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        *,
        tools: list | None = None,
        agent_name: str | None = None,
    ) -> SchemaT | None:
        """调用结构化输出 Agent，并返回 Pydantic 模型实例。"""
        if not self.is_available():
            return None
        if not self._consume_budget():
            return None

        try:
            from langchain.agents import create_agent
            from langchain.agents.structured_output import ToolStrategy
            from langchain_openai import ChatOpenAI
        except Exception as exc:
            self.last_error = f"Failed to import LangChain agent components: {type(exc).__name__}: {exc}"
            return None

        llm = self._build_model(ChatOpenAI)
        invoke_start = time.monotonic()
        try:
            response_format = ToolStrategy(schema) if tools else schema
            agent = self._create_agent(
                create_agent,
                model=llm,
                tools=tools or [],
                system_prompt=system_prompt,
                response_format=response_format,
                name=agent_name,
            )
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_prompt}]},
                config={"recursion_limit": max(8, self.max_model_calls * 4)},
            )
            structured = result.get("structured_response") if isinstance(result, dict) else None
            if isinstance(structured, schema):
                self.last_error = None
                return structured
            if isinstance(structured, dict):
                self.last_error = None
                return schema(**structured)
            self.last_error = "Agent invocation finished but did not return a structured_response payload."
        except Exception as exc:
            if self._should_retry_model_error(exc):
                elapsed = time.monotonic() - invoke_start
                self.last_error = self._build_retry_exhausted_message(error=exc, elapsed_seconds=elapsed)
                raise ModelRetryExhaustedError(self.last_error) from exc
            self.last_error = f"Structured agent invocation failed: {type(exc).__name__}: {exc}"
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
        """调用文本输出 Agent，并抽取最终 AI 文本。"""
        if not self.is_available():
            return None
        if not self._consume_budget():
            return None

        try:
            from langchain.agents import create_agent
            from langchain_openai import ChatOpenAI
        except Exception as exc:
            self.last_error = f"Failed to import LangChain agent components: {type(exc).__name__}: {exc}"
            return None

        llm = self._build_model(ChatOpenAI)
        invoke_start = time.monotonic()
        try:
            agent = self._create_agent(
                create_agent,
                model=llm,
                tools=tools or [],
                system_prompt=system_prompt,
                name=agent_name,
            )
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_prompt}]},
                config={"recursion_limit": max(8, self.max_model_calls * 4)},
            )
        except Exception as exc:
            if self._should_retry_model_error(exc):
                elapsed = time.monotonic() - invoke_start
                self.last_error = self._build_retry_exhausted_message(error=exc, elapsed_seconds=elapsed)
                raise ModelRetryExhaustedError(self.last_error) from exc
            self.last_error = f"Text agent invocation failed: {type(exc).__name__}: {exc}"
            return None

        text = self._extract_text_from_agent_result(result)
        if text is None:
            self.last_error = "Agent invocation finished but no AI text message was found."
            return None
        self.last_error = None
        return text

    def _build_model(self, chat_openai_cls):
        """创建节点级 Agent 复用的聊天模型实例。"""
        timeout_seconds = max(1.0, float(self.config.model_request_timeout_seconds))
        kwargs = {
            "model": self.config.model,
            "api_key": self.config.api_key,
            "base_url": self.config.base_url,
            "temperature": self.config.temperature,
            # 1) timeout 保证“超过 N 秒无响应”能抛错
            "timeout": timeout_seconds,
            # 2) 关闭 SDK 内部重试，统一交给 middleware 控制
            "max_retries": 0,
        }

        # 优先使用 timeout 参数；老版本兼容 request_timeout。
        try:
            return chat_openai_cls(**kwargs)
        except TypeError:
            fallback_kwargs = dict(kwargs)
            timeout_value = fallback_kwargs.pop("timeout")
            fallback_kwargs["request_timeout"] = timeout_value
            try:
                return chat_openai_cls(**fallback_kwargs)
            except TypeError:
                # 极端兼容：若不支持 max_retries，则移除后重试。
                fallback_kwargs.pop("max_retries", None)
                return chat_openai_cls(**fallback_kwargs)

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
