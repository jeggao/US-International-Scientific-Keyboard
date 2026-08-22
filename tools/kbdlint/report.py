"""Diagnostics shared by every check."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

#: Emit GitHub Actions workflow commands when running inside Actions.
IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    message: str
    severity: str = "error"

    def format_text(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.severity}: [{self.check}] {self.message}"

    def format_github(self) -> str:
        command = "error" if self.severity == "error" else "warning"
        message = self.message.replace("\n", "%0A")
        return (
            f"::{command} file={self.path},line={max(self.line, 1)},title={self.check}::{message}"
        )


class Reporter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[Finding] = []

    def add(
        self,
        check: str,
        path: str | Path,
        line: int,
        message: str,
        severity: str = "error",
    ) -> None:
        try:
            rel = str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            rel = str(path)
        self.findings.append(Finding(check, rel, line, message, severity))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def emit(self, stream=sys.stdout) -> None:
        for finding in sorted(self.findings, key=lambda f: (f.path, f.line, f.check)):
            print(finding.format_text(), file=stream)
            if IN_GITHUB_ACTIONS:
                print(finding.format_github(), file=stream)
