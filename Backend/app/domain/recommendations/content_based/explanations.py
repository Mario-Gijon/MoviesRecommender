from __future__ import annotations

from .constants import (
    DEFAULT_EXPLANATION_LIMIT,
    EXPLANATION_REASON_LIMIT,
    SIMILAR_RATED_MOVIE_LIMIT,
)
from .explanation_evidence import (
    ExplanationEvidence,
    clean_signal_for_explanation,
    select_explanation_evidence,
)
from .schemas import (
    ContentIndex,
    DiversifiedContentCandidate,
    ExplainedContentRecommendation,
    RecommendationExplanation,
    UserProfile,
)


def explain_diversified_recommendations(
    content_index: ContentIndex,
    user_profile: UserProfile,
    diversified_candidates: list[DiversifiedContentCandidate],
    *,
    limit: int = DEFAULT_EXPLANATION_LIMIT,
) -> list[ExplainedContentRecommendation]:
    explained: list[ExplainedContentRecommendation] = []

    for rank, candidate in enumerate(diversified_candidates[:limit], start=1):
        evidence, avoided_signals = select_explanation_evidence(
            candidate_matched_signals=candidate.matchedSignals,
            user_positive_signals=user_profile.positiveSignals,
            user_negative_signals=user_profile.negativeSignals,
            candidate_genres=candidate.genres,
        )
        similar_rated_movies = _find_similar_positive_rated_movies(
            content_index=content_index,
            user_profile=user_profile,
            candidate=candidate,
        )
        headline = _build_headline(candidate=candidate, evidence=evidence, rank=rank)
        reasons = _build_reasons(
            candidate=candidate,
            user_profile=user_profile,
            evidence=evidence,
            avoided_signals=avoided_signals,
            similar_rated_movies=similar_rated_movies,
            rank=rank,
        )
        explanation = RecommendationExplanation(
            headline=headline,
            reasons=reasons[:EXPLANATION_REASON_LIMIT],
            matchedSignals=[item.displayText for item in evidence],
            avoidedSignals=avoided_signals,
            similarRatedMovies=similar_rated_movies,
            style=user_profile.style,
        )
        explained.append(
            ExplainedContentRecommendation(
                movieId=candidate.movieId,
                displayTitle=candidate.displayTitle,
                year=candidate.year,
                suitabilityCategory=candidate.suitabilityCategory,
                standDisplayScore=candidate.standDisplayScore,
                recommendationScore=candidate.recommendationScore,
                contentSimilarity=candidate.contentSimilarity,
                mmrScore=candidate.mmrScore,
                genres=candidate.genres,
                explanation=explanation,
            )
        )

    return explained


def _find_similar_positive_rated_movies(
    *,
    content_index: ContentIndex,
    user_profile: UserProfile,
    candidate: DiversifiedContentCandidate,
) -> list[str]:
    if not user_profile.positiveRatedMovieIds:
        return []

    candidate_row = content_index.features.getrow(content_index.movieIdToRowIndex[candidate.movieId])
    similar_movies: list[tuple[float, str]] = []

    for movie_id in user_profile.positiveRatedMovieIds:
        rated_movie = content_index.movies[content_index.movieIdToRowIndex[movie_id]]
        rated_row = content_index.features.getrow(content_index.movieIdToRowIndex[movie_id])
        similarity = float(candidate_row.dot(rated_row.transpose()).toarray()[0][0])
        similar_movies.append((similarity, str(rated_movie.get("displayTitle", movie_id))))

    similar_movies.sort(key=lambda item: (-item[0], item[1].casefold()))
    return [title for _, title in similar_movies[:SIMILAR_RATED_MOVIE_LIMIT]]


def _build_headline(
    *,
    candidate: DiversifiedContentCandidate,
    evidence: list[ExplanationEvidence],
    rank: int,
) -> str:
    primary_signals = [item.displayText for item in evidence[:2]]
    signal_phrase = _build_signal_phrase(primary_signals)

    if signal_phrase:
        templates = [
            f"Pelis con {signal_phrase}.",
            f"Una opción con mezcla de {signal_phrase}.",
            f"Una mezcla de {signal_phrase} que entra fácil.",
        ]
        return templates[(candidate.movieId + rank) % len(templates)]

    fallback_templates = [
        "Una mezcla que puede ir contigo.",
        "Una opción bastante en tu línea.",
        "Puede encajarte por el tipo de aventura que buscas.",
    ]
    return fallback_templates[(candidate.movieId + rank) % len(fallback_templates)]


def _build_reasons(
    *,
    candidate: DiversifiedContentCandidate,
    user_profile: UserProfile,
    evidence: list[ExplanationEvidence],
    avoided_signals: list[str],
    similar_rated_movies: list[str],
    rank: int,
) -> list[str]:
    reasons: list[str] = []
    signal_phrase = _build_signal_phrase([item.displayText for item in evidence[:3]])

    if signal_phrase:
        reason_templates = _reason_templates_for_style(user_profile.style, signal_phrase)
        reasons.append(reason_templates[(candidate.movieId + rank) % len(reason_templates)])

    if similar_rated_movies:
        movie_phrase = _build_movie_phrase(similar_rated_movies)
        if signal_phrase:
            reasons.append(
                f"Como has puntuado alto {movie_phrase}, esta puede encajarte por su mezcla de {signal_phrase}."
            )
        else:
            reasons.append(
                f"Como has puntuado alto {movie_phrase}, esta puede ir bastante en esa línea."
            )

    if avoided_signals:
        avoided_phrase = _build_signal_phrase(avoided_signals[:2])
        if avoided_phrase:
            negative_templates = [
                f"Además, no se va tanto hacia cosas como {avoided_phrase}, que por tus valoraciones parece llamarte menos.",
                f"También se aleja un poco de {avoided_phrase}, que parece interesarte menos.",
                f"Y no carga tanto con {avoided_phrase}, que por tus notas parece que no era lo que más te apetecía.",
            ]
            reasons.append(negative_templates[(candidate.movieId + rank) % len(negative_templates)])

    if len(reasons) < EXPLANATION_REASON_LIMIT and signal_phrase:
        extra_templates = [
            f"Aquí hay una mezcla de {signal_phrase}, con un tono fácil de entrar.",
            f"Tiene elementos de {signal_phrase}, que aparecen bastante en tus valoraciones.",
            f"Va bastante en la línea de lo que has puntuado alto: {signal_phrase}.",
        ]
        extra_reason = extra_templates[(candidate.movieId + rank) % len(extra_templates)]
        if extra_reason not in reasons:
            reasons.append(extra_reason)

    deduped_reasons: list[str] = []
    seen_reasons: set[str] = set()
    for reason in reasons:
        if reason in seen_reasons:
            continue
        seen_reasons.add(reason)
        deduped_reasons.append(reason)
        if len(deduped_reasons) >= EXPLANATION_REASON_LIMIT:
            break

    return deduped_reasons


def _reason_templates_for_style(style: str, signal_phrase: str) -> list[str]:
    if style == "family":
        return [
            f"Veo que te van las pelis con {signal_phrase}. Esta tiene bastante de ese estilo.",
            f"Esta puede encajarte por su mezcla de {signal_phrase} y un tono fácil de entrar.",
            f"Aquí hay una mezcla de {signal_phrase}, con un rollo muy disfrutable para una sesión ligera.",
        ]
    if style == "teen":
        return [
            f"Tiene pinta de encajarte porque mezcla {signal_phrase}, como varias pelis que has puntuado alto.",
            f"Va bastante en la línea de lo que te suele funcionar: {signal_phrase}.",
            f"Creo que puede ir contigo si te apetece algo con {signal_phrase}.",
        ]
    return [
        f"Esta puede encajarte porque comparte {signal_phrase} con varias películas que has valorado alto.",
        f"Tiene una mezcla de {signal_phrase} que aparece bastante en tus gustos.",
        f"Puede ser una buena opción si buscas algo parecido, pero no exactamente igual, con {signal_phrase}.",
    ]


def _build_signal_phrase(signals: list[str]) -> str:
    cleaned = [clean_signal_for_explanation(signal) for signal in signals if clean_signal_for_explanation(signal)]
    cleaned = cleaned[:3]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} y {cleaned[1]}"
    return f"{cleaned[0]}, {cleaned[1]} y {cleaned[2]}"


def _build_movie_phrase(movie_titles: list[str]) -> str:
    if not movie_titles:
        return ""
    if len(movie_titles) == 1:
        return movie_titles[0]
    return f"{movie_titles[0]} y {movie_titles[1]}"
