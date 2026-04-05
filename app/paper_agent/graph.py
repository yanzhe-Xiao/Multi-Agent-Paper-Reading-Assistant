from __future__ import annotations

from .config import PaperAgentConfig
from .llm import LLMClient
from .nodes import PaperAgentNodes
from .repository import PaperRepository
from .state import PaperAgentState
from .tools import PaperToolkit


def build_checkpointer(config: PaperAgentConfig):
    """构建会话级 checkpointer。

    默认回退到内存版；如果配置了 MySQL 连接串，则优先尝试 MySQL saver。
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except Exception:
        return None

    if not config.checkpointer_uri:
        return MemorySaver()

    try:
        from importlib import import_module

        module = import_module("langgraph.checkpoint.mysql")
        for class_name in ("PyMySQLSaver", "AsyncMySQLSaver", "AsyncPyMySQLSaver"):
            saver_cls = getattr(module, class_name, None)
            if saver_cls is not None and hasattr(saver_cls, "from_conn_string"):
                return saver_cls.from_conn_string(config.checkpointer_uri)
    except Exception:
        return MemorySaver()

    return MemorySaver()


def build_graph(config: PaperAgentConfig | None = None):
    """构建论文阅读 Agent 的主图。

    这里的设计是：
    - `LangGraph` 负责宏观编排
    - `create_agent(...)` 负责节点内部的工具调用与推理
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:
        raise RuntimeError(
            "LangGraph is not installed. Install the project requirements before running the paper agent."
        ) from exc

    config = config or PaperAgentConfig.from_env()
    repository = PaperRepository(config)
    toolkit = PaperToolkit(config=config, repository=repository)
    nodes = PaperAgentNodes(
        config=config,
        repository=repository,
        toolkit=toolkit,
        llm=LLMClient(config),
    )

    # 主图负责表达论文助手的显式状态流转。
    graph = StateGraph(PaperAgentState)
    graph.add_node("initialize", nodes.initialize)
    graph.add_node("planner", nodes.planner)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("vision", nodes.vision)
    graph.add_node("python", nodes.python)
    graph.add_node("web", nodes.web)
    graph.add_node("review_input", nodes.review_input)
    graph.add_node("methodology_review", nodes.methodology_review)
    graph.add_node("experiment_review", nodes.experiment_review)
    graph.add_node("critical_review", nodes.critical_review)
    graph.add_node("consensus", nodes.consensus)
    graph.add_node("draft", nodes.draft)
    graph.add_node("qa", nodes.qa)
    graph.add_node("rewrite", nodes.rewrite)
    graph.add_node("finalize", nodes.finalize)
    graph.add_node("compress_history", nodes.compress_history)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "planner")
    graph.add_conditional_edges(
        "planner",
        nodes.route_after_planner,
        {
            "retrieve": "retrieve",
            "vision": "vision",
            "python": "python",
            "web": "web",
            "review_input": "review_input",
            "draft": "draft",
        },
    )
    # 工具节点执行后回到 planner，由 planner 决定下一步。
    graph.add_edge("retrieve", "planner")
    graph.add_edge("vision", "planner")
    graph.add_edge("python", "planner")
    graph.add_edge("web", "planner")

    graph.add_edge("review_input", "methodology_review")
    graph.add_edge("review_input", "experiment_review")
    graph.add_edge("review_input", "critical_review")
    graph.add_edge("methodology_review", "consensus")
    graph.add_edge("experiment_review", "consensus")
    graph.add_edge("critical_review", "consensus")
    graph.add_edge("consensus", "planner")

    # 草稿生成后必须经过质量检查，必要时回流。
    graph.add_edge("draft", "qa")
    graph.add_conditional_edges(
        "qa",
        nodes.route_after_qa,
        {
            "planner": "planner",
            "rewrite": "rewrite",
            "finalize": "finalize",
        },
    )
    graph.add_edge("rewrite", "qa")
    graph.add_edge("finalize", "compress_history")
    graph.add_edge("compress_history", END)

    checkpointer = build_checkpointer(config)
    return graph.compile(checkpointer=checkpointer) if checkpointer is not None else graph.compile()
