from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from functools import lru_cache

from .constants import EXPLANATION_TEMPLATES_PATH


PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
REQUIRED_GROUPS = {
    "headline",
    "signal_reason",
    "similar_movie_reason",
    "negative_avoidance_reason",
    "natural_closing",
    "profile_reaction",
}


@dataclass(frozen=True)
class ExplanationTemplate:
    id: str
    text: str
    requires: list[str]


@dataclass(frozen=True)
class ExplanationTemplateBank:
    version: int
    description: str
    selection: dict
    groups: dict[str, dict[str, list[ExplanationTemplate]]]


@dataclass
class ExplanationTemplateUsage:
    used_template_ids: set[str] = field(default_factory=set)


@lru_cache(maxsize=1)
def load_explanation_templates() -> ExplanationTemplateBank:
    if not EXPLANATION_TEMPLATES_PATH.exists():
        raise RuntimeError(f"Explanation template file is missing: {EXPLANATION_TEMPLATES_PATH}")

    raw_bank = json.loads(EXPLANATION_TEMPLATES_PATH.read_text(encoding="utf-8"))
    _validate_template_bank(raw_bank)

    groups: dict[str, dict[str, list[ExplanationTemplate]]] = {}
    for group_name, styles in raw_bank["groups"].items():
        groups[group_name] = {}
        for style_name, templates in styles.items():
            groups[group_name][style_name] = [
                ExplanationTemplate(
                    id=str(item["id"]),
                    text=str(item["text"]),
                    requires=[str(value) for value in item["requires"]],
                )
                for item in templates
            ]

    return ExplanationTemplateBank(
        version=int(raw_bank["version"]),
        description=str(raw_bank["description"]),
        selection=dict(raw_bank["selection"]),
        groups=groups,
    )


def select_template(
    *,
    template_bank: ExplanationTemplateBank,
    usage: ExplanationTemplateUsage,
    group_name: str,
    style: str,
    available_values: dict[str, str],
    movie_id: int,
    rank: int,
    slot: str,
    template_session_id: str,
) -> ExplanationTemplate | None:
    styles_to_try = [style, "mixed"]
    if style not in {"family", "teen", "mixed"}:
        styles_to_try = ["mixed", "family", "teen"]
    else:
        for fallback in ("family", "teen"):
            if fallback not in styles_to_try:
                styles_to_try.append(fallback)

    candidates: list[ExplanationTemplate] = []
    for style_name in styles_to_try:
        candidates.extend(template_bank.groups.get(group_name, {}).get(style_name, []))

    viable = [template for template in candidates if _requirements_satisfied(template, available_values)]
    if not viable:
        return None

    unused = [template for template in viable if template.id not in usage.used_template_ids]
    pool = unused or viable
    ordered = sorted(pool, key=lambda template: _stable_template_key(
        template_session_id=template_session_id,
        movie_id=movie_id,
        rank=rank,
        slot=slot,
        style=style,
        group_name=group_name,
        template_id=template.id,
    ))
    selected = ordered[0]
    usage.used_template_ids.add(selected.id)
    return selected


def render_template(template: ExplanationTemplate, available_values: dict[str, str]) -> str:
    rendered_text = template.text
    for placeholder in PLACEHOLDER_RE.findall(template.text):
        value = available_values.get(placeholder)
        if not value:
            raise RuntimeError(
                f"Template {template.id} requires placeholder {placeholder} but no value was provided."
            )
        rendered_text = rendered_text.replace(f"{{{placeholder}}}", value)
    return rendered_text


def _validate_template_bank(raw_bank: dict) -> None:
    for key in ("version", "description", "selection", "groups"):
        if key not in raw_bank:
            raise RuntimeError(f"Explanation template JSON is missing top-level key: {key}")

    groups = raw_bank["groups"]
    missing_groups = REQUIRED_GROUPS - set(groups.keys())
    if missing_groups:
        missing_text = ", ".join(sorted(missing_groups))
        raise RuntimeError(f"Explanation template JSON is missing required groups: {missing_text}")

    for group_name, styles in groups.items():
        if not isinstance(styles, dict):
            raise RuntimeError(f"Template group {group_name} must be an object keyed by style.")
        for style_name, templates in styles.items():
            if not isinstance(templates, list):
                raise RuntimeError(f"Template group {group_name}.{style_name} must be a list.")
            for template in templates:
                _validate_template(group_name=group_name, style_name=style_name, template=template)


def _validate_template(
    *,
    group_name: str,
    style_name: str,
    template: dict,
) -> None:
    for key in ("id", "text", "requires"):
        if key not in template:
            raise RuntimeError(
                f"Template in {group_name}.{style_name} is missing required key: {key}"
            )

    placeholders = set(PLACEHOLDER_RE.findall(str(template["text"])))
    requires = {str(item) for item in template["requires"]}
    if placeholders - requires:
        missing = ", ".join(sorted(placeholders - requires))
        raise RuntimeError(
            f"Template {template['id']} uses placeholders not declared in requires: {missing}"
        )


def _requirements_satisfied(template: ExplanationTemplate, available_values: dict[str, str]) -> bool:
    for requirement in template.requires:
        if not available_values.get(requirement):
            return False
    return True


def _stable_template_key(
    *,
    template_session_id: str,
    movie_id: int,
    rank: int,
    slot: str,
    style: str,
    group_name: str,
    template_id: str,
) -> str:
    payload = f"{template_session_id}|{movie_id}|{rank}|{slot}|{style}|{group_name}|{template_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
