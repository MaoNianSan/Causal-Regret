"""Tests for the formal-Full clean-worktree gate and full lineage recording."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from exp4.outputs.run_lineage import fresh_lineage, load_run_lineage, write_run_lineage
from exp4.outputs.writers import (
    RunContext,
    git_commit,
    git_commit_available,
    write_run_config,
)
from main import _assert_full_worktree_ready

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str, cwd: Path):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True, text=True)


def _init_git_repo(path: Path, commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@example.com", cwd=path)
    _git("config", "user.name", "test", cwd=path)
    if commit:
        (path / "base.txt").write_text("x\n", encoding="utf-8")
        _git("add", ".", cwd=path)
        _git("commit", "-q", "-m", "init", cwd=path)
    return path


def test_formal_full_refuses_dirty_exp4_worktree(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    (repo / "dirty.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        _assert_full_worktree_ready(repo)
    assert "FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE" in str(excinfo.value)


def test_formal_full_accepts_clean_exp4_worktree(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    _assert_full_worktree_ready(repo)  # must not raise


def test_formal_full_refuses_unresolvable_git_commit(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo", commit=False)
    with pytest.raises(SystemExit) as excinfo:
        _assert_full_worktree_ready(repo)
    assert "FORMAL_FULL_REFUSED_UNRESOLVABLE_GIT_COMMIT" in str(excinfo.value)


def test_fast_allows_dirty_worktree_but_records_it(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_fast"
    (run_dir / "logs").mkdir(parents=True)
    context = RunContext(
        run_id="fast_dirty",
        run_tier="fast",
        run_dir=run_dir,
        code_commit="abc",
        config_hash="cfg",
        source_code_hash="src",
        n_jobs=1,
        exp4_worktree_clean_at_start=False,
    )
    write_run_config(context)
    payload = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    assert payload["exp4_worktree_clean_at_start"] is False
    assert payload["formal_full_clean_worktree_required"] is False


def test_full_run_config_requires_clean_worktree(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_full"
    (run_dir / "logs").mkdir(parents=True)
    context = RunContext(
        run_id="full_clean",
        run_tier="full",
        run_dir=run_dir,
        code_commit="abc",
        config_hash="cfg",
        source_code_hash="src",
        n_jobs=1,
        exp4_worktree_clean_at_start=True,
    )
    write_run_config(context)
    payload = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    assert payload["formal_full_clean_worktree_required"] is True
    assert payload["exp4_worktree_clean_at_start"] is True


def test_full_records_nonempty_git_commit() -> None:
    commit = git_commit(ROOT)
    assert commit not in {"", "UNAVAILABLE", "UNKNOWN"}
    assert len(commit) >= 7
    assert git_commit_available(ROOT) is True


def test_full_lineage_records_clean_start(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_lineage"
    (run_dir / "logs").mkdir(parents=True)
    write_run_lineage(run_dir, fresh_lineage("full_l", "full", "abc", True))
    lineage = load_run_lineage(run_dir)
    assert lineage is not None
    assert lineage.exp4_worktree_clean_at_start is True
    assert lineage.simulation_execution_mode == "FRESH"
    assert lineage.downstream_execution_mode == "INLINE_FRESH"


def test_full_lineage_records_dirty_start(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_lineage_dirty"
    (run_dir / "logs").mkdir(parents=True)
    write_run_lineage(run_dir, fresh_lineage("full_d", "full", "abc", False))
    lineage = load_run_lineage(run_dir)
    assert lineage is not None
    assert lineage.exp4_worktree_clean_at_start is False
