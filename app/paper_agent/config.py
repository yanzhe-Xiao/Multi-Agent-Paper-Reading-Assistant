"""
配置管理模块
定义PaperAgent的系统配置，支持从环境变量加载
使用dataclass提供类型安全的配置对象
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PaperAgentConfig:
    """
    论文阅读Agent配置类
    
    包含LLM模型、检索参数、文档路径等所有可配置项
    使用slots优化内存占用
    """
    
    # LLM模型配置
    model: str = "gpt-4.1-mini"  # 使用的模型名称
    api_key: str | None = None  # API密钥
    base_url: str | None = None  # API基础URL（用于自定义端点）
    temperature: float = 0.1  # 生成温度（越低越确定）
    model_request_timeout_seconds: float = 60.0  # 单次模型请求超时时间（秒）
    model_retry_max_retries: int = 3  # 模型请求失败后的重试次数（不含首次请求）
    model_retry_initial_delay_seconds: float = 1.0  # 首次重试前等待时间（秒）
    model_retry_backoff_factor: float = 2.0  # 指数退避因子
    model_retry_max_delay_seconds: float = 15.0  # 重试等待的最大间隔（秒）
    model_retry_timeout_only: bool = True  # 是否仅在超时类错误时重试
    
    # 工作流控制参数
    max_model_calls: int = 24  # 单次请求允许的最大模型调用次数（节点级）
    
    # 文本检索参数
    retrieval_top_k: int = 4  # 每次检索返回的最相关文本块数量
    chunk_size: int = 1600  # 文本分块大小（字符数）
    chunk_overlap: int = 200  # 文本分块重叠大小（避免信息丢失）
    
    # 文档存储路径
    docs_root: Path | None = None  # 论文文档根目录
    
    # LangGraph检查点配置（用于状态持久化）
    checkpointer_uri: str | None = None
    
    # 功能开关
    enable_web_search: bool = False  # 是否启用网络搜索
    enable_python_tool: bool = True  # 是否启用Python代码执行工具
    
    # 消息历史管理
    keep_recent_messages: int = 4  # 保留的最近消息数量（用于上下文压缩）

    # 调试与可观测性
    verbose_progress: bool = False  # 是否打印中间节点进度

    @classmethod
    def from_env(cls) -> "PaperAgentConfig":
        """
        从环境变量创建配置对象
        
        优先级：环境变量 > 默认值
        支持的环境变量：
        - OPENAI_MODEL: 模型名称
        - OPENAI_API_KEY: API密钥
        - OPENAI_BASE_URL: API基础URL
        - PAPER_DOCS_ROOT: 文档根目录
        - PAPER_AGENT_TEMPERATURE: 温度参数
        - PAPER_AGENT_MODEL_TIMEOUT_SECONDS: 单次模型请求超时（秒）
        - PAPER_AGENT_MODEL_RETRY_MAX_RETRIES: 模型请求最大重试次数
        - PAPER_AGENT_MODEL_RETRY_INITIAL_DELAY_SECONDS: 首次重试前等待（秒）
        - PAPER_AGENT_MODEL_RETRY_BACKOFF_FACTOR: 重试指数退避因子
        - PAPER_AGENT_MODEL_RETRY_MAX_DELAY_SECONDS: 重试最大等待（秒）
        - PAPER_AGENT_MODEL_RETRY_TIMEOUT_ONLY: 是否仅超时时重试（true/false）
        - PAPER_AGENT_MAX_MODEL_CALLS: 单次请求模型调用上限
        - PAPER_AGENT_TOP_K: 检索top_k
        - PAPER_AGENT_CHUNK_SIZE: 分块大小
        - PAPER_AGENT_CHUNK_OVERLAP: 分块重叠
        - PAPER_AGENT_KEEP_RECENT_MESSAGES: 保留消息数
        - PAPER_AGENT_VERBOSE_PROGRESS: 是否打印中间进度（true/false）
        - LANGGRAPH_CHECKPOINTER_URI: 检查点URI
        - PAPER_AGENT_ENABLE_WEB: 启用网络搜索
        - TAVILY_API_KEY: Tavily 搜索 API Key（由 search_web 工具读取）
        - PAPER_AGENT_WEB_TOP_K: 联网搜索返回结果条数（1-10）
        - PAPER_AGENT_ENABLE_PYTHON: 启用Python工具
        
        Returns:
            从环境变量加载的配置对象
        """
        docs_root = os.getenv("PAPER_DOCS_ROOT")
        raw_temperature = os.getenv("PAPER_AGENT_TEMPERATURE")
        raw_model_timeout_seconds = os.getenv("PAPER_AGENT_MODEL_TIMEOUT_SECONDS")
        raw_model_retry_max_retries = os.getenv("PAPER_AGENT_MODEL_RETRY_MAX_RETRIES")
        raw_model_retry_initial_delay_seconds = os.getenv("PAPER_AGENT_MODEL_RETRY_INITIAL_DELAY_SECONDS")
        raw_model_retry_backoff_factor = os.getenv("PAPER_AGENT_MODEL_RETRY_BACKOFF_FACTOR")
        raw_model_retry_max_delay_seconds = os.getenv("PAPER_AGENT_MODEL_RETRY_MAX_DELAY_SECONDS")
        raw_max_model_calls = os.getenv("PAPER_AGENT_MAX_MODEL_CALLS")
        raw_top_k = os.getenv("PAPER_AGENT_TOP_K")
        raw_chunk_size = os.getenv("PAPER_AGENT_CHUNK_SIZE")
        raw_chunk_overlap = os.getenv("PAPER_AGENT_CHUNK_OVERLAP")
        raw_keep_recent = os.getenv("PAPER_AGENT_KEEP_RECENT_MESSAGES")

        return cls(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=float(raw_temperature or 0.1),
            model_request_timeout_seconds=max(1.0, float(raw_model_timeout_seconds or 60.0)),
            model_retry_max_retries=max(0, int(raw_model_retry_max_retries or 3)),
            model_retry_initial_delay_seconds=max(0.0, float(raw_model_retry_initial_delay_seconds or 1.0)),
            model_retry_backoff_factor=max(0.0, float(raw_model_retry_backoff_factor or 2.0)),
            model_retry_max_delay_seconds=max(0.0, float(raw_model_retry_max_delay_seconds or 15.0)),
            model_retry_timeout_only=os.getenv("PAPER_AGENT_MODEL_RETRY_TIMEOUT_ONLY", "true").lower() == "true",
            max_model_calls=max(1, int(raw_max_model_calls or 24)),
            retrieval_top_k=int(raw_top_k or 4),
            chunk_size=int(raw_chunk_size or 1600),
            chunk_overlap=int(raw_chunk_overlap or 200),
            docs_root=Path(docs_root).resolve() if docs_root else None,
            checkpointer_uri=os.getenv("LANGGRAPH_CHECKPOINTER_URI"),
            enable_web_search=os.getenv("PAPER_AGENT_ENABLE_WEB", "false").lower() == "true",
            enable_python_tool=os.getenv("PAPER_AGENT_ENABLE_PYTHON", "true").lower() == "true",
            keep_recent_messages=int(raw_keep_recent or 4),
            verbose_progress=os.getenv("PAPER_AGENT_VERBOSE_PROGRESS", "false").lower() == "true",
        )

    @property
    def has_llm_config(self) -> bool:
        """
        检查是否配置了有效的LLM API密钥
        
        Returns:
            True如果已配置API密钥，否则False
        """
        return bool(self.api_key)