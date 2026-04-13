import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="Levi Webster")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    quiz_attempts = relationship("QuizAttempt", back_populates="user")
    curricula = relationship("Curriculum", back_populates="user")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="in_progress")  # in_progress, completed
    current_question = Column(Integer, default=0)
    responses = Column(JSON, default=list)  # list of response dicts
    domain_scores = Column(JSON, default=dict)  # {domain: score}
    overall_score = Column(Float, default=0.0)
    level = Column(String, default="")  # Foundations / Practitioner / Builder / Innovator
    strengths = Column(JSON, default=list)
    gaps = Column(JSON, default=list)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="quiz_attempts")


class Curriculum(Base):
    __tablename__ = "curricula"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_attempt_id = Column(Integer, ForeignKey("quiz_attempts.id"), nullable=False)
    content_md = Column(Text, default="")  # raw markdown
    content_html = Column(Text, default="")  # rendered HTML
    weeks = Column(JSON, default=list)  # structured week-by-week data
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="curricula")
    quiz_attempt = relationship("QuizAttempt")
    chat_sessions = relationship("ChatSession", back_populates="curriculum")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_id = Column(Integer, ForeignKey("curricula.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    messages = Column(JSON, default=list)  # [{role, content, timestamp}]
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    curriculum = relationship("Curriculum", back_populates="chat_sessions")


# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./ai_mastery.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session
