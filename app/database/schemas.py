from pydantic import BaseModel, ConfigDict
from typing import Optional


class ImgPathBase(BaseModel):
    img_id: Optional[int] = None
    img_path: str


class ImgPathCreate(ImgPathBase):
    img_id: Optional[int] = None


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