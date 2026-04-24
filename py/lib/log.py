"""Pretty, consistent workflow logging.

Every workflow prints in the same shape:

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      page_audit  ·  best prepaid unlimited plans
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

      ▸ [███████░░░░░░░]  2/7  Analyzing content structure  0.0s
          · Got 23,477 chars of content

      ▸ [██████████████] 7/7  Synthesizing audit report     2.1s
          · Synthesis complete

      ✓ Done in 3m 42s  →  outputs/page_audit/2026-04-23T...md

Colors are applied only when stdout is a TTY.
"""

from __future__ import annotations

import os
import sys
import time


# ── Color helpers ────────────────────────────────────────────────────────────

_IS_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _IS_TTY else s


def cyan(s):   return _c("36", s)
def green(s):  return _c("32;1", s)
def yellow(s): return _c("33", s)
def red(s):    return _c("31;1", s)
def dim(s):    return _c("2", s)
def bold(s):   return _c("1", s)


# ── Progress bar ─────────────────────────────────────────────────────────────

def _bar(current: int, total: int, width: int = 14) -> str:
    if total <= 0:
        return "[" + "░" * width + "]"
    filled = int(round(width * current / total))
    filled = max(0, min(width, filled))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs:02d}s"


# ── Logger ───────────────────────────────────────────────────────────────────

class WorkflowLogger:
    """Per-workflow logger. Instantiate once at the top of run()."""

    def __init__(self, name: str, total_steps: int):
        self.name = name
        self.total_steps = total_steps
        self.current_step = 0
        self._workflow_started = time.monotonic()
        self._step_started: float | None = None

    def start(self, topic: str) -> None:
        rule = "━" * 60
        print()
        print(f"  {dim(rule)}")
        print(f"    {bold(self.name)}  {dim('·')}  {topic}")
        print(f"  {dim(rule)}")

    def step(self, label: str) -> None:
        # Close the previous step's timing (printed inline on the next line below)
        self.current_step += 1
        self._step_started = time.monotonic()
        bar = _bar(self.current_step, self.total_steps)
        counter = f"{self.current_step}/{self.total_steps}"
        print()
        print(f"    {cyan('▸')} {cyan(bar)}  {dim(counter)}  {bold(label)}")

    def detail(self, msg: str) -> None:
        print(f"        {dim('·')} {msg}")

    def warn(self, msg: str) -> None:
        print(f"        {yellow('!')} {dim(msg)}")

    def error(self, msg: str) -> None:
        print(f"        {red('✗')} {msg}")

    def step_done(self, note: str | None = None) -> None:
        if self._step_started is None:
            elapsed = 0.0
        else:
            elapsed = time.monotonic() - self._step_started
        tail = f" {dim('·')} {note}" if note else ""
        print(f"        {green('✓')} {dim(_fmt_duration(elapsed))}{tail}")

    def done(self, output_path: str | None = None) -> None:
        total = time.monotonic() - self._workflow_started
        rule = "─" * 60
        print()
        print(f"  {dim(rule)}")
        if output_path:
            print(f"    {green('✓')} Done in {bold(_fmt_duration(total))}  {dim('→')}  {cyan(output_path)}")
        else:
            print(f"    {green('✓')} Done in {bold(_fmt_duration(total))}")
        print(f"  {dim(rule)}")
        print()

    def failed(self, err: str) -> None:
        total = time.monotonic() - self._workflow_started
        rule = "─" * 60
        print()
        print(f"  {dim(rule)}")
        print(f"    {red('✗')} Failed after {bold(_fmt_duration(total))}  {dim('·')}  {err}")
        print(f"  {dim(rule)}")
        print()
