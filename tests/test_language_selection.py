from __future__ import annotations

from pathlib import Path

import global_git.config as config_module
import global_git.state as state_module
from global_git.config import load_config
from global_git.gitglobal_cli import _resolve_language_codes
from global_git.state import (
    DEFAULT_LANGUAGE_KEY,
    load_active_languages,
    save_active_languages,
)


def _patch_state_paths(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / ".config" / "global-git"
    state_path = config_dir / "state.json"
    monkeypatch.setattr(state_module, "CONFIG_DIR", str(config_dir), raising=False)
    monkeypatch.setattr(state_module, "STATE_PATH", str(state_path), raising=False)
    user_config_dir = tmp_path / ".config" / "global-git"
    user_config_path = user_config_dir / "config.json"
    monkeypatch.setattr(config_module, "USER_CONFIG_HOME", str(user_config_dir), raising=False)
    monkeypatch.setattr(config_module, "USER_CONFIG_PATH", str(user_config_path), raising=False)


def test_switch_core_enables_plain_git(monkeypatch, tmp_path):
    _patch_state_paths(monkeypatch, tmp_path)

    cfg = load_config()
    targets = _resolve_language_codes(["core"], cfg)
    assert targets == [DEFAULT_LANGUAGE_KEY]

    save_active_languages(targets)
    active = load_active_languages(cfg.languages.keys())
    assert active == (DEFAULT_LANGUAGE_KEY,)


def test_switch_none_disables_all_languages(monkeypatch, tmp_path):
    _patch_state_paths(monkeypatch, tmp_path)

    cfg = load_config()
    targets = _resolve_language_codes(["none"], cfg)
    assert targets == []

    save_active_languages(targets)
    active = load_active_languages(cfg.languages.keys())
    assert active == ()
