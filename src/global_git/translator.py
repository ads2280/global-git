from __future__ import annotations

import re
from typing import Iterable, List, Mapping, Tuple


def _split_flag_value(token: str) -> Tuple[str, str | None]:
    # Handle --flag=value form
    if token.startswith("--") and "=" in token:
        name, value = token.split("=", 1)
        return name, value
    return token, None


def translate_args(argv: Iterable[str], command_map: Mapping[str, str], flag_map: Mapping[str, str]) -> List[str]:
    args = list(argv)

    # 1) Translate the first non-option token as the subcommand
    cmd_index = _first_non_option_index(args)
    if cmd_index is not None and cmd_index < len(args):
        original = args[cmd_index]
        mapped = command_map.get(original.lower())
        if mapped:
            args[cmd_index] = mapped

    # 2) Translate standalone flags and --flag=value names
    for i, tok in enumerate(args):
        if tok.startswith("-"):
            name, value = _split_flag_value(tok)
            mapped = flag_map.get(name.lower())
            if mapped:
                args[i] = f"{mapped}={value}" if value is not None else mapped

    return args


def translate_output_text(text: str, replacements: Mapping[str, str]) -> str:
    if not text or not replacements:
        return text
    # Apply longer phrases first to avoid partial overlaps clobbering more specific translations.
    for original in sorted(replacements, key=len, reverse=True):
        replacement = replacements[original]
        text = text.replace(original, replacement)
    return text


def _first_non_option_index(args: List[str]) -> int | None:
    # Git allows many global options before the subcommand. The first token that
    # does not start with '-' is treated as the subcommand. We skip values for
    # options that take a value (e.g., '-C path', '-c key=value').
    i = 0
    while i < len(args):
        tok = args[i]
        if not tok.startswith("-"):
            return i

        # Options with required next-arg values in git
        if tok in {"-C", "-c", "-I", "-i", "-X"}:  # not exhaustive; sufficient for wrapper
            # If next arg exists and current is not of the form -ckey=value
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 2
                continue
        i += 1
    return None
