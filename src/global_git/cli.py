from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Iterable, List, Optional

from .config import load_config
from .translator import translate_args


_REAL_GIT_CACHE: Optional[str] = None
_REAL_GIT_ENV = "GLOBAL_GIT_REAL_EXECUTABLE"
_SHIM_DEPTH_ENV = "GLOBAL_GIT_SHIM_DEPTH"
_WRAPPER_MARKERS = (
    b"global_git",
    b"global-git",
    b"GLOBAL_GIT",
    b"load_entry_point",
    b"pyenv",
    b"PYENV",
)


def _looks_like_wrapper(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            snippet = handle.read(2048)
        return any(marker in snippet for marker in _WRAPPER_MARKERS)
    except OSError:
        return False


def _detect_wrapper_location() -> tuple[Optional[str], Optional[str]]:
    candidates = {os.path.basename(sys.argv[0]) or "", "git"}
    for name in candidates:
        if not name:
            continue
        resolved = shutil.which(name)
        if not resolved:
            continue
        real_resolved = os.path.realpath(resolved)
        if _looks_like_wrapper(real_resolved):
            return real_resolved, os.path.dirname(real_resolved)

    argv_path = os.path.realpath(sys.argv[0])
    if os.path.exists(argv_path):
        return argv_path, os.path.dirname(argv_path)
    return None, None


def _filtered_path_entries(wrapper_dir: Optional[str]) -> List[str]:
    path_env = os.environ.get("PATH", "")
    entries: List[str] = []
    seen_real: set[str] = set()
    for chunk in path_env.split(os.pathsep):
        if not chunk:
            continue
        real_chunk = os.path.realpath(chunk)
        if wrapper_dir and real_chunk == wrapper_dir:
            continue
        if real_chunk in seen_real:
            continue
        seen_real.add(real_chunk)
        entries.append(chunk)
    return entries


def _is_valid_candidate(candidate: str, wrapper_path: Optional[str]) -> bool:
    if not candidate:
        return False
    if not os.path.exists(candidate):
        return False
    if not os.access(candidate, os.X_OK):
        return False
    if _looks_like_wrapper(candidate):
        return False
    candidate_real = os.path.realpath(candidate)
    if wrapper_path and candidate_real == wrapper_path:
        return False
    return True


def _first_valid_git(wrapper_path: Optional[str], entries: Iterable[str]) -> Optional[str]:
    seen_real: set[str] = set()
    for entry in entries:
        if not entry:
            continue
        candidate = shutil.which("git", path=entry)
        if not candidate:
            continue
        candidate_real = os.path.realpath(candidate)
        if wrapper_path and candidate_real == wrapper_path:
            continue
        if candidate_real in seen_real:
            continue
        seen_real.add(candidate_real)
        if _is_valid_candidate(candidate, wrapper_path):
            return candidate
    return None


def _real_git_executable(wrapper_path: Optional[str], filtered_entries: Iterable[str]) -> Optional[str]:
    global _REAL_GIT_CACHE

    env_hint = os.environ.get(_REAL_GIT_ENV)
    if env_hint and _is_valid_candidate(env_hint, wrapper_path):
        _REAL_GIT_CACHE = env_hint
        return env_hint

    if _REAL_GIT_CACHE and _is_valid_candidate(_REAL_GIT_CACHE, wrapper_path):
        return _REAL_GIT_CACHE

    candidate = _first_valid_git(wrapper_path, filtered_entries)
    if candidate:
        _REAL_GIT_CACHE = candidate
        return candidate

    candidate = _first_valid_git(wrapper_path, os.environ.get("PATH", "").split(os.pathsep))
    if candidate:
        _REAL_GIT_CACHE = candidate
        return candidate

    git_exec_path = os.environ.get("GIT_EXEC_PATH")
    if git_exec_path:
        fallback = os.path.join(git_exec_path, "git")
        if _is_valid_candidate(fallback, wrapper_path):
            _REAL_GIT_CACHE = fallback
            return fallback

    if sys.platform == "darwin":
        xcrun_path = shutil.which("xcrun")
        if xcrun_path:
            try:
                proc = subprocess.run(
                    [xcrun_path, "--find", "git"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                candidate = proc.stdout.strip()
                if candidate and _is_valid_candidate(candidate, wrapper_path):
                    _REAL_GIT_CACHE = candidate
                    return candidate
            except Exception:
                pass

    return None


def _git_execution_env(
    filtered_entries: Iterable[str], real_exec: Optional[str], shim_depth: int
) -> dict[str, str]:
    env = os.environ.copy()
    filtered_path = os.pathsep.join(filtered_entries)
    if filtered_path:
        env["PATH"] = filtered_path
    env["GLOBAL_GIT_BYPASS"] = "1"
    if real_exec:
        env[_REAL_GIT_ENV] = real_exec
    env[_SHIM_DEPTH_ENV] = str(shim_depth + 1)
    return env


def main() -> int:
    try:
        shim_depth = int(os.environ.get(_SHIM_DEPTH_ENV, "0"))
    except ValueError:
        shim_depth = 0

    if shim_depth >= 3:
        print(
            "global-git: detected repeated shim invocation without locating real git; "
            "set GLOBAL_GIT_BYPASS=1 to run the system git directly.",
            file=sys.stderr,
        )
        return 126

    wrapper_path, wrapper_dir = _detect_wrapper_location()
    filtered_entries = _filtered_path_entries(wrapper_dir)
    exec_path = _real_git_executable(wrapper_path, filtered_entries)
    env = _git_execution_env(filtered_entries, exec_path, shim_depth)

    # Allow disabling translation via env var
    if os.environ.get("GLOBAL_GIT_BYPASS", "0") in {"1", "true", "True"}:
        if not exec_path:
            print("global-git: unable to locate `git` in PATH", file=sys.stderr)
            return 127
        return subprocess.call([exec_path, *sys.argv[1:]], env=env)

    cfg = load_config()
    translated = translate_args(sys.argv[1:], cfg.command_map, cfg.flag_map)

    if not exec_path:
        print("global-git: unable to locate the real `git` executable", file=sys.stderr)
        return 127

    # Execute real git with passthrough stdio
    try:
        proc = subprocess.run([exec_path, *translated], env=env)
        return proc.returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
