import logging, os, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from .. import engine, speech, vision, scoring
from ..config import settings
from ..database import get_db
from ..deps import current_user, owned_interview
from ..llm import LLMError
from ..models import Interview, Question, Answer, User, QuestionCategory
from ..pdf import build_pdf
from ..serializers import iv_out, q_out, a_out, question_full

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
log = logging.getLogger("interviews")
ALLOWED_EXT = {".webm", ".mp4", ".ogg", ".wav", ".m4a", ".mkv"}


class Create(BaseModel):
    interview_type: str
    difficulty: str = "Mixed"
    num_questions: int = Field(5, ge=0, le=1000)  # 0 = adaptive, ends when the candidate ends it
    consent_recording: bool = False
    extra: str = ""
    full_name: str | None = None
    education: str | None = None
    college: str | None = None
    experience_level: str | None = None
    target_role: str | None = None
    target_company: str | None = None
    skills: str | None = None
    languages: str | None = None


class Submit(BaseModel):
    transcript: str = Field(max_length=20000)
    mode: str = Field("voice", pattern="^(voice|text)$")


def _history(iv):
    return [{"text": q.text, "transcript": q.answer.transcript, "score": q.answer.score,
             "missing": (q.answer.evaluation or {}).get("missing_concepts")}
            for q in iv.questions if q.answer and q.answer.status == "evaluated"]


def _add_question(db, iv, g: engine.GenQuestion):
    q = Question(interview_id=iv.id, number=len(iv.questions) + 1, text=g.text, category=g.category, difficulty=g.difficulty,
                 expected_concepts=g.expected_concepts, evaluation_criteria=g.evaluation_criteria, hint=g.hint,
                 sample_answer=g.sample_answer, is_coding=g.is_coding or iv.interview_type.lower().startswith("coding"),
                 is_followup=g.is_followup)
    db.add(q); db.commit(); db.refresh(q)
    return q


def _llm(fn, *a):
    try:
        return fn(*a)
    except LLMError as e:
        raise HTTPException(502, f"AI service error: {e}. You can retry.")


def _question(iv, qid):
    q = next((x for x in iv.questions if x.id == qid), None)
    if not q:
        raise HTTPException(404, "Question not found")
    return q


@router.post("", status_code=201)
def create(body: Create, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.query(QuestionCategory).filter_by(name=body.interview_type, enabled=True).first():
        raise HTTPException(400, "Unsupported or disabled interview type")
    p = u.profile
    cfg = {"full_name": body.full_name or u.full_name, "education": body.education or p.education, "college": body.college or p.college,
           "experience_level": body.experience_level or p.experience_level, "target_role": body.target_role or p.target_role,
           "target_company": body.target_company or p.target_company, "skills": body.skills or p.skills,
           "languages": body.languages or p.languages, "extra": body.extra}
    iv = Interview(user_id=u.id, config=cfg, interview_type=body.interview_type, difficulty=body.difficulty,
                   num_questions=body.num_questions, consent_recording=body.consent_recording)
    db.add(iv); db.flush()
    try:
        g = engine.generate_question(iv, [])
    except LLMError as e:
        db.rollback()
        raise HTTPException(502, f"AI service error: {e}. Interview was not created; you can retry.")
    db.commit()
    _add_question(db, iv, g)
    db.refresh(iv)
    return iv_out(iv, detail=True)


@router.get("")
def list_(u: User = Depends(current_user), db: Session = Depends(get_db)):
    ivs = db.query(Interview).filter_by(user_id=u.id).order_by(Interview.started_at.desc()).all()
    return [iv_out(i) for i in ivs]


@router.delete("")
def delete_all(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for iv in db.query(Interview).filter_by(user_id=u.id).all():
        _purge_media(iv); db.delete(iv)
    db.commit()
    return {"detail": "All interviews and recordings deleted"}


@router.get("/{iid}")
def get(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return iv_out(owned_interview(db, u, iid), detail=True)


def _purge_media(iv):
    for q in iv.questions:
        a = q.answer
        if a and a.media_path:
            Path(a.media_path).unlink(missing_ok=True)
            a.media_path = None; a.media_size = None


@router.delete("/{iid}")
def delete(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    _purge_media(iv); db.delete(iv); db.commit()
    return {"detail": "Interview and all associated data deleted"}


@router.post("/{iid}/questions/{qid}/media")
def upload_media(iid: int, qid: int, file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Store the candidate's webcam+mic recording, transcribe it, analyze audio and video."""
    iv = owned_interview(db, u, iid)
    if iv.status != "active":
        raise HTTPException(409, "Interview is not active")
    if not iv.consent_recording:
        raise HTTPException(403, "Recording consent was not given for this interview")
    q = _question(iv, qid)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"Unsupported file type '{ext}'")
    folder = settings.storage_dir / str(u.id) / str(iv.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"q{q.id}_{uuid.uuid4().hex[:8]}{ext}"
    limit, size, head = settings.max_upload_mb * 1024 * 1024, 0, b""
    with open(path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            head = head or chunk[:12]
            size += len(chunk)
            if size > limit:
                f.close(); path.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
            f.write(chunk)
    sig_ok = head[:4] in (b"\x1a\x45\xdf\xa3", b"OggS", b"RIFF") or head[4:8] == b"ftyp"
    if not sig_ok or size < 1000:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "File is not a valid audio/video recording")

    a = q.answer or Answer(question_id=q.id)
    if a.status == "evaluated":
        path.unlink(missing_ok=True)
        raise HTTPException(409, "This question has already been answered")
    if a.media_path:
        Path(a.media_path).unlink(missing_ok=True)
    db.add(a)
    a.mode, a.media_path, a.media_size = "voice", str(path), size

    with ThreadPoolExecutor(2) as ex:
        f_tr = ex.submit(speech.transcribe, str(path))
        f_vi = ex.submit(vision.analyze_video, path)
        tr, vi = f_tr.result(), None
        try:
            vi = f_vi.result()
        except Exception as e:
            log.exception("video analysis failed")
            vi = {"available": False, "reason": f"Video analysis failed: {e}"}
    a.raw_transcript = a.transcript = tr["text"]
    a.duration_sec = tr["duration"]
    a.audio_analysis = speech.analyze_audio(tr) if not tr["error"] else {"available": False, "reason": tr["error"]}
    a.visual_analysis = vi
    a.status = "transcribed"
    db.commit()
    out = a_out(a)
    out["warning"] = tr["error"] or (None if tr["text"] else "No speech was detected. Check your microphone and try recording again, or type your answer.")
    return out


@router.post("/{iid}/questions/{qid}/submit")
def submit(iid: int, qid: int, body: Submit, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    if iv.status != "active":
        raise HTTPException(409, "Interview is not active")
    q = _question(iv, qid)
    text = body.transcript.strip()
    if len(text.split()) < 3:
        raise HTTPException(400, "Answer is empty or too short to evaluate")
    a = q.answer or Answer(question_id=q.id, mode=body.mode)
    if a.status == "evaluated":
        raise HTTPException(409, "This question has already been answered")
    db.add(a)
    if body.mode == "text":
        a.mode = "text"
    a.transcript = text
    ev, score = _llm(engine.evaluate_answer, q, text, a.mode)  # on failure nothing is stored as evaluated
    a.evaluation, a.score, a.status = ev.model_dump(), score, "evaluated"
    db.commit(); db.refresh(q)
    return {"question": question_full(q)}


@router.post("/{iid}/next")
def next_question(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    if iv.status != "active":
        raise HTTPException(409, "Interview is not active")
    if iv.questions and not (iv.questions[-1].answer and iv.questions[-1].answer.status == "evaluated"):
        raise HTTPException(409, "Submit an answer to the current question first")
    if iv.num_questions and len(iv.questions) >= iv.num_questions:
        return {"done": True}
    g = _llm(engine.generate_question, iv, _history(iv))
    return {"done": False, "question": q_out(_add_question(db, iv, g))}


@router.post("/{iid}/finish")
def finish(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    if iv.status == "completed":
        return iv_out(iv, detail=True)
    answers = [q.answer for q in iv.questions if q.answer and q.answer.status == "evaluated"]
    iv.ended_at = datetime.utcnow()
    iv.duration_sec = (iv.ended_at - iv.started_at).total_seconds()
    if not answers:  # interrupted before any answer was evaluated
        iv.status = "abandoned"; db.commit()
        return iv_out(iv, detail=True)
    cats = scoring.category_scores(answers)
    total, used = scoring.overall(cats)
    rows = [{"q": q.text, "category": q.category, "difficulty": q.difficulty, "score": q.answer.score,
             "correct": q.answer.evaluation["correct_concepts"], "missing": q.answer.evaluation["missing_concepts"],
             "wrong": q.answer.evaluation["incorrect_statements"],
             "wpm": (q.answer.audio_analysis or {}).get("words_per_minute"),
             "fillers": (q.answer.audio_analysis or {}).get("hesitation_fillers")}
            for q in iv.questions if q.answer and q.answer.status == "evaluated"]
    s = _llm(engine.summarize, iv.interview_type, iv.config.get("target_role"), rows, cats)
    prev = [i.overall_score for i in db.query(Interview).filter(Interview.user_id == u.id, Interview.status == "completed",
                                                                  Interview.id != iv.id).all() if i.overall_score is not None]
    iv.report = {**s.model_dump(), "category_scores": cats, "weights_used": used,
                 "answered": len(answers), "total_questions": len(iv.questions),
                 "previous_average": round(sum(prev) / len(prev), 1) if prev else None,
                 "weighting_note": "Overall = weighted mean of the categories that were actually measured; unmeasured categories are excluded, not scored as zero."}
    iv.overall_score, iv.status = total, "completed"
    db.commit()
    return iv_out(iv, detail=True)


@router.post("/{iid}/abandon")
def abandon(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    if iv.status == "active":
        iv.status, iv.ended_at = "abandoned", datetime.utcnow()
        iv.duration_sec = (iv.ended_at - iv.started_at).total_seconds()
        db.commit()
    return iv_out(iv)


@router.get("/{iid}/report.pdf")
def report_pdf(iid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    iv = owned_interview(db, u, iid)
    if iv.status != "completed":
        raise HTTPException(409, "Report is only available for completed interviews")
    return Response(build_pdf(iv, u, iv.questions), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="interview_report_{iv.id}.pdf"'})


def _answer(db, u, aid):
    a = db.get(Answer, aid)
    if not a or a.question.interview.user_id != u.id:
        raise HTTPException(404, "Recording not found")
    return a


@router.get("/answers/{aid}/media")
def get_media(aid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _answer(db, u, aid)
    if not a.media_path or not os.path.exists(a.media_path):
        raise HTTPException(404, "No recording stored for this answer")
    return FileResponse(a.media_path, media_type="video/webm" if a.media_path.endswith(".webm") else None)


@router.delete("/answers/{aid}/media")
def delete_media(aid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _answer(db, u, aid)
    if a.media_path:
        Path(a.media_path).unlink(missing_ok=True)
    a.media_path = a.media_size = None
    db.commit()
    return {"detail": "Recording deleted"}
