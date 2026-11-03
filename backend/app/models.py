from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="candidate")
    reset_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reset_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    education: Mapped[str] = mapped_column(String(200), default="")
    college: Mapped[str] = mapped_column(String(200), default="")
    experience_level: Mapped[str] = mapped_column(String(50), default="Fresher")
    target_role: Mapped[str] = mapped_column(String(200), default="")
    target_company: Mapped[str] = mapped_column(String(200), default="")
    skills: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[str] = mapped_column(Text, default="")
    user: Mapped[User] = relationship(back_populates="profile")


class QuestionCategory(Base):
    __tablename__ = "question_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    config: Mapped[dict] = mapped_column(JSON)  # configuration snapshot (profile + selections)
    interview_type: Mapped[str] = mapped_column(String(100))
    difficulty: Mapped[str] = mapped_column(String(30))
    num_questions: Mapped[int] = mapped_column(Integer, default=5)  # 0 = adaptive (candidate ends it)
    consent_recording: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|completed|abandoned
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user: Mapped[User] = relationship(back_populates="interviews")
    questions: Mapped[list["Question"]] = relationship(back_populates="interview", cascade="all, delete-orphan", order_by="Question.number")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="General")
    difficulty: Mapped[str] = mapped_column(String(30), default="intermediate")
    expected_concepts: Mapped[list] = mapped_column(JSON, default=list)
    evaluation_criteria: Mapped[list] = mapped_column(JSON, default=list)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_coding: Mapped[bool] = mapped_column(Boolean, default=False)
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    interview: Mapped[Interview] = relationship(back_populates="questions")
    answer: Mapped["Answer"] = relationship(back_populates="question", uselist=False, cascade="all, delete-orphan")


class Answer(Base):
    """One answer per question: transcript, recording metadata, audio/visual analysis and AI evaluation."""
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), unique=True)
    mode: Mapped[str] = mapped_column(String(10), default="voice")  # voice|text
    transcript: Mapped[str] = mapped_column(Text, default="")
    raw_transcript: Mapped[str] = mapped_column(Text, default="")  # unedited speech-to-text output
    media_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    visual_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|transcribed|evaluated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    question: Mapped[Question] = relationship(back_populates="answer")
