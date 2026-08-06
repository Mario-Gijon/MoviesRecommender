"""Explicit execution modes for repository and packaged managers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Runtime:
    root: Path
    packaged: bool = False


def repository_runtime() -> Runtime:
    return Runtime(root=Path(__file__).resolve().parents[1])


def deployment_runtime(archive_path: str) -> Runtime:
    """Use the directory containing the executed archive, never the CWD."""
    return Runtime(root=Path(archive_path).resolve().parent, packaged=True)
