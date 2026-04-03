# Mental Arithmetic Speed Trainer

A local mental arithmetic speed trainer with interview-style, practice, and Zetamac-inspired modes. Keyboard-first, tracks timing per question, stores runs in SQLite, and shows analytics after each run.

## Quick Start

### Option 1: Download (no Python required)

Download the latest build for your platform from [Releases](../../releases), then run it:

```bash
# Mac / Linux
./mental-math-trainer

# Windows — double-click mental-math-trainer-windows.exe
```

The app opens in your browser automatically at `http://127.0.0.1:8000`.

> **Mac users:** If you see an "unidentified developer" warning, right-click the file and select Open, or run: `xattr -d com.apple.quarantine ./mental-math-trainer-macos`

### Option 2: Run from source

Mac / Linux:

```bash
./run.sh
```

Windows (double-click `run.bat`, or in PowerShell):

```powershell
.\run.ps1
```

### Option 3: pip install

```bash
pip install .
mental-math-trainer
```

Use `--port 9000` to change the port, or `--no-browser` to skip auto-opening.

## Modes

- **Interview Mode** — typed-answer, 8-minute / 80-question format
- **Practice Mode** — same generator with optional multiple-choice
- **Zetamac Mode** — timed drill with configurable duration and per-operation ranges

Adaptive Difficulty adjusts question difficulty during a run based on recent response time and accuracy. It is presented as a local training aid.

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

When running from source, you can override settings with `data/question_settings.json`. Installed or bundled runs use a per-user app data directory by default, and `MATH_TRAINER_DATA_DIR` can override the location. Example:

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

When Adaptive Difficulty is enabled, the results screen also shows the target pace plus initial, final, peak, and average difficulty for that run.

Completed runs are stored in `leaderboard.db` under the active app data directory. From source that defaults to `data/leaderboard.db`; installed or bundled runs use a per-user app data directory unless `MATH_TRAINER_DATA_DIR` is set.

## Project structure

- `app/main.py`: FastAPI app setup and static file serving
- `app/api/routes.py`: start, answer, state, abort, finish, and leaderboard routes
- `app/models/game.py`: session state, summaries, and analytics helpers
- `app/services/config.py`: presets, aliases, and Zetamac defaults
- `app/services/generator.py`: arithmetic question generation
- `app/services/session_manager.py`: answer handling, timing, scoring, and finalization
- `app/services/storage.py`: SQLite persistence
- `app/static/`: minimal HTML, CSS, and vanilla JavaScript frontend
