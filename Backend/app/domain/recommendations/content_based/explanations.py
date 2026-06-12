from __future__ import annotations

from .constants import (
    DEFAULT_EXPLANATION_LIMIT,
    EXPLANATION_REASON_LIMIT,
    DEFAULT_TEMPLATE_SESSION_ID,
    SIMILAR_RATED_MOVIE_LIMIT,
)
from .explanation_evidence import (
    ExplanationEvidence,
    clean_signal_for_explanation,
    select_explanation_evidence,
)
from .explanation_template_loader import (
    ExplanationTemplateUsage,
    load_explanation_templates,
    render_template,
    select_template,
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
    template_session_id: str = DEFAULT_TEMPLATE_SESSION_ID,
) -> list[ExplainedContentRecommendation]:
    explained: list[ExplainedContentRecommendation] = []
    template_bank = load_explanation_templates()
    usage = ExplanationTemplateUsage()

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
        headline = _build_headline(
            candidate=candidate,
            user_profile=user_profile,
            evidence=evidence,
            rank=rank,
            template_bank=template_bank,
            usage=usage,
            template_session_id=template_session_id,
        )
        reasons = _build_reasons(
            candidate=candidate,
            user_profile=user_profile,
            evidence=evidence,
            avoided_signals=avoided_signals,
            similar_rated_movies=similar_rated_movies,
            rank=rank,
            template_bank=template_bank,
            usage=usage,
            template_session_id=template_session_id,
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
    user_profile: UserProfile,
    evidence: list[ExplanationEvidence],
    rank: int,
    template_bank,
    usage: ExplanationTemplateUsage,
    template_session_id: str,
) -> str:
    primary_signals = [item.displayText for item in evidence[:2]]
    signal_phrase = _build_signal_phrase(primary_signals)
    available_values = {"signals": signal_phrase}
    template = select_template(
        template_bank=template_bank,
        usage=usage,
        group_name="headline",
        style=user_profile.style,
        available_values=available_values,
        movie_id=candidate.movieId,
        rank=rank,
        slot="headline",
        template_session_id=template_session_id,
    )
    if template is None:
        return "Una mezcla que puede ir contigo."
    return render_template(template, available_values)


def _build_reasons(
    *,
    candidate: DiversifiedContentCandidate,
    user_profile: UserProfile,
    evidence: list[ExplanationEvidence],
    avoided_signals: list[str],
    similar_rated_movies: list[str],
    rank: int,
    template_bank,
    usage: ExplanationTemplateUsage,
    template_session_id: str,
) -> list[str]:
    reasons: list[str] = []
    signal_phrase = _build_signal_phrase([item.displayText for item in evidence[:3]])
    movie_phrase = _build_movie_phrase(similar_rated_movies)
    avoided_phrase = _build_signal_phrase(avoided_signals[:2]) if avoided_signals else ""
    available_values = {
        "signals": signal_phrase,
        "movies": movie_phrase,
        "avoided": avoided_phrase,
    }

    signal_template = select_template(
        template_bank=template_bank,
        usage=usage,
        group_name="signal_reason",
        style=user_profile.style,
        available_values=available_values,
        movie_id=candidate.movieId,
        rank=rank,
        slot="reason_1",
        template_session_id=template_session_id,
    )
    if signal_template is not None:
        reasons.append(render_template(signal_template, available_values))

    if movie_phrase:
        similar_template = select_template(
            template_bank=template_bank,
            usage=usage,
            group_name="similar_movie_reason",
            style=user_profile.style,
            available_values=available_values,
            movie_id=candidate.movieId,
            rank=rank,
            slot="reason_2",
            template_session_id=template_session_id,
        )
        if similar_template is not None:
            reasons.append(render_template(similar_template, available_values))

    if avoided_phrase:
        negative_template = select_template(
            template_bank=template_bank,
            usage=usage,
            group_name="negative_avoidance_reason",
            style=user_profile.style,
            available_values=available_values,
            movie_id=candidate.movieId,
            rank=rank,
            slot="reason_3",
            template_session_id=template_session_id,
        )
        if negative_template is not None:
            reasons.append(render_template(negative_template, available_values))
    else:
        closing_template = select_template(
            template_bank=template_bank,
            usage=usage,
            group_name="natural_closing",
            style=user_profile.style,
            available_values=available_values,
            movie_id=candidate.movieId,
            rank=rank,
            slot="reason_3",
            template_session_id=template_session_id,
        )
        if closing_template is not None:
            closing_reason = render_template(closing_template, available_values)
            if not reasons or closing_reason != reasons[-1]:
                reasons.append(closing_reason)

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
