from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence

from .state import DEFAULT_LANGUAGE_KEY


@dataclass(frozen=True)
class AliasThreshold:
    alias: str
    threshold: int
    language: str | None = None


@dataclass(frozen=True)
class LanguageDiversity:
    minimum_languages: int
    minimum_each: int


Criterion = AliasThreshold | LanguageDiversity


@dataclass(frozen=True)
class AchievementDefinition:
    identifier: str
    name: str
    description: str
    emoji: str
    color: str
    criteria: Criterion


ACHIEVEMENTS: Sequence[AchievementDefinition] = (
    AchievementDefinition(
        identifier="fr_pull_marathon",
        name="French Pull Marathon",
        description="Call `git tirer` one hundred times to truly master the art of syncing.",
        emoji="🗼",
        color="38;5;219",
        criteria=AliasThreshold(alias="tirer", language="fr", threshold=100),
    ),
    AchievementDefinition(
        identifier="es_commit_conquistador",
        name="Commit Conquistador",
        description="Confirm your work with `git cometer` at least seventy-five times.",
        emoji="🪶",
        color="38;5;208",
        criteria=AliasThreshold(alias="cometer", language="es", threshold=75),
    ),
    AchievementDefinition(
        identifier="de_push_dynamo",
        name="Push Dynamo",
        description="Launch code skyward with `git schieben` sixty times.",
        emoji="🚀",
        color="38;5;40",
        criteria=AliasThreshold(alias="schieben", language="de", threshold=60),
    ),
    AchievementDefinition(
        identifier="pt_pull_wave",
        name="Atlântico Pull Wave",
        description="Ride the tides with fifty uses of `git puxar`.",
        emoji="🌊",
        color="38;5;33",
        criteria=AliasThreshold(alias="puxar", language="pt", threshold=50),
    ),
    AchievementDefinition(
        identifier="polyglot_trailblazer",
        name="Polyglot Trailblazer",
        description="Use translated commands in at least three languages forty times each.",
        emoji="🧭",
        color="38;5;201",
        criteria=LanguageDiversity(minimum_languages=3, minimum_each=40),
    ),
)

ACHIEVEMENT_LOOKUP = {achievement.identifier: achievement for achievement in ACHIEVEMENTS}


def _alias_met(stats: Mapping[str, object], criterion: AliasThreshold) -> bool:
    aliases = stats.get("aliases")
    if not isinstance(aliases, Mapping):
        return False
    entry = aliases.get(criterion.alias.lower())
    if not isinstance(entry, Mapping):
        return False
    count = entry.get("count")
    if not isinstance(count, int):
        return False
    if criterion.language:
        language = entry.get("language")
        if language != criterion.language:
            return False
    return count >= criterion.threshold


def _language_diversity_met(stats: Mapping[str, object], criterion: LanguageDiversity) -> bool:
    languages = stats.get("languages")
    if not isinstance(languages, Mapping):
        return False
    qualifying = 0
    for code, value in languages.items():
        if not isinstance(code, str):
            continue
        if code == DEFAULT_LANGUAGE_KEY:
            continue
        count = value if isinstance(value, int) else None
        if count is None:
            continue
        if count >= criterion.minimum_each:
            qualifying += 1
    return qualifying >= criterion.minimum_languages


def is_achievement_met(stats: Mapping[str, object], definition: AchievementDefinition) -> bool:
    criteria = definition.criteria
    if isinstance(criteria, AliasThreshold):
        return _alias_met(stats, criteria)
    if isinstance(criteria, LanguageDiversity):
        return _language_diversity_met(stats, criteria)
    return False


def newly_earned_achievements(
    stats: Mapping[str, object],
    earned_ids: Iterable[str],
) -> List[str]:
    earned_set = {str(identifier) for identifier in earned_ids}
    unlocked: List[str] = []
    for definition in ACHIEVEMENTS:
        if definition.identifier in earned_set:
            continue
        if is_achievement_met(stats, definition):
            unlocked.append(definition.identifier)
    return unlocked
