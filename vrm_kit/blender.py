"""Blender headless runner — invoke Blender scripts from Python."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent / "blender_scripts"


def find_blender() -> str:
    path = shutil.which("blender")
    if path:
        return path
    # macOS app bundle
    app = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    if app.exists():
        return str(app)
    raise FileNotFoundError(
        "Blender not found. Install via: brew install --cask blender"
    )


def run_script(
    script_name: str,
    args: list[str],
    *,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a Blender script in background mode.

    Args:
        script_name: Name of the script file in blender_scripts/ (without path).
        args: Arguments to pass after '--'.
        timeout: Timeout in seconds.

    Returns:
        CompletedProcess with stdout/stderr.
    """
    blender = find_blender()
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")

    cmd = [blender, "--background", "--python", str(script), "--"] + args

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_script_json(
    script_name: str,
    args: list[str],
    *,
    timeout: int = 300,
) -> dict:
    """Run a Blender script and parse JSON from its output.

    Expects the script to print JSON between ===JSON_START=== and ===JSON_END=== markers.
    """
    result = run_script(script_name, args, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(
            f"Blender script failed (exit {result.returncode}):\n{result.stderr}"
        )

    stdout = result.stdout
    start = stdout.find("===JSON_START===")
    end = stdout.find("===JSON_END===")
    if start == -1 or end == -1:
        raise RuntimeError(f"No JSON markers in output:\n{stdout[-500:]}")

    json_str = stdout[start + len("===JSON_START===") : end].strip()
    return json.loads(json_str)
