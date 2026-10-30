"""Live gate: open a workbook in Tableau Desktop and report whether it loads (Windows only)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tableau_load_check.ps1"


@dataclass(frozen=True)
class LoadResult:
    status: str        # pass | fail | timeout | unavailable
    details: str


def tableau_available() -> bool:
    return shutil.which("powershell") is not None and any(
        Path("C:/Program Files/Tableau").glob("Tableau */bin/tableau.exe"))


def load_in_tableau(path: Path, timeout_s: int = 150) -> LoadResult:
    if not tableau_available():
        return LoadResult("unavailable", "Tableau Desktop or PowerShell not found")
    powershell = shutil.which("powershell")
    proc = subprocess.run(  # noqa: S603 - fixed script path and arguments, no shell
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
         "-Path", str(path), "-TimeoutSec", str(timeout_s)],
        capture_output=True, text=True, timeout=timeout_s + 60, check=False,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        return LoadResult("timeout", (proc.stdout + proc.stderr).strip()[:2000])
    data = json.loads(lines[-1])
    return LoadResult(data.get("status", "timeout"), str(data.get("details", "")))
