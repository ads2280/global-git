from __future__ import annotations

import argparse
import os
import sys
import shutil
import textwrap
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .achievements import ACHIEVEMENTS, AchievementDefinition
from .config import LanguageDefinition, TranslationConfig, load_config
from .globe_animation import show_globe_animation
from .state import DEFAULT_LANGUAGE_KEY, load_usage_stats, save_active_languages, load_achievements_state


ASCII_GLOBE = r"""
             ___.....___
       ,..-.=--.-.       "".
     .{_..        `        ,. .
   .'     \      /        | ,'.\`.
  /        :   ;'          `____> \
 :         `. (           /       :
 |           `>\_         \      r|
             /   \         `._   \
 |          |      `          ;   |
  :          \     /          `   ;
   \          \.  '            ` /
     `.        | /             .'
        `      `/          . '
           `---'.....---''
"""

_ANIMATION_DISABLE_ENV = "GLOBAL_GIT_NO_ANIMATION"
_TRUTHY = {"1", "true", "True", "yes", "on", "YES", "On"}


LANGUAGE_NAMES = {
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "en-gb": "English (UK)",
}

RESET = "\033[0m"
SECTION_COLOR = "38;5;45"
COMMAND_COLOR = "38;5;81"
ALIAS_COLOR = "38;5;200"
COUNTER_COLOR = "38;5;118"
DIM_COLOR = "38;5;244"

LANGUAGE_COLORS = {
    "es": "38;5;208",
    "fr": "38;5;177",
    "de": "38;5;70",
    "pt": "38;5;39",
    "ru": "38;5;33",
    "ja": "38;5;176",
    "en-gb": "38;5;33",
    DEFAULT_LANGUAGE_KEY: "38;5;246",
}

LOCKED_FG_COLOR = "38;5;250"
LOCKED_BG_COLOR = "48;5;236"


def _paint(text: str, color: str, *, bold: bool = False, dim: bool = False, bg: str | None = None) -> str:
    codes = []
    if bold:
        codes.append("1")
    if dim:
        codes.append("2")
    codes.append(color)
    if bg:
        codes.append(bg)
    return f"\033[{';'.join(codes)}m{text}{RESET}"

def _language_label(code: str) -> str:
    if code == DEFAULT_LANGUAGE_KEY:
        return "Core (English)"
    return f"{_display_name(code)} ({code})"


def _format_number(value: int) -> str:
    return f"{value:,}"


def _terminal_width(fallback: int = 100) -> int:
    try:
        return shutil.get_terminal_size((fallback, 24)).columns
    except Exception:
        return fallback

def _foreign_command_totals(stats: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    per_language = stats.get("language_command_counts")
    if not isinstance(per_language, Mapping):
        return counts
    for lang_code, payload in per_language.items():
        if not isinstance(lang_code, str) or lang_code == DEFAULT_LANGUAGE_KEY:
            continue
        if not isinstance(payload, Mapping):
            continue
        for command, value in payload.items():
            if not isinstance(command, str):
                continue
            if not isinstance(value, int) or value <= 0:
                continue
            counts[command] = counts.get(command, 0) + value
    return counts


def _foreign_command_total(stats: Mapping[str, Any]) -> int:
    total = 0
    languages = stats.get("languages")
    if isinstance(languages, Mapping):
        for code, value in languages.items():
            if not isinstance(code, str) or code == DEFAULT_LANGUAGE_KEY:
                continue
            if isinstance(value, int) and value > 0:
                total += value
    return total


def _print_command_section(stats: Mapping[str, Any], width: int) -> None:
    counts = _foreign_command_totals(stats)
    total = sum(counts.values())
    entries = _top_entries(counts, 6)
    bar_width = max(10, min(36, width - 48))
    _section_heading("Command Heavy Hitters")
    _render_metric_table(
        entries,
        total=total,
        bar_width=bar_width,
        label_fn=lambda key: f"git {key}",
        color_fn=lambda _key: COMMAND_COLOR,
    )


def _alias_entries(stats: Mapping[str, Any]) -> List[tuple[str, int, str, str | None, str | None]]:
    aliases = stats.get("aliases")
    if not isinstance(aliases, Mapping):
        return []
    entries: List[tuple[str, int, str, str | None, str | None]] = []
    for key, payload in aliases.items():
        if not isinstance(key, str):
            continue
        if not isinstance(payload, Mapping):
            continue
        count = payload.get("count")
        if not isinstance(count, int) or count <= 0:
            continue
        label = payload.get("label")
        language = payload.get("language")
        command = payload.get("command")
        label_text = label if isinstance(label, str) else key
        lang_text = language if isinstance(language, str) else None
        command_text = command if isinstance(command, str) else None
        entries.append((key, count, label_text, lang_text, command_text))
    entries.sort(key=lambda item: item[1], reverse=True)
    return entries[:6]


def _print_alias_section(stats: Mapping[str, Any]) -> None:
    entries = _alias_entries(stats)
    _section_heading("Localized Favorites")
    filtered = [entry for entry in entries if entry[3] and entry[3] != DEFAULT_LANGUAGE_KEY]
    if not filtered:
        print(_paint("  Your translated catchphrases will appear here once you try them.", DIM_COLOR, dim=True))
        return
    for key, count, label, language, command in filtered:
        lang_code = language or DEFAULT_LANGUAGE_KEY
        color = _language_color(lang_code)
        alias_plain = f"git {label}"
        language_plain = _language_label(lang_code)
        command_plain = f"git {command}" if command else "—"
        alias_field = alias_plain.ljust(22)
        language_field = language_plain.ljust(22)
        command_field = command_plain.ljust(18)
        alias_text = _paint(alias_field, color, bold=True)
        language_text = _paint(language_field, color)
        command_text = _paint(command_field, COMMAND_COLOR)
        count_text = _paint(_format_number(count), COUNTER_COLOR, bold=True)
        print(f"  {alias_text} {language_text} ⇢ {command_text} × {count_text}")


def _print_signature_moves(stats: Mapping[str, Any]) -> None:
    mapping = stats.get("language_command_counts")
    if not isinstance(mapping, Mapping):
        return
    candidates: List[tuple[str, str, int]] = []
    for language, commands in mapping.items():
        if not isinstance(language, str):
            continue
        if language == DEFAULT_LANGUAGE_KEY:
            continue
        if not isinstance(commands, Mapping):
            continue
        top = _top_entries(commands, 1)
        if not top:
            continue
        command, count = top[0]
        candidates.append((language, command, count))
    candidates.sort(key=lambda item: item[2], reverse=True)
    if not candidates:
        return
    _section_heading("Signature Moves")
    for language, command, count in candidates[:4]:
        lang_label = _language_label(language)
        color = _language_color(language)
        lang_text = _paint(lang_label, color, bold=True)
        command_text = _paint(f"git {command}", COMMAND_COLOR, bold=True)
        count_text = _paint(_format_number(count), COUNTER_COLOR, bold=True)
        print(f"  {lang_text} leans on {command_text} × {count_text}")


def _print_stats_dashboard(stats: Mapping[str, Any], cfg: TranslationConfig) -> None:
    width = _terminal_width()
    _banner("GitGlobal Voyager Stats")
    total_commands = _foreign_command_total(stats)

    total_label = _paint("Foreign commands relayed:", SECTION_COLOR, bold=True)
    total_count = _paint(_format_number(total_commands), COUNTER_COLOR, bold=True)
    active_label = _paint("Currently active languages:", SECTION_COLOR, bold=True)
    active_tags = []
    for code in cfg.active_languages:
        active_tags.append(_paint(_language_label(code), _language_color(code), bold=True))
    active_display = ", ".join(active_tags) if active_tags else _paint("None", DIM_COLOR, dim=True)

    print()
    print(f"  {total_label} {total_count}")
    print(f"  {active_label} {active_display}")

    _print_language_section(stats, width)
    _print_command_section(stats, width)
    _print_alias_section(stats)
    _print_signature_moves(stats)
    print()
    print(_paint("Tip: Run commands like `git tirar` or `git confirmar` to uncover more trends.", DIM_COLOR, dim=True))


def _partition_achievements(
    achievements_state: Mapping[str, Any]
) -> tuple[List[tuple[AchievementDefinition, Mapping[str, Any]]], List[AchievementDefinition]]:
    earned_map = achievements_state.get("earned")
    earned = earned_map if isinstance(earned_map, Mapping) else {}
    unlocked: List[tuple[AchievementDefinition, Mapping[str, Any]]] = []
    locked: List[AchievementDefinition] = []
    for definition in ACHIEVEMENTS:
        payload = earned.get(definition.identifier) if isinstance(earned, Mapping) else None
        if isinstance(payload, Mapping):
            unlocked.append((definition, payload))
        else:
            locked.append(definition)
    return unlocked, locked


def _print_achievement_summary(achievements_state: Mapping[str, Any]) -> None:
    earned = achievements_state.get("earned")
    earned_count = len(earned) if isinstance(earned, Mapping) else 0
    total = len(ACHIEVEMENTS)
    remaining = max(0, total - earned_count)
    _banner("Achievement Ledger")
    unlocked_label = _paint("Unlocked wonders:", SECTION_COLOR, bold=True)
    remaining_label = _paint("Mysteries remaining:", SECTION_COLOR, bold=True)
    unlocked_value = _paint(_format_number(earned_count), COUNTER_COLOR, bold=True)
    remaining_value = _paint(_format_number(remaining), COUNTER_COLOR, bold=True)
    print()
    print(f"  {unlocked_label} {unlocked_value} / {_paint(_format_number(total), DIM_COLOR, dim=True)}")
    print(f"  {remaining_label} {remaining_value}")
    print()
    if remaining:
        print(_paint("Keep exploring languages—the secrets stay hidden until you earn them!", DIM_COLOR, dim=True))
    else:
        print(_paint("You have unlocked every achievement. A legend in every tongue!", COUNTER_COLOR, bold=True))

def _bar_line(
    label: str,
    count: int,
    max_value: int,
    total: int,
    bar_width: int,
    color: str,
) -> str:
    safe_max = max_value if max_value > 0 else max(count, 1)
    ratio = count / safe_max if safe_max else 0.0
    filled = int(round(ratio * bar_width))
    if count > 0:
        filled = max(1, min(bar_width, filled))
    empty = max(0, bar_width - filled)
    bar = ("█" * filled) + (" " * empty)
    label_field = 18
    label_text = label if len(label) <= label_field else label[: label_field - 1] + "…"
    label_text = label_text.ljust(label_field)
    styled_label = _paint(label_text, color, bold=True)
    colored_bar = _paint(bar, color)
    count_text = _paint(_format_number(count), COUNTER_COLOR, bold=True)
    percent = (count / total * 100) if total else 0.0
    percent_text = _paint(f"{percent:5.1f}%", DIM_COLOR, dim=True)
    return f"  {styled_label} {colored_bar} {count_text:>8} {percent_text}"


def _render_metric_table(
    entries: List[tuple[str, int]],
    *,
    total: int,
    bar_width: int,
    label_fn,
    color_fn,
) -> None:
    if not entries:
        print(_paint("  No activity yet. Try a translated command to begin the journey!", DIM_COLOR, dim=True))
        return
    max_value = entries[0][1]
    for key, count in entries:
        label = label_fn(key)
        color = color_fn(key)
        line = _bar_line(label, count, max_value, total, bar_width, color)
        print(line)


def _print_compact_table(entries: Sequence[str], indent: str = "    ") -> None:
    if not entries:
        print(f"{indent}(none recorded.)")
        return
    width = _terminal_width()
    columns = max(1, min(3, width // 28))
    rows = (len(entries) + columns - 1) // columns
    column_widths: List[int] = []
    for col in range(columns):
        max_len = 0
        for row in range(rows):
            idx = row * columns + col
            if idx >= len(entries):
                continue
            max_len = max(max_len, len(entries[idx]))
        column_widths.append(max_len)
    for row in range(rows):
        parts: List[str] = []
        for col in range(columns):
            idx = row * columns + col
            if idx >= len(entries):
                continue
            text = entries[idx]
            width_hint = column_widths[col]
            if col < columns - 1:
                parts.append(text.ljust(width_hint))
            else:
                parts.append(text)
        print(f"{indent}" + "   ".join(parts).rstrip())


def _print_language_section(stats: Mapping[str, Any], width: int) -> None:
    language_counts = stats.get("languages")
    filtered: Dict[str, int] = {}
    if isinstance(language_counts, Mapping):
        for code, value in language_counts.items():
            if not isinstance(code, str) or code == DEFAULT_LANGUAGE_KEY:
                continue
            if isinstance(value, int) and value > 0:
                filtered[code] = value
    total = sum(filtered.values())
    entries = _top_entries(filtered, 6)
    bar_width = max(10, min(36, width - 48))
    _section_heading("Language Frequency")
    _render_metric_table(
        entries,
        total=total,
        bar_width=bar_width,
        label_fn=_language_label,
        color_fn=_language_color,
    )

def _banner(title: str) -> None:
    span = len(title) + 4
    top = "╔" + "═" * span + "╗"
    middle = f"║  {title}  ║"
    bottom = "╚" + "═" * span + "╝"
    print(_paint(top, SECTION_COLOR, bold=True))
    print(_paint(middle, SECTION_COLOR, bold=True))
    print(_paint(bottom, SECTION_COLOR, bold=True))


def _section_heading(title: str) -> None:
    print()
    print(_paint(title, SECTION_COLOR, bold=True))


def _top_entries(mapping: Any, limit: int) -> List[tuple[str, int]]:
    if not isinstance(mapping, Mapping):
        return []
    items: List[tuple[str, int]] = []
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, int) and value > 0:
            items.append((key, value))
    items.sort(key=lambda pair: pair[1], reverse=True)
    return items[:limit]


def _language_color(code: str) -> str:
    return LANGUAGE_COLORS.get(code, SECTION_COLOR)


def _print_achievement_showcase(achievements_state: Mapping[str, Any]) -> None:
    unlocked, locked = _partition_achievements(achievements_state)
    width = _terminal_width()
    wrap_width = max(48, min(width - 10, 80))

    _banner("Achievement Showcase")
    print()

    _section_heading("Unlocked Achievements")
    if not unlocked:
        print(_paint("  None unlocked yet. Launch a localized command to begin your collection!", DIM_COLOR, dim=True))
    else:
        for definition, meta in unlocked:
            color = getattr(definition, "color", SECTION_COLOR)
            title = f"{definition.emoji}  {definition.name}"
            print(_paint(f"  {title}", color, bold=True))
            for line in textwrap.wrap(definition.description, width=wrap_width):
                print(_paint(f"    {line}", color))
            awarded = meta.get("awarded_at")
            if isinstance(awarded, str):
                print(_paint(f"    Earned on {awarded}", DIM_COLOR, dim=True))
            print()

    _section_heading("Locked Achievements")
    if not locked:
        print(_paint("  You have unlocked every achievement. Phenomenal!", COUNTER_COLOR, bold=True))
        return

    for definition in locked:
        title = f"{definition.emoji}  {definition.name}"
        print(_paint(f"  {title}", LOCKED_FG_COLOR, bold=True, bg=LOCKED_BG_COLOR))
        for line in textwrap.wrap(definition.description, width=wrap_width):
            print(_paint(f"    {line}", LOCKED_FG_COLOR, bg=LOCKED_BG_COLOR))
        print()

def _display_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


def _animation_disabled_by_env() -> bool:
    value = os.environ.get(_ANIMATION_DISABLE_ENV, "0")
    if value in _TRUTHY:
        return True
    # Backward-compatible alias
    legacy = os.environ.get("GLOBAL_GIT_DISABLE_ANIMATION")
    return bool(legacy and legacy in _TRUTHY)


def _print_welcome(cfg: TranslationConfig, animation_played: bool) -> None:
    active = ", ".join(cfg.active_languages) if cfg.active_languages else "none"
    if not animation_played:
        print(ASCII_GLOBE.rstrip())
        print()
    print("Finally, you can use Git commands in Spanish/French/British/etc. without your computer yelling at you")
    print()
    print(f"Active languages: {active}")
    print()
    print("Helpful commands:")
    print("  gitglobal show [code...]   view translations for specific languages")
    print("  gitglobal languages        list available languages")
    print("  gitglobal switch <codes>   choose the languages Git understands")
    print("  gitglobal all              enable every language")
    print()
    print("Tip: try localized help like `gitglobal --ayuda` for Spanish translations.")


def _language_lookup(cfg: TranslationConfig) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for code in cfg.languages.keys():
        lookup[code.lower()] = code
        lookup[_display_name(code).lower()] = code
    return lookup


def _resolve_language_codes(tokens: Sequence[str], cfg: TranslationConfig) -> List[str]:
    lookup = _language_lookup(cfg)
    resolved: List[str] = []
    for token in tokens:
        key = token.lower()
        if key == "all":
            return list(cfg.languages.keys())
        if key not in lookup:
            raise ValueError(f"Unknown language '{token}'.")
        code = lookup[key]
        if code not in resolved:
            resolved.append(code)
    return resolved


def _localized_help_request(args: Sequence[str], languages: Mapping[str, LanguageDefinition]) -> str | None:
    if len(args) != 1:
        return None
    token = args[0]
    if token in {"--help", "-h"}:
        return None
    key = token.lower()
    for lang in languages.values():
        for alias, target in lang.flags.items():
            if target == "--help" and alias.lower() == key:
                return lang.code
    return None


def _print_language_details(codes: Iterable[str], cfg: TranslationConfig) -> int:
    languages = cfg.languages
    any_printed = False
    for code in codes:
        lang = languages.get(code)
        if not lang:
            continue
        any_printed = True
        name = _display_name(code)
        print(f"{name} ({code})")
        command_items = sorted(lang.commands.items())
        print("  Commands:")
        command_lines = [f"git {original} -> git {mapped}" for original, mapped in command_items]
        _print_compact_table(command_lines)

        flag_items = sorted(lang.flags.items())
        print("  Flags:")
        flag_lines = [f"{original} -> {mapped}" for original, mapped in flag_items]
        _print_compact_table(flag_lines)
        print()
    if not any_printed:
        print("No matching languages to display.", file=sys.stderr)
        return 1
    return 0


def _print_languages(cfg: TranslationConfig) -> None:
    active = set(cfg.active_languages)
    print("Available languages:")
    for code, lang in cfg.languages.items():
        marker = "*" if code in active else " "
        name = _display_name(code)
        print(f" {marker} {name} ({code})")
    if active:
        print("\n* denotes currently active languages.")


def _print_status(active_languages: Sequence[str]) -> None:
    active = ", ".join(active_languages) if active_languages else "none"
    print(f"Active languages: {active}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitglobal",
        description="Manage global-git's language configuration.",
    )
    parser.add_argument(
        "--no-animation",
        action="store_true",
        help="Skip the startup globe animation (env: GLOBAL_GIT_NO_ANIMATION=1).",
    )
    subparsers = parser.add_subparsers(dest="command")

    show_parser = subparsers.add_parser("show", help="Display translations for languages.")
    show_parser.add_argument("codes", nargs="*", help="Language codes (e.g. es, fr) or names.")
    show_parser.add_argument("--all", action="store_true", help="Display every language.")

    subparsers.add_parser("languages", help="List all known languages.")

    switch_parser = subparsers.add_parser("switch", help="Select which languages are active.")
    switch_parser.add_argument("codes", nargs="*", help="Language codes or names.")
    switch_parser.add_argument("--all", action="store_true", help="Activate every language.")

    subparsers.add_parser("all", help="Activate every language.")
    subparsers.add_parser("status", help="Show the current language selection.")
    subparsers.add_parser("stats", help="Display your GitGlobal usage dashboard.")
    achievements_parser = subparsers.add_parser(
        "achievements",
        help="Step into an interactive gallery of your localized milestones.",
    )
    achievements_parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        dest="stats",
        help="Show counts of unlocked achievements instead of the interactive gallery.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    cfg = load_config()
    args = list(argv if argv is not None else sys.argv[1:])

    localized = _localized_help_request(args, cfg.languages)
    if localized:
        return _print_language_details([localized], cfg)

    parser = _build_parser()
    namespace = parser.parse_args(args)
    command = namespace.command

    if command is None:
        animation_disabled = _animation_disabled_by_env() or getattr(namespace, "no_animation", False)
        animation_played = False
        if not animation_disabled:
            animation_played = show_globe_animation()
            if animation_played:
                print()
        _print_welcome(cfg, animation_played)
        return 0

    if command == "show":
        if getattr(namespace, "all", False):
            targets = list(cfg.languages.keys())
        elif namespace.codes:
            try:
                targets = _resolve_language_codes(namespace.codes, cfg)
            except ValueError as exc:
                parser.error(str(exc))
        else:
            targets = list(cfg.active_languages)
        return _print_language_details(targets, cfg)

    if command == "languages":
        _print_languages(cfg)
        return 0

    if command == "stats":
        stats = load_usage_stats()
        _print_stats_dashboard(stats, cfg)
        return 0

    if command == "switch":
        if getattr(namespace, "all", False):
            targets = list(cfg.languages.keys())
        else:
            if not namespace.codes:
                parser.error("Provide at least one language or use --all.")
            try:
                targets = _resolve_language_codes(namespace.codes, cfg)
            except ValueError as exc:
                parser.error(str(exc))
        try:
            save_active_languages(targets)
        except OSError as exc:
            print(f"Unable to update active languages: {exc}", file=sys.stderr)
            return 1
        print("Active languages updated:")
        _print_status(targets)
        return 0

    if command == "all":
        targets = list(cfg.languages.keys())
        try:
            save_active_languages(targets)
        except OSError as exc:
            print(f"Unable to update active languages: {exc}", file=sys.stderr)
            return 1
        print("All languages activated.")
        _print_status(targets)
        return 0

    if command == "status":
        _print_status(cfg.active_languages)
        return 0

    if command == "achievements":
        achievements_state = load_achievements_state()
        if getattr(namespace, "stats", False):
            _print_achievement_summary(achievements_state)
        else:
            _print_achievement_showcase(achievements_state)
        return 0

    _print_welcome(cfg, False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
