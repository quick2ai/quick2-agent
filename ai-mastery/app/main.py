import os
import json
import datetime
import asyncio
import markdown as md_lib
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import init_db, get_db, User, QuizAttempt, Curriculum, ChatSession
from .quiz import load_questions, get_question_by_index, get_total_questions, RATING_SCORES
from .scoring import calculate_scores, get_level_description
from .curriculum import parse_curriculum_weeks, render_curriculum_html
from . import claude_client

load_dotenv()

# Track in-flight curriculum generation
_curriculum_state: dict = {"generating": False, "ready": False, "error": None, "curriculum_id": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="AI Mastery Diagnostic", lifespan=lifespan)

# Templates
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Custom Jinja2 filter for rendering markdown safely
def safe_md_filter(text):
    return md_lib.markdown(text, extensions=["extra", "sane_lists"])

templates.env.filters["safe_md"] = safe_md_filter


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    # Get or create user
    user = await _get_or_create_user(db)

    # Get latest quiz attempt
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id)
        .order_by(desc(QuizAttempt.id))
    )
    latest_attempt = result.scalars().first()

    # Get all completed attempts for history
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id, QuizAttempt.status == "completed")
        .order_by(QuizAttempt.id)
    )
    all_attempts = result.scalars().all()

    # Check if curriculum exists
    has_curriculum = False
    if latest_attempt and latest_attempt.status == "completed":
        cur_result = await db.execute(
            select(Curriculum).where(Curriculum.quiz_attempt_id == latest_attempt.id)
        )
        has_curriculum = cur_result.scalars().first() is not None

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "latest_attempt": latest_attempt,
        "all_attempts": all_attempts,
        "has_curriculum": has_curriculum,
    })


# ──────────────────────────────────────────────
# QUIZ ENGINE
# ──────────────────────────────────────────────

@app.get("/quiz/start", response_class=HTMLResponse)
async def quiz_start(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new quiz attempt and redirect to first question."""
    user = await _get_or_create_user(db)
    attempt = QuizAttempt(user_id=user.id, responses=[], domain_scores={})
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return RedirectResponse(f"/quiz/{attempt.id}", status_code=303)


@app.get("/quiz/{attempt_id}", response_class=HTMLResponse)
async def quiz_page(request: Request, attempt_id: int, db: AsyncSession = Depends(get_db)):
    """Show current quiz question."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.status == "completed":
        return RedirectResponse("/", status_code=303)

    total = get_total_questions()
    current = attempt.current_question

    if current >= total:
        # All questions answered — finalize
        return RedirectResponse(f"/quiz/{attempt_id}/complete", status_code=303)

    question = get_question_by_index(current)

    return templates.TemplateResponse("quiz.html", {
        "request": request,
        "attempt_id": attempt_id,
        "question": question,
        "current": current,
        "total": total,
        "domain": question["domain"],
    })


@app.post("/quiz/{attempt_id}/answer", response_class=HTMLResponse)
async def quiz_answer(
    request: Request,
    attempt_id: int,
    rating: str = Form(...),
    free_text: str = Form(""),
    question_index: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Process a quiz answer."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        return RedirectResponse("/", status_code=303)

    question = get_question_by_index(question_index)
    if not question:
        return RedirectResponse(f"/quiz/{attempt_id}", status_code=303)

    response_data = {
        "question_id": question["id"],
        "question_text": question["text"],
        "domain": question["domain"],
        "difficulty": question["difficulty"],
        "rating": rating,
        "free_text": free_text,
        "override_rating": None,
        "feedback": None,
        "follow_up": None,
        "follow_up_answer": None,
    }

    # If user provided free text, evaluate with Claude
    if free_text.strip():
        evaluation = await claude_client.evaluate_free_text(
            question["text"], free_text, rating, question["domain"]
        )
        if evaluation.get("override"):
            response_data["override_rating"] = evaluation.get("assessed_level", rating)
        response_data["feedback"] = evaluation.get("feedback", "")

    # If user claims mastery (A) on a hard question, generate adaptive follow-up
    if rating == "A" and question["difficulty"] >= 2:
        follow_up = await claude_client.generate_follow_up(
            question["text"], free_text or "(no written answer)", question["domain"]
        )
        response_data["follow_up"] = follow_up.get("question", "")

    # Save response
    responses = list(attempt.responses or [])
    responses.append(response_data)
    attempt.responses = responses
    attempt.current_question = question_index + 1
    await db.commit()

    # If there's a follow-up, show it inline
    if response_data["follow_up"]:
        return templates.TemplateResponse("_follow_up.html", {
            "request": request,
            "attempt_id": attempt_id,
            "follow_up_question": response_data["follow_up"],
            "question_index": question_index,
            "original_rating": rating,
            "feedback": response_data.get("feedback", ""),
        })

    # Otherwise, advance to next question
    total = get_total_questions()
    next_index = question_index + 1
    if next_index >= total:
        return HTMLResponse(
            content=f'<script>window.location.href="/quiz/{attempt_id}/complete";</script>'
        )

    next_q = get_question_by_index(next_index)
    return templates.TemplateResponse("quiz.html", {
        "request": request,
        "attempt_id": attempt_id,
        "question": next_q,
        "current": next_index,
        "total": total,
        "domain": next_q["domain"],
    })


@app.post("/quiz/{attempt_id}/follow-up", response_class=HTMLResponse)
async def quiz_follow_up_answer(
    request: Request,
    attempt_id: int,
    follow_up_answer: str = Form(""),
    question_index: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Process follow-up question answer."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        return RedirectResponse("/", status_code=303)

    # Update the last response with follow-up answer
    responses = list(attempt.responses or [])
    if responses:
        responses[-1]["follow_up_answer"] = follow_up_answer

        # Re-evaluate with follow-up context if answer provided
        if follow_up_answer.strip():
            q_text = responses[-1]["question_text"]
            fu_text = responses[-1].get("follow_up", "")
            full_context = f"Original: {q_text}\nFollow-up: {fu_text}\nAnswer: {follow_up_answer}"
            evaluation = await claude_client.evaluate_free_text(
                full_context, follow_up_answer, responses[-1]["rating"], responses[-1]["domain"]
            )
            if evaluation.get("override"):
                responses[-1]["override_rating"] = evaluation.get("assessed_level")
            if evaluation.get("feedback"):
                existing = responses[-1].get("feedback", "")
                responses[-1]["feedback"] = f"{existing} | Follow-up: {evaluation['feedback']}"

        attempt.responses = responses
        await db.commit()

    # Advance
    total = get_total_questions()
    next_index = question_index + 1
    if next_index >= total:
        return HTMLResponse(
            content=f'<script>window.location.href="/quiz/{attempt_id}/complete";</script>'
        )

    next_q = get_question_by_index(next_index)
    return templates.TemplateResponse("quiz.html", {
        "request": request,
        "attempt_id": attempt_id,
        "question": next_q,
        "current": next_index,
        "total": total,
        "domain": next_q["domain"],
    })


@app.get("/quiz/{attempt_id}/skip", response_class=HTMLResponse)
async def quiz_skip(
    request: Request,
    attempt_id: int,
    index: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Skip a question (scores as D)."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        return RedirectResponse("/", status_code=303)

    question = get_question_by_index(index)
    if question:
        responses = list(attempt.responses or [])
        responses.append({
            "question_id": question["id"],
            "question_text": question["text"],
            "domain": question["domain"],
            "difficulty": question["difficulty"],
            "rating": "D",
            "free_text": "",
            "override_rating": None,
            "feedback": "Skipped",
            "follow_up": None,
            "follow_up_answer": None,
        })
        attempt.responses = responses
        attempt.current_question = index + 1
        await db.commit()

    return RedirectResponse(f"/quiz/{attempt_id}", status_code=303)


@app.get("/quiz/{attempt_id}/complete", response_class=HTMLResponse)
async def quiz_complete(request: Request, attempt_id: int, db: AsyncSession = Depends(get_db)):
    """Finalize quiz and show results."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        return RedirectResponse("/", status_code=303)

    # Calculate scores
    scores = calculate_scores(attempt.responses or [])
    attempt.domain_scores = scores["domain_scores"]
    attempt.overall_score = scores["overall_score"]
    attempt.level = scores["level"]
    attempt.strengths = scores["strengths"]
    attempt.gaps = scores["gaps"]
    attempt.status = "completed"
    attempt.completed_at = datetime.datetime.utcnow()
    await db.commit()

    return templates.TemplateResponse("results.html", {
        "request": request,
        "attempt": attempt,
        "level_description": get_level_description(attempt.level),
    })


# ──────────────────────────────────────────────
# CURRICULUM
# ──────────────────────────────────────────────

@app.get("/curriculum/generate", response_class=HTMLResponse)
async def curriculum_generate_page(request: Request):
    """Show the curriculum generation loading page."""
    global _curriculum_state
    _curriculum_state = {"generating": False, "ready": False, "error": None, "curriculum_id": None}
    return templates.TemplateResponse("generating.html", {"request": request})


@app.post("/curriculum/generate")
async def curriculum_generate(db: AsyncSession = Depends(get_db)):
    """Kick off curriculum generation in background."""
    global _curriculum_state

    if _curriculum_state["generating"]:
        return JSONResponse({"status": "already_generating"})

    _curriculum_state["generating"] = True

    user = await _get_or_create_user(db)

    # Get latest completed attempt
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id, QuizAttempt.status == "completed")
        .order_by(desc(QuizAttempt.id))
    )
    attempt = result.scalars().first()

    if not attempt:
        _curriculum_state = {"generating": False, "ready": False, "error": "No completed quiz found", "curriculum_id": None}
        return JSONResponse({"status": "error", "error": "No completed quiz"})

    # Generate curriculum via Claude
    try:
        curriculum_md = await claude_client.generate_curriculum(
            attempt.domain_scores or {},
            attempt.level or "Foundations",
            attempt.strengths or [],
            attempt.gaps or [],
        )

        weeks = parse_curriculum_weeks(curriculum_md)
        curriculum_html = render_curriculum_html(curriculum_md)

        curriculum = Curriculum(
            user_id=user.id,
            quiz_attempt_id=attempt.id,
            content_md=curriculum_md,
            content_html=curriculum_html,
            weeks=[w for w in weeks],
        )
        db.add(curriculum)
        await db.commit()
        await db.refresh(curriculum)

        _curriculum_state = {"generating": False, "ready": True, "error": None, "curriculum_id": curriculum.id}
    except Exception as e:
        _curriculum_state = {"generating": False, "ready": False, "error": str(e), "curriculum_id": None}

    return JSONResponse({"status": "done"})


@app.get("/curriculum/status")
async def curriculum_status():
    """Poll endpoint for curriculum generation status."""
    return JSONResponse({
        "ready": _curriculum_state["ready"],
        "error": _curriculum_state["error"],
    })


@app.get("/curriculum", response_class=HTMLResponse)
async def curriculum_view(request: Request, db: AsyncSession = Depends(get_db)):
    """View the latest curriculum."""
    user = await _get_or_create_user(db)
    result = await db.execute(
        select(Curriculum)
        .where(Curriculum.user_id == user.id)
        .order_by(desc(Curriculum.id))
    )
    curriculum = result.scalars().first()

    if not curriculum:
        return RedirectResponse("/", status_code=303)

    weeks = curriculum.weeks or []
    curriculum_html = render_curriculum_html(curriculum.content_md)

    return templates.TemplateResponse("curriculum_view.html", {
        "request": request,
        "curriculum": curriculum,
        "weeks": weeks,
        "curriculum_html": curriculum_html,
    })


@app.get("/curriculum/{curriculum_id}/download")
async def curriculum_download(curriculum_id: int, db: AsyncSession = Depends(get_db)):
    """Download curriculum as Markdown file."""
    curriculum = await db.get(Curriculum, curriculum_id)
    if not curriculum:
        return RedirectResponse("/curriculum", status_code=303)

    return PlainTextResponse(
        content=curriculum.content_md,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=ai_mastery_curriculum.md"},
    )


# ──────────────────────────────────────────────
# STUDY MODE
# ──────────────────────────────────────────────

@app.get("/study/{curriculum_id}/{week_number}", response_class=HTMLResponse)
async def study_page(
    request: Request,
    curriculum_id: int,
    week_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Study mode page for a specific week."""
    curriculum = await db.get(Curriculum, curriculum_id)
    if not curriculum:
        return RedirectResponse("/curriculum", status_code=303)

    # Find the week data
    weeks = curriculum.weeks or []
    week_data = next((w for w in weeks if w.get("week") == week_number), None)

    week_title = week_data["title"] if week_data else f"Week {week_number}"
    week_objective = week_data["objective"] if week_data else ""
    week_content = ""
    if week_data:
        week_content = render_curriculum_html(week_data.get("content_md", ""))

    # Get or create chat session
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.curriculum_id == curriculum_id, ChatSession.week_number == week_number)
        .order_by(desc(ChatSession.id))
    )
    chat_session = result.scalars().first()

    messages = []
    if chat_session:
        messages = chat_session.messages or []

    from .resources import get_resources_for_week
    week_resources = get_resources_for_week(week_number)

    return templates.TemplateResponse("study.html", {
        "request": request,
        "curriculum_id": curriculum_id,
        "week_number": week_number,
        "week_title": week_title,
        "week_objective": week_objective,
        "week_content": week_content,
        "messages": messages,
        "resources": week_resources,
    })


@app.post("/study/{curriculum_id}/{week_number}/chat")
async def study_chat(
    request: Request,
    curriculum_id: int,
    week_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Stream a chat response for study mode."""
    body = await request.json()
    user_message = body.get("message", "")

    if not user_message.strip():
        return JSONResponse({"error": "Empty message"}, status_code=400)

    curriculum = await db.get(Curriculum, curriculum_id)
    if not curriculum:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)

    # Get week context
    weeks = curriculum.weeks or []
    week_data = next((w for w in weeks if w.get("week") == week_number), None)
    week_context = week_data.get("content_md", f"Week {week_number}") if week_data else f"Week {week_number}"

    # Get or create chat session
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.curriculum_id == curriculum_id, ChatSession.week_number == week_number)
        .order_by(desc(ChatSession.id))
    )
    chat_session = result.scalars().first()

    if not chat_session:
        chat_session = ChatSession(
            curriculum_id=curriculum_id,
            week_number=week_number,
            messages=[],
        )
        db.add(chat_session)
        await db.commit()
        await db.refresh(chat_session)

    # Build message history for Claude
    messages = list(chat_session.messages or [])
    messages.append({"role": "user", "content": user_message, "timestamp": str(datetime.datetime.utcnow())})

    # Prepare Claude messages (strip timestamps)
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    async def stream_response():
        full_response = ""
        async for chunk in claude_client.chat_stream(claude_messages, week_context, week_number):
            full_response += chunk
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

        # Save both messages to session
        all_messages = list(messages)
        all_messages.append({
            "role": "assistant",
            "content": full_response,
            "timestamp": str(datetime.datetime.utcnow()),
        })
        chat_session.messages = all_messages
        chat_session.updated_at = datetime.datetime.utcnow()
        await db.commit()

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@app.post("/study/{curriculum_id}/{week_number}/quiz", response_class=HTMLResponse)
async def study_mini_quiz(
    request: Request,
    curriculum_id: int,
    week_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate a mini-quiz for a specific week."""
    curriculum = await db.get(Curriculum, curriculum_id)
    if not curriculum:
        return HTMLResponse("Curriculum not found", status_code=404)

    weeks = curriculum.weeks or []
    week_data = next((w for w in weeks if w.get("week") == week_number), None)
    week_context = week_data.get("content_md", f"Week {week_number}") if week_data else f"Week {week_number}"

    quiz_md = await claude_client.generate_mini_quiz(week_context)
    return HTMLResponse(quiz_md)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

async def _get_or_create_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(name="Levi Webster")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
