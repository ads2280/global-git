from __future__ import annotations

import json
import os
from typing import Iterable, Sequence, Tuple


CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "global-git")
STATE_PATH = os.path.join(CONFIG_DIR, "state.json")


def _unique_ordered(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def load_active_languages(available_codes: Iterable[str]) -> Tuple[str, ...]:
    available = list(available_codes)
    available_set = {code.lower(): code for code in available}

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        saved = payload.get("active_languages", [])
        if isinstance(saved, list):
            normalized: list[str] = []
            for entry in saved:
                if not isinstance(entry, str):
                    continue
                lookup = available_set.get(entry.lower())
                if lookup and lookup not in normalized:
                    normalized.append(lookup)
            if normalized:
                return tuple(normalized)
    except Exception:
        pass

    return tuple(available)


def save_active_languages(codes: Sequence[str]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    ordered = _unique_ordered(code.lower() for code in codes if code)
    payload = {"active_languages": ordered}
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
