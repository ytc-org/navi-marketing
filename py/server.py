#!/usr/bin/env python3
"""Content Ops Workflow Server

A lightweight HTTP server that exposes each content workflow as a POST endpoint.
Designed to be called by Claude Code running on the same Mac via http://localhost:8100.

Async job model:
  POST /api/<workflow>      -> returns {"job_id": "..."} immediately; workflow runs in a background thread.
  GET  /api/jobs/<job_id>   -> returns {"status": "pending|running|done|error", "result": ..., "error": ...}

  The async pattern keeps each curl fast and lets Claude show progress
  to the user. Workflows take 2–8 minutes; poll /api/jobs/<id> every
  15–30 seconds until status is "done" or "error".

Endpoints:
  POST /api/page_audit
  POST /api/refresh_recommendations
  POST /api/rewrite_draft
  POST /api/metadata_suggestions
  POST /api/internal_link_recommendations
  POST /api/net_new_content_brief
  GET  /api/jobs/<job_id>
  GET  /api/health
  GET  /api/workflows

Usage:
  python3 py/server.py              # Starts on port 8100, binds 127.0.0.1
  python3 py/server.py --port 9000  # Custom port

The server loads .env from the project root on startup.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse


# ─── Startup checks ──────────────────────────────────────────────────────────
# Run these before anything else so users get clear errors, not tracebacks.

def _check_python_version():
    if sys.version_info < (3, 10):
        print(f"ERROR: Python 3.10+ is required. You're running Python {sys.version}")
        print()
        print("Fix: Install Python 3.10 or newer from https://python.org/downloads")
        sys.exit(1)


def _check_dependencies():
    missing = []
    for package, import_name in [
        ("anthropic", "anthropic"),
        ("pydantic", "pydantic"),
        ("python-dotenv", "dotenv"),
        ("pyyaml", "yaml"),
        ("firecrawl-py", "firecrawl"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package)

    if missing:
        print("ERROR: Missing Python packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print()
        print("Fix: Run this command in Terminal, then try again:")
        print()
        print(f"  python3 -m pip install {' '.join(missing)}")
        print()
        print("Or install everything at once:")
        print(f"  python3 -m pip install -r py/requirements.txt")
        sys.exit(1)


def _check_env_file(project_root: Path):
    env_path = project_root / ".env"
    if not env_path.is_file():
        print("ERROR: No .env file found.")
        print()
        print("Fix: Create a .env file in the project root with your API keys:")
        print(f"  1. Copy the example:  cp .env.example .env")
        print(f"  2. Open it:           open .env")
        print(f"  3. Paste your Anthropic API key after ANTHROPIC_API_KEY=")
        print()
        print(f"Expected location: {env_path}")
        sys.exit(1)


def _check_api_keys():
    issues = []

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        issues.append(("ANTHROPIC_API_KEY", "Required. Get one at https://console.anthropic.com/"))
    elif not anthropic_key.startswith("sk-"):
        issues.append(("ANTHROPIC_API_KEY", f"Doesn't look right (starts with '{anthropic_key[:8]}...'). Should start with 'sk-'."))

    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not firecrawl_key:
        issues.append(("FIRECRAWL_API_KEY", "Missing (optional but needed for web scraping). Get one at https://firecrawl.dev"))

    if issues:
        has_required = any(name == "ANTHROPIC_API_KEY" for name, _ in issues)
        label = "ERROR" if has_required else "WARNING"
        print(f"{label}: API key issues found in .env:")
        for name, msg in issues:
            print(f"  {name}: {msg}")
        print()
        if has_required:
            print("Fix: Open your .env file and add the missing key(s).")
            sys.exit(1)
        else:
            print("The server will start, but some features may not work.")
            print()


def _check_artifacts(project_root: Path):
    artifacts_dir = project_root / "artifacts"
    if not artifacts_dir.is_dir():
        print("WARNING: No artifacts/ directory found. Workflows won't have brand context.")
        print(f"Expected: {artifacts_dir}")
        print()
        return

    md_files = list(artifacts_dir.glob("*.md"))
    if not md_files:
        print("NOTE: artifacts/ is empty. This is normal on first run —")
        print("      Claude will populate it from Google Drive before each workflow.")
        print()


# ─── Server ───────────────────────────────────────────────────────────────────

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "py"))


# --- Registry of available workflows ---

WORKFLOWS: dict[str, dict] = {
    "page_audit": {
        "description": "Audit a page against brand artifacts, competitors, and search intent",
        "module": "workflows.page_audit",
        "function": "run",
    },
    "refresh_recommendations": {
        "description": "Generate prioritized refresh recommendations for a page",
        "module": "workflows.refresh_recommendations",
        "function": "run",
    },
    "rewrite_draft": {
        "description": "Draft a refreshed version of a page or section",
        "module": "workflows.rewrite_draft",
        "function": "run",
    },
    "metadata_suggestions": {
        "description": "Generate title tags, meta descriptions, and heading guidance",
        "module": "workflows.metadata_suggestions",
        "function": "run",
    },
    "internal_link_recommendations": {
        "description": "Identify internal linking opportunities for a page",
        "module": "workflows.internal_link_recommendations",
        "function": "run",
    },
    "net_new_content_brief": {
        "description": "Create a content brief for a new article or page (optionally drafts the full article when write_article=true)",
        "module": "workflows.net_new_content_brief",
        "function": "run",
    },
}


def import_workflow(name: str):
    """Dynamically import a workflow module and return its run function."""
    info = WORKFLOWS[name]
    module = __import__(info["module"], fromlist=[info["function"]])
    return getattr(module, info["function"])


# --- Job store (in-memory, survives only until server restart) ---

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_create(workflow_name: str, topic: str) -> str:
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "workflow": workflow_name,
            "topic": topic,
            "status": "pending",
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
    return job_id


def _job_update(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def _job_get(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _run_workflow_in_background(job_id: str, workflow_name: str, workflow_input) -> None:
    """Executed in a daemon thread. Updates the job store with result or error."""
    _job_update(job_id, status="running", started_at=_now_iso())
    short = job_id[:8]
    print(f"\n  {_dim('→ dispatch')}  {_cyan(workflow_name)}  {_dim(f'· job {short}')}")
    try:
        run_fn = import_workflow(workflow_name)
        result = run_fn(workflow_input)
        _job_update(
            job_id,
            status="done",
            finished_at=_now_iso(),
            result=result.model_dump(),
        )
        print(f"  {_green('✓ completed')}  {_cyan(workflow_name)}  {_dim(f'· job {short}')}\n")
    except Exception as e:
        traceback.print_exc()
        _job_update(
            job_id,
            status="error",
            finished_at=_now_iso(),
            error=str(e),
        )
        print(f"  {_yellow('✗ failed')}     {_cyan(workflow_name)}  {_dim(f'· job {short}')}  {_yellow(str(e))}\n")


class WorkflowHandler(BaseHTTPRequestHandler):
    """HTTP request handler for workflow endpoints."""

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")

        if path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return

        if path == "/api/workflows":
            self._send_json(200, {
                "workflows": {
                    name: info["description"]
                    for name, info in WORKFLOWS.items()
                }
            })
            return

        # /api/jobs/<job_id>
        if path.startswith("/api/jobs/"):
            job_id = path[len("/api/jobs/"):]
            job = _job_get(job_id)
            if not job:
                self._send_json(404, {"error": f"Unknown job_id: {job_id}"})
                return
            self._send_json(200, job)
            return

        self._send_json(404, {"error": f"Not found: {path}"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")

        # Extract workflow name from /api/<workflow_name>
        if not path.startswith("/api/"):
            self._send_json(404, {"error": f"Not found: {path}"})
            return

        workflow_name = path[len("/api/"):]

        if workflow_name not in WORKFLOWS:
            self._send_json(404, {
                "error": f"Unknown workflow: {workflow_name}",
                "available": list(WORKFLOWS.keys()),
            })
            return

        # Parse request body
        try:
            body = self._read_body()
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return

        # Validate input
        try:
            from lib.validation import WorkflowInput
            workflow_input = WorkflowInput(**data)
        except Exception as e:
            self._send_json(422, {"error": f"Invalid input: {e}"})
            return

        # Create a job and dispatch to a background thread
        job_id = _job_create(workflow_name, workflow_input.topic)
        thread = threading.Thread(
            target=_run_workflow_in_background,
            args=(job_id, workflow_name, workflow_input),
            daemon=True,
            name=f"wf-{workflow_name}-{job_id[:8]}",
        )
        thread.start()

        # Respond immediately with the job_id
        self._send_json(202, {
            "job_id": job_id,
            "status": "pending",
            "poll_url": f"/api/jobs/{job_id}",
            "hint": "Poll GET /api/jobs/<job_id> every 15–30s until status is 'done' or 'error'.",
        })

    def log_message(self, format, *args):
        """Suppress default access logging — we do our own."""
        pass


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a separate thread.

    Required so that GET /api/jobs/<id> polling isn't blocked by in-flight
    POSTs. (The workflow itself already runs in a background thread, but
    without ThreadingMixIn, the stdlib HTTPServer serializes even the quick
    polling GETs behind any slow request.)
    """
    daemon_threads = True
    allow_reuse_address = True


BANNER = r"""
   ╔══════════════════════════════════════════════════════════════╗
   ║                                                              ║
   ║     ███╗   ██╗ █████╗ ██╗   ██╗██╗                           ║
   ║     ████╗  ██║██╔══██╗██║   ██║██║     content ops           ║
   ║     ██╔██╗ ██║███████║██║   ██║██║     workflow server       ║
   ║     ██║╚██╗██║██╔══██║╚██╗ ██╔╝██║                           ║
   ║     ██║ ╚████║██║  ██║ ╚████╔╝ ██║     port 8100             ║
   ║     ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝  ╚═╝                           ║
   ║                                                              ║
   ╚══════════════════════════════════════════════════════════════╝
"""

# ANSI styles — only applied when stdout is a TTY
_IS_TTY = sys.stdout.isatty()
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _IS_TTY else s
def _cyan(s):  return _c("36", s)
def _green(s): return _c("32;1", s)
def _dim(s):   return _c("2", s)
def _bold(s):  return _c("1", s)
def _yellow(s): return _c("33", s)


def main() -> None:
    # ── Banner ────────────────────────────────────────────────────────────
    print(_cyan(BANNER))

    # ── Pre-flight checks ─────────────────────────────────────────────────
    print(_bold("  Pre-flight checks"))
    print(_dim("  ────────────────────────────────────────────────"))

    _check_python_version()
    print(f"    {_green('✓')} Python {sys.version.split()[0]}")

    _check_dependencies()
    print(f"    {_green('✓')} All dependencies installed")

    _check_env_file(PROJECT_ROOT)
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    print(f"    {_green('✓')} .env loaded")

    _check_api_keys()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    print(f"    {_green('✓') if anthropic_key else _yellow('!')} Anthropic API key {'configured' if anthropic_key else 'MISSING'}")
    print(f"    {_green('✓') if firecrawl_key else _yellow('!')} Firecrawl API key {'configured' if firecrawl_key else 'not set (scraping disabled)'}")

    _check_artifacts(PROJECT_ROOT)
    artifact_count = len(list((PROJECT_ROOT / "artifacts").glob("*.md"))) if (PROJECT_ROOT / "artifacts").is_dir() else 0
    print(f"    {_green('✓')} Artifacts: {artifact_count} file(s) in artifacts/")
    print()

    # ── Start server ──────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Content Ops Workflow Server")
    parser.add_argument("--port", type=int, default=8100, help="Port to listen on (default: 8100)")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1 — loopback only, safest)")
    args = parser.parse_args()

    try:
        server = ThreadingHTTPServer((args.host, args.port), WorkflowHandler)
    except OSError as e:
        if "Address already in use" in str(e):
            print(_yellow(f"  ✗ Port {args.port} is already in use."))
            print()
            print("  The server is probably already running in another Terminal window.")
            print("  Options:")
            print(f"    1. Use the existing server — it's already at http://localhost:{args.port}")
            print(f"    2. Find and stop the other process, then run this again")
            print(f"    3. Start on a different port:  python3 py/server.py --port 8200")
            sys.exit(1)
        raise

    print(_bold("  Server is running"))
    print(_dim("  ────────────────────────────────────────────────"))
    print(f"    {_green('▸')} {_cyan(f'http://localhost:{args.port}')}  {_dim('(for Claude Code on this Mac)')}")
    print()
    print(f"    {_dim('Health check:')}    http://localhost:{args.port}/api/health")
    print(f"    {_dim('List workflows:')}  http://localhost:{args.port}/api/workflows")
    print()
    print(_bold("  Available workflows"))
    print(_dim("  ────────────────────────────────────────────────"))
    for name, info in WORKFLOWS.items():
        print(f"    {_cyan('POST')} /api/{name}")
        print(f"         {_dim(info['description'])}")
    print()
    print(_dim("  ────────────────────────────────────────────────"))
    print(f"  {_green('Ready.')} Leave this window open while you work in Claude.")
    print(f"  {_dim('Press Ctrl+C to stop.')}")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
