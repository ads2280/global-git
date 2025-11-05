from __future__ import annotations

import codecs
import errno
import locale
import os
import select
import signal
import shutil
import subprocess
import sys
from typing import Iterable, List, Mapping, Optional, Sequence, TextIO

try:  # pragma: no cover - platform dependent fallback
    import pty  # type: ignore
except ImportError:  # pragma: no cover
    pty = None  # type: ignore

try:  # pragma: no cover - platform dependent fallback
    import termios  # type: ignore
    import tty  # type: ignore
except ImportError:  # pragma: no cover
    termios = None  # type: ignore
    tty = None  # type: ignore

from .achievements import ACHIEVEMENT_LOOKUP, newly_earned_achievements
from .config import load_config
from .state import award_achievements, load_achievements_state, record_command_usage
from .translator import TranslationResult, translate_output_text, translate_with_metadata


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


def _first_non_option_index(args: Sequence[str]) -> Optional[int]:
    i = 0
    while i < len(args):
        token = args[i]
        if not token.startswith("-"):
            return i
        if token in {"-C", "-c", "-I", "-i", "-X"} and i + 1 < len(args) and not args[i + 1].startswith("-"):
            i += 2
            continue
        i += 1
    return None


def _extract_base_command(args: Sequence[str]) -> Optional[str]:
    index = _first_non_option_index(args)
    if index is None or index >= len(args):
        return None
    return args[index]


def _normalize_language(language: Optional[str]) -> Optional[str]:
    if not language or language == "__global__":
        return None
    return language


def _celebrate_achievements(identifiers: Sequence[str]) -> None:
    if not identifiers:
        return
    for identifier in identifiers:
        definition = ACHIEVEMENT_LOOKUP.get(identifier)
        if not definition:
            continue
        color = definition.color
        reset = "\033[0m"
        accent = f"\033[1;{color}m"
        title = f"{definition.emoji}  Achievement Unlocked!"
        name_line = f"{definition.name}"
        border_length = max(len(title), len(name_line)) + 4
        top_border = accent + "╔" + "═" * (border_length - 2) + "╗" + reset
        bottom_border = accent + "╚" + "═" * (border_length - 2) + "╝" + reset
        padded_title = title.ljust(border_length - 4)
        padded_name = name_line.ljust(border_length - 4)
        description = definition.description
        print()
        print(top_border)
        print(f"{accent}║ {padded_title} ║{reset}")
        print(f"{accent}║ {padded_name} ║{reset}")
        print(bottom_border)
        print(f"{accent}{description}{reset}")
        print()


def _post_git_invocation(args: Sequence[str], translation: TranslationResult) -> None:
    try:
        base_command = _extract_base_command(args)
        if base_command and base_command.lower() == "for-each-ref":
            return
        alias = translation.command.original if translation.command else None
        language = _normalize_language(translation.command.language if translation.command else None)
        stats = record_command_usage(base_command, language=language, alias=alias)
        achievements_state = load_achievements_state()
        earned_ids = achievements_state.get("earned", {}).keys()
        pending = newly_earned_achievements(stats, earned_ids)
        newly_awarded, _ = award_achievements(pending)
        _celebrate_achievements(newly_awarded)
    except Exception:
        # Stats tracking should never block git usage; swallow unexpected issues.
        pass


def main() -> int:
    try:
        shim_depth = int(os.environ.get(_SHIM_DEPTH_ENV, "0"))
    except ValueError:
        shim_depth = 0

    args = sys.argv[1:]
    if (
        args
        and args[0].lower() == "global"
        and os.environ.get("GLOBAL_GIT_BYPASS", "0") not in {"1", "true", "True"}
    ):
        from .gitglobal_cli import main as gitglobal_main

        return gitglobal_main(args[1:])

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
        return subprocess.call([exec_path, *args], env=env)

    cfg = load_config()
    translation = translate_with_metadata(
        args,
        cfg.command_map,
        cfg.flag_map,
        cfg.command_sources,
        cfg.flag_sources,
    )
    translated = translation.args

    if not exec_path:
        print("global-git: unable to locate the real `git` executable", file=sys.stderr)
        return 127

    output_map = cfg.output_map
    if not output_map:
        # No output translations configured; passthrough stdio directly.
        ran_git = True
        exit_code: int
        try:
            try:
                proc = subprocess.run([exec_path, *translated], env=env)
                exit_code = proc.returncode
            except KeyboardInterrupt:
                exit_code = 130
            return exit_code
        finally:
            if ran_git:
                _post_git_invocation(translated, translation)

    ran_git = True
    try:
        exit_code = _run_git_with_output_translation(exec_path, translated, env, output_map)
        return exit_code
    finally:
        if ran_git:
            _post_git_invocation(translated, translation)


def _preferred_encoding(stream: TextIO) -> str:
    return getattr(stream, "encoding", None) or locale.getpreferredencoding(False) or "utf-8"


def _emit_translated(data: Optional[bytes], stream: TextIO, replacements: Mapping[str, str]) -> None:
    if not data:
        return
    encoding = _preferred_encoding(stream)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            buffer.write(data)
            buffer.flush()
        else:
            stream.write(data.decode(encoding, errors="ignore"))
            stream.flush()
        return
    translated = translate_output_text(text, replacements)
    stream.write(translated)
    stream.flush()


def _run_git_with_output_translation(
    exec_path: str,
    args: Sequence[str],
    env: Mapping[str, str],
    output_map: Mapping[str, str],
) -> int:
    if _should_use_pty(output_map):
        return _run_git_via_pty(exec_path, args, env, output_map)
    return _run_git_via_pipes(exec_path, args, env, output_map)


def _should_use_pty(output_map: Mapping[str, str]) -> bool:
    if not output_map:
        return False
    if pty is None or termios is None or tty is None:
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    try:
        if not sys.stdin.isatty():
            return False
    except Exception:
        return False
    return True


def _run_git_via_pipes(
    exec_path: str,
    args: Sequence[str],
    env: Mapping[str, str],
    output_map: Mapping[str, str],
) -> int:
    proc: Optional[subprocess.Popen[bytes]] = None
    try:
        proc = subprocess.Popen(
            [exec_path, *args],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_data, stderr_data = proc.communicate()
    except KeyboardInterrupt:
        if proc is not None:
            try:
                proc.send_signal(signal.SIGINT)
            except Exception:
                proc.kill()
            proc.wait()
        return 130

    _emit_translated(stdout_data, sys.stdout, output_map)
    _emit_translated(stderr_data, sys.stderr, output_map)
    return proc.returncode if proc else 1


def _run_git_via_pty(
    exec_path: str,
    args: Sequence[str],
    env: Mapping[str, str],
    output_map: Mapping[str, str],
) -> int:
    assert pty is not None and termios is not None and tty is not None

    master_fd: Optional[int] = None
    slave_fd: Optional[int] = None
    try:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            [exec_path, *args],
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
    except Exception:
        if master_fd is not None:
            os.close(master_fd)
        if slave_fd is not None:
            os.close(slave_fd)
        raise
    finally:
        if slave_fd is not None:
            os.close(slave_fd)

    return _pump_pty_output(master_fd, proc, output_map)


def _pump_pty_output(master_fd: int, proc: subprocess.Popen[bytes], output_map: Mapping[str, str]) -> int:
    assert termios is not None and tty is not None

    stdout_stream = sys.stdout
    encoding = _preferred_encoding(stdout_stream)
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    text_buffer = ""
    max_key_length = max((len(key) for key in output_map if key), default=0)
    tail_keep = max(0, max_key_length - 1)

    stdin_fd = _safe_tty_fileno(sys.stdin)
    old_attrs = None
    if stdin_fd is not None:
        try:
            old_attrs = termios.tcgetattr(stdin_fd)
            tty.setcbreak(stdin_fd)
        except Exception:
            old_attrs = None
            stdin_fd = None

    try:
        while True:
            read_fds = [master_fd]
            if stdin_fd is not None:
                read_fds.append(stdin_fd)
            try:
                ready, _, _ = select.select(read_fds, [], [])
            except InterruptedError:
                continue

            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        chunk = b""
                    else:
                        raise
                if not chunk:
                    break
                decoded = decoder.decode(chunk)
                if decoded:
                    text_buffer += decoded
                    text_buffer = _flush_ready_buffer(text_buffer, tail_keep, output_map, stdout_stream)

            if stdin_fd is not None and stdin_fd in ready:
                try:
                    data = os.read(stdin_fd, 1024)
                except OSError:
                    data = b""
                if not data:
                    stdin_fd = None
                else:
                    os.write(master_fd, data)

        remaining = decoder.decode(b"", final=True)
        if remaining:
            text_buffer += remaining
        if text_buffer:
            _write_translated(text_buffer, output_map, stdout_stream)

    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()
        return 130
    finally:
        if old_attrs is not None and stdin_fd is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
        os.close(master_fd)

    return proc.wait()


def _safe_tty_fileno(stream: TextIO) -> Optional[int]:
    try:
        if not stream.isatty():
            return None
        return stream.fileno()
    except Exception:
        return None


def _flush_ready_buffer(
    buffer: str,
    tail_keep: int,
    output_map: Mapping[str, str],
    stream: TextIO,
) -> str:
    if not buffer:
        return buffer
    if tail_keep:
        emit_length = max(0, len(buffer) - tail_keep)
    else:
        emit_length = len(buffer)
    if emit_length <= 0:
        return buffer

    emit_text = buffer[:emit_length]
    _write_translated(emit_text, output_map, stream)
    return buffer[emit_length:]


def _write_translated(text: str, output_map: Mapping[str, str], stream: TextIO) -> None:
    transformed = translate_output_text(text, output_map)
    stream.write(transformed)
    stream.flush()


if __name__ == "__main__":
    raise SystemExit(main())
