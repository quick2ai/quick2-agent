"""
Math Puzzle Safe — FastAPI service.

A virtual safe for electronics that kids unlock by solving math problems.
Each correct answer slides one locking bar out of position.
"""

from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .puzzle_generator import generate_daily_problems

app = FastAPI(title="Math Puzzle Safe", version="1.0.0")


# ---------------------------------------------------------------------------
# In-memory state (resets on restart — fine for a family safe)
# ---------------------------------------------------------------------------
class SafeConfig(BaseModel):
    num_problems: int = Field(default=5, ge=1, le=10)
    difficulty: str = Field(default="easy", pattern="^(easy|medium|hard)$")
    custom_salt: str = Field(default="family")


class AnswerRequest(BaseModel):
    problem_id: int
    answer: int


_config = SafeConfig()
_unlocked: dict[str, set[int]] = {}  # date_str -> set of unlocked bar ids


def _today_key() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    return _config


@app.post("/api/config")
def update_config(cfg: SafeConfig):
    global _config, _unlocked
    _config = cfg
    _unlocked = {}  # reset unlocked state when config changes
    return {"status": "ok", "config": _config}


@app.get("/api/problems")
def get_problems():
    """Return today's problems (without answers)."""
    problems = generate_daily_problems(
        num_problems=_config.num_problems,
        difficulty=_config.difficulty,
        day=date.today(),
        custom_salt=_config.custom_salt,
    )
    day_key = _today_key()
    unlocked = _unlocked.get(day_key, set())
    return {
        "date": day_key,
        "total": len(problems),
        "unlocked_count": len(unlocked),
        "safe_open": len(unlocked) == len(problems),
        "problems": [
            {
                "id": p.id,
                "question": p.question,
                "difficulty": p.difficulty,
                "unlocked": p.id in unlocked,
            }
            for p in problems
        ],
    }


@app.post("/api/verify")
def verify_answer(req: AnswerRequest):
    """Check a kid's answer. If correct, unlock that bar."""
    problems = generate_daily_problems(
        num_problems=_config.num_problems,
        difficulty=_config.difficulty,
        day=date.today(),
        custom_salt=_config.custom_salt,
    )
    day_key = _today_key()
    if day_key not in _unlocked:
        _unlocked[day_key] = set()

    if req.problem_id < 0 or req.problem_id >= len(problems):
        return {"correct": False, "message": "Invalid problem ID"}

    problem = problems[req.problem_id]
    if req.answer == problem.answer:
        _unlocked[day_key].add(req.problem_id)
        all_unlocked = len(_unlocked[day_key]) == len(problems)
        return {
            "correct": True,
            "message": "Correct! Bar unlocked!" if not all_unlocked else "SAFE IS OPEN!",
            "safe_open": all_unlocked,
            "unlocked_count": len(_unlocked[day_key]),
        }
    else:
        return {"correct": False, "message": "Try again!", "safe_open": False}


@app.post("/api/reset")
def reset_safe():
    """Lock the safe again (parent action)."""
    day_key = _today_key()
    _unlocked[day_key] = set()
    return {"status": "locked"}


# ---------------------------------------------------------------------------
# Serve the single-page UI
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_ui(request: Request):
    return SAFE_HTML


# ---------------------------------------------------------------------------
# Full self-contained HTML/CSS/JS UI
# ---------------------------------------------------------------------------
SAFE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Math Puzzle Safe</title>
<style>
  :root {
    --safe-bg: #3a3a3a;
    --safe-border: #222;
    --bar-locked: #c0392b;
    --bar-unlocked: #27ae60;
    --door-closed: #555;
    --door-open: #2d6b3f;
    --accent: #f39c12;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    color: #eee;
  }
  h1 { font-size: 2rem; margin-bottom: 4px; color: var(--accent); }
  .subtitle { color: #aaa; margin-bottom: 20px; font-size: 0.95rem; }

  /* ---------- safe container ---------- */
  .safe-wrapper {
    display: flex;
    gap: 30px;
    flex-wrap: wrap;
    justify-content: center;
    align-items: flex-start;
  }
  .safe {
    width: 360px;
    background: var(--safe-bg);
    border: 6px solid var(--safe-border);
    border-radius: 18px;
    padding: 24px 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,.5), inset 0 2px 4px rgba(255,255,255,.05);
    position: relative;
  }
  .safe-label {
    text-align: center;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #888;
    font-size: .75rem;
    margin-bottom: 16px;
  }

  /* ---------- bars ---------- */
  .bar-slot {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    gap: 10px;
  }
  .bar {
    height: 28px;
    flex: 1;
    border-radius: 6px;
    background: var(--bar-locked);
    transition: transform .6s cubic-bezier(.34,1.56,.64,1), background .4s;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: .8rem;
    color: rgba(255,255,255,.8);
    cursor: default;
    box-shadow: inset 0 -2px 4px rgba(0,0,0,.3);
  }
  .bar.unlocked {
    background: var(--bar-unlocked);
    transform: translateX(120px);
  }
  .bar-num {
    width: 26px;
    text-align: center;
    font-weight: 700;
    font-size: .85rem;
    color: var(--accent);
  }

  /* door status */
  .door-status {
    text-align: center;
    margin-top: 18px;
    padding: 12px;
    border-radius: 10px;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 1px;
    transition: all .4s;
  }
  .door-status.locked { background: rgba(192,57,43,.25); color: #e74c3c; }
  .door-status.open   { background: rgba(39,174,96,.25); color: #2ecc71; }

  /* ---------- problems panel ---------- */
  .problems {
    width: 380px;
  }
  .problem-card {
    background: rgba(255,255,255,.07);
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: all .3s;
  }
  .problem-card.solved {
    border-color: var(--bar-unlocked);
    background: rgba(39,174,96,.1);
  }
  .problem-card .question {
    font-size: 1.2rem;
    font-weight: 600;
    margin-bottom: 8px;
  }
  .problem-card .input-row {
    display: flex;
    gap: 8px;
  }
  .problem-card input {
    flex: 1;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,.2);
    background: rgba(0,0,0,.3);
    color: #fff;
    font-size: 1rem;
    outline: none;
  }
  .problem-card input:focus { border-color: var(--accent); }
  .problem-card button {
    padding: 8px 18px;
    border: none;
    border-radius: 8px;
    background: var(--accent);
    color: #000;
    font-weight: 700;
    cursor: pointer;
    font-size: .95rem;
    transition: background .2s;
  }
  .problem-card button:hover { background: #e67e22; }
  .problem-card .feedback {
    margin-top: 6px;
    font-size: .85rem;
    min-height: 1.2em;
  }
  .feedback.correct { color: #2ecc71; }
  .feedback.wrong   { color: #e74c3c; }

  /* ---------- config panel ---------- */
  .config-toggle {
    margin-top: 24px;
    background: none;
    border: 1px solid rgba(255,255,255,.15);
    color: #aaa;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: .85rem;
  }
  .config-toggle:hover { color: #fff; border-color: rgba(255,255,255,.3); }
  .config-panel {
    display: none;
    margin-top: 14px;
    background: rgba(255,255,255,.05);
    border-radius: 12px;
    padding: 18px;
    max-width: 500px;
    width: 100%;
  }
  .config-panel.visible { display: block; }
  .config-panel label { display: block; margin-bottom: 10px; font-size: .9rem; }
  .config-panel select, .config-panel input[type=number], .config-panel input[type=text] {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,.2);
    background: rgba(0,0,0,.3);
    color: #fff;
    font-size: .9rem;
    margin-left: 8px;
    width: 140px;
  }
  .config-panel .save-btn {
    margin-top: 10px;
    padding: 8px 24px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    color: #000;
    font-weight: 700;
    cursor: pointer;
  }

  /* celebration */
  .celebration {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    z-index: 999;
  }
  .celebration.active { display: block; }
  .confetti {
    position: absolute;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    animation: fall 2.5s ease-in forwards;
  }
  @keyframes fall {
    0%   { transform: translateY(-20px) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
  }
</style>
</head>
<body>

<h1>Math Puzzle Safe</h1>
<p class="subtitle">Solve each problem to slide a bar and unlock the safe!</p>

<div class="safe-wrapper">
  <!-- SAFE VISUAL -->
  <div class="safe">
    <div class="safe-label">Electronics Vault</div>
    <div id="bars-container"></div>
    <div id="door-status" class="door-status locked">LOCKED</div>
  </div>

  <!-- PROBLEMS -->
  <div class="problems" id="problems-container"></div>
</div>

<!-- PARENT CONFIG -->
<button class="config-toggle" onclick="toggleConfig()">Parent Settings</button>
<div class="config-panel" id="config-panel">
  <label>
    Number of bars (1-10):
    <input type="number" id="cfg-num" min="1" max="10" value="5">
  </label>
  <label>
    Difficulty:
    <select id="cfg-diff">
      <option value="easy">Easy (ages 5-7)</option>
      <option value="medium">Medium (ages 8-10)</option>
      <option value="hard">Hard (ages 11+)</option>
    </select>
  </label>
  <label>
    Daily secret word:
    <input type="text" id="cfg-salt" placeholder="family" value="family">
  </label>
  <button class="save-btn" onclick="saveConfig()">Save &amp; Reset Safe</button>
</div>

<div class="celebration" id="celebration"></div>

<script>
const API = '';

async function loadConfig() {
  const res = await fetch(API + '/api/config');
  const cfg = await res.json();
  document.getElementById('cfg-num').value = cfg.num_problems;
  document.getElementById('cfg-diff').value = cfg.difficulty;
  document.getElementById('cfg-salt').value = cfg.custom_salt;
}

async function loadProblems() {
  const res = await fetch(API + '/api/problems');
  const data = await res.json();
  renderBars(data);
  renderProblems(data);
  updateDoor(data);
}

function renderBars(data) {
  const c = document.getElementById('bars-container');
  c.innerHTML = '';
  data.problems.forEach((p, i) => {
    const slot = document.createElement('div');
    slot.className = 'bar-slot';
    const num = document.createElement('div');
    num.className = 'bar-num';
    num.textContent = (i + 1);
    const bar = document.createElement('div');
    bar.className = 'bar' + (p.unlocked ? ' unlocked' : '');
    bar.id = 'bar-' + p.id;
    bar.textContent = p.unlocked ? 'OPEN' : 'LOCKED';
    slot.appendChild(num);
    slot.appendChild(bar);
    c.appendChild(slot);
  });
}

function renderProblems(data) {
  const c = document.getElementById('problems-container');
  c.innerHTML = '';
  data.problems.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'problem-card' + (p.unlocked ? ' solved' : '');
    card.id = 'card-' + p.id;

    if (p.unlocked) {
      card.innerHTML = `
        <div class="question">Bar ${i+1}: ${p.question} = ?</div>
        <div class="feedback correct">Solved!</div>`;
    } else {
      card.innerHTML = `
        <div class="question">Bar ${i+1}: ${p.question} = ?</div>
        <div class="input-row">
          <input type="number" id="input-${p.id}" placeholder="Answer"
                 onkeydown="if(event.key==='Enter')submitAnswer(${p.id})">
          <button onclick="submitAnswer(${p.id})">Unlock</button>
        </div>
        <div class="feedback" id="fb-${p.id}"></div>`;
    }
    c.appendChild(card);
  });
}

function updateDoor(data) {
  const el = document.getElementById('door-status');
  if (data.safe_open) {
    el.className = 'door-status open';
    el.textContent = 'SAFE IS OPEN!';
    celebrate();
  } else {
    el.className = 'door-status locked';
    el.textContent = `LOCKED  (${data.unlocked_count} / ${data.total} bars)`;
  }
}

async function submitAnswer(pid) {
  const input = document.getElementById('input-' + pid);
  const val = parseInt(input.value, 10);
  if (isNaN(val)) return;

  const res = await fetch(API + '/api/verify', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({problem_id: pid, answer: val}),
  });
  const result = await res.json();
  const fb = document.getElementById('fb-' + pid);

  if (result.correct) {
    fb.textContent = 'Correct!';
    fb.className = 'feedback correct';
    // refresh entire UI to show bar slide
    setTimeout(loadProblems, 300);
  } else {
    fb.textContent = 'Try again!';
    fb.className = 'feedback wrong';
    input.value = '';
    input.focus();
    // shake animation
    const card = document.getElementById('card-' + pid);
    card.style.animation = 'none';
    card.offsetHeight; // reflow
    card.style.animation = 'shake .4s';
  }
}

function celebrate() {
  const el = document.getElementById('celebration');
  el.innerHTML = '';
  el.classList.add('active');
  const colors = ['#e74c3c','#f39c12','#2ecc71','#3498db','#9b59b6','#1abc9c'];
  for (let i = 0; i < 80; i++) {
    const c = document.createElement('div');
    c.className = 'confetti';
    c.style.left = Math.random() * 100 + '%';
    c.style.background = colors[Math.floor(Math.random() * colors.length)];
    c.style.animationDelay = (Math.random() * 1.5) + 's';
    c.style.width = (6 + Math.random() * 8) + 'px';
    c.style.height = (6 + Math.random() * 8) + 'px';
    el.appendChild(c);
  }
  setTimeout(() => el.classList.remove('active'), 3500);
}

function toggleConfig() {
  document.getElementById('config-panel').classList.toggle('visible');
}

async function saveConfig() {
  const cfg = {
    num_problems: parseInt(document.getElementById('cfg-num').value, 10),
    difficulty: document.getElementById('cfg-diff').value,
    custom_salt: document.getElementById('cfg-salt').value || 'family',
  };
  await fetch(API + '/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(cfg),
  });
  document.getElementById('config-panel').classList.remove('visible');
  loadProblems();
}

// Init
loadConfig();
loadProblems();
</script>

<style>
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-8px); }
    75% { transform: translateX(8px); }
  }
</style>
</body>
</html>
"""
