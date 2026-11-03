import shutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import llm, vision
from ..config import settings
from ..database import get_db
from ..deps import admin_user
from ..models import User, Interview, Answer, QuestionCategory

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_user)])


class Cat(BaseModel):
    name: str
    enabled: bool = True


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Aggregate statistics only: no interview content, transcripts or recordings are exposed."""
    by_type = dict(db.query(Interview.interview_type, func.count()).group_by(Interview.interview_type).all())
    by_status = dict(db.query(Interview.status, func.count()).group_by(Interview.status).all())
    return {"users": db.query(User).count(), "interviews": by_status, "by_type": by_type,
            "answers_evaluated": db.query(Answer).filter_by(status="evaluated").count(),
            "avg_score": db.query(func.avg(Interview.overall_score)).filter_by(status="completed").scalar()}


@router.get("/users")
def users(db: Session = Depends(get_db)):
    rows = db.query(User, func.count(Interview.id)).outerjoin(Interview).group_by(User.id).all()
    return [{"id": u.id, "email": u.email, "name": u.full_name, "role": u.role, "joined": u.created_at.isoformat(), "interviews": n} for u, n in rows]


@router.get("/system")
def system():
    total, used, free = shutil.disk_usage(settings.storage_dir)
    return {"llm_provider": settings.llm_provider, "llm_configured": llm.configured(),
            "llm_model": settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model,
            "whisper_model": settings.whisper_model, "face_landmarker_model_present": vision.MODEL_PATH.exists(),
            "disk_free_gb": round(free / 1e9, 1), "retention_days": settings.retention_days}


@router.get("/categories")
def cats(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "enabled": c.enabled} for c in db.query(QuestionCategory).all()]


@router.post("/categories", status_code=201)
def add_cat(body: Cat, db: Session = Depends(get_db)):
    if db.query(QuestionCategory).filter_by(name=body.name).first():
        raise HTTPException(409, "Category exists")
    c = QuestionCategory(name=body.name.strip(), enabled=body.enabled); db.add(c); db.commit()
    return {"id": c.id, "name": c.name, "enabled": c.enabled}


@router.put("/categories/{cid}")
def set_cat(cid: int, body: Cat, db: Session = Depends(get_db)):
    c = db.get(QuestionCategory, cid)
    if not c:
        raise HTTPException(404, "Not found")
    c.name, c.enabled = body.name, body.enabled; db.commit()
    return {"id": c.id, "name": c.name, "enabled": c.enabled}
