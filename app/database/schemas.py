from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ImgPathBase(BaseModel):
    img_id: int
    img_path: str
    is_check: bool = False


class ImgPathCreate(ImgPathBase):
    pass


class ImgPathUpdate(BaseModel):
    """更新图片路径信息,paper_id 不可修改"""
    img_id: Optional[int] = None
    img_path: Optional[str] = None
    is_check: Optional[bool] = None


class ImgPathResponse(ImgPathBase):
    id: int
    paper_id: str
    model_config = ConfigDict(from_attributes=True)

class PaperSummary(BaseModel):
    title: str = Field(description="Title of the paper")
    authors: list[str] = Field(description="Authors of the paper, note that this is a list")
    one_sentence_summary: str = Field(description="One-sentence summary of the paper")
    core_problem: str = Field(description="The Core Problem: What is the paper trying to solve?")
    methodology: str = Field(description="Methodology/Approach: How did the authors solve it?")
    experiments: str = Field(description="Key Experiments & Results: What were the major findings?")
    conclusion: str = Field(description="Conclusion: What is the final takeaway?")


class PaperBase(BaseModel):
    id: str
    path: str
    title: Optional[str] = None
    authors: Optional[str] = None
    one_sentence: Optional[str] = None
    core_problem: Optional[str] = None
    methodology: Optional[str] = None
    experiments: Optional[str] = None
    conclusion: Optional[str] = None


def convert_paper_summary_to_base(paper_summary: PaperSummary, paper_id: str, paper_path: str) -> PaperBase:
    """
    将 PaperSummary 转换为 PaperBase
    
    Args:
        paper_summary: PaperSummary 对象
        paper_id: 论文ID
        paper_path: 论文路径
    
    Returns:
        PaperBase 对象
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
    pass


class PaperUpdate(BaseModel):
    path: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    one_sentence: Optional[str] = None
    core_problem: Optional[str] = None
    methodology: Optional[str] = None
    experiments: Optional[str] = None
    conclusion: Optional[str] = None


class PaperResponse(PaperBase):
    model_config = ConfigDict(from_attributes=True)


class PaperDetailResponse(PaperResponse):
    images: list[ImgPathResponse] = []

    model_config = ConfigDict(from_attributes=True)