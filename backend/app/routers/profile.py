from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import current_user
from pathlib import Path
from ..models import User, Profile, QuestionCategory, Interview, Answer, Question

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=200)
    education: str = ""
    college: str = ""
    experience_level: str = "Fresher"
    target_role: str = ""
    target_company: str = ""
    skills: str = ""
    languages: str = ""


def p_out(u: User):
    p = u.profile
    return {"full_name": u.full_name, "email": u.email, "education": p.education, "college": p.college,
            "experience_level": p.experience_level, "target_role": p.target_role, "target_company": p.target_company,
            "skills": p.skills, "languages": p.languages}


@router.get("/profile")
def get_profile(u: User = Depends(current_user)):
    return p_out(u)


@router.put("/profile")
def put_profile(body: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.profile is None:
        u.profile = Profile()
    for k, v in body.model_dump(exclude={"full_name"}).items():
        setattr(u.profile, k, v)
    if body.full_name:
        u.full_name = body.full_name.strip()
    db.commit()
    return p_out(u)


@router.get("/categories")
def categories(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [c.name for c in db.query(QuestionCategory).filter_by(enabled=True).order_by(QuestionCategory.id)]


@router.delete("/me/recordings")
def delete_my_recordings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Delete every stored webcam/audio recording of this user (transcripts and reports are kept)."""
    n = 0
    for a in db.query(Answer).join(Question).join(Interview).filter(Interview.user_id == u.id, Answer.media_path.isnot(None)):
        Path(a.media_path).unlink(missing_ok=True); a.media_path = a.media_size = None; n += 1
    db.commit()
    return {"deleted": n}
