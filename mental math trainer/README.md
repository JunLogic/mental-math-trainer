# Mental Arithmetic Speed Trainer

A local mental arithmetic speed trainer with interview-style, practice, and Zetamac-inspired modes. Keyboard-first, tracks timing per question, stores runs in SQLite, and shows analytics after each run.

This repository now contains two complementary apps:

- **Mental Math Trainer** — the full FastAPI, SQLite, analytics, exports, adaptive generation, and ML-artifact-driven training app.
- **Zetamac Lite** — a standalone static PWA in `lite/` for phone-first score practice with no Python, no backend, and no database.

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
Use `--host 0.0.0.0` only when you want to make the app reachable from another device on the same trusted network.

## Modes

- **Interview Mode** — typed-answer, 8-minute / 80-question format
- **Practice Mode** — same generator with optional multiple-choice
- **Zetamac Mode** — timed drill with configurable duration and per-operation ranges
- **Zetamac Optimization** — score-throughput training that keeps forward arithmetic first

Adaptive Difficulty adjusts question difficulty during a run based on recent response time and accuracy. It is presented as a local training aid.

## Export History

The **Export History** button on the start and results screens downloads saved run/question history as `mental_math_history_YYYYMMDD_HHMMSS.json` from `GET /api/history/export`. If no runs have been saved, the UI reports that there is no history to export.

The **History** button opens a lightweight recent-runs panel backed by `GET /api/history/recent`. It shows mode, score, accuracy, average response time, and timestamp. Use Export History for the full per-question dataset.

## Phone and iPad Use

Typed-answer modes include an optional **On-Screen Keypad** setting. It shows large touch-friendly buttons for digits, decimal point where applicable, minus sign, backspace, clear, and submit. Physical keyboard input continues to work.

To use the app from an iPhone or iPad on the same Wi-Fi:

```bash
./run.sh --host 0.0.0.0 --no-browser
```

Then find your computer's local IP address and open `http://YOUR_LOCAL_IP:8000` on the phone or tablet. Keep this on a trusted network; the local SQLite history stays on the computer running the FastAPI server.

Examples for finding the local IP address:

```bash
# macOS
ipconfig getifaddr en0

# Windows PowerShell
Get-NetIPAddress -AddressFamily IPv4
```

## Zetamac Lite

`lite/` is a separate static PWA for fast phone/iPad play. It is HTML/CSS/JavaScript only, has no FastAPI dependency, makes no API calls, and includes addition, subtraction, multiplication, exact division, configurable run duration, score/streak tracking, hardware keyboard support, a large touch keypad, offline caching, and home-screen metadata.

To test locally:

```bash
python3 -m http.server 8080 --directory lite
```

Then open `http://127.0.0.1:8080`.

The GitHub Actions workflow at `.github/workflows/pages-lite.yml` publishes only `lite/` to GitHub Pages. It does not publish or run the FastAPI app. After Pages is enabled for the repository, the deployed Lite app will be available at:

```text
https://<username>.github.io/<repo>/
```

GitHub Pages cannot host the full Mental Math Trainer because that app requires Python/FastAPI and SQLite. For the full app, run locally/LAN with `--host 0.0.0.0` or deploy to a backend-capable host such as Render, Fly.io, Railway, or a VPS.

## Presets

The preset definitions live in [app/services/config.py](app/services/config.py).

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
- `lite/`: standalone static Zetamac Lite PWA for GitHub Pages
