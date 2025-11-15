from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from typing import List, Sequence


_ANIMATION_DISABLE_ENV = "GLOBAL_GIT_NO_ANIMATION"
_TRUTHY = {"1", "true", "True", "yes", "on", "YES", "On"}

_NANCY_RAW_FRAMES: List[List[str]] = [
    [
        "   __       ",
        "  /__\\_     ",
        " ( ^  )     ",
        " /|\\  )    ",
        "  / \\       ",
        " /   \\      ",
    ],
    [
        "   __       ",
        "  /__\\_     ",
        " ( ^  )     ",
        " /| \\ )    ",
        "  / \\       ",
        " /   \\      ",
    ],
    [
        "   __       ",
        "  /__\\_     ",
        " ( ^  )     ",
        " /|/  )    ",
        "  / \\       ",
        " /   \\      ",
    ],
]

_NED_RAW_FRAMES: List[List[str]] = [
    [
        "   .--.     ",
        "  ( oo )    ",
        "  /|\\_/    ",
        "   / \\      ",
        "  /   \\     ",
        "  '   '     ",
    ],
    [
        "   .--.     ",
        "  ( oo )    ",
        "  /|_/\\    ",
        "   / \\      ",
        "  /   \\     ",
        "  '   '     ",
    ],
    [
        "   .--.     ",
        "  ( oo )    ",
        "  /|\\_/    ",
        "   /\\       ",
        "  /  \\      ",
        "  '   '     ",
    ],
]


def _animation_disabled() -> bool:
    value = os.environ.get(_ANIMATION_DISABLE_ENV, "0")
    return value in _TRUTHY


def _normalize_frames(raw_frames: Sequence[Sequence[str]]) -> tuple[List[List[str]], int, int]:
    height = 0
    width = 0
    processed: List[List[str]] = []
    for frame in raw_frames:
        lines = [line.rstrip("\n") for line in frame]
        height = max(height, len(lines))
        width = max(width, max((len(line) for line in lines), default=0))
        processed.append(lines)
    normalized: List[List[str]] = []
    for lines in processed:
        padded = [line.ljust(width) for line in lines]
        while len(padded) < height:
            padded.append(" " * width)
        normalized.append(padded)
    return normalized, height, width


def _prepare_frame_strings(frames: Sequence[Sequence[str]]) -> tuple[List[str], int]:
    normalized, height, _ = _normalize_frames(frames)
    compiled = ["\n".join(lines) + "\n" for lines in normalized]
    return compiled, height


@contextmanager
def _cursor_hidden():
    if not sys.stdout.isatty():
        yield
        return
    try:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        yield
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def _play_animation(frames: Sequence[Sequence[str]], *, loops: int = 3, delay: float = 0.22) -> None:
    texts, height = _prepare_frame_strings(frames)
    if not sys.stdout.isatty() or _animation_disabled():
        sys.stdout.write(texts[-1])
        sys.stdout.flush()
        return

    with _cursor_hidden():
        for _ in range(max(1, loops)):
            for frame in texts:
                sys.stdout.write(frame)
                sys.stdout.flush()
                time.sleep(delay)
                sys.stdout.write(f"\033[{height}F")
        # Hold on the final frame
        sys.stdout.write(texts[-1])
        sys.stdout.flush()


def play_nancy_animation() -> None:
    """Play Nancy's solo animation."""
    _play_animation(_NANCY_RAW_FRAMES)


def play_ned_animation() -> None:
    """Play Ned's solo animation."""
    _play_animation(_NED_RAW_FRAMES)


def play_duo_animation() -> None:
    """Play Nancy and Ned together in sync."""
    duo_frames: List[List[str]] = []
    nancy_frames, _, _ = _normalize_frames(_NANCY_RAW_FRAMES)
    ned_frames, _, _ = _normalize_frames(_NED_RAW_FRAMES)
    # Ensure we have the same number of frames on both sides
    frame_count = max(len(nancy_frames), len(ned_frames))
    for index in range(frame_count):
        nancy = nancy_frames[index % len(nancy_frames)]
        ned = ned_frames[index % len(ned_frames)]
        combined = [f"{left}   {right}" for left, right in zip(nancy, ned)]
        duo_frames.append(combined)
    _play_animation(duo_frames, loops=4, delay=0.18)
