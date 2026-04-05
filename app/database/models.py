"""
数据库模型定义模块
定义了论文(Paper)和图片路径(ImgPath)的ORM模型
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class Paper(Base):
    """
    论文数据模型
    
    存储论文的基本信息和结构化摘要内容
    与图片路径表(ImgPath)建立一对多关系
    """
    __tablename__ = "paper"

    # 主键：论文唯一标识符（通常为UUID）
    id = Column(String(50), primary_key=True, index=True)
    # 论文文件路径
    path = Column(String(100), nullable=False)
    # 论文标题
    title = Column(String(100), nullable=True)
    # 作者列表（以逗号分隔的字符串形式存储）
    authors = Column(String(100), nullable=True)
    # 一句话总结
    one_sentence = Column("one_sentence_summary", Text, nullable=True)
    # 核心问题：论文试图解决什么问题
    core_problem = Column(Text, nullable=True)
    # 方法论：作者如何解决问题
    methodology = Column(Text, nullable=True)
    # 关键实验与结果
    experiments = Column(Text, nullable=True)
    # 结论：最终要点
    conclusion = Column(Text, nullable=True)

    # 关联的图片路径列表，设置级联删除（删除论文时自动删除相关图片）
    images = relationship("ImgPath", back_populates="paper", cascade="all, delete-orphan")

    def __repr__(self):
        """返回论文对象的可读字符串表示"""
        return f"<Paper(id='{self.id}', title='{self.title}')>"


class ImgPath(Base):
    """
    图片路径数据模型
    
    存储论文中引用的图片文件路径
    与论文表(Paper)建立多对一关系
    """
    __tablename__ = "img_path"

    # 主键：自增ID
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # 外键：关联的论文ID
    paper_id = Column(String(50), ForeignKey("paper.id"), nullable=False, index=True)
    # 图片编号（用于排序和引用）
    img_id = Column(Integer, nullable=False)
    # 图片文件路径
    img_path = Column(String(100), nullable=False)
    # 是否已检查标记
    is_check = Column(Boolean, nullable=False, default=False)

    # 反向关联到论文对象
    paper = relationship("Paper", back_populates="images")