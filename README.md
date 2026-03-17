# Mental Arithmetic Speed Trainer

This project is a local mental arithmetic speed trainer built as a minimal, fast web app for arithmetic drill practice.

It includes three modes:

- Interview Mode: typed-answer, interview-style arithmetic mode with an 8-minute, 80-question format
- Practice Mode: the same generator with the existing optional multiple-choice flow
- Zetamac Mode: a local practice implementation inspired by public arithmetic-drill behavior

The app is keyboard-first, keeps timing per question, stores completed runs in SQLite, and now shows lightweight timing analytics after each run.

## Run locally

Mac / Linux:

```bash
./run.sh
```

Windows PowerShell:

```powershell
.\run.ps1
```

Open:

```text
http://127.0.0.1:8000
```

## Presets

The preset definitions live in [app/services/config.py](/Users/arjunkapoor/VScode/app/services/config.py).

Public presets:

- `interview_default`
- `interview_balanced`
- `practice_default`
- `practice_easy`

Legacy preset names are still accepted as aliases so older local configs do not break.

The default interview preset is intentionally harder by default:

- substantially more decimal arithmetic
- frequent missing-variable questions
- tougher integer multiplication and division
- more carry and borrow pressure in integer and decimal questions

Question families include:

- integer addition
- integer subtraction
- integer multiplication
- integer division
- decimal arithmetic
- missing-variable equations

Division questions are generated backwards where needed so answers stay clean and mentally solvable.

To override settings locally, create `data/question_settings.json`. Example:

```json
{
  "preset_name": "interview_default",
  "mode": "assessment",
  "addition_weight": 15,
  "subtraction_weight": 17,
  "multiplication_weight": 18,
  "division_weight": 14,
  "decimal_weight": 42,
  "missing_variable_weight": 28
}
```

## Zetamac Mode

Zetamac Mode is a typed-input drill mode with:

- Enter-to-submit input
- immediate question transitions
- continuous timer behavior
- instant score updates
- configurable duration and per-operation ranges

Generation rules:

- addition samples directly from the configured ranges
- subtraction is generated backwards so answers stay clean
- multiplication samples directly from the configured ranges
- division is generated backwards so answers stay exact

## Results analytics

After each run, the results screen shows:

- average response time
- median response time
- fastest response
- slowest response
- average response time by operation
- accuracy by operation
- question-level history with response times

Completed runs are stored in SQLite at `data/leaderboard.db`.

## Project structure

- `app/main.py`: FastAPI app setup and static file serving
- `app/api/routes.py`: start, answer, state, abort, finish, and leaderboard routes
- `app/models/game.py`: session state, summaries, and analytics helpers
- `app/services/config.py`: presets, aliases, and Zetamac defaults
- `app/services/generator.py`: arithmetic question generation
- `app/services/session_manager.py`: answer handling, timing, scoring, and finalization
- `app/services/storage.py`: SQLite persistence
- `app/static/`: minimal HTML, CSS, and vanilla JavaScript frontend
