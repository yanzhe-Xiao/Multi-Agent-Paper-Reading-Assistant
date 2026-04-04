from pydantic import BaseModel, ConfigDict
from typing import Optional


class ImgPathBase(BaseModel):
    img_id: int
    img_path: str
    is_check: bool = False


class ImgPathCreate(ImgPathBase):
    pass


class ImgPathUpdate(BaseModel):
    """更新图片路径信息，paper_id 不可修改"""
    img_id: Optional[int] = None
    img_path: Optional[str] = None
    is_check: Optional[bool] = None


class ImgPathResponse(ImgPathBase):
    id: int
    paper_id: str
    model_config = ConfigDict(from_attributes=True)


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