from __future__ import annotations

import json
import os
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple

try:
    from importlib.resources import files as resource_files  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    from importlib_resources import files as resource_files  # type: ignore[no-redef]

from .state import load_active_languages


CONFIG_ENV = "GLOBAL_GIT_CONFIG"
USER_CONFIG_HOME = os.path.join(os.path.expanduser("~"), ".config", "global-git")
USER_CONFIG_PATH = os.path.join(USER_CONFIG_HOME, "config.json")


@dataclass(frozen=True)
class LanguageDefinition:
    code: str
    commands: Mapping[str, str]
    flags: Mapping[str, str]
    outputs: Mapping[str, str]


@dataclass(frozen=True)
class _LoadedConfig:
    languages: Mapping[str, LanguageDefinition]
    commands: Mapping[str, str]
    flags: Mapping[str, str]
    outputs: Mapping[str, str]


@dataclass(frozen=True)
class TranslationConfig:
    command_map: Mapping[str, str]
    command_sources: Mapping[str, str]
    flag_map: Mapping[str, str]
    flag_sources: Mapping[str, str]
    output_map: Mapping[str, str]
    languages: Mapping[str, LanguageDefinition]
    active_languages: Tuple[str, ...]


def _lowercase_map(data: Mapping[str, str]) -> Dict[str, str]:
    return {str(k).lower(): str(v) for k, v in data.items()}


def _to_str_map(data: Mapping[str, str]) -> Dict[str, str]:
    return {str(k): str(v) for k, v in data.items()}


def _parse_config(payload: Mapping) -> _LoadedConfig:
    languages: Dict[str, LanguageDefinition] = {}
    commands: Dict[str, str] = {}
    flags: Dict[str, str] = {}
    outputs: Dict[str, str] = {}

    langs = payload.get("languages")
    if isinstance(langs, MappingABC):
        for raw_code, section in langs.items():
            if not isinstance(section, MappingABC):
                continue
            code = str(raw_code)
            lang_commands = {}
            lang_flags = {}
            lang_outputs = {}
            raw_commands = section.get("commands", {})
            raw_flags = section.get("flags", {})
            raw_outputs = section.get("outputs", {})
            if isinstance(raw_commands, MappingABC):
                lang_commands.update(_lowercase_map({k: v for k, v in raw_commands.items()}))
            if isinstance(raw_flags, MappingABC):
                lang_flags.update(_lowercase_map({k: v for k, v in raw_flags.items()}))
            if isinstance(raw_outputs, MappingABC):
                lang_outputs.update(_to_str_map({k: v for k, v in raw_outputs.items()}))
            languages[code] = LanguageDefinition(
                code=code,
                commands=lang_commands,
                flags=lang_flags,
                outputs=lang_outputs,
            )

    if isinstance(payload.get("commands"), MappingABC):
        commands.update(_lowercase_map(payload["commands"]))
    if isinstance(payload.get("flags"), MappingABC):
        flags.update(_lowercase_map(payload["flags"]))
    if isinstance(payload.get("outputs"), MappingABC):
        outputs.update(_to_str_map(payload["outputs"]))

    return _LoadedConfig(languages=languages, commands=commands, flags=flags, outputs=outputs)


def _merge_configs(base: _LoadedConfig, override: _LoadedConfig) -> _LoadedConfig:
    languages: Dict[str, LanguageDefinition] = {
        code: LanguageDefinition(
            code=code,
            commands=dict(lang.commands),
            flags=dict(lang.flags),
            outputs=dict(lang.outputs),
        )
        for code, lang in base.languages.items()
    }

    for code, lang in override.languages.items():
        if code in languages:
            existing = languages[code]
            merged_commands = dict(existing.commands)
            merged_commands.update(lang.commands)
            merged_flags = dict(existing.flags)
            merged_flags.update(lang.flags)
            merged_outputs = dict(existing.outputs)
            merged_outputs.update(lang.outputs)
            languages[code] = LanguageDefinition(
                code=code,
                commands=merged_commands,
                flags=merged_flags,
                outputs=merged_outputs,
            )
        else:
            languages[code] = LanguageDefinition(
                code=code,
                commands=dict(lang.commands),
                flags=dict(lang.flags),
                outputs=dict(lang.outputs),
            )

    commands = dict(base.commands)
    commands.update(override.commands)
    flags = dict(base.flags)
    flags.update(override.flags)
    outputs = dict(base.outputs)
    outputs.update(override.outputs)
    return _LoadedConfig(languages=languages, commands=commands, flags=flags, outputs=outputs)


def _load_default() -> _LoadedConfig:
    # default_config.yaml packaged with the module
    import json as _json

    path = resource_files("global_git").joinpath("default_config.yaml")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except Exception:
        data = _json.loads(text)

    if not isinstance(data, MappingABC):
        data = {}
    return _parse_config(data)


def _load_user_override() -> _LoadedConfig | None:
    # Support override via env var path or ~/.config/global-git/config.json
    path = os.environ.get(CONFIG_ENV) or USER_CONFIG_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, MappingABC):
            return _parse_config(data)
    except Exception:
        return None
    return None


def _aggregate_maps(
    config: _LoadedConfig, active: Iterable[str]
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
    command_map: Dict[str, str] = {}
    command_sources: Dict[str, str] = {}
    flag_map: Dict[str, str] = {}
    flag_sources: Dict[str, str] = {}
    output_map: Dict[str, str] = {}
    for code in active:
        lang = config.languages.get(code)
        if not lang:
            continue
        for alias, target in lang.commands.items():
            command_map[alias] = target
            command_sources[alias] = code
        for alias, target in lang.flags.items():
            flag_map[alias] = target
            flag_sources[alias] = code
        output_map.update(lang.outputs)
    # Global-level overrides are applied last so they win
    for alias, target in config.commands.items():
        command_map[alias] = target
        command_sources[alias] = "__global__"
    for alias, target in config.flags.items():
        flag_map[alias] = target
        flag_sources[alias] = "__global__"
    output_map.update(config.outputs)
    return command_map, command_sources, flag_map, flag_sources, output_map


def load_config() -> TranslationConfig:
    base = _load_default()
    user = _load_user_override()
    merged = _merge_configs(base, user) if user else base

    available_codes = tuple(merged.languages.keys())
    active_languages = load_active_languages(available_codes)
    command_map, command_sources, flag_map, flag_sources, output_map = _aggregate_maps(
        merged, active_languages
    )

    return TranslationConfig(
        command_map=command_map,
        command_sources=command_sources,
        flag_map=flag_map,
        flag_sources=flag_sources,
        output_map=output_map,
        languages=merged.languages,
        active_languages=active_languages,
    )
