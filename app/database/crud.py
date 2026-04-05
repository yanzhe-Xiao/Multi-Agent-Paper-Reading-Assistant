"""
数据库CRUD操作模块
提供论文和图片的增删改查功能
"""
from sqlalchemy.orm import Session
from . import models, schemas


def create_paper(db: Session, paper: schemas.PaperCreate):
    """
    创建新论文记录
    
    Args:
        db: 数据库会话对象
        paper: 包含论文信息的PaperCreate对象
    
    Returns:
        创建的Paper模型对象
    """
    db_paper = models.Paper(
        id=paper.id,
        path=paper.path,
        title=paper.title,
        authors=paper.authors,
        one_sentence=paper.one_sentence,
        core_problem=paper.core_problem,
        methodology=paper.methodology,
        experiments=paper.experiments,
        conclusion=paper.conclusion,
    )
    db.add(db_paper)
    db.commit()
    db.refresh(db_paper)
    return db_paper


def get_paper(db: Session, paper_id: str):
    """
    根据ID查询单篇论文
    
    Args:
        db: 数据库会话对象
        paper_id: 论文ID
    
    Returns:
        Paper模型对象，如果不存在则返回None
    """
    return db.query(models.Paper).filter(models.Paper.id == paper_id).first()


def get_papers(db: Session, skip: int = 0, limit: int = 10):
    """
    分页查询论文列表
    
    Args:
        db: 数据库会话对象
        skip: 跳过的记录数（用于分页）
        limit: 返回的最大记录数
    
    Returns:
        Paper模型对象列表
    """
    return db.query(models.Paper).offset(skip).limit(limit).all()


def update_paper(db: Session, paper_id: str, paper_data: schemas.PaperUpdate):
    """
    更新论文信息
    
    Args:
        db: 数据库会话对象
        paper_id: 要更新的论文ID
        paper_data: 包含更新数据的PaperUpdate对象
    
    Returns:
        更新后的Paper模型对象，如果论文不存在则返回None
    """
    db_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not db_paper:
        return None

    # 只更新提供的字段（exclude_unset=True跳过未设置的字段）
    update_data = paper_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_paper, key, value)

    db.commit()
    db.refresh(db_paper)
    return db_paper


def delete_paper(db: Session, paper_id: str):
    """
    删除论文及其关联的图片记录
    
    Args:
        db: 数据库会话对象
        paper_id: 要删除的论文ID
    
    Returns:
        被删除的Paper模型对象，如果论文不存在则返回None
    """
    db_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not db_paper:
        return None

    db.delete(db_paper)
    db.commit()
    return db_paper


def create_image_for_paper(db: Session, paper_id: str, image: schemas.ImgPathCreate):
    """
    为论文添加图片路径记录
    
    Args:
        db: 数据库会话对象
        paper_id: 关联的论文ID
        image: 包含图片信息的ImgPathCreate对象
    
    Returns:
        创建的ImgPath模型对象
    """
    db_image = models.ImgPath(
        paper_id=paper_id,
        img_id=image.img_id,
        img_path=image.img_path,
        is_check=image.is_check
    )

    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def get_images_by_paper_id(db: Session, paper_id: str):
    """
    查询指定论文的所有图片路径（按img_id升序排列）
    
    Args:
        db: 数据库会话对象
        paper_id: 论文ID
    
    Returns:
        ImgPath模型对象列表
    """
    return (
        db.query(models.ImgPath)
        .filter(models.ImgPath.paper_id == paper_id)
        .order_by(models.ImgPath.img_id.asc())
        .all()
    )


def get_image_by_paper_and_img_id(db: Session, paper_id: str, img_id: int):
    """
    查询指定论文的特定图片
    
    Args:
        db: 数据库会话对象
        paper_id: 论文ID
        img_id: 图片编号
    
    Returns:
        ImgPath模型对象，如果不存在则返回None
    """
    return (
        db.query(models.ImgPath)
        .filter(models.ImgPath.paper_id == paper_id, models.ImgPath.img_id == img_id)
        .first()
    )


def update_image(db: Session, image_id: int, image_update: schemas.ImgPathUpdate):
    """
    更新图片路径信息
    注意：paper_id 不可修改，只能更新 img_id 和 img_path
    
    Args:
        db: 数据库会话对象
        image_id: 要更新的图片记录ID
        image_update: 包含更新数据的ImgPathUpdate对象
    
    Returns:
        更新后的ImgPath模型对象，如果记录不存在则返回None
    """
    db_image = db.query(models.ImgPath).filter(models.ImgPath.id == image_id).first()
    if not db_image:
        return None

    # 只更新提供的字段（排除 paper_id）
    update_data = image_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_image, field, value)

    db.commit()
    db.refresh(db_image)
    return db_image