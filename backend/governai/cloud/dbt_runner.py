"""Subprocess boundary for a real dbt Core build."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class DbtExecutionError(RuntimeError):
    pass


class DbtRunner:
    def __init__(self, *, project_dir: Path, profiles_dir: Path, target: str = "prod"):
        self.project_dir = project_dir.resolve()
        self.profiles_dir = profiles_dir.resolve()
        self.target = target

    def build(self, *, select: str) -> tuple[str, ...]:
        executable = shutil.which("dbt")
        if not executable:
            raise DbtExecutionError(
                "dbt executable not found; install the cloud extra before a live run"
            )
        command = (
            executable,
            "build",
            "--project-dir",
            str(self.project_dir),
            "--profiles-dir",
            str(self.profiles_dir),
            "--target",
            self.target,
            "--select",
            select,
            "--fail-fast",
        )
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        if completed.returncode:
            tail = "\n".join((completed.stdout + completed.stderr).splitlines()[-30:])
            raise DbtExecutionError(f"dbt build failed with exit code {completed.returncode}:\n{tail}")
        return command
