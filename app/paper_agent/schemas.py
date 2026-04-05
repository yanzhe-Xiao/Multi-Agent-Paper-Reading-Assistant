"""
数据模式定义模块
定义Agent工作流中使用的各种数据结构（Pydantic模型）
用于类型检查、数据验证和API文档生成
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# 规划器可执行的动作类型
PlannerAction = Literal["retrieve", "vision", "python", "web", "review", "finalize"]

# 质量评估结果类型
QualityVerdict = Literal["pass", "need_more_info", "rewrite"]

# 审查模式：单论文审查或多论文对比审查
ReviewMode = Literal["single_paper", "multi_paper"]


class PaperInput(BaseModel):
    """
    论文输入模型
    表示待处理的单篇论文
    """
    paper_id: str  # 论文唯一标识符
    title: str | None = None  # 论文标题（可选）


class RetrievedChunk(BaseModel):
    """
    检索到的文本块模型
    表示从论文中检索出的一段相关内容
    """
    paper_id: str  # 所属论文ID
    chunk_id: str  # 文本块唯一标识符
    content: str  # 文本内容
    source_path: str  # 源文件路径
    score: float = 0.0  # 相关性评分（0-1之间）
    title: str | None = None  # 所属章节标题（可选）


class FigureAsset(BaseModel):
    """
    图表资源模型
    表示论文中的一个图表（Figure/Table）及其元数据
    """
    paper_id: str  # 所属论文ID
    img_id: int  # 图片编号
    img_path: str  # 图片相对路径
    absolute_path: str  # 图片绝对路径
    caption: str | None = None  # 图表标题/说明文字（可选）
    page_idx: int | None = None  # 所在页码（可选）
    is_checked: bool = False  # 是否已人工检查标记


class ToolCallRecord(BaseModel):
    """
    工具调用记录模型
    记录每次工具调用的执行情况和结果摘要
    """
    tool_name: str  # 工具名称
    status: Literal["ok", "skipped", "error"]  # 执行状态：成功/跳过/错误
    summary: str  # 执行结果摘要
    payload: dict[str, Any] = Field(default_factory=dict)  # 调用参数和返回数据


class ReviewNote(BaseModel):
    """
    审查意见模型
    记录专家Agent对论文的审查结果
    """
    reviewer: Literal["methodology", "experiment", "critic", "consensus"]  # 审查者角色
    summary: str  # 审查总结
    strengths: list[str] = Field(default_factory=list)  # 优点列表
    weaknesses: list[str] = Field(default_factory=list)  # 缺点列表
    evidence: list[str] = Field(default_factory=list)  # 支撑证据列表


class PlannerDecision(BaseModel):
    """
    规划器决策模型
    决定下一步执行什么动作以及原因
    """
    next_action: PlannerAction  # 下一步动作
    reasoning: str  # 决策理由
    retrieval_query: str | None = None  # 检索查询语句（retrieve/web 通用，需自包含主题与检索目标）
    focus_figure_ids: list[int] = Field(default_factory=list)  # 需要重点关注的图表ID列表
    mode: ReviewMode = "single_paper"  # 审查模式


class QualityReport(BaseModel):
    """
    质量评估报告模型
    对当前答案的质量进行评估，并提供改进建议
    """
    verdict: QualityVerdict  # 评估结论：通过/需要更多信息/需要重写
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)  # 质量评分（0-1之间）
    missing_points: list[str] = Field(default_factory=list)  # 缺失的要点列表
    rewrite_instructions: list[str] = Field(default_factory=list)  # 重写指令列表
    reasoning: str  # 评估理由


class AgentResponse(BaseModel):
    """
    Agent最终响应模型
    包含完整的答案和相关元数据
    """
    final_answer: str  # 最终答案文本
    quality_score: float  # 质量评分
    tool_results: dict[str, ToolCallRecord] = Field(default_factory=dict)  # 所有工具调用记录
    review_notes: dict[str, ReviewNote] = Field(default_factory=dict)  # 所有审查意见