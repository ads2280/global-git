from __future__ import annotations

import math
import os
import shutil
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Tuple


_NO_COLOR_ENV = {"1", "true", "True", "yes", "YES"}


def _is_color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("GLOBAL_GIT_NO_COLOR") in _NO_COLOR_ENV:
        return False
    return sys.stdout.isatty()


@dataclass(frozen=True)
class _Palette:
    land_chars: str
    ocean_chars: str
    land_rgb: Tuple[int, int, int]
    ocean_rgb: Tuple[int, int, int]
    text_rgb: Tuple[int, int, int]


PALETTE = _Palette(
    land_chars=" .:-=+*#%@",
    ocean_chars="  ..--==++**##@@",
    land_rgb=(90, 220, 160),
    ocean_rgb=(60, 185, 220),
    text_rgb=(160, 215, 255),
)


def _ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    k = (2 * t) - 2
    return 0.5 * k * k * k + 1


def _normalize(vec: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = vec
    mag = math.sqrt(x * x + y * y + z * z)
    if mag == 0:
        return (0.0, 0.0, 0.0)
    return (x / mag, y / mag, z / mag)


def _dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _rotate_y(vector: Tuple[float, float, float], angle: float) -> Tuple[float, float, float]:
    x, y, z = vector
    sin_a = math.sin(angle)
    cos_a = math.cos(angle)
    return (x * cos_a + z * sin_a, y, -x * sin_a + z * cos_a)


def _is_land(lat_deg: float, lon_deg: float) -> bool:
    """
    Rough heuristic for continents using hand-tuned latitude/longitude regions.
    """
    lat = lat_deg
    lon = lon_deg

    def band(lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    # North America
    if band(12, 75, -170, -45):
        if lat > 55 and lon < -110:
            return True
        if lat < 40 and lon < -95:
            return True
        if lon > -110 and lat < 60:
            return True
        if lat > 55 and -110 <= lon <= -45:
            return True

    # South America
    if band(-56, 15, -82, -30):
        if lon < -70 and lat > -15:
            return True
        if lon > -70:
            return True

    # Europe + Asia (Eurasia)
    if band(25, 80, -15, 180):
        if lon < 60 or lat > 45:
            return True
        if lon > 60 and lat < 55:
            return True

    # Africa
    if band(-35, 37, -20, 55):
        if lon < 15:
            return True
        if lat < 5 or lon > 15:
            return True

    # Australia
    if band(-45, -5, 110, 155):
        return True

    # India + Southeast Asia
    if band(5, 30, 65, 120):
        return True

    # Greenland
    if band(58, 84, -72, -10):
        return True

    # Antarctica
    if lat < -64:
        return True

    return False


def _sample_texture(p: Tuple[float, float, float]) -> bool:
    x, y, z = p
    lon = math.degrees(math.atan2(x, z))
    lat = math.degrees(math.asin(max(-1.0, min(1.0, y))))
    return _is_land(lat, lon)


def _char_for(value: float, chars: str) -> str:
    value = max(0.0, min(1.0, value))
    index = int(value * (len(chars) - 1))
    return chars[index]


def _apply_color(s: str, rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m{s}\033[0m"


def _interpolate_rgb(color: Tuple[int, int, int], alpha: float) -> Tuple[int, int, int]:
    clamped = max(0.0, min(1.0, alpha))
    return tuple(int(component * clamped) for component in color)


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


def _render_frame(
    angle: float,
    width: int,
    height: int,
    color_enabled: bool,
    text_alpha: float,
    palette: _Palette = PALETTE,
) -> str:
    light_dir = _normalize((0.6, 0.8, 1.0))
    lines: list[str] = []
    for row in range(height):
        y = ((row + 0.5) - height / 2) / (height / 2)
        line_chars: list[str] = []
        for col in range(width):
            x = ((col + 0.5) - width / 2) / (width / 2)
            if x * x + y * y > 1.0:
                line_chars.append(" ")
                continue
            z = math.sqrt(max(0.0, 1.0 - x * x - y * y))
            camera_point = (x, y, z)
            object_point = _rotate_y(camera_point, -angle)
            land = _sample_texture(object_point)
            normal = _normalize(camera_point)
            light = max(0.0, _dot(normal, light_dir))
            shaded = math.pow(light, 0.65)
            if land:
                char = _char_for(shaded, palette.land_chars)
                if color_enabled:
                    rgb = tuple(
                        min(255, int(base * (0.45 + 0.55 * (0.5 + shaded / 2))))
                        for base in palette.land_rgb
                    )
                    char = _apply_color(char, rgb)
            else:
                char = _char_for(shaded, palette.ocean_chars)
                if color_enabled:
                    rgb = tuple(
                        min(255, int(base * (0.35 + 0.65 * (0.4 + shaded / 2))))
                        for base in palette.ocean_rgb
                    )
                    char = _apply_color(char, rgb)
            line_chars.append(char)
        lines.append("".join(line_chars))

    text_line = ""
    if text_alpha > 0:
        label = "GitGlobal Voyager"
        fade_rgb = _interpolate_rgb(palette.text_rgb, text_alpha)
        if color_enabled:
            label = _apply_color(label, fade_rgb)
        else:
            label = label
        padding = max(0, (width - len("GitGlobal Voyager")) // 2)
        text_line = " " * padding + label
    return "\n".join(lines + ([text_line] if text_line else []))


def show_globe_animation(duration: float = 4.0, fps: int = 18) -> bool:
    """
    Render a smooth spinning ASCII globe animation.

    Returns True if the animation was shown, False otherwise.
    """
    if not sys.stdout.isatty():
        return False

    term_size = shutil.get_terminal_size()
    min_cols, min_rows = 30, 20
    if term_size.columns < min_cols or term_size.lines < min_rows:
        return False

    color_enabled = _is_color_enabled()
    frames = max(1, int(duration * fps))
    start_time = time.perf_counter()
    base_interval = 1.0 / fps
    angle_span = math.pi * 2.4  # ~1.2 rotations

    with _cursor_hidden():
        try:
            for index in range(frames):
                now = time.perf_counter()
                elapsed = now - start_time
                progress = min(1.0, elapsed / duration) if duration > 0 else 1.0
                eased = _ease_in_out_cubic(progress)
                angle = eased * angle_span

                # Re-evaluate terminal size for responsive behaviour
                term_size = shutil.get_terminal_size()
                width = min(30, max(20, term_size.columns - 10))
                height = min(30, max(20, term_size.lines - 8))

                text_alpha = 0.0
                if progress > 0.65:
                    text_alpha = (progress - 0.65) / 0.35

                frame = _render_frame(angle, width, height, color_enabled, text_alpha)

                vertical_margin = max(0, (term_size.lines - (height + (1 if text_alpha else 0))) // 2 - 1)
                horizontal_margin = max(0, (term_size.columns - width) // 2)

                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(
                    ("\n" * vertical_margin)
                    + "\n".join(" " * horizontal_margin + line for line in frame.splitlines())
                )
                sys.stdout.flush()

                target = start_time + (index + 1) * base_interval
                sleep_for = target - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
        except KeyboardInterrupt:
            return True
        finally:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    # Final settle frame
    term_size = shutil.get_terminal_size()
    width = min(30, max(20, term_size.columns - 10))
    height = min(30, max(20, term_size.lines - 8))
    frame = _render_frame(angle_span, width, height, color_enabled, 1.0)
    vertical_margin = max(0, (term_size.lines - (height + 1)) // 2 - 1)
    horizontal_margin = max(0, (term_size.columns - width) // 2)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(
        ("\n" * vertical_margin) + "\n".join(" " * horizontal_margin + line for line in frame.splitlines())
    )
    sys.stdout.flush()
    return True


__all__ = ["show_globe_animation"]
