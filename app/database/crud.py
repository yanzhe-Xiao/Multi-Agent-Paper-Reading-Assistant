from sqlalchemy.orm import Session
from . import models, schemas


def create_paper(db: Session, paper: schemas.PaperCreate):
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
    return db.query(models.Paper).filter(models.Paper.id == paper_id).first()


def get_papers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Paper).offset(skip).limit(limit).all()


def update_paper(db: Session, paper_id: str, paper_data: schemas.PaperUpdate):
    db_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not db_paper:
        return None

    update_data = paper_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_paper, key, value)

    db.commit()
    db.refresh(db_paper)
    return db_paper


def delete_paper(db: Session, paper_id: str):
    db_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not db_paper:
        return None

    db.delete(db_paper)
    db.commit()
    return db_paper


def create_image_for_paper(db: Session, paper_id: str, image: schemas.ImgPathCreate):
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
    return db.query(models.ImgPath).filter(models.ImgPath.paper_id == paper_id).all()


def update_image(db: Session, image_id: int, image_update: schemas.ImgPathUpdate):
    """
    更新图片路径信息
    注意：paper_id 不可修改，只能更新 img_id 和 img_path
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
