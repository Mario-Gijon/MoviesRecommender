from __future__ import annotations

from functools import lru_cache
import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from stopwordsiso import stopwords

from .constants import (
    EXPLANATION_SIGNAL_LIMIT,
    EXPLANATION_SOURCE_WEIGHTS,
    GENERIC_EXPLANATION_TOKENS,
    NON_EXPLAINABLE_SIGNAL_TOKENS,
)
from .feature_parsing import normalize_feature_token

WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class ExplanationEvidence:
    rawSignal: str
    displayText: str
    source: str
    score: float
    isGeneric: bool


def clean_signal_for_explanation(signal: str) -> str:
    cleaned = signal.strip()
    for prefix in ("genre:", "tag:", "keyword:", "text:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    cleaned = cleaned.replace("_", " ").replace('"', " ")
    cleaned = " ".join(cleaned.split())
    normalized = normalize_feature_token(cleaned)
    if not normalized:
        return ""
    return normalized


def detect_signal_source(signal: str) -> str:
    if signal.startswith("genre:"):
        return "genre"
    if signal.startswith("tag:"):
        return "tag"
    if signal.startswith("keyword:"):
        return "keyword"
    if signal.startswith("text:"):
        return "text"

    return "unknown"


def is_explainable_signal(signal: str) -> bool:
    display_text = clean_signal_for_explanation(signal)
    normalized = normalize_feature_token(display_text)
    if not normalized:
        return False
    if normalized in NON_EXPLAINABLE_SIGNAL_TOKENS:
        return False
    if normalized.isdigit():
        return False
    if len(normalized) < 3:
        return False
    tokens = _meaningful_tokens(normalized)
    if not tokens:
        return False
    if _starts_with_stopword(normalized) or _ends_with_stopword(normalized):
        return False
    total_words = len(_split_words(normalized))
    stopword_count = total_words - len(tokens)
    if stopword_count >= len(tokens) and total_words > 1:
        return False
    if total_words >= 5 and len(tokens) <= 2:
        return False
    return True


def score_explanation_signal(
    signal: str,
    *,
    contribution: float | None = None,
    source: str | None = None,
) -> float:
    if not is_explainable_signal(signal):
        return 0.0

    detected_source = source or detect_signal_source(signal)
    display_text = clean_signal_for_explanation(signal)
    normalized = normalize_feature_token(display_text)
    tokens = _meaningful_tokens(normalized)
    total_words = len(_split_words(normalized))

    score = contribution if contribution is not None else 1.0
    score *= EXPLANATION_SOURCE_WEIGHTS.get(detected_source, 0.82)

    if normalized in GENERIC_EXPLANATION_TOKENS:
        score *= 0.72
    if total_words >= 2 and len(tokens) >= 2:
        score *= 1.18
    if detected_source in {"tag", "keyword"}:
        score *= 1.08
    if detected_source == "genre":
        score *= 0.92

    stopword_ratio = 0.0 if total_words == 0 else (total_words - len(tokens)) / total_words
    score *= max(0.45, 1.0 - (stopword_ratio * 0.4))

    word_count = total_words
    if word_count >= 5:
        score *= 0.74
    elif word_count == 4:
        score *= 0.88
    elif word_count == 3 and len(tokens) >= 2:
        score *= 1.05

    return float(score)


def select_explanation_evidence(
    *,
    candidate_matched_signals: list[str],
    user_positive_signals: list[str],
    user_negative_signals: list[str],
    candidate_genres: list[str],
) -> tuple[list[ExplanationEvidence], list[str]]:
    positive_normalized = {
        normalize_feature_token(clean_signal_for_explanation(signal))
        for signal in user_positive_signals
        if clean_signal_for_explanation(signal)
    }
    negative_normalized = {
        normalize_feature_token(clean_signal_for_explanation(signal))
        for signal in user_negative_signals
        if clean_signal_for_explanation(signal)
    }
    candidate_normalized = {
        normalize_feature_token(clean_signal_for_explanation(signal))
        for signal in candidate_matched_signals
        if clean_signal_for_explanation(signal)
    }

    evidence_by_text: dict[str, ExplanationEvidence] = {}

    for index, signal in enumerate(candidate_matched_signals):
        display_text = clean_signal_for_explanation(signal)
        normalized = normalize_feature_token(display_text)
        if not normalized or normalized in negative_normalized:
            continue
        source = detect_signal_source(signal)
        contribution = max(0.15, 1.0 - (index * 0.08))
        evidence = ExplanationEvidence(
            rawSignal=signal,
            displayText=display_text,
            source=source,
            score=score_explanation_signal(
                signal,
                contribution=contribution,
                source=source,
            ),
            isGeneric=normalized in GENERIC_EXPLANATION_TOKENS,
        )
        _register_better_evidence(evidence_by_text, evidence)

    for genre in candidate_genres:
        display_text = clean_signal_for_explanation(f"genre:{genre}")
        normalized = normalize_feature_token(display_text)
        if not normalized or normalized in negative_normalized:
            continue
        evidence = ExplanationEvidence(
            rawSignal=f"genre:{genre}",
            displayText=display_text,
            source="genre",
            score=score_explanation_signal(
                f"genre:{genre}",
                contribution=0.65 if normalized in positive_normalized else 0.45,
                source="genre",
            ),
            isGeneric=normalized in GENERIC_EXPLANATION_TOKENS,
        )
        _register_better_evidence(evidence_by_text, evidence)

    selected = sorted(
        evidence_by_text.values(),
        key=lambda item: (-item.score, item.displayText.casefold()),
    )[:EXPLANATION_SIGNAL_LIMIT]

    avoided_signals: list[str] = []
    if negative_normalized:
        for signal in user_negative_signals:
            display_text = clean_signal_for_explanation(signal)
            normalized = normalize_feature_token(display_text)
            if not normalized or normalized in candidate_normalized:
                continue
            if display_text not in avoided_signals:
                avoided_signals.append(display_text)
            if len(avoided_signals) >= 2:
                break

    return selected, avoided_signals


@lru_cache(maxsize=1)
def get_explanation_stop_words() -> set[str]:
    return set(ENGLISH_STOP_WORDS) | set(stopwords("en")) | set(stopwords("es"))


def _register_better_evidence(
    evidence_by_text: dict[str, ExplanationEvidence],
    evidence: ExplanationEvidence,
) -> None:
    if evidence.score <= 0:
        return
    current = evidence_by_text.get(evidence.displayText)
    if current is None or evidence.score > current.score:
        evidence_by_text[evidence.displayText] = evidence


def _split_words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _meaningful_tokens(text: str) -> list[str]:
    stop_words = get_explanation_stop_words()
    return [
        token
        for token in _split_words(text)
        if token not in stop_words and not token.isdigit() and len(token) >= 2
    ]


def _starts_with_stopword(text: str) -> bool:
    words = _split_words(text)
    return bool(words) and words[0] in get_explanation_stop_words()


def _ends_with_stopword(text: str) -> bool:
    words = _split_words(text)
    return bool(words) and words[-1] in get_explanation_stop_words()
