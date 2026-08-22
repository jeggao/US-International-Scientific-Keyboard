"""Turn a layout into the files the repository ships, and keep them current.

This is the producing half; :mod:`kbdlayout.checks.generated` is the comparing
half, and it reads :func:`render_all` from here so the two can never disagree
about what the layout is supposed to produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .generators import TARGETS
from .model import Layout

#: What happened to one file. ``stale`` only occurs in a dry run.
Status = str

UNCHANGED: Status = "unchanged"
CREATED: Status = "created"
UPDATED: Status = "updated"
STALE: Status = "stale"


@dataclass(frozen=True)
class Outcome:
    """One generated file, and what writing it did (or would have done)."""

    relative: str
    status: Status

    @property
    def is_stale(self) -> bool:
        return self.status == STALE


def render_all(layout: Layout) -> dict[str, str | bytes]:
    """Every file this layout generates, keyed by repository-relative path."""
    files: dict[str, str | bytes] = {}
    claimed_by: dict[str, str] = {}
    for name, target in TARGETS.items():
        for path, content in target.generate(layout).items():
            if path in files:
                raise ValueError(f"{name} generates {path}, which {claimed_by[path]} also claims")
            files[path] = content
            claimed_by[path] = name
    return files


def as_bytes(content: str | bytes) -> bytes:
    """``bytes`` verbatim; ``str`` as UTF-8 with the LF endings it was built with."""
    return content if isinstance(content, bytes) else content.encode("utf-8")


def sync(root: Path, layout: Layout, write: bool = True) -> list[Outcome]:
    """Write every generated file, or report which ones are out of date.

    With ``write=False`` nothing is touched and any file that differs comes
    back as :data:`STALE`.
    """
    outcomes: list[Outcome] = []
    for relative, content in sorted(render_all(layout).items()):
        path = root / relative
        expected = as_bytes(content)
        current = path.read_bytes() if path.exists() else None
        if current == expected:
            outcomes.append(Outcome(relative, UNCHANGED))
            continue
        if not write:
            outcomes.append(Outcome(relative, STALE))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        outcomes.append(Outcome(relative, UPDATED if current is not None else CREATED))
    return outcomes
