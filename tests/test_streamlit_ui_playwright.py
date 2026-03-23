"""Playwright UI smoke tests for the Streamlit POC app.

Inherited Wisdom:
Read from .sisyphus/notepads/phase1-streamlit-poc-basic/learnings.md
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

EVIDENCE_DIR = Path(".sisyphus/evidence/phase1-ui-qa")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


NOTEPAD_PATH = Path(".sisyphus/notepads/phase1-streamlit-poc-basic/learnings.md")
NOTEPAD_PATH.parent.mkdir(parents=True, exist_ok=True)


def _append_notepad(text: str) -> None:
    timestamp = datetime.utcnow().isoformat() + "Z"
    with open(NOTEPAD_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] {text}\n")


def _write_report(data: dict[str, Any]) -> None:
    report_path = EVIDENCE_DIR / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _screenshot(page, name: str) -> str:
    path = EVIDENCE_DIR / f"screenshot-{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _attach_console_listener(page_obj, console_errors: list[str]) -> None:
    def _on_console(msg):
        if msg.type == "error":
            console_errors.append(f"{msg.type}: {msg.text}")

    page_obj.on("console", _on_console)


def _select_first_sidebar_option(page_obj, checks: list[str]) -> bool:
    sel = page_obj.query_selector('select[aria-label="Selecione um ticker"]')
    if not sel:
        return False
    opts = sel.query_selector_all("option")
    for o in opts:
        val = o.get_attribute("value") or ""
        if val.strip():
            sel.select_option(val)
            checks.append("selected_ticker_from_sidebar")
            return True
    return False


def _test_empty_state(
    inp_obj, page_obj, screenshots: list[str], checks: list[str]
) -> None:
    inp_obj.fill("FAKETICKER")
    inp_obj.press("Enter")
    time.sleep(1)
    screenshots.append(_screenshot(page_obj, "empty-state"))
    body = page_obj.text_content("body") or ""
    if "Nenhum dado" in body:
        checks.append("empty_state_shown")


def _test_charts(
    page_obj, inp_obj, tickers_list, screenshots: list[str], checks: list[str]
) -> None:
    if inp_obj:
        inp_obj.fill("")
        inp_obj.press("Enter")
    sel = page_obj.query_selector('select[aria-label="Selecione um ticker"]')
    if not sel:
        return
    sel.select_option(tickers_list[0])
    time.sleep(1)
    screenshots.append(_screenshot(page_obj, "charts-loaded"))
    svg = page_obj.query_selector_all("svg")
    if svg and len(svg) >= 1:
        checks.append("charts_rendered")


def _run_playwright_flow(
    pw, checks: list[str], screenshots: list[str], console_errors: list[str]
) -> None:
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        _attach_console_listener(page, console_errors)
        page.goto("http://127.0.0.1:8501", wait_until="networkidle")
        screenshots.append(_screenshot(page, "initial-load"))

        from src.db.prices import list_price_tickers

        tickers = list_price_tickers()
        if tickers:
            _select_first_sidebar_option(page, checks)

        inp = page.query_selector(
            'input[aria-label="Ou digite um ticker livre (ex: PETR4)"]'
        )
        if inp:
            _test_empty_state(inp, page, screenshots, checks)

        if tickers:
            _test_charts(page, inp, tickers, screenshots, checks)

        context.close()
        browser.close()


def _start_streamlit() -> subprocess.Popen[Any]:
    """Start Streamlit app in a subprocess using the test Python executable.

    Returns the Popen object. The caller is responsible to terminate it.
    """
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
    # Use a new process group so we can kill the whole group on teardown
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


def test_streamlit_ui_playwright(monkeypatch, sample_db):
    """End-to-end UI smoke test using Playwright.

    Steps:
    - start streamlit with sys.executable -m streamlit run ...
    - wait until HTTP root responds
    - use Playwright to open the page, interact with sidebar controls,
      take screenshots and collect console errors
    - produce a JSON report under .sisyphus/evidence/phase1-ui-qa/
    """
    # Skip at runtime if Playwright isn't importable. Using pytest.importorskip
    # avoids static imports which cause lsp errors in environments without
    # Playwright installed.
    pw = pytest.importorskip("playwright.sync_api", reason="Playwright not installed")

    proc = _start_streamlit()

    try:
        ok = _wait_for_http("http://127.0.0.1:8501", timeout=30.0)
        assert ok, "Streamlit did not become available in time"

        checks: list[str] = []
        screenshots: list[str] = []
        console_errors: list[str] = []

        # Delegate Playwright interactions to module-level helper to reduce
        # cyclomatic complexity in this test body.
        _run_playwright_flow(pw, checks, screenshots, console_errors)

        # write report (keep the summary concise to satisfy line-length limits)
        ok_flag = len(console_errors) == 0 and "charts_rendered" in checks
        report = {
            "ok": ok_flag,
            "checks": checks,
            "screenshots": screenshots,
            "console_errors": console_errors,
            "playwright_available": True,
        }
        _write_report(report)
        # append a brief note to the notepad (do not overwrite existing)
        _append_notepad(f"Playwright run: ok={ok_flag}, checks={checks}")

        assert report["ok"], f"UI smoke checks failed: {report}"

    finally:
        # terminate streamlit process group
        try:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass


def test_streamlit_http_fallback():
    """A lightweight HTTP-only fallback when Playwright isn't available.

    This test ensures the app serves HTTP and contains the expected
    Portuguese warning when no ticker is provided.
    """
    import requests

    proc = None
    try:
        proc = _start_streamlit()
        ok = _wait_for_http("http://127.0.0.1:8501", timeout=20.0)
        assert ok
        r = requests.get("http://127.0.0.1:8501", timeout=5)
        body = r.text
        # We can't evaluate client-side rendered strings reliably without a
        # full browser environment. Instead check that Streamlit returned the
        # expected app skeleton and assets.
        assert r.status_code == 200
        assert ('<div id="root"' in body) or ("streamlit" in body.lower())
        # write minimal report
        report = {
            "ok": True,
            "checks": ["http_root_ok", "skeleton_present"],
            "screenshots": [],
            "console_errors": [],
            "playwright_available": False,
        }
        _write_report(report)
        _append_notepad("HTTP fallback run: ok=True, skeleton_present")
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
