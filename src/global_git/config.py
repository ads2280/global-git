from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

try:
    from importlib.resources import files as resource_files  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    from importlib_resources import files as resource_files  # type: ignore[no-redef]


CONFIG_ENV = "GLOBAL_GIT_CONFIG"
USER_CONFIG_HOME = os.path.join(os.path.expanduser("~"), ".config", "global-git")
USER_CONFIG_PATH = os.path.join(USER_CONFIG_HOME, "config.json")


@dataclass(frozen=True)
class TranslationConfig:
    command_map: Mapping[str, str]
    flag_map: Mapping[str, str]


def _load_default() -> TranslationConfig:
    # default_config.yaml packaged with the module
    import json as _json
    path = resource_files("global_git").joinpath("default_config.yaml")
    text = path.read_text(encoding="utf-8")
    # parse very small subset of YAML (keys/values) without dependency by using a tiny shim
    # The file is structured as JSON-compatible YAML. We'll convert via a trivial loader:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except Exception:
        # Fallback: accept JSON content inside .yaml file
        data = _json.loads(text)

    return _normalize_config(data)


def _normalize_config(data: Mapping) -> TranslationConfig:
    # Support either flat maps or nested languages -> {commands, flags}
    command_map: Dict[str, str] = {}
    flag_map: Dict[str, str] = {}

    if "languages" in data:
        langs = data["languages"]
        if isinstance(langs, dict):
            for _lang, maps in langs.items():
                if isinstance(maps, dict):
                    command_map.update({k: v for k, v in maps.get("commands", {}).items()})
                    flag_map.update({k: v for k, v in maps.get("flags", {}).items()})
    else:
        command_map.update({k: v for k, v in data.get("commands", {}).items()})
        flag_map.update({k: v for k, v in data.get("flags", {}).items()})

    # Normalize keys to lower-case for case-insensitive command/flag matching
    command_map = {str(k).lower(): str(v) for k, v in command_map.items()}
    flag_map = {str(k).lower(): str(v) for k, v in flag_map.items()}
    return TranslationConfig(command_map=command_map, flag_map=flag_map)


def _load_user_override() -> TranslationConfig | None:
    # Support override via env var path or ~/.config/global-git/config.json
    path = os.environ.get(CONFIG_ENV) or USER_CONFIG_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_config(data)
    except Exception:
        return None


def load_config() -> TranslationConfig:
    base = _load_default()
    user = _load_user_override()
    if not user:
        return base
    # Merge user before default to allow overrides/expansions
    commands = dict(base.command_map)
    commands.update(user.command_map)
    flags = dict(base.flag_map)
    flags.update(user.flag_map)
    return TranslationConfig(command_map=commands, flag_map=flags)

