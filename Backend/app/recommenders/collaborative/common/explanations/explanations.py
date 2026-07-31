from dataclasses import dataclass

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.common.explanations.explanation_template_loader import (
    ExplanationTemplateUsage,
    load_explanation_templates,
    render_template,
    select_template,
)
from app.recommenders.collaborative.common.models import (
    CollaborativeRecommendationExplanation,
)


@dataclass(frozen=True)
class CollaborativeExplanationContribution:
    source_movie_id: int
    source_rating: int
    rating_weight: float
    similarity: float
    support: int
    contribution: float


def build_collaborative_explanation(
    *,
    candidate_movie_id: int,
    rank: int,
    profile_style: str,
    template_seed: str | None,
    contributions: list[CollaborativeExplanationContribution],
) -> CollaborativeRecommendationExplanation:
    template_bank = load_explanation_templates()
    usage = ExplanationTemplateUsage()
    selection_seed = template_seed or "collaborative-default-seed"

    positive_contributions = [
        contribution
        for contribution in contributions
        if contribution.contribution > 0
    ]
    positive_contributions.sort(
        key=lambda contribution: contribution.contribution,
        reverse=True,
    )

    negative_contributions = [
        contribution
        for contribution in contributions
        if contribution.contribution < 0
    ]
    negative_contributions.sort(
        key=lambda contribution: contribution.contribution,
    )

    positive_movie_titles = _source_movie_titles(positive_contributions[:2])
    negative_movie_titles = _source_movie_titles(negative_contributions[:2])

    available_values = {
        "movies": _join_titles(positive_movie_titles),
        "avoided": _join_titles(negative_movie_titles),
    }

    headline = _render_selected_template(
        group_name="headline",
        style=profile_style,
        available_values=available_values,
        movie_id=candidate_movie_id,
        rank=rank,
        slot="headline",
        template_seed=selection_seed,
        usage=usage,
        requirement_priority=[{"movies"}, set()],
    )

    reasons = [
        _render_selected_template(
            group_name="positive_connection_reason",
            style=profile_style,
            available_values=available_values,
            movie_id=candidate_movie_id,
            rank=rank,
            slot="positive_connection",
            template_seed=selection_seed,
            usage=usage,
            requirement_priority=[{"movies"}, set()],
        ),
        _render_selected_template(
            group_name="collaborative_support_reason",
            style=profile_style,
            available_values=available_values,
            movie_id=candidate_movie_id,
            rank=rank,
            slot="collaborative_support",
            template_seed=selection_seed,
            usage=usage,
        ),
    ]

    if negative_movie_titles:
        reasons.append(
            _render_selected_template(
                group_name="negative_balance_reason",
                style=profile_style,
                available_values=available_values,
                movie_id=candidate_movie_id,
                rank=rank,
                slot="negative_balance",
                template_seed=selection_seed,
                usage=usage,
                requirement_priority=[{"avoided"}],
            )
        )

    reasons.append(
        _render_selected_template(
            group_name="natural_closing",
            style=profile_style,
            available_values=available_values,
            movie_id=candidate_movie_id,
            rank=rank,
            slot="natural_closing",
            template_seed=selection_seed,
            usage=usage,
        )
    )

    return CollaborativeRecommendationExplanation(
        headline=headline,
        reasons=[reason for reason in reasons if reason],
        evidence=[
            "ItemKNN colaborativo sobre patrones de valoraciones reales.",
        ],
    )


def _render_selected_template(
    *,
    group_name: str,
    style: str,
    available_values: dict[str, str],
    movie_id: int,
    rank: int,
    slot: str,
    template_seed: str,
    usage: ExplanationTemplateUsage,
    requirement_priority: list[set[str]] | None = None,
) -> str:
    template = select_template(
        template_bank=load_explanation_templates(),
        usage=usage,
        group_name=group_name,
        style=style,
        available_values=available_values,
        movie_id=movie_id,
        rank=rank,
        slot=slot,
        template_seed=template_seed,
        requirement_priority=requirement_priority,
    )

    if template is None:
        return ""

    return render_template(template, available_values)


def _source_movie_titles(
    contributions: list[CollaborativeExplanationContribution],
) -> list[str]:
    titles: list[str] = []

    for contribution in contributions:
        try:
            movie = catalog_repository.get_public_movie_by_id(contribution.source_movie_id)
        except RuntimeError:
            continue

        titles.append(str(movie.get("displayTitle") or movie["title"]))

    return titles


def _join_titles(titles: list[str]) -> str:
    if not titles:
        return ""

    if len(titles) == 1:
        return titles[0]

    return f"{', '.join(titles[:-1])} y {titles[-1]}"