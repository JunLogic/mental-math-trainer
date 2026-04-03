from __future__ import annotations

import argparse
import os
import threading
import webbrowser

from app.runtime import DATA_DIR_ENV_VAR, resolve_data_dir


def _open_browser(url: str, delay: float = 1.0) -> None:
    import time
    time.sleep(delay)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mental Arithmetic Speed Trainer")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser")
    args = parser.parse_args()

    os.environ.setdefault(DATA_DIR_ENV_VAR, str(resolve_data_dir()))

    url = f"http://127.0.0.1:{args.port}"

    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    print(f"Starting Mental Math Trainer at {url}")
    print("Press Ctrl+C to stop.\n")

    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
