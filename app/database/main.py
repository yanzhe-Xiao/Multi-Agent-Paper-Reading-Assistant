from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .database import get_db
from . import models, schemas, crud

app = FastAPI(title="Paper API")


@app.get("/")
def root():
    return {"message": "Paper API is running"}


@app.post("/papers", response_model=schemas.PaperResponse)
def create_paper(paper: schemas.PaperCreate, db: Session = Depends(get_db)):
    existing = crud.get_paper(db, paper.id)
    if existing:
        raise HTTPException(status_code=400, detail="Paper already exists")
    return crud.create_paper(db, paper)


@app.get("/papers", response_model=list[schemas.PaperResponse])
def read_papers(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_papers(db, skip=skip, limit=limit)


@app.get("/papers/{paper_id}", response_model=schemas.PaperDetailResponse)
def read_paper_detail(paper_id: str, db: Session = Depends(get_db)):
    paper = (
        db.query(models.Paper)
        .options(joinedload(models.Paper.images))
        .filter(models.Paper.id == paper_id)
        .first()
    )
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@app.put("/papers/{paper_id}", response_model=schemas.PaperResponse)
def update_paper(paper_id: str, paper: schemas.PaperUpdate, db: Session = Depends(get_db)):
    updated = crud.update_paper(db, paper_id, paper)
    if not updated:
        raise HTTPException(status_code=404, detail="Paper not found")
    return updated


@app.delete("/papers/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)):
    deleted = crud.delete_paper(db, paper_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"message": "Paper deleted successfully"}


@app.post("/papers/{paper_id}/images", response_model=schemas.ImgPathResponse)
def add_image_to_paper(paper_id: str, image: schemas.ImgPathCreate, db: Session = Depends(get_db)):
    paper = crud.get_paper(db, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return crud.create_image_for_paper(db, paper_id, image)


@app.get("/papers/{paper_id}/images", response_model=list[schemas.ImgPathResponse])
def get_paper_images(paper_id: str, db: Session = Depends(get_db)):
    paper = crud.get_paper(db, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return crud.get_images_by_paper_id(db, paper_id)