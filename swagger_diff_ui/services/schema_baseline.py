"""Git helpers for OpenAPI baseline schema export (local/dev)."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings

from swagger_diff_ui.exceptions import SchemaDiffError, SchemaDiffNotFound

logger = logging.getLogger(__name__)

# Branch/tag/SHA plus relative history forms (HEAD~1, main^2, origin/dev~3).
# Allows '-' inside names (feature-x) but validate_git_ref rejects a leading '-'.
# Deliberately excludes shell metacharacters, spaces, and ".." path traversal.
_REF_RE = re.compile(r"^[A-Za-z0-9._/\-~^]+$")

_DEFAULT_SETTINGS_MODULE = "config.settings.local"


def _repo_root() -> Path:
    """Django project root (``settings.BASE_DIR``), where ``manage.py`` usually lives."""
    return Path(settings.BASE_DIR).resolve()


def _git_toplevel(cwd: Path) -> Path:
    """Return the git working-tree root that contains ``cwd``."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            text=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise SchemaDiffError(
            detail="Failed to locate git repository root.",
            code="SCHEMA_DIFF_GIT_UNAVAILABLE",
        ) from exc
    return Path(out.strip()).resolve()


def manage_py_relative_to_git_root(project_root: Path, git_root: Path) -> Path:
    """Path to ``manage.py`` relative to the git toplevel (may be nested)."""
    manage = (project_root / "manage.py").resolve()
    if not manage.is_file():
        raise SchemaDiffError(
            detail="manage.py not found under Django BASE_DIR.",
            code="SCHEMA_DIFF_GENERATE_FAILED",
        )
    git_root = git_root.resolve()
    try:
        return manage.relative_to(git_root)
    except ValueError as exc:
        raise SchemaDiffError(
            detail="manage.py is outside the git repository.",
            code="SCHEMA_DIFF_GENERATE_FAILED",
        ) from exc


def _baseline_settings_module() -> str:
    return (
        getattr(settings, "SWAGGER_DIFF_SETTINGS_MODULE", None)
        or os.environ.get("DJANGO_SETTINGS_MODULE")
        or _DEFAULT_SETTINGS_MODULE
    )


def _ensure_local_only() -> None:
    if getattr(settings, "DJANGO_ENV", "") != "local" and not settings.DEBUG:
        raise SchemaDiffError(
            detail="Schema baseline/diff is only available in local/debug.",
            code="SCHEMA_DIFF_LOCAL_ONLY",
        )


def validate_git_ref(ref: str) -> str:
    """Accept branch names, SHAs, and relative refs like ``HEAD~1`` / ``main^``.

    Refs that start with ``-`` are rejected so they cannot be parsed as git
    options (e.g. ``--output``).
    """
    ref = (ref or "").strip()
    if (
        not ref
        or ref.startswith("-")
        or not _REF_RE.match(ref)
        or ".." in ref
    ):
        raise SchemaDiffError(detail="Invalid git ref.", code="SCHEMA_DIFF_INVALID_REF")
    return ref


def resolve_sha(ref: str) -> str:
    ref = validate_git_ref(ref)
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--verify", "--end-of-options", ref],
            cwd=_repo_root(),
            text=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise SchemaDiffNotFound(detail=f"Git ref not found: {ref}") from exc
    return out.strip()


def list_git_refs(
    *,
    branch: str | None = None,
    branch_limit: int = 80,
    commit_limit: int = 50,
) -> dict[str, Any]:
    _ensure_local_only()
    root = _repo_root()

    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.PIPE)

    try:
        head = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        head_sha = run(["git", "rev-parse", "HEAD"]).strip()
        local_branches = [
            b
            for b in run(
                [
                    "git",
                    "for-each-ref",
                    "--sort=-committerdate",
                    "refs/heads",
                    "--format=%(refname:short)",
                ]
            ).splitlines()
            if b
        ]
        remote_branches = [
            b
            for b in run(
                [
                    "git",
                    "for-each-ref",
                    "--sort=-committerdate",
                    "refs/remotes",
                    "--format=%(refname:short)",
                ]
            ).splitlines()
            if b and not b.endswith("/HEAD")
        ]
    except subprocess.CalledProcessError as exc:
        raise SchemaDiffError(
            detail="Failed to read git refs. Is this a git checkout?",
            code="SCHEMA_DIFF_GIT_UNAVAILABLE",
        ) from exc

    branches: list[str] = []
    seen: set[str] = set()
    for name in local_branches + remote_branches:
        if name in seen:
            continue
        seen.add(name)
        branches.append(name)
        if len(branches) >= branch_limit:
            break

    commit_ref = validate_git_ref(branch) if branch else head
    try:
        commits_raw = run(
            [
                "git",
                "log",
                f"-n{commit_limit}",
                "--pretty=format:%H\t%h\t%s\t%cr",
                "--end-of-options",
                commit_ref,
            ]
        )
    except subprocess.CalledProcessError as exc:
        raise SchemaDiffNotFound(detail=f"Git ref not found: {commit_ref}") from exc

    commits: list[dict[str, str]] = []
    for line in commits_raw.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        full, short, subject, relative = parts
        commits.append(
            {"sha": full, "short": short, "subject": subject, "relative": relative}
        )

    return {
        "head": head,
        "head_sha": head_sha,
        "branch": commit_ref,
        "branches": branches,
        "commits": commits,
    }


def _cache_path(sha: str) -> Path:
    cache_dir = _repo_root() / ".schema-cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{sha}.openapi.json"


def generate_current_schema() -> dict[str, Any]:
    from drf_spectacular.generators import SchemaGenerator

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    if not isinstance(schema, dict):
        raise SchemaDiffError(
            detail="Failed to generate current OpenAPI schema.",
            code="SCHEMA_DIFF_GENERATE_FAILED",
        )
    return schema


def generate_schema_at_ref(
    ref: str,
    *,
    use_cache: bool = True,
    require_local: bool = True,
) -> dict[str, Any]:
    """Export OpenAPI schema for ``ref`` via a temporary git worktree.

    ``require_local`` gates HTTP/debug use. The management command passes
    ``False`` so CI can run without ``DEBUG=True``.
    """
    if require_local:
        _ensure_local_only()
    sha = resolve_sha(ref)
    cache = _cache_path(sha)
    if use_cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    project_root = _repo_root()
    git_root = _git_toplevel(project_root)
    manage_rel = manage_py_relative_to_git_root(project_root, git_root)

    with tempfile.TemporaryDirectory(prefix="schema-wt-") as tmp:
        tmp_path = Path(tmp)
        try:
            subprocess.check_call(
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(tmp_path),
                    "--end-of-options",
                    sha,
                ],
                cwd=git_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise SchemaDiffError(
                detail=f"Could not create git worktree for {ref}.",
                code="SCHEMA_DIFF_GENERATE_FAILED",
            ) from exc

        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = _baseline_settings_module()
        env["SCHEMA_DIFF_EXPORT"] = "1"

        manage_in_wt = tmp_path / manage_rel
        out_file = manage_in_wt.parent / "_baseline.openapi.json"
        schema: dict[str, Any] | None = None
        try:
            if not manage_in_wt.is_file():
                raise SchemaDiffError(
                    detail=(
                        "manage.py not found in the baseline worktree at "
                        f"{manage_rel.as_posix()}. That git ref may predate this "
                        "Django project layout."
                    ),
                    code="SCHEMA_DIFF_GENERATE_FAILED",
                )
            proc = subprocess.run(
                [
                    sys.executable,
                    manage_in_wt.name,
                    "spectacular",
                    "--file",
                    str(out_file),
                    "--format",
                    "openapi-json",
                ],
                cwd=manage_in_wt.parent,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if proc.returncode != 0 or not out_file.exists():
                logger.error(
                    "spectacular failed for %s (code=%s): %s",
                    sha,
                    proc.returncode,
                    (proc.stderr or proc.stdout or "")[-2000:],
                )
                raise SchemaDiffError(
                    detail="Failed to generate OpenAPI schema for the selected ref.",
                    code="SCHEMA_DIFF_GENERATE_FAILED",
                )
            try:
                schema = json.loads(out_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise SchemaDiffError(
                    detail="Schema export returned invalid JSON.",
                    code="SCHEMA_DIFF_GENERATE_FAILED",
                ) from exc
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tmp_path)],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=False,
            )

    if schema is None:
        raise SchemaDiffError(
            detail="Failed to generate OpenAPI schema for the selected ref.",
            code="SCHEMA_DIFF_GENERATE_FAILED",
        )

    cache.write_text(json.dumps(schema), encoding="utf-8")
    return schema
