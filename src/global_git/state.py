from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "global-git")
STATE_PATH = os.path.join(CONFIG_DIR, "state.json")

DEFAULT_LANGUAGE_KEY = "__core__"


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _unique_ordered(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _load_state() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _write_state(payload: Mapping[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _ensure_stats_structure(raw: Any) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    if isinstance(raw, dict):
        stats.update(raw)

    if not isinstance(stats.get("total_invocations"), int):
        stats["total_invocations"] = 0
    stats.setdefault("commands", {})
    stats.setdefault("languages", {})
    stats.setdefault("aliases", {})
    stats.setdefault("language_command_counts", {})
    return stats


def _ensure_achievements_structure(raw: Any) -> Dict[str, Any]:
    achievements: Dict[str, Any] = {}
    if isinstance(raw, dict):
        achievements.update(raw)
    earned = achievements.get("earned")
    if not isinstance(earned, dict):
        earned = {}
    achievements["earned"] = earned
    notified = achievements.get("notified")
    if isinstance(notified, list):
        achievements["notified"] = [str(item) for item in notified if isinstance(item, str)]
    else:
        achievements["notified"] = []
    return achievements


def _sanitize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE_KEY
    return language


def load_active_languages(available_codes: Iterable[str]) -> Tuple[str, ...]:
    available = list(available_codes)
    available_set = {code.lower(): code for code in available}

    payload = _load_state()
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

    return tuple(available)


def save_active_languages(codes: Sequence[str]) -> None:
    state = _load_state()
    ordered = _unique_ordered(code.lower() for code in codes if code)
    state["active_languages"] = ordered
    _write_state(state)


def record_command_usage(
    base_command: str | None,
    *,
    language: str | None = None,
    alias: str | None = None,
) -> Dict[str, Any]:
    payload = _load_state()
    stats = _ensure_stats_structure(payload.get("usage_stats"))

    timestamp = _now_timestamp()
    stats["total_invocations"] += 1

    if base_command:
        commands = stats.get("commands")
        if not isinstance(commands, dict):
            commands = {}
            stats["commands"] = commands
        commands[base_command] = int(commands.get(base_command, 0)) + 1

    lang_key = _sanitize_language(language)
    languages = stats.get("languages")
    if not isinstance(languages, dict):
        languages = {}
        stats["languages"] = languages
    languages[lang_key] = int(languages.get(lang_key, 0)) + 1

    if base_command:
        per_lang = stats.get("language_command_counts")
        if not isinstance(per_lang, dict):
            per_lang = {}
            stats["language_command_counts"] = per_lang
        lang_bucket = per_lang.get(lang_key)
        if not isinstance(lang_bucket, dict):
            lang_bucket = {}
            per_lang[lang_key] = lang_bucket
        lang_bucket[base_command] = int(lang_bucket.get(base_command, 0)) + 1

    if alias:
        alias_key = alias.lower()
        aliases = stats.get("aliases")
        if not isinstance(aliases, dict):
            aliases = {}
            stats["aliases"] = aliases
        entry = aliases.get(alias_key)
        if not isinstance(entry, dict):
            entry = {}
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["label"] = alias
        entry["language"] = language
        entry["command"] = base_command
        entry.setdefault("first_used_at", timestamp)
        entry["last_used_at"] = timestamp
        aliases[alias_key] = entry

    payload["usage_stats"] = stats
    _write_state(payload)
    return stats


def load_usage_stats() -> Dict[str, Any]:
    payload = _load_state()
    stats = _ensure_stats_structure(payload.get("usage_stats"))
    payload["usage_stats"] = stats
    _write_state(payload)
    # Deep copy to avoid accidental mutation by callers
    return json.loads(json.dumps(stats))


def load_achievements_state() -> Dict[str, Any]:
    payload = _load_state()
    achievements = _ensure_achievements_structure(payload.get("achievements"))
    payload["achievements"] = achievements
    _write_state(payload)
    return json.loads(json.dumps(achievements))


def award_achievements(ids: Iterable[str]) -> Tuple[list[str], Dict[str, Any]]:
    normalized = [str(identifier) for identifier in ids if identifier]
    if not normalized:
        achievements = load_achievements_state()
        return [], achievements

    payload = _load_state()
    achievements = _ensure_achievements_structure(payload.get("achievements"))
    earned = achievements["earned"]
    now = _now_timestamp()
    newly_awarded: list[str] = []
    for identifier in normalized:
        if identifier in earned:
            continue
        earned[identifier] = {"awarded_at": now}
        newly_awarded.append(identifier)
    if newly_awarded:
        payload["achievements"] = achievements
        _write_state(payload)
    return newly_awarded, json.loads(json.dumps(achievements))
