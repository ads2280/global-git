from __future__ import annotations

import argparse
import sys
from typing import Dict, Iterable, List, Mapping, Sequence

from .config import LanguageDefinition, TranslationConfig, load_config
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

LANGUAGE_NAMES = {
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "en-gb": "English (UK)",
}


def _display_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


def _print_welcome(cfg: TranslationConfig) -> None:
    active = ", ".join(cfg.active_languages) if cfg.active_languages else "none"
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
        if lang.commands:
            print("  Commands:")
            for original, mapped in sorted(lang.commands.items()):
                print(f"    git {original:<18} -> git {mapped}")
        else:
            print("  Commands: none recorded.")
        if lang.flags:
            print("  Flags:")
            for original, mapped in sorted(lang.flags.items()):
                print(f"    {original:<21} -> {mapped}")
        else:
            print("  Flags: none recorded.")
        if lang.outputs:
            print("  Output phrases:")
            for original, mapped in sorted(lang.outputs.items()):
                print(f"    \"{original}\" -> \"{mapped}\"")
        else:
            print("  Output phrases: none recorded.")
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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    cfg = load_config()
    args = list(argv if argv is not None else sys.argv[1:])

    localized = _localized_help_request(args, cfg.languages)
    if localized:
        return _print_language_details([localized], cfg)

    if not args:
        _print_welcome(cfg)
        return 0

    parser = _build_parser()
    namespace = parser.parse_args(args)
    command = namespace.command

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

    _print_welcome(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
