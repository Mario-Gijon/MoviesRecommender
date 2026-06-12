from __future__ import annotations

import math
import re
import unicodedata

import pandas as pd


SPACE_RE = re.compile(r"\s+")
MISSING_TOKENS = {"", "<na>", "nan", "none", "null"}


def split_pipe_values(value: object) -> list[str]:
    if is_missing_value(value):
        return []

    text = str(value).strip()
    if _is_missing_text(text):
        return []

    values: list[str] = []
    for part in text.split("|"):
        normalized_part = normalize_feature_token(part)
        if normalized_part:
            values.append(str(part).strip())
    return values


def normalize_feature_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.strip().lower()
    text = SPACE_RE.sub(" ", text)
    return "" if _is_missing_text(text) else text


def build_prefixed_binary_documents(values_by_movie: list[list[str]], prefix: str) -> list[str]:
    documents: list[str] = []
    for values in values_by_movie:
        normalized_tokens = {
            _to_structured_token(prefix=prefix, value=value)
            for value in values
            if normalize_feature_token(value)
        }
        documents.append(" ".join(sorted(normalized_tokens)))
    return documents


def build_text_document(row: pd.Series) -> str:
    text_parts: list[str] = []
    for field_name in ("overview", "tagline"):
        if field_name not in row.index:
            continue
        value = row.get(field_name)
        if is_missing_value(value):
            continue
        text = str(value).strip()
        if normalize_feature_token(text):
            text_parts.append(text)
    return " ".join(text_parts)


def parse_movie_keywords(row: pd.Series) -> list[str]:
    for column_name in ("tmdbKeywords", "keywords", "keywordNames", "tmdbKeywordNames"):
        if column_name not in row.index:
            continue
        values = split_pipe_values(row.get(column_name))
        if values:
            return values
    return []


def parse_movie_tags(row: pd.Series) -> list[str]:
    if "userTags" not in row.index:
        return []
    return split_pipe_values(row.get("userTags"))


def to_feature_name(prefix: str, value: str) -> str:
    return _to_structured_token(prefix=prefix, value=value)


def _to_structured_token(*, prefix: str, value: str) -> str:
    normalized = normalize_feature_token(value)
    normalized = normalized.replace(" ", "_")
    return f"{prefix}{normalized}" if normalized else ""


def is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if value is pd.NA:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    return _is_missing_text(str(value).strip())


def _is_missing_text(value: str) -> bool:
    return SPACE_RE.sub(" ", value.strip()).lower() in MISSING_TOKENS
