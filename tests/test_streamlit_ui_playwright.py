"""UI smoke tests for the Streamlit POC app.

These tests start the Streamlit app as a real HTTP server and validate
its behavior via HTTP requests. This avoids the cross-thread monkeypatch
complexity of streamlit.testing (AppTest runs app in a threading.Thread,
making module-level patches ineffective).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from datetime import timezone as tz
from pathlib import Path
from typing import Any

EVIDENCE_DIR = Path(".sisyphus/evidence/phase1-ui-qa")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

NOTEPAD_PATH = Path(".sisyphus/notepads/phase1-streamlit-poc-basic/learnings.md")
NOTEPAD_PATH.parent.mkdir(parents=True, exist_ok=True)


def _append_notepad(text: str) -> None:
    ts = datetime.now(tz.utc).isoformat().replace("+00:00", "Z")
    with open(NOTEPAD_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{ts}] {text}\n")


def _write_report(data: dict[str, Any]) -> None:
    with open(EVIDENCE_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _start_streamlit() -> subprocess.Popen[Any]:
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "src/apps/streamlit_poc.py",
        "--server.port",
        "8501",
        "--server.address",
        "127.0.0.1",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    return proc


def _wait_for_http(url: str, timeout: float = 20.0) -> bool:
    import requests

    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def test_streamlit_http_smoke():
    import requests

    proc = None
    try:
        proc = _start_streamlit()
        ok = _wait_for_http("http://127.0.0.1:8501", timeout=30.0)
        assert ok, "Streamlit did not become available in time"

        r = requests.get("http://127.0.0.1:8501", timeout=10)
        assert r.status_code == 200
        html = r.text
        assert ('<div id="root"' in html) or ("streamlit" in html.lower())

        report = {
            "ok": True,
            "checks": ["http_root_ok", "skeleton_present"],
            "screenshots": [],
            "console_errors": [],
            "playwright_available": False,
        }
        _write_report(report)
        _append_notepad(
            "HTTP smoke: ok=True, checks=['http_root_ok','skeleton_present']"
        )
    finally:
        if proc:
            try:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
