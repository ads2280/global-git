from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .achievements import ACHIEVEMENT_LOOKUP, ACHIEVEMENTS, AchievementDefinition
from .config import LanguageDefinition, TranslationConfig, load_config
from .globe_animation import show_globe_animation
from .state import save_active_languages


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

    _print_welcome(cfg, False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
