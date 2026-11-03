import logging, time
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import llm, vision
from .config import settings
from .database import Base, engine, SessionLocal
from .models import QuestionCategory, Answer
from .routers import auth, profile, interviews, analytics, admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
DEFAULT_CATEGORIES = ["HR Interview", "Technical Interview", "Coding Interview", "Behavioral Interview", "Data Science Interview",
                      "Python Interview", "SQL Interview", "Machine Learning Interview", "Full Stack Developer Interview", "Custom Interview"]


def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for n in DEFAULT_CATEGORIES:
            if not db.query(QuestionCategory).filter_by(name=n).first():
                db.add(QuestionCategory(name=n))
        db.commit()


def apply_retention():
    if settings.retention_days <= 0:
        return
    cutoff = datetime.utcnow() - timedelta(days=settings.retention_days)
    with SessionLocal() as db:
        for a in db.query(Answer).filter(Answer.media_path.isnot(None), Answer.created_at < cutoff):
            Path(a.media_path).unlink(missing_ok=True); a.media_path = a.media_size = None
        db.commit()


app = FastAPI(title="AI Smart Interview Simulator API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for r in (auth, profile, interviews, analytics, admin):
    app.include_router(r.router)


@app.on_event("startup")
def startup():
    init_db(); apply_retention(); vision.ensure_model()
    if not llm.configured():
        logging.warning("LLM API key is NOT configured; question generation and evaluation will return errors.")


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "time": time.time(), "llm_configured": llm.configured(),
            "face_landmarker": vision.MODEL_PATH.exists()}
