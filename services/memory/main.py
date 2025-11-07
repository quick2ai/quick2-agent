import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import KnowledgeBase, UserProfile

app = FastAPI(title="Memory Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/quick2agent")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database schema with pgvector extension"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                preferences JSONB DEFAULT '{}',
                context JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_bases (
                kb_id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                content TEXT NOT NULL,
                embedding vector(384),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
            )
        """))
        conn.commit()
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_kb_embedding ON knowledge_bases 
            USING ivfflat (embedding vector_cosine_ops)
        """))
        conn.commit()


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "memory"}


@app.get("/v1/memory/profile/{user_id}")
async def get_profile(user_id: str):
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT * FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return {
            "user_id": result.user_id,
            "name": result.name,
            "preferences": result.preferences,
            "context": result.context,
            "created_at": result.created_at.isoformat(),
            "updated_at": result.updated_at.isoformat()
        }


@app.put("/v1/memory/profile/{user_id}")
async def update_profile(user_id: str, profile: UserProfile):
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT user_id FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        
        if result:
            session.execute(
                text("""
                    UPDATE user_profiles 
                    SET name = :name, preferences = :preferences, 
                        context = :context, updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                    "name": profile.name,
                    "preferences": profile.preferences,
                    "context": profile.context
                }
            )
        else:
            session.execute(
                text("""
                    INSERT INTO user_profiles (user_id, name, preferences, context)
                    VALUES (:user_id, :name, :preferences, :context)
                """),
                {
                    "user_id": user_id,
                    "name": profile.name,
                    "preferences": profile.preferences,
                    "context": profile.context
                }
            )
        
        session.commit()
        
        return {"status": "success", "user_id": user_id}


@app.post("/v1/memory/kb")
async def create_kb(kb: KnowledgeBase):
    kb_id = kb.kb_id or str(uuid4())
    
    embedding = kb.embedding or [0.0] * 384
    
    with SessionLocal() as session:
        session.execute(
            text("SELECT user_id FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": kb.user_id}
        ).fetchone()
        
        session.execute(
            text("""
                INSERT INTO knowledge_bases (kb_id, user_id, title, content, embedding, metadata)
                VALUES (:kb_id, :user_id, :title, :content, :embedding::vector, :metadata)
            """),
            {
                "kb_id": kb_id,
                "user_id": kb.user_id,
                "title": kb.title,
                "content": kb.content,
                "embedding": str(embedding),
                "metadata": kb.metadata
            }
        )
        session.commit()
    
    return {"status": "success", "kb_id": kb_id}


@app.get("/v1/memory/kb/{kb_id}")
async def get_kb(kb_id: str):
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT * FROM knowledge_bases WHERE kb_id = :kb_id"),
            {"kb_id": kb_id}
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="KB not found")
        
        return {
            "kb_id": result.kb_id,
            "user_id": result.user_id,
            "title": result.title,
            "content": result.content,
            "metadata": result.metadata,
            "created_at": result.created_at.isoformat()
        }


@app.delete("/v1/memory/kb/{kb_id}")
async def delete_kb(kb_id: str):
    with SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM knowledge_bases WHERE kb_id = :kb_id RETURNING kb_id"),
            {"kb_id": kb_id}
        )
        session.commit()
        
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="KB not found")
    
    return {"status": "success", "kb_id": kb_id}


@app.get("/v1/memory/kb")
async def list_kb(user_id: Optional[str] = None):
    with SessionLocal() as session:
        if user_id:
            results = session.execute(
                text("SELECT kb_id, title, created_at FROM knowledge_bases WHERE user_id = :user_id ORDER BY created_at DESC"),
                {"user_id": user_id}
            ).fetchall()
        else:
            results = session.execute(
                text("SELECT kb_id, title, created_at FROM knowledge_bases ORDER BY created_at DESC LIMIT 100")
            ).fetchall()
        
        return {
            "items": [
                {"kb_id": r.kb_id, "title": r.title, "created_at": r.created_at.isoformat()}
                for r in results
            ],
            "total": len(results)
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run(app, host="0.0.0.0", port=port)
