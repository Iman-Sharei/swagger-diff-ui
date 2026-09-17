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

_REF_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")


def _repo_root() -> Path:
    return Path(settings.BASE_DIR).resolve()


def _ensure_local_only() -> None:
    if getattr(settings, "DJANGO_ENV", "") != "local" and not settings.DEBUG:
        raise SchemaDiffError(
            detail="Schema baseline/diff is only available in local/debug.",
            code="SCHEMA_DIFF_LOCAL_ONLY",
        )


def validate_git_ref(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref or not _REF_RE.match(ref) or ".." in ref:
        raise SchemaDiffError(detail="Invalid git ref.", code="SCHEMA_DIFF_INVALID_REF")
    return ref


def resolve_sha(ref: str) -> str:
    ref = validate_git_ref(ref)
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--verify", ref],
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
                commit_ref,
                f"-n{commit_limit}",
                "--pretty=format:%H\t%h\t%s\t%cr",
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


def generate_schema_at_ref(ref: str, *, use_cache: bool = True) -> dict[str, Any]:
    _ensure_local_only()
    sha = resolve_sha(ref)
    cache = _cache_path(sha)
    if use_cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    root = _repo_root()
    with tempfile.TemporaryDirectory(prefix="schema-wt-") as tmp:
        tmp_path = Path(tmp)
        try:
            subprocess.check_call(
                ["git", "worktree", "add", "--detach", str(tmp_path), sha],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise SchemaDiffError(
                detail=f"Could not create git worktree for {ref}.",
                code="SCHEMA_DIFF_GENERATE_FAILED",
            ) from exc

        env = os.environ.copy()
        env.setdefault(
            "DJANGO_SETTINGS_MODULE",
            os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.local"),
        )
        env["SCHEMA_DIFF_EXPORT"] = "1"

        out_file = tmp_path / "_baseline.openapi.json"
        schema: dict[str, Any] | None = None
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "manage.py",
                    "spectacular",
                    "--file",
                    str(out_file),
                    "--format",
                    "openapi-json",
                ],
                cwd=tmp_path,
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
                cwd=root,
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
