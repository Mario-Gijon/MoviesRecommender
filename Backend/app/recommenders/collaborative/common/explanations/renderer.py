from __future__ import annotations

from app.recommenders.collaborative.common.explanations.models import (
    CollaborativeExplanation,
    CollaborativeExplanationStrength,
    EvidenceMovie,
    EvidenceProfile,
)
from app.recommenders.collaborative.common.explanations.template_bank import (
    CollaborativeExplanationTemplateUsage,
    CollaborativeTemplateSelectionInput,
    load_collaborative_template_bank,
    render_template,
    select_template,
)
from app.recommenders.collaborative.common.explanations.text_formatting import (
    cleanup_rendered_text,
    format_evidence_movies,
    format_profiles,
    format_shared_movies,
)


def render_collaborative_explanation(
    *,
    explanation_type: str,
    algorithm_id: str,
    variant_id: str | None,
    movie_id: int | None,
    rank: int | None,
    evidence_movies: list[EvidenceMovie] | None = None,
    shared_evidence_movies: list[EvidenceMovie] | None = None,
    evidence_profiles: list[EvidenceProfile] | None = None,
    evidence_strength: CollaborativeExplanationStrength = "medium",
    candidate_title: str | None = None,
    template_session_id: str | None = None,
    explanation_source: str = "algorithmic_evidence",
    fidelity: str = "medium",
    limitations: list[str] | None = None,
    debug: dict | None = None,
) -> CollaborativeExplanation:
    template_bank = load_collaborative_template_bank()
    usage = CollaborativeExplanationTemplateUsage()
    normalized_evidence_movies = list(evidence_movies or [])
    normalized_shared_evidence_movies = list(shared_evidence_movies or [])
    normalized_evidence_profiles = list(evidence_profiles or [])
    selection_evidence_movies = (
        normalized_evidence_movies
        if normalized_evidence_movies
        else normalized_shared_evidence_movies
    )
    selection_input = CollaborativeTemplateSelectionInput(
        templateSessionId=template_session_id,
        algorithmId=algorithm_id,
        variantId=variant_id,
        movieId=movie_id,
        rank=rank,
        explanationType=explanation_type,
        evidenceStrength=evidence_strength,
        evidenceMovieIds=[movie.movieId for movie in selection_evidence_movies],
    )
    available_values = {
        "movies": format_evidence_movies(normalized_evidence_movies),
        "sharedMovies": (
            format_evidence_movies(normalized_shared_evidence_movies)
            or format_shared_movies(normalized_evidence_profiles)
        ),
        "profiles": format_profiles(normalized_evidence_profiles),
        "candidateTitle": cleanup_rendered_text(candidate_title or ""),
    }

    template = select_template(
        template_bank=template_bank,
        usage=usage,
        selection_input=selection_input,
        available_values=available_values,
    )

    if template is not None:
        explanation_text = cleanup_rendered_text(
            render_template(template, available_values)
        )
        template_id = template.id
    else:
        explanation_text = _ultimate_fallback_text(
            candidate_title=candidate_title,
            evidence_movies=selection_evidence_movies,
        )
        template_id = None

    return CollaborativeExplanation(
        explanationText=explanation_text,
        explanationType=explanation_type,
        explanationSource=explanation_source,
        fidelity=fidelity,
        evidenceStrength=evidence_strength,
        evidenceMovies=selection_evidence_movies,
        evidenceProfiles=normalized_evidence_profiles,
        templateId=template_id,
        limitations=list(limitations or []),
        debug=debug,
    )


def _ultimate_fallback_text(
    *,
    candidate_title: str | None,
    evidence_movies: list[EvidenceMovie],
) -> str:
    movie_phrase = format_evidence_movies(evidence_movies, max_items=2)
    if movie_phrase:
        return cleanup_rendered_text(
            f"Como te gustaron {movie_phrase}, esta pelicula puede encajar contigo."
        )
    if candidate_title:
        return cleanup_rendered_text(
            f"{candidate_title} puede ser una buena candidata para seguir afinando tus gustos."
        )
    return (
        "Todavia tenemos pocas pistas sobre tus gustos, pero esta pelicula puede ser una buena candidata."
    )
