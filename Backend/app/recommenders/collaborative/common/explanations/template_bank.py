from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.recommenders.collaborative.common.explanations.models import (
    CollaborativeExplanationStrength,
)


COLLABORATIVE_EXPLANATION_TEMPLATES_PATH = (
    Path(__file__).resolve().parent / "collaborative_explanation_templates.json"
)
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
DEFAULT_STRENGTHS: tuple[CollaborativeExplanationStrength, ...] = (
    "strong",
    "medium",
    "weak",
    "fallback",
)


@dataclass(frozen=True)
class CollaborativeExplanationTemplate:
    id: str
    text: str
    requires: list[str]
    strength: CollaborativeExplanationStrength


@dataclass(frozen=True)
class CollaborativeExplanationTemplateBank:
    version: int
    description: str
    selection: dict[str, Any]
    groups: dict[str, dict[CollaborativeExplanationStrength, list[CollaborativeExplanationTemplate]]]
    source: str


@dataclass
class CollaborativeExplanationTemplateUsage:
    used_template_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CollaborativeTemplateSelectionInput:
    templateSeed: str | None
    algorithmId: str
    variantId: str | None
    movieId: int | None
    rank: int | None
    explanationType: str
    evidenceStrength: CollaborativeExplanationStrength
    evidenceMovieIds: list[int]


@lru_cache(maxsize=1)
def load_collaborative_template_bank() -> CollaborativeExplanationTemplateBank:
    base_bank = _build_builtin_template_bank()
    if not COLLABORATIVE_EXPLANATION_TEMPLATES_PATH.exists():
        return base_bank

    try:
        raw_bank = json.loads(
            COLLABORATIVE_EXPLANATION_TEMPLATES_PATH.read_text(encoding="utf-8")
        )
        return _merge_raw_bank_with_builtin(raw_bank, base_bank)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return base_bank


def select_template(
    *,
    template_bank: CollaborativeExplanationTemplateBank,
    usage: CollaborativeExplanationTemplateUsage,
    selection_input: CollaborativeTemplateSelectionInput,
    available_values: dict[str, str],
) -> CollaborativeExplanationTemplate | None:
    group_names = [
        selection_input.explanationType,
        _group_for_algorithm(selection_input.algorithmId),
        "fallback_low_evidence",
    ]
    strengths_to_try = _strength_order(selection_input.evidenceStrength)

    for group_name in group_names:
        if not group_name:
            continue
        for strength in strengths_to_try:
            templates = template_bank.groups.get(group_name, {}).get(strength, [])
            viable = [
                template
                for template in templates
                if _requirements_satisfied(template, available_values)
            ]
            if not viable:
                continue

            unused = [
                template
                for template in viable
                if template.id not in usage.used_template_ids
            ]
            pool = unused or viable
            ordered = sorted(
                pool,
                key=lambda template: _stable_template_key(
                    selection_input=selection_input,
                    template_id=template.id,
                ),
            )
            selected = ordered[0]
            usage.used_template_ids.add(selected.id)
            return selected

    return None


def render_template(
    template: CollaborativeExplanationTemplate,
    available_values: dict[str, str],
) -> str:
    rendered_text = template.text
    for placeholder in PLACEHOLDER_RE.findall(template.text):
        value = available_values.get(placeholder, "")
        rendered_text = rendered_text.replace(f"{{{placeholder}}}", value)
    return rendered_text


def _merge_raw_bank_with_builtin(
    raw_bank: dict[str, Any],
    builtin_bank: CollaborativeExplanationTemplateBank,
) -> CollaborativeExplanationTemplateBank:
    version = int(raw_bank.get("version", builtin_bank.version))
    description = str(raw_bank.get("description", builtin_bank.description))
    selection = dict(builtin_bank.selection)
    if isinstance(raw_bank.get("selection"), dict):
        selection.update(raw_bank["selection"])

    groups: dict[str, dict[CollaborativeExplanationStrength, list[CollaborativeExplanationTemplate]]] = {
        group_name: {
            strength: list(templates)
            for strength, templates in strengths.items()
        }
        for group_name, strengths in builtin_bank.groups.items()
    }

    raw_groups = raw_bank.get("groups")
    if not isinstance(raw_groups, dict):
        return builtin_bank

    for group_name, raw_group in raw_groups.items():
        group_templates = _parse_group_templates(group_name, raw_group)
        if not group_templates:
            continue
        bucket = groups.setdefault(group_name, _empty_group_bucket())
        for strength, templates in group_templates.items():
            bucket[strength].extend(templates)

    return CollaborativeExplanationTemplateBank(
        version=version,
        description=description,
        selection=selection,
        groups=groups,
        source=str(COLLABORATIVE_EXPLANATION_TEMPLATES_PATH),
    )


def _parse_group_templates(
    group_name: str,
    raw_group: Any,
) -> dict[CollaborativeExplanationStrength, list[CollaborativeExplanationTemplate]]:
    parsed = _empty_group_bucket()

    if isinstance(raw_group, list):
        for raw_template in raw_group:
            template = _parse_template(raw_template, default_strength="medium")
            if template is not None:
                parsed[template.strength].append(template)
        return parsed

    if not isinstance(raw_group, dict):
        return parsed

    for strength, raw_templates in raw_group.items():
        normalized_strength = _normalize_strength(strength)
        if normalized_strength is None or not isinstance(raw_templates, list):
            continue
        for raw_template in raw_templates:
            template = _parse_template(
                raw_template,
                default_strength=normalized_strength,
            )
            if template is not None:
                parsed[template.strength].append(template)

    return parsed


def _parse_template(
    raw_template: Any,
    *,
    default_strength: CollaborativeExplanationStrength,
) -> CollaborativeExplanationTemplate | None:
    if not isinstance(raw_template, dict):
        return None

    template_id = raw_template.get("id")
    text = raw_template.get("text")
    requires = raw_template.get("requires", [])
    strength = _normalize_strength(raw_template.get("strength")) or default_strength

    if not isinstance(template_id, str) or not template_id.strip():
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    if not isinstance(requires, list):
        return None

    normalized_requires = [
        str(item).strip()
        for item in requires
        if isinstance(item, str) and str(item).strip()
    ]
    placeholders = set(PLACEHOLDER_RE.findall(text))
    if placeholders - set(normalized_requires):
        return None

    return CollaborativeExplanationTemplate(
        id=template_id.strip(),
        text=text.strip(),
        requires=normalized_requires,
        strength=strength,
    )


def _requirements_satisfied(
    template: CollaborativeExplanationTemplate,
    available_values: dict[str, str],
) -> bool:
    for requirement in template.requires:
        if not available_values.get(requirement):
            return False
    return True


def _stable_template_key(
    *,
    selection_input: CollaborativeTemplateSelectionInput,
    template_id: str,
) -> str:
    payload = "|".join(
        [
            selection_input.templateSeed or "",
            selection_input.algorithmId,
            selection_input.variantId or "",
            str(selection_input.movieId or ""),
            str(selection_input.rank or ""),
            selection_input.explanationType,
            selection_input.evidenceStrength,
            ",".join(str(movie_id) for movie_id in selection_input.evidenceMovieIds),
            template_id,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_strength(value: Any) -> CollaborativeExplanationStrength | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in DEFAULT_STRENGTHS:
        return normalized
    return None


def _strength_order(
    requested_strength: CollaborativeExplanationStrength,
) -> list[CollaborativeExplanationStrength]:
    if requested_strength == "strong":
        return ["strong", "medium", "weak", "fallback"]
    if requested_strength == "medium":
        return ["medium", "strong", "weak", "fallback"]
    if requested_strength == "weak":
        return ["weak", "medium", "fallback", "strong"]
    return ["fallback", "weak", "medium", "strong"]


def _group_for_algorithm(algorithm_id: str) -> str | None:
    mapping = {
        "item_knn_cosine": "item_knn_similar_movies",
        "user_knn_pearson_shrinkage": "user_knn_similar_profiles",
        "biased_matrix_factorization": "bmf_profile_pattern",
        "popularity_baseline": "popularity_general",
    }
    return mapping.get(algorithm_id)


def _empty_group_bucket() -> dict[
    CollaborativeExplanationStrength, list[CollaborativeExplanationTemplate]
]:
    return {strength: [] for strength in DEFAULT_STRENGTHS}


def _build_builtin_template_bank() -> CollaborativeExplanationTemplateBank:
    return CollaborativeExplanationTemplateBank(
        version=1,
        description=(
            "Built-in fallback template bank for collaborative recommendation explanations."
        ),
        selection={
            "deterministic": True,
            "recommended_seed_parts": [
                "templateSeed",
                "algorithmId",
                "variantId",
                "movieId",
                "rank",
                "explanationType",
                "evidenceStrength",
                "evidenceMovieIds",
            ],
        },
        groups={
            "item_knn_similar_movies": {
                "strong": [
                    CollaborativeExplanationTemplate(
                        id="builtin_item_knn_strong_001",
                        text="Como te gustaron {movies}, esta pelicula tiene bastante sentido en tu lista.",
                        requires=["movies"],
                        strength="strong",
                    ),
                    CollaborativeExplanationTemplate(
                        id="builtin_item_knn_strong_002",
                        text="Esta no sale al azar: varias pelis que te gustaron apuntan hacia ella, como {movies}.",
                        requires=["movies"],
                        strength="strong",
                    ),
                ],
                "medium": [
                    CollaborativeExplanationTemplate(
                        id="builtin_item_knn_medium_001",
                        text="Esta pelicula encaja con algunas peliculas que has valorado bien, como {movies}.",
                        requires=["movies"],
                        strength="medium",
                    ),
                ],
                "weak": [
                    CollaborativeExplanationTemplate(
                        id="builtin_item_knn_weak_001",
                        text="Esta pelicula encaja con algunas señales de tus valoraciones.",
                        requires=[],
                        strength="weak",
                    ),
                ],
                "fallback": [],
            },
            "user_knn_similar_profiles": {
                "strong": [
                    CollaborativeExplanationTemplate(
                        id="builtin_user_knn_strong_001",
                        text="Perfiles con gustos parecidos al tuyo tambien disfrutaron esta pelicula.",
                        requires=[],
                        strength="strong",
                    ),
                ],
                "medium": [
                    CollaborativeExplanationTemplate(
                        id="builtin_user_knn_medium_001",
                        text="Esta recomendacion encaja con valoraciones de personas que se parecen bastante a tu perfil.",
                        requires=[],
                        strength="medium",
                    ),
                ],
                "weak": [
                    CollaborativeExplanationTemplate(
                        id="builtin_user_knn_weak_001",
                        text="Hay varias pistas en tus valoraciones que acercan esta pelicula a tu perfil.",
                        requires=[],
                        strength="weak",
                    ),
                ],
                "fallback": [],
            },
            "bmf_profile_pattern": {
                "strong": [
                    CollaborativeExplanationTemplate(
                        id="builtin_bmf_strong_001",
                        text="Esta pelicula encaja bastante con el patron que dejan tus valoraciones.",
                        requires=[],
                        strength="strong",
                    ),
                ],
                "medium": [
                    CollaborativeExplanationTemplate(
                        id="builtin_bmf_medium_001",
                        text="Esta pelicula encaja con algunas señales de tus valoraciones.",
                        requires=[],
                        strength="medium",
                    ),
                ],
                "weak": [
                    CollaborativeExplanationTemplate(
                        id="builtin_bmf_weak_001",
                        text="Tu perfil de valoraciones apunta en parte hacia esta pelicula.",
                        requires=[],
                        strength="weak",
                    ),
                ],
                "fallback": [],
            },
            "popularity_general": {
                "strong": [
                    CollaborativeExplanationTemplate(
                        id="builtin_popularity_strong_001",
                        text="Como aun sabemos poco de tus gustos, esta recomendacion se apoya en peliculas que suelen funcionar bien.",
                        requires=[],
                        strength="strong",
                    ),
                ],
                "medium": [
                    CollaborativeExplanationTemplate(
                        id="builtin_popularity_medium_001",
                        text="Esta pelicula puede ser una buena candidata porque suele funcionar bien con mucha gente.",
                        requires=[],
                        strength="medium",
                    ),
                ],
                "weak": [],
                "fallback": [],
            },
            "fallback_low_evidence": {
                "strong": [],
                "medium": [],
                "weak": [
                    CollaborativeExplanationTemplate(
                        id="builtin_low_evidence_weak_001",
                        text="Todavia tenemos pocas pistas sobre tus gustos, pero esta pelicula puede ser una buena candidata.",
                        requires=[],
                        strength="weak",
                    ),
                ],
                "fallback": [
                    CollaborativeExplanationTemplate(
                        id="builtin_low_evidence_fallback_001",
                        text="Como aun sabemos poco de tus gustos, esta recomendacion se apoya en peliculas que suelen funcionar bien.",
                        requires=[],
                        strength="fallback",
                    ),
                ],
            },
        },
        source="builtin",
    )
