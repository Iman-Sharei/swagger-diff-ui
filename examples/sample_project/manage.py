#!/usr/bin/env python
"""Django's command-line utility for the swagger-diff-ui sample project."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    # Allow running without install: repo root (swagger_diff_ui) + this example dir.
    example_root = Path(__file__).resolve().parent
    repo_root = example_root.parents[1]
    for path in (example_root, repo_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sample_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install the package with "
            '`pip install -e ".[dev]"` from the repo root.'
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
