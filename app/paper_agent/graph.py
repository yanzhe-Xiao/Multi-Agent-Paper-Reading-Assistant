"""
LangGraph工作流编排模块
构建论文阅读Agent的主图，定义节点和执行流程
负责宏观状态流转控制
"""
from __future__ import annotations

import atexit

from .config import PaperAgentConfig
from .llm import LLMClient
from .nodes import PaperAgentNodes
from .repository import PaperRepository
from .state import PaperAgentState
from .tools import PaperToolkit


_CHECKPOINTER_CONTEXT_MANAGERS: list[object] = []
_CHECKPOINTER_CLEANUP_REGISTERED = False


def _register_checkpointer_context_manager(context_manager: object) -> None:
    """注册 checkpointer 上下文管理器，确保进程退出时释放连接资源。"""
    global _CHECKPOINTER_CLEANUP_REGISTERED
    _CHECKPOINTER_CONTEXT_MANAGERS.append(context_manager)

    if _CHECKPOINTER_CLEANUP_REGISTERED:
        return

    def _cleanup() -> None:
        while _CHECKPOINTER_CONTEXT_MANAGERS:
            manager = _CHECKPOINTER_CONTEXT_MANAGERS.pop()
            try:
                manager.__exit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                # 关闭失败不影响进程退出
                pass

    atexit.register(_cleanup)
    _CHECKPOINTER_CLEANUP_REGISTERED = True


def build_checkpointer(config: PaperAgentConfig):
    """
    构建会话级检查点器（用于状态持久化）
    
    默认使用内存版检查点器；如果配置了MySQL连接串，则优先尝试MySQL检查点器。
    支持断点续传和状态恢复功能。
    
    Args:
        config: Agent配置对象
    
    Returns:
        检查点器实例（MemorySaver或MySQL Saver）
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except Exception:
        return None

    if not config.checkpointer_uri:
        # 未配置检查点URI，使用内存版
        return MemorySaver()

    try:
        from importlib import import_module

        # 不同版本的 langgraph-checkpoint-mysql 暴露类的位置可能不同：
        # - 旧版本常在 `langgraph.checkpoint.mysql`
        # - 新版本常在 `langgraph.checkpoint.mysql.pymysql`
        module_names = (
            "langgraph.checkpoint.mysql",
            "langgraph.checkpoint.mysql.pymysql",
        )
        class_names = (
            "PyMySQLSaver",
            "ShallowPyMySQLSaver",
            "AsyncMySQLSaver",
            "AsyncPyMySQLSaver",
        )

        for module_name in module_names:
            try:
                module = import_module(module_name)
            except Exception:
                continue

            for class_name in class_names:
                saver_cls = getattr(module, class_name, None)
                if saver_cls is None or not hasattr(saver_cls, "from_conn_string"):
                    continue

                try:
                    saver_or_manager = saver_cls.from_conn_string(config.checkpointer_uri)

                    # 异步上下文管理器不适用于当前同步 graph 编译路径，跳过。
                    if hasattr(saver_or_manager, "__aenter__") and not hasattr(saver_or_manager, "__enter__"):
                        continue

                    # 某些实现返回 context manager，需要先进入再交给 graph。
                    if hasattr(saver_or_manager, "__enter__") and hasattr(saver_or_manager, "__exit__"):
                        saver = saver_or_manager.__enter__()
                        if hasattr(saver, "setup"):
                            saver.setup()
                        _register_checkpointer_context_manager(saver_or_manager)
                        return saver

                    if hasattr(saver_or_manager, "setup"):
                        saver_or_manager.setup()
                    return saver_or_manager
                except Exception:
                    continue
    except Exception:
        # MySQL检查点器创建失败，回退到内存版
        return MemorySaver()

    return MemorySaver()


def build_graph(config: PaperAgentConfig | None = None):
    """
    构建论文阅读Agent的主图
    
    设计原则：
    - LangGraph负责宏观编排（节点间的状态流转）
    - create_agent负责节点内部的工具调用与推理
    
    工作流程：
    1. 初始化 -> 规划器
    2. 规划器决定下一步动作（检索/视觉/Python/网络/审查/草稿）
    3. 执行相应工具节点后返回规划器
    4. 如果是审查模式，并行执行多个专家审查节点
    5. 生成草稿后进行质量评估
    6. 根据质量评估结果决定：继续迭代/重写/完成
    7. 压缩历史消息后结束
    
    Args:
        config: Agent配置对象（可选，默认从环境变量加载）
    
    Returns:
        编译后的LangGraph图对象
    
    Raises:
        RuntimeError: 如果LangGraph未安装
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:
        raise RuntimeError(
            "LangGraph is not installed. Install the project requirements before running the paper agent."
        ) from exc

    # 加载配置
    config = config or PaperAgentConfig.from_env()
    
    # 初始化核心组件
    repository = PaperRepository(config)  # 论文数据仓库
    toolkit = PaperToolkit(config=config, repository=repository)  # 工具集
    nodes = PaperAgentNodes(  # 节点处理器
        config=config,
        repository=repository,
        toolkit=toolkit,
        llm=LLMClient(config),  # LLM客户端
    )

    # 创建状态图
    graph = StateGraph(PaperAgentState)
    
    # ==================== 添加节点 ====================
    graph.add_node("initialize", nodes.initialize)  # 初始化节点
    graph.add_node("planner", nodes.planner)  # 规划器节点
    graph.add_node("retrieve", nodes.retrieve)  # 文本检索节点
    graph.add_node("vision", nodes.vision)  # 视觉分析节点（图表理解）
    graph.add_node("python", nodes.python)  # Python代码执行节点
    graph.add_node("web", nodes.web)  # 网络搜索节点
    graph.add_node("review_input", nodes.review_input)  # 审查输入准备节点
    graph.add_node("methodology_review", nodes.methodology_review)  # 方法论审查节点
    graph.add_node("experiment_review", nodes.experiment_review)  # 实验审查节点
    graph.add_node("critical_review", nodes.critical_review)  # 批判性审查节点
    graph.add_node("consensus", nodes.consensus)  # 共识汇总节点
    graph.add_node("draft", nodes.draft)  # 草稿生成节点
    graph.add_node("qa", nodes.qa)  # 质量评估节点
    graph.add_node("rewrite", nodes.rewrite)  # 重写节点
    graph.add_node("finalize", nodes.finalize)  # 最终化处理节点
    graph.add_node("compress_history", nodes.compress_history)  # 历史压缩节点

    # ==================== 定义边（状态流转）====================
    
    # 起始 -> 初始化 -> 规划器
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "planner")
    
    # 规划器条件分支：根据决策路由到不同节点
    graph.add_conditional_edges(
        "planner",
        nodes.route_after_planner,
        {
            "retrieve": "retrieve",      # 检索相关文本
            "vision": "vision",          # 分析图表
            "python": "python",          # 执行Python代码
            "web": "web",                # 网络搜索
            "review_input": "review_input",  # 准备审查
            "draft": "draft",            # 生成草稿
            "finalize": "finalize",      # 预算上限触发时直接输出
        },
    )
    
    # 工具节点执行后回到规划器，由规划器决定下一步
    graph.add_edge("retrieve", "planner")
    graph.add_edge("vision", "planner")
    graph.add_edge("python", "planner")
    graph.add_edge("web", "planner")

    # 审查流程：并行执行多个专家审查
    graph.add_edge("review_input", "methodology_review")
    graph.add_edge("review_input", "experiment_review")
    graph.add_edge("review_input", "critical_review")
    graph.add_edge("methodology_review", "consensus")
    graph.add_edge("experiment_review", "consensus")
    graph.add_edge("critical_review", "consensus")
    graph.add_edge("consensus", "planner")  # 审查完成后返回规划器

    # 草稿生成后通常进入质量检查；若已达到 LLM 调用上限则直接收敛输出
    graph.add_conditional_edges(
        "draft",
        nodes.route_after_draft,
        {
            "qa": "qa",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "qa",
        nodes.route_after_qa,
        {
            "planner": "planner",   # 需要更多信息，继续迭代
            "rewrite": "rewrite",   # 需要重写
            "finalize": "finalize", # 质量通过，完成
        },
    )
    graph.add_edge("rewrite", "qa")  # 重写后重新评估
    graph.add_edge("finalize", "compress_history")  # 完成后压缩历史
    graph.add_edge("compress_history", END)  # 结束

    # 编译图（附带检查点器）
    checkpointer = build_checkpointer(config)
    return graph.compile(checkpointer=checkpointer) if checkpointer is not None else graph.compile()