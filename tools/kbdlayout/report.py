"""Diagnostics shared by every check.

The findings are the report, and they go to **stdout** in whichever format was
asked for; the human summary and anything that stopped the run go to
**stderr**. That split is what makes ``--format json`` pipeable.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Severity = Literal["error", "warning"]

ERROR: Severity = "error"
WARNING: Severity = "warning"

#: Every severity a finding may carry. ``Reporter.add`` rejects anything else,
#: so a typo cannot silently downgrade an error to a warning.
SEVERITIES: frozenset[str] = frozenset({ERROR, WARNING})


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    message: str
    severity: Severity = ERROR

    def format_text(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.severity}: [{self.check}] {self.message}"

    def format_github(self) -> str:
        command = "error" if self.severity == ERROR else "warning"
        message = self.message.replace("\n", "%0A")
        return (
            f"::{command} file={self.path},line={max(self.line, 1)},title={self.check}::{message}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "check": self.check,
            "path": self.path,
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
        }


def _text(findings: Iterable[Finding]) -> str:
    return "\n".join(finding.format_text() for finding in findings)


def _github(findings: Iterable[Finding]) -> str:
    # Both lines: the annotation is invisible in the log, the text is what a
    # human reads when scrolling it.
    out: list[str] = []
    for finding in findings:
        out.append(finding.format_text())
        out.append(finding.format_github())
    return "\n".join(out)


def _json(findings: Iterable[Finding]) -> str:
    return json.dumps([finding.as_dict() for finding in findings], indent=2)


#: How findings can be printed. ``github`` adds the workflow-command
#: annotations that make findings show up on the diff.
FORMATS: dict[str, Callable[[Iterable[Finding]], str]] = {
    "text": _text,
    "github": _github,
    "json": _json,
}


def default_style() -> str:
    """The format to use when none was asked for.

    Read at call time rather than at import, so a test can set the environment
    variable and see the effect.
    """
    return "github" if os.environ.get("GITHUB_ACTIONS") == "true" else "text"


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
        severity: Severity = ERROR,
    ) -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}; expected one of {sorted(SEVERITIES)}")
        try:
            rel = str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            # Outside the repository: keep the absolute path rather than
            # inventing a relative one, and say so where it is read.
            rel = str(Path(path).resolve())
        self.findings.append(Finding(check, rel, line, message, severity))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (f.path, f.line, f.check))

    def emit(self, stream=None, style: str | None = None) -> None:
        # Resolved here, not in the signature: a default argument would bind
        # whatever ``sys.stdout`` was at import time and keep writing there
        # even after something replaced it.
        stream = sys.stdout if stream is None else stream
        chosen = style or default_style()
        try:
            formatter = FORMATS[chosen]
        except KeyError:
            raise ValueError(
                f"unknown format {chosen!r}; expected one of {sorted(FORMATS)}"
            ) from None
        findings = self.sorted_findings()
        if not findings and chosen != "json":
            return
        print(formatter(findings), file=stream)
