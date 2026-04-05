"""
状态管理模块
定义LangGraph工作流的全局状态结构（TypedDict）
所有Agent节点通过读取和更新此状态来协作完成任务
"""
from __future__ import annotations

import operator
from typing import Any
from typing_extensions import Annotated, TypedDict

from .schemas import FigureAsset, PaperInput, PlannerDecision, QualityReport, RetrievedChunk, ReviewNote, ToolCallRecord


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """
    合并两个字典（用于状态更新）
    右侧字典的键值对会覆盖左侧字典中的同名键
    
    Args:
        left: 左操作数字典
        right: 右操作数字典
    
    Returns:
        合并后的新字典
    """
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def merge_lists(left: list[Any], right: list[Any]) -> list[Any]:
    """
    合并两个列表（用于状态更新）
    将右侧列表追加到左侧列表后面
    
    Args:
        left: 左操作数列表
        right: 右操作数列表
    
    Returns:
        合并后的新列表
    """
    return list(left or []) + list(right or [])


class PaperAgentState(TypedDict, total=False):
    """
    论文阅读Agent的全局状态
    
    使用TypedDict定义结构化状态，total=False表示所有字段都是可选的
    每个字段都可以通过Annotated指定合并策略
    """
    
    # 消息历史列表（使用operator.add进行追加合并）
    messages: Annotated[list[dict[str, str]], operator.add]
    
    # 用户查询内容
    user_query: str
    
    # 待处理的论文输入列表
    paper_inputs: list[PaperInput]
    
    # 检索到的文本块列表（使用merge_lists合并）
    retrieved_chunks: Annotated[list[RetrievedChunk], merge_lists]
    
    # 图表映射表：图表ID -> 图表资源列表（使用merge_dicts合并）
    figure_map: Annotated[dict[str, list[FigureAsset]], merge_dicts]
    
    # 工具调用结果记录：工具名 -> 调用记录（使用merge_dicts合并）
    tool_results: Annotated[dict[str, ToolCallRecord], merge_dicts]
    
    # 审查笔记：步骤名 -> 审查意见（使用merge_dicts合并）
    review_notes: Annotated[dict[str, ReviewNote], merge_dicts]
    
    # 草稿答案
    draft_answer: str
    
    # 质量评分（0-1之间）
    quality_score: float
    
    # 用户偏好设置
    user_preferences: dict[str, Any]
    
    # 规划器决策结果
    planner_decision: PlannerDecision
    
    # 质量报告
    quality_report: QualityReport
    
    # 最终答案
    final_answer: str
    
    # 历史对话摘要（用于长上下文压缩）
    history_summary: str