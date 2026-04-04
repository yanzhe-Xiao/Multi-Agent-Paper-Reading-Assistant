from sqlalchemy import Column, String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class Paper(Base):
    __tablename__ = "paper"

    id = Column(String(50), primary_key=True, index=True)
    path = Column(String(100), nullable=False)
    title = Column(String(100), nullable=True)
    authors = Column(String(100), nullable=True)
    one_sentence = Column("one_sentence_summary", Text, nullable=True)
    core_problem = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    experiments = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)

    images = relationship("ImgPath", back_populates="paper", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Paper(id='{self.id}', title='{self.title}')>"


class ImgPath(Base):
    __tablename__ = "img_path"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    paper_id = Column(String(50), ForeignKey("paper.id"), nullable=False, index=True)
    img_id = Column(Integer, nullable=False)
    img_path = Column(String(100), nullable=False)
    is_check = Column(Boolean, nullable=False, default=False)

    paper = relationship("Paper", back_populates="images")