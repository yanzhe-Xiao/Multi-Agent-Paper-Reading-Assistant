"""
Pydantic数据模型模块
定义API请求和响应的数据结构，用于数据验证和序列化
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ImgPathBase(BaseModel):
    """图片路径基础模型"""
    img_id: int  # 图片编号
    img_path: str  # 图片文件路径
    is_check: bool = False  # 是否已检查标记


class ImgPathCreate(ImgPathBase):
    """创建图片路径的请求模型（继承自ImgPathBase）"""
    pass


class ImgPathUpdate(BaseModel):
    """
    更新图片路径信息的请求模型
    注意：paper_id 不可修改，只能更新其他字段
    """
    img_id: Optional[int] = None  # 可选的图片编号
    img_path: Optional[str] = None  # 可选的图片路径
    is_check: Optional[bool] = None  # 可选的检查标记


class ImgPathResponse(ImgPathBase):
    """图片路径的响应模型（包含数据库生成的ID和关联的论文ID）"""
    id: int  # 数据库自增主键
    paper_id: str  # 关联的论文ID
    model_config = ConfigDict(from_attributes=True)  # 允许从ORM模型转换


class PaperSummary(BaseModel):
    """
    论文结构化摘要模型
    用于Agent输出的标准化格式
    """
    title: str = Field(description="论文标题")
    authors: list[str] = Field(description="作者列表（注意：这是一个列表）")
    one_sentence_summary: str = Field(description="一句话总结")
    core_problem: str = Field(description="核心问题：论文试图解决什么问题？")
    methodology: str = Field(description="方法论：作者如何解决问题？")
    experiments: str = Field(description="关键实验与结果：主要发现是什么？")
    conclusion: str = Field(description="结论：最终要点是什么？")


class PaperBase(BaseModel):
    """
    论文基础模型
    包含论文的基本信息和结构化摘要
    """
    id: str  # 论文唯一标识符
    path: str  # 论文文件路径
    title: Optional[str] = None  # 论文标题（可选）
    authors: Optional[str] = None  # 作者列表（逗号分隔的字符串，可选）
    one_sentence: Optional[str] = None  # 一句话总结（可选）
    core_problem: Optional[str] = None  # 核心问题（可选）
    methodology: Optional[str] = None  # 方法论（可选）
    experiments: Optional[str] = None  # 实验结果（可选）
    conclusion: Optional[str] = None  # 结论（可选）


def convert_paper_summary_to_base(paper_summary: PaperSummary, paper_id: str, paper_path: str) -> PaperBase:
    """
    将 PaperSummary 转换为 PaperBase
    
    Args:
        paper_summary: PaperSummary 对象（Agent输出的结构化摘要）
        paper_id: 论文ID
        paper_path: 论文路径
    
    Returns:
        PaperBase 对象（可用于数据库存储）
    """
    # 将作者列表转换为字符串（用逗号分隔）
    authors_str = ", ".join(paper_summary.authors) if paper_summary.authors else None
    
    return PaperBase(
        id=paper_id,
        path=paper_path,
        title=paper_summary.title,
        authors=authors_str,
        one_sentence=paper_summary.one_sentence_summary,
        core_problem=paper_summary.core_problem,
        methodology=paper_summary.methodology,
        experiments=paper_summary.experiments,
        conclusion=paper_summary.conclusion
    )


class PaperCreate(PaperBase):
    """创建论文的请求模型（继承自PaperBase）"""
    pass


class PaperUpdate(BaseModel):
    """
    更新论文信息的请求模型
    所有字段都是可选的，只更新提供的字段
    """
    path: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    one_sentence: Optional[str] = None
    core_problem: Optional[str] = None
    methodology: Optional[str] = None
    experiments: Optional[str] = None
    conclusion: Optional[str] = None


class PaperResponse(PaperBase):
    """论文的响应模型（支持从ORM模型转换）"""
    model_config = ConfigDict(from_attributes=True)


class PaperDetailResponse(PaperResponse):
    """
    论文详细响应模型
    包含论文信息和关联的所有图片路径
    """
    images: list[ImgPathResponse] = []  # 关联的图片路径列表

    model_config = ConfigDict(from_attributes=True)