# 80 in 8 Simulator

This project is a local web app that simulates the publicly reported format of Optiver's "80 in 8" mental-math screen as closely as possible without claiming to reproduce any proprietary internals. It is intentionally minimal, fast, plain, and assessment-like.

The app now supports three local practice modes:

- Optiver-style typed assessment mode
- Training mode with optional multiple choice
- Zetamac-inspired arithmetic drill mode

All modes keep the UI minimal, keyboard-first, and low-latency.

Decimal and missing-variable frequencies are configurable because public reports are inconsistent about the exact question mix. The default preset is a harder `user_observed` profile in `app/services/config.py`, with substantially more decimal and missing-variable questions than the old consensus-style mix.

## Setup

Start the app with one command.

Mac / Linux:

```bash
./run.sh
```

Windows PowerShell:

```powershell
.\run.ps1
```

These commands:

- create `.venv` if it does not exist
- install packages from `requirements.txt`
- launch the FastAPI server with reload enabled

Open the app in your browser:

```text
http://127.0.0.1:8000
```

## Presets and calibration

The preset definitions live in [app/services/config.py](/Users/arjunkapoor/VScode/app/services/config.py). The app ships with four presets:

- `consensus`
- `user_observed`
- `training_easy`
- `training_hard`

`user_observed` is the default and is meant to feel materially harder. Its default weights are:

- `addition_weight = 18`
- `subtraction_weight = 16`
- `multiplication_weight = 14`
- `division_weight = 12`
- `decimal_weight = 35`
- `missing_variable_weight = 20`

The app normalizes them automatically before generation:

- Base operation is chosen from addition, subtraction, multiplication, and division weights.
- Decimal mode is then applied with an independent Bernoulli draw using the normalized `decimal_weight`.
- Missing-variable mode is then applied with an independent Bernoulli draw using the normalized `missing_variable_weight`.

Each preset also carries its own operand difficulty ranges so the app can tune awkward borrowing, larger multiplication, and cleaner but less obvious decimal division without overengineering the generator.

To override these locally, create `data/question_settings.json` with any subset of the supported keys:

```json
{
  "preset_name": "user_observed",
  "mode": "assessment",
  "addition_weight": 18,
  "subtraction_weight": 16,
  "multiplication_weight": 14,
  "division_weight": 12,
  "decimal_weight": 35,
  "missing_variable_weight": 20
}
```

## Zetamac Mode

Zetamac mode is a separate typed-input mode inspired by the publicly visible Zetamac arithmetic format. It uses one question at a time, submits on Enter, advances immediately, tracks per-question timing, and scores by `number correct`.

The built-in Zetamac settings support:

- durations of `30`, `60`, `120`, `300`, and `600` seconds
- enable/disable toggles for addition, subtraction, multiplication, and division
- configurable left/right operand ranges for each operation

Generation rules:

- addition samples directly from the configured ranges
- subtraction is generated as reversed addition so the answer stays clean
- multiplication samples directly from the configured ranges
- division is generated as reversed multiplication so the answer is exact

Zetamac settings live under `zetamac_settings` in the backend config/request payload. Example:

```json
{
  "mode": "zetamac",
  "zetamac_settings": {
    "duration_seconds": 120,
    "operations": {
      "addition": true,
      "subtraction": true,
      "multiplication": true,
      "division": true
    },
    "ranges": {
      "addition": { "left_min": 10, "left_max": 99, "right_min": 10, "right_max": 99 },
      "subtraction": { "left_min": 10, "left_max": 99, "right_min": 10, "right_max": 99 },
      "multiplication": { "left_min": 2, "left_max": 12, "right_min": 2, "right_max": 12 },
      "division": { "left_min": 2, "left_max": 12, "right_min": 2, "right_max": 12 }
    }
  }
}
```

## Scoring and storage

- Optiver mode: `correct - incorrect`
- Training mode: `correct - incorrect`
- Zetamac mode: `score = correct`

Completed runs are stored in SQLite at `data/leaderboard.db`.

The app persists:

- run-level summary rows in `runs`
- per-question history rows in `run_questions`

For Zetamac runs, per-question rows include prompt, submitted answer, correctness, response time, and operation type.

## Architecture

- `app/main.py`: FastAPI app setup, lifespan, static file serving.
- `app/api/routes.py`: API routes for starting, answering, finishing, session state, and leaderboard.
- `app/models/game.py`: Internal session and question data structures.
- `app/services/config.py`: Optiver presets plus Zetamac defaults and validation.
- `app/services/generator.py`: Optiver/training question generation and Zetamac range-based arithmetic generation.
- `app/services/session_manager.py`: Mode-aware session state, typed input evaluation, scoring, and finalization.
- `app/services/storage.py`: SQLite persistence for completed runs and per-question history.
- `app/static/`: Minimal HTML, CSS, and vanilla JavaScript frontend with Optiver, Training, and Zetamac modes.
