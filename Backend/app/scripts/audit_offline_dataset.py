import json
from html import escape
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns

from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_AUDIT_CHARTS_DIR,
    OFFLINE_DATASET_AUDIT_DASHBOARD_PATH,
    OFFLINE_DATASET_AUDIT_DETAILED_DIR,
    OFFLINE_DATASET_AUDIT_DIR,
    OFFLINE_DATASET_AUDIT_INDEX_PATH,
    OFFLINE_DATASET_AUDIT_TABLES_DIR,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


LOW_STAND_DISPLAY_SCORE = 0.25
LOW_RATING_COUNT = 250
LOW_TMDB_POPULARITY = 1.0
OLD_PUBLIC_YEAR = 2000
COMMON_PUBLIC_LANGUAGES = {"en", "es", "ja", "fr", "it", "de"}

SUMMARY_MD_PATH = OFFLINE_DATASET_AUDIT_DIR / "summary.md"
SUMMARY_JSON_PATH = OFFLINE_DATASET_AUDIT_DIR / "summary.json"

DETAIL_COLUMNS = [
    "auditPartition",
    "movieId",
    "title",
    "displayTitle",
    "year",
    "originalLanguage",
    "genres",
    "suitabilityCategory",
    "ratingCount",
    "averageRating",
    "filteredRatingCount",
    "filteredAverageRating",
    "standDisplayScore",
    "candidateScore",
    "dataReliabilityScore",
    "tmdbPopularity",
    "publicExclusionReasons",
    "publicBlockedTerms",
    "suitabilityReasons",
    "exclusionCategory",
    "exclusionReasons",
    "auditFlags",
]
TEXT_COLUMNS = [
    "auditPartition",
    "title",
    "displayTitle",
    "displayOverview",
    "originalLanguage",
    "genres",
    "suitabilityCategory",
    "publicExclusionReasons",
    "publicBlockedTerms",
    "suitabilityReasons",
    "exclusionCategory",
    "exclusionReasons",
    "auditFlags",
]
NUMERIC_COLUMNS = [
    "movieId",
    "year",
    "ratingCount",
    "averageRating",
    "filteredRatingCount",
    "filteredAverageRating",
    "standDisplayScore",
    "candidateScore",
    "dataReliabilityScore",
    "tmdbPopularity",
]
PIPE_COLUMNS = [
    "genres",
    "publicBlockedTerms",
    "publicExclusionReasons",
    "exclusionReasons",
]
PARTITION_LABELS = {
    "public": "Público",
    "collaborative_support": "Soporte colaborativo",
    "excluded": "Excluidas",
}
SINBAD_BLUE = "#4da3ff"
SINBAD_GOLD = "#e3b341"
SINBAD_CYAN = "#67d9ff"
SINBAD_RED = "#ff6b6b"
SINBAD_SLATE = "#8fa3bf"
SINBAD_BG = "#08111f"
SINBAD_PANEL = "#101a2f"


def main() -> None:
    _ensure_required_inputs()
    _ensure_output_dirs()

    manifest = json.loads(OFFLINE_DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
    public_df = _read_partition_csv(OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH, "public")
    support_df = _read_partition_csv(
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        "collaborative_support",
    )
    excluded_df = _read_partition_csv(OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH, "excluded")
    ratings_summary_df = pd.read_csv(OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH)

    combined_df = _build_combined_dataframe(
        public_df=public_df,
        support_df=support_df,
        excluded_df=excluded_df,
        ratings_summary_df=ratings_summary_df,
    )
    suspicious_public_df = _build_suspicious_public_df(combined_df)

    _write_detailed_outputs(combined_df, suspicious_public_df)

    tables = _build_summary_tables(
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
    )
    _write_summary_tables(tables)

    chart_paths = _generate_static_charts(
        combined_df=combined_df,
        tables=tables,
    )
    conclusions = _build_conclusions(
        manifest=manifest,
        combined_df=combined_df,
        tables=tables,
        suspicious_public_df=suspicious_public_df,
    )

    dashboard_html = _build_dashboard_html(
        manifest=manifest,
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        tables=tables,
        chart_paths=chart_paths,
        conclusions=conclusions,
    )
    OFFLINE_DATASET_AUDIT_DASHBOARD_PATH.write_text(dashboard_html, encoding="utf-8")
    OFFLINE_DATASET_AUDIT_INDEX_PATH.write_text(dashboard_html, encoding="utf-8")

    summary_markdown = _build_markdown_summary(
        manifest=manifest,
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        tables=tables,
        chart_paths=chart_paths,
        conclusions=conclusions,
    )
    SUMMARY_MD_PATH.write_text(summary_markdown, encoding="utf-8")

    summary_json = _build_summary_json(
        manifest=manifest,
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        tables=tables,
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _ensure_required_inputs() -> None:
    required_paths = [
        OFFLINE_DATASET_MANIFEST_PATH,
        OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
        OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    ]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing_text = ", ".join(str(path) for path in missing_paths)
        raise RuntimeError(f"Offline dataset audit inputs are missing: {missing_text}")


def _ensure_output_dirs() -> None:
    for directory in [
        OFFLINE_DATASET_AUDIT_DIR,
        OFFLINE_DATASET_AUDIT_TABLES_DIR,
        OFFLINE_DATASET_AUDIT_DETAILED_DIR,
        OFFLINE_DATASET_AUDIT_CHARTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def _read_partition_csv(path: Path, audit_partition: str) -> pd.DataFrame:
    dataframe = pd.read_csv(path)
    dataframe["auditPartition"] = audit_partition
    return dataframe


def _build_combined_dataframe(
    *,
    public_df: pd.DataFrame,
    support_df: pd.DataFrame,
    excluded_df: pd.DataFrame,
    ratings_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    combined_df = pd.concat([public_df, support_df, excluded_df], ignore_index=True, sort=False)

    summary_df = ratings_summary_df.rename(
        columns={
            "title": "summaryTitle",
            "displayTitle": "summaryDisplayTitle",
            "ratingCount": "summaryRatingCount",
            "averageRating": "summaryAverageRating",
            "filteredRatingCount": "summaryFilteredRatingCount",
            "filteredAverageRating": "summaryFilteredAverageRating",
        }
    )
    combined_df = combined_df.merge(
        summary_df[
            [
                "movieId",
                "summaryTitle",
                "summaryDisplayTitle",
                "summaryRatingCount",
                "summaryAverageRating",
                "summaryFilteredRatingCount",
                "summaryFilteredAverageRating",
            ]
        ],
        on="movieId",
        how="left",
    )

    for column in TEXT_COLUMNS + ["movieId"]:
        if column not in combined_df.columns:
            combined_df[column] = ""

    for column in NUMERIC_COLUMNS:
        if column not in combined_df.columns:
            combined_df[column] = pd.NA

    combined_df["title"] = _coalesce_text(
        combined_df.get("title"),
        combined_df.get("summaryTitle"),
    )
    combined_df["displayTitle"] = _coalesce_text(
        combined_df.get("displayTitle"),
        combined_df.get("summaryDisplayTitle"),
    )

    for primary, fallback in [
        ("ratingCount", "summaryRatingCount"),
        ("averageRating", "summaryAverageRating"),
        ("filteredRatingCount", "summaryFilteredRatingCount"),
        ("filteredAverageRating", "summaryFilteredAverageRating"),
    ]:
        combined_df[primary] = _coalesce_numeric(
            combined_df.get(primary),
            combined_df.get(fallback),
        )

    for column in TEXT_COLUMNS:
        combined_df[column] = _normalize_text_series(combined_df[column])

    for column in NUMERIC_COLUMNS:
        combined_df[column] = pd.to_numeric(combined_df[column], errors="coerce")

    combined_df["movieId"] = combined_df["movieId"].astype("Int64")
    combined_df["year"] = combined_df["year"].astype("Int64")
    combined_df["ratingCount"] = combined_df["ratingCount"].astype("Int64")
    combined_df["filteredRatingCount"] = combined_df["filteredRatingCount"].astype("Int64")

    combined_df["displayLabel"] = combined_df["displayTitle"].where(
        combined_df["displayTitle"] != "",
        combined_df["title"],
    )
    combined_df["displayLabel"] = combined_df["displayLabel"].where(
        combined_df["displayLabel"] != "",
        "(sin título)",
    )
    combined_df["decade"] = combined_df["year"].apply(_year_to_decade_label)
    combined_df["auditFlags"] = ""

    public_mask = combined_df["auditPartition"] == "public"
    combined_df.loc[public_mask, "auditFlags"] = _compute_public_audit_flags(
        combined_df.loc[public_mask]
    )
    combined_df["hasAuditFlags"] = combined_df["auditFlags"] != ""
    combined_df["auditFlagCount"] = combined_df["auditFlags"].apply(
        lambda value: len([item for item in value.split("|") if item]) if value else 0
    )

    return combined_df


def _build_suspicious_public_df(combined_df: pd.DataFrame) -> pd.DataFrame:
    suspicious_df = combined_df[
        (combined_df["auditPartition"] == "public") & (combined_df["auditFlags"] != "")
    ].copy()
    suspicious_df = suspicious_df.sort_values(
        by=[
            "auditFlagCount",
            "standDisplayScore",
            "ratingCount",
            "tmdbPopularity",
            "displayLabel",
        ],
        ascending=[False, True, True, True, True],
        na_position="last",
        kind="mergesort",
    )
    return suspicious_df


def _write_detailed_outputs(
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
) -> None:
    partition_paths = {
        "public": OFFLINE_DATASET_AUDIT_DETAILED_DIR / "public_movies_audit.csv",
        "collaborative_support": (
            OFFLINE_DATASET_AUDIT_DETAILED_DIR / "collaborative_support_audit.csv"
        ),
        "excluded": OFFLINE_DATASET_AUDIT_DETAILED_DIR / "excluded_movies_audit.csv",
    }

    _write_csv(
        combined_df[DETAIL_COLUMNS],
        OFFLINE_DATASET_AUDIT_DETAILED_DIR / "all_movies_audit.csv",
    )

    for partition, output_path in partition_paths.items():
        partition_df = combined_df.loc[combined_df["auditPartition"] == partition, DETAIL_COLUMNS]
        _write_csv(partition_df, output_path)

    suspicious_columns = DETAIL_COLUMNS + ["auditFlagCount"]
    _write_csv(
        suspicious_public_df[suspicious_columns],
        OFFLINE_DATASET_AUDIT_DETAILED_DIR / "suspicious_public_movies.csv",
    )


def _build_summary_tables(
    *,
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    public_df = combined_df[combined_df["auditPartition"] == "public"].copy()
    support_df = combined_df[combined_df["auditPartition"] == "collaborative_support"].copy()
    excluded_df = combined_df[combined_df["auditPartition"] == "excluded"].copy()

    comparison_by_partition = (
        combined_df.groupby("auditPartition", dropna=False)
        .agg(
            movieCount=("movieId", "size"),
            moviesWithRatings=("ratingCount", lambda series: int(series.fillna(0).gt(0).sum())),
            moviesWithFilteredRatings=(
                "filteredRatingCount",
                lambda series: int(series.fillna(0).gt(0).sum()),
            ),
            averageRatingCount=("ratingCount", "mean"),
            averageFilteredRatingCount=("filteredRatingCount", "mean"),
            averageStandDisplayScore=("standDisplayScore", "mean"),
            medianStandDisplayScore=("standDisplayScore", "median"),
            suspiciousMovieCount=("hasAuditFlags", "sum"),
        )
        .reset_index()
    )

    suitability_by_partition = _count_by_field(
        combined_df,
        field_name="suitabilityCategory",
        value_column="suitabilityCategory",
        empty_label="unknown",
    )
    language_by_partition = _count_by_field(
        combined_df,
        field_name="originalLanguage",
        value_column="originalLanguage",
        empty_label="unknown",
        include_percentage=True,
    )
    decade_by_partition = _count_by_field(
        combined_df.assign(decadeLabel=combined_df["decade"]),
        field_name="decadeLabel",
        value_column="decade",
        empty_label="unknown",
    )
    genre_by_partition = _explode_pipe_field(
        combined_df,
        field_name="genres",
        value_column="genre",
        empty_label="unknown",
    )
    blocked_terms_by_partition = _explode_pipe_field(
        combined_df,
        field_name="publicBlockedTerms",
        value_column="blockedTerm",
    )
    public_exclusion_reasons_by_partition = _explode_pipe_field(
        combined_df,
        field_name="publicExclusionReasons",
        value_column="publicExclusionReason",
    )
    excluded_reasons = _explode_pipe_field(
        excluded_df,
        field_name="exclusionReasons",
        value_column="exclusionReason",
        include_partition=False,
    )

    public_top_movies = _select_public_movies(public_df, ascending=False).head(100)
    public_low_score_movies = _select_public_movies(public_df, ascending=True).head(100)
    suspicious_public_movies_sample = suspicious_public_df.head(100)

    return {
        "comparison_by_partition": comparison_by_partition,
        "suitability_by_partition": suitability_by_partition,
        "language_by_partition": language_by_partition,
        "decade_by_partition": decade_by_partition,
        "genre_by_partition": genre_by_partition,
        "blocked_terms_by_partition": blocked_terms_by_partition,
        "public_exclusion_reasons_by_partition": public_exclusion_reasons_by_partition,
        "excluded_reasons": excluded_reasons,
        "public_top_movies": public_top_movies[
            [
                "movieId",
                "displayTitle",
                "year",
                "standDisplayScore",
                "ratingCount",
                "filteredRatingCount",
                "tmdbPopularity",
                "suitabilityCategory",
            ]
        ],
        "public_low_score_movies": public_low_score_movies[
            [
                "movieId",
                "displayTitle",
                "year",
                "standDisplayScore",
                "ratingCount",
                "filteredRatingCount",
                "tmdbPopularity",
                "suitabilityCategory",
            ]
        ],
        "suspicious_public_movies_sample": suspicious_public_movies_sample[
            [
                "movieId",
                "displayTitle",
                "year",
                "standDisplayScore",
                "ratingCount",
                "tmdbPopularity",
                "auditFlagCount",
                "auditFlags",
                "publicBlockedTerms",
                "publicExclusionReasons",
            ]
        ],
        "support_examples": support_df[
            [
                "movieId",
                "displayTitle",
                "year",
                "publicBlockedTerms",
                "publicExclusionReasons",
                "suitabilityReasons",
            ]
        ].copy(),
    }


def _write_summary_tables(tables: dict[str, pd.DataFrame]) -> None:
    for table_name, dataframe in tables.items():
        if table_name == "support_examples":
            continue
        _write_csv(dataframe, OFFLINE_DATASET_AUDIT_TABLES_DIR / f"{table_name}.csv")


def _generate_static_charts(
    *,
    combined_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> dict[str, str]:
    sns.set_theme(
        style="darkgrid",
        rc={
            "axes.facecolor": "#0f1a2d",
            "figure.facecolor": "#08111f",
            "grid.color": "#2a3a58",
            "axes.labelcolor": "#e5eefc",
            "text.color": "#e5eefc",
            "xtick.color": "#dbe6f8",
            "ytick.color": "#dbe6f8",
            "axes.edgecolor": "#3b4c6b",
        },
    )

    chart_paths = {
        "partition_counts": "charts/partition_counts.png",
        "suitability_by_partition": "charts/suitability_by_partition.png",
        "public_languages": "charts/public_languages.png",
        "public_decades": "charts/public_decades.png",
        "public_genres": "charts/public_genres.png",
        "support_blocked_terms": "charts/support_blocked_terms.png",
        "stand_display_score_distribution": "charts/stand_display_score_distribution.png",
        "rating_count_vs_stand_score": "charts/rating_count_vs_stand_score.png",
    }

    comparison_df = tables["comparison_by_partition"].copy()
    if comparison_df.empty:
        _save_empty_chart("Conteo por partición", OFFLINE_DATASET_AUDIT_CHARTS_DIR / "partition_counts.png")
    else:
        plt.figure(figsize=(9, 5))
        ax = sns.barplot(
            data=comparison_df,
            x="auditPartition",
            y="movieCount",
            palette=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_RED],
        )
        _style_axes(
            ax,
            title="Películas analizadas por partición",
            xlabel="Partición",
            ylabel="Películas",
        )
        ax.set_xticklabels([PARTITION_LABELS.get(label.get_text(), label.get_text()) for label in ax.get_xticklabels()])
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "partition_counts.png")

    suitability_df = tables["suitability_by_partition"].copy()
    if suitability_df.empty:
        _save_empty_chart(
            "Suitability por partición",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "suitability_by_partition.png",
        )
    else:
        plt.figure(figsize=(11, 6))
        pivot_df = suitability_df.pivot(
            index="suitabilityCategory",
            columns="auditPartition",
            values="movieCount",
        ).fillna(0)
        pivot_df = pivot_df.sort_values(by=list(pivot_df.columns), ascending=False)
        ax = pivot_df.plot(
            kind="bar",
            color=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_RED],
            figsize=(11, 6),
        )
        _style_axes(
            ax,
            title="Distribución de suitabilityCategory por partición",
            xlabel="Suitability",
            ylabel="Películas",
        )
        ax.legend(title="Partición")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "suitability_by_partition.png")

    public_languages_df = tables["language_by_partition"].copy()
    public_languages_df = public_languages_df[
        public_languages_df["auditPartition"] == "public"
    ].head(12)
    if public_languages_df.empty:
        _save_empty_chart(
            "Idiomas del catálogo público",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_languages.png",
        )
    else:
        plt.figure(figsize=(10, 5))
        ax = sns.barplot(
            data=public_languages_df,
            x="originalLanguage",
            y="movieCount",
            color=SINBAD_BLUE,
        )
        _style_axes(
            ax,
            title="Idiomas originales más frecuentes en el catálogo público",
            xlabel="Idioma original",
            ylabel="Películas",
        )
        plt.xticks(rotation=35, ha="right")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_languages.png")

    public_decades_df = tables["decade_by_partition"].copy()
    public_decades_df = public_decades_df[public_decades_df["auditPartition"] == "public"]
    if public_decades_df.empty:
        _save_empty_chart(
            "Décadas del catálogo público",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_decades.png",
        )
    else:
        plt.figure(figsize=(10, 5))
        ax = sns.barplot(
            data=public_decades_df,
            x="decade",
            y="movieCount",
            color=SINBAD_GOLD,
        )
        _style_axes(
            ax,
            title="Décadas dominantes en el catálogo público",
            xlabel="Década",
            ylabel="Películas",
        )
        plt.xticks(rotation=35, ha="right")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_decades.png")

    public_genres_df = tables["genre_by_partition"].copy()
    public_genres_df = public_genres_df[public_genres_df["auditPartition"] == "public"].head(15)
    if public_genres_df.empty:
        _save_empty_chart(
            "Géneros del catálogo público",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_genres.png",
        )
    else:
        plt.figure(figsize=(11, 6))
        ax = sns.barplot(
            data=public_genres_df,
            x="movieCount",
            y="genre",
            color=SINBAD_CYAN,
        )
        _style_axes(
            ax,
            title="Géneros más frecuentes en el catálogo público",
            xlabel="Películas",
            ylabel="Género",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_genres.png")

    support_blocked_terms_df = tables["blocked_terms_by_partition"].copy()
    support_blocked_terms_df = support_blocked_terms_df[
        support_blocked_terms_df["auditPartition"] == "collaborative_support"
    ].head(15)
    if support_blocked_terms_df.empty:
        _save_empty_chart(
            "Blocked terms del soporte colaborativo",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "support_blocked_terms.png",
        )
    else:
        plt.figure(figsize=(11, 6))
        ax = sns.barplot(
            data=support_blocked_terms_df,
            x="movieCount",
            y="blockedTerm",
            color=SINBAD_RED,
        )
        _style_axes(
            ax,
            title="Blocked terms más frecuentes en soporte colaborativo",
            xlabel="Películas",
            ylabel="Blocked term",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "support_blocked_terms.png")

    public_df = combined_df[combined_df["auditPartition"] == "public"].copy()
    if public_df["standDisplayScore"].dropna().empty:
        _save_empty_chart(
            "Distribución de standDisplayScore",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "stand_display_score_distribution.png",
        )
    else:
        plt.figure(figsize=(10, 5))
        ax = sns.histplot(
            public_df["standDisplayScore"].dropna(),
            bins=20,
            color=SINBAD_BLUE,
            edgecolor="#dbe6f8",
        )
        _style_axes(
            ax,
            title="Distribución de standDisplayScore en el catálogo público",
            xlabel="standDisplayScore",
            ylabel="Películas",
        )
        _finalize_chart(
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "stand_display_score_distribution.png"
        )

    scatter_df = public_df.dropna(subset=["ratingCount", "standDisplayScore"]).copy()
    if scatter_df.empty:
        _save_empty_chart(
            "RatingCount vs standDisplayScore",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "rating_count_vs_stand_score.png",
        )
    else:
        plt.figure(figsize=(10, 6))
        ax = sns.scatterplot(
            data=scatter_df,
            x="ratingCount",
            y="standDisplayScore",
            hue="suitabilityCategory",
            palette="crest",
            alpha=0.75,
            s=55,
        )
        ax.set_xscale("log")
        _style_axes(
            ax,
            title="ratingCount frente a standDisplayScore en catálogo público",
            xlabel="ratingCount (escala log)",
            ylabel="standDisplayScore",
        )
        ax.legend(title="Suitability", loc="best", fontsize=8)
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "rating_count_vs_stand_score.png")

    return chart_paths


def _build_conclusions(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    suspicious_public_df: pd.DataFrame,
) -> list[str]:
    counts = combined_df["auditPartition"].value_counts()
    public_languages = tables["language_by_partition"]
    public_languages = public_languages[public_languages["auditPartition"] == "public"]
    top_language = public_languages.iloc[0]["originalLanguage"] if not public_languages.empty else "unknown"

    public_decades = tables["decade_by_partition"]
    public_decades = public_decades[public_decades["auditPartition"] == "public"]
    top_decade = public_decades.iloc[0]["decade"] if not public_decades.empty else "unknown"

    blocked_terms = tables["blocked_terms_by_partition"]
    blocked_terms = blocked_terms[blocked_terms["auditPartition"] == "collaborative_support"]
    top_blocked_term = blocked_terms.iloc[0]["blockedTerm"] if not blocked_terms.empty else "sin señal dominante"

    excluded_reasons = tables["excluded_reasons"]
    top_excluded_reason = (
        excluded_reasons.iloc[0]["exclusionReason"]
        if not excluded_reasons.empty
        else "sin razón dominante"
    )

    collaborative_ratings = manifest.get("counts", {}).get("collaborativeRatings", 0)

    return [
        (
            "El balance general muestra "
            f"{int(counts.get('public', 0))} películas públicas, "
            f"{int(counts.get('collaborative_support', 0))} de soporte colaborativo y "
            f"{int(counts.get('excluded', 0))} excluidas."
        ),
        (
            "El dataset offline conserva un volumen colaborativo alto con "
            f"{_format_int(collaborative_ratings)} ratings filtrados según el manifest."
        ),
        (
            "En el catálogo público domina el idioma "
            f"{top_language} y la década más frecuente es {top_decade}."
        ),
        (
            "La señal de revisión pública alcanza "
            f"{len(suspicious_public_df)} películas con auditFlags no vacíos."
        ),
        (
            "En soporte colaborativo, el blocked term más repetido es "
            f"{top_blocked_term}."
        ),
        (
            "Entre las películas excluidas predomina la razón "
            f"{top_excluded_reason}, lo que sugiere revisar primero fallos técnicos y de enriquecimiento."
        ),
    ]


def _build_dashboard_html(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    chart_paths: dict[str, str],
    conclusions: list[str],
) -> str:
    public_df = combined_df[combined_df["auditPartition"] == "public"].copy()
    counts = combined_df["auditPartition"].value_counts()
    collaborative_ratings = int(manifest.get("counts", {}).get("collaborativeRatings", 0))

    partition_fig = px.bar(
        tables["comparison_by_partition"],
        x="auditPartition",
        y="movieCount",
        color="auditPartition",
        color_discrete_map={
            "public": SINBAD_BLUE,
            "collaborative_support": SINBAD_GOLD,
            "excluded": SINBAD_RED,
        },
        title="Películas analizadas por partición",
    )
    _style_plotly_figure(partition_fig)

    suitability_fig = px.bar(
        tables["suitability_by_partition"],
        x="suitabilityCategory",
        y="movieCount",
        color="auditPartition",
        barmode="group",
        color_discrete_map={
            "public": SINBAD_BLUE,
            "collaborative_support": SINBAD_GOLD,
            "excluded": SINBAD_RED,
        },
        title="suitabilityCategory por partición",
    )
    _style_plotly_figure(suitability_fig)

    language_fig = px.bar(
        tables["language_by_partition"].query("auditPartition == 'public'").head(10),
        x="originalLanguage",
        y="movieCount",
        color_discrete_sequence=[SINBAD_BLUE],
        title="Idiomas principales del catálogo público",
    )
    _style_plotly_figure(language_fig)

    decade_fig = px.bar(
        tables["decade_by_partition"].query("auditPartition == 'public'"),
        x="decade",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Décadas dominantes del catálogo público",
    )
    _style_plotly_figure(decade_fig)

    genre_fig = px.bar(
        tables["genre_by_partition"].query("auditPartition == 'public'").head(12),
        x="genre",
        y="movieCount",
        color_discrete_sequence=[SINBAD_CYAN],
        title="Géneros principales del catálogo público",
    )
    _style_plotly_figure(genre_fig)

    score_dist_fig = px.histogram(
        public_df.dropna(subset=["standDisplayScore"]),
        x="standDisplayScore",
        nbins=24,
        title="Distribución de standDisplayScore",
        color_discrete_sequence=[SINBAD_BLUE],
    )
    _style_plotly_figure(score_dist_fig)

    scatter_fig = px.scatter(
        public_df.dropna(subset=["ratingCount", "standDisplayScore"]),
        x="ratingCount",
        y="standDisplayScore",
        color="suitabilityCategory",
        hover_data=["displayTitle", "year", "tmdbPopularity"],
        log_x=True,
        title="ratingCount vs standDisplayScore",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_CYAN, SINBAD_RED],
    )
    _style_plotly_figure(scatter_fig)

    blocked_terms_fig = px.bar(
        tables["blocked_terms_by_partition"]
        .query("auditPartition == 'collaborative_support'")
        .head(12),
        x="blockedTerm",
        y="movieCount",
        color_discrete_sequence=[SINBAD_RED],
        title="Blocked terms del soporte colaborativo",
    )
    _style_plotly_figure(blocked_terms_fig)

    excluded_reasons_fig = px.bar(
        tables["excluded_reasons"].head(12),
        x="exclusionReason",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Razones de exclusión más frecuentes",
    )
    _style_plotly_figure(excluded_reasons_fig)

    plotly_sections = [
        partition_fig.to_html(full_html=False, include_plotlyjs="inline"),
        suitability_fig.to_html(full_html=False, include_plotlyjs=False),
        language_fig.to_html(full_html=False, include_plotlyjs=False),
        decade_fig.to_html(full_html=False, include_plotlyjs=False),
        genre_fig.to_html(full_html=False, include_plotlyjs=False),
        score_dist_fig.to_html(full_html=False, include_plotlyjs=False),
        scatter_fig.to_html(full_html=False, include_plotlyjs=False),
        blocked_terms_fig.to_html(full_html=False, include_plotlyjs=False),
        excluded_reasons_fig.to_html(full_html=False, include_plotlyjs=False),
    ]

    support_examples = tables["support_examples"].copy()
    support_examples = support_examples[
        (support_examples["publicBlockedTerms"].fillna("") != "")
        | (support_examples["publicExclusionReasons"].fillna("") != "")
    ].head(12)

    kpis = [
        ("Películas públicas", _format_int(int(counts.get("public", 0)))),
        (
            "Soporte colaborativo",
            _format_int(int(counts.get("collaborative_support", 0))),
        ),
        ("Películas excluidas", _format_int(int(counts.get("excluded", 0)))),
        ("Total analizado", _format_int(int(len(combined_df)))),
        ("Ratings colaborativos", _format_int(collaborative_ratings)),
        ("Públicas revisables", _format_int(int(len(suspicious_public_df)))),
    ]

    chart_gallery = "".join(
        [
            _chart_card_html("Conteo por partición", chart_paths["partition_counts"]),
            _chart_card_html(
                "Suitability por partición",
                chart_paths["suitability_by_partition"],
            ),
            _chart_card_html("Idiomas públicos", chart_paths["public_languages"]),
            _chart_card_html("Décadas públicas", chart_paths["public_decades"]),
            _chart_card_html("Géneros públicos", chart_paths["public_genres"]),
            _chart_card_html(
                "Blocked terms de soporte",
                chart_paths["support_blocked_terms"],
            ),
            _chart_card_html(
                "Distribución de standDisplayScore",
                chart_paths["stand_display_score_distribution"],
            ),
            _chart_card_html(
                "ratingCount vs standDisplayScore",
                chart_paths["rating_count_vs_stand_score"],
            ),
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Auditoría del dataset offline</title>
  <style>
    :root {{
      --bg: {SINBAD_BG};
      --panel: {SINBAD_PANEL};
      --panel-soft: #0d1527;
      --text: #eef5ff;
      --muted: #9db0ca;
      --blue: {SINBAD_BLUE};
      --gold: {SINBAD_GOLD};
      --cyan: {SINBAD_CYAN};
      --red: {SINBAD_RED};
      --border: #223252;
      --shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(77, 163, 255, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(227, 179, 65, 0.14), transparent 26%),
        linear-gradient(180deg, #060c18 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{
      width: min(1380px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    .hero {{
      padding: 28px;
      border: 1px solid var(--border);
      border-radius: 24px;
      background: linear-gradient(135deg, rgba(16,26,47,0.95), rgba(8,17,31,0.96));
      box-shadow: var(--shadow);
    }}
    .eyebrow {{
      color: var(--gold);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 12px;
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(32px, 4vw, 52px);
      line-height: 1.02;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 920px;
      font-size: 17px;
      line-height: 1.6;
    }}
    .section {{
      margin-top: 28px;
      padding: 24px;
      border: 1px solid var(--border);
      border-radius: 22px;
      background: rgba(16, 26, 47, 0.9);
      box-shadow: var(--shadow);
    }}
    .section h2 {{
      margin: 0 0 14px;
      font-size: 24px;
    }}
    .section p {{
      color: var(--muted);
      line-height: 1.65;
    }}
    .grid {{
      display: grid;
      gap: 16px;
    }}
    .kpis {{
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-top: 22px;
    }}
    .kpi {{
      background: linear-gradient(180deg, rgba(11,19,35,0.95), rgba(15,25,44,0.95));
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
    }}
    .kpi .label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .kpi .value {{
      font-size: 30px;
      font-weight: 700;
    }}
    .two {{
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .three {{
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    .card {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .plot {{
      overflow: hidden;
      border-radius: 16px;
      background: rgba(8, 17, 31, 0.85);
      border: 1px solid #1d2d4e;
    }}
    .gallery-card img {{
      width: 100%;
      display: block;
      border-radius: 14px;
      border: 1px solid #223252;
      background: #08111f;
    }}
    .gallery-card h3 {{
      margin: 0 0 12px;
      font-size: 17px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #20304f;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--gold);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .table-wrap {{
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid #20304f;
      background: rgba(8, 17, 31, 0.72);
    }}
    ul.conclusions {{
      margin: 0;
      padding-left: 20px;
    }}
    ul.conclusions li {{
      margin-bottom: 10px;
      color: var(--text);
      line-height: 1.6;
    }}
    .muted {{
      color: var(--muted);
    }}
    a {{
      color: var(--cyan);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">SINBAD Offline Audit</div>
      <h1>Auditoría del dataset offline</h1>
      <p class="subtitle">
        Este panel analiza el dataset portable offline del recomendador y resume cómo se distribuyen
        las películas públicas, el soporte colaborativo y las exclusiones, sin tocar heurísticas ni lógica de recomendación.
      </p>
      <div class="grid kpis">
        {''.join([f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>' for label, value in kpis])}
      </div>
    </section>

    <section class="section">
      <h2>A. Particiones principales</h2>
      <p>Vista general del reparto entre catálogo público, soporte colaborativo y películas excluidas.</p>
      <div class="plot">{plotly_sections[0]}</div>
    </section>

    <section class="section">
      <h2>B. Comparación de suitability</h2>
      <p>Distribución de <code>suitabilityCategory</code> por partición para detectar sesgos de segmentación.</p>
      <div class="plot">{plotly_sections[1]}</div>
    </section>

    <section class="section">
      <h2>C. Catálogo público</h2>
      <p>Idiomas, décadas, géneros y señales de calidad visual del catálogo visible para la demo.</p>
      <div class="grid two">
        <div class="plot">{plotly_sections[2]}</div>
        <div class="plot">{plotly_sections[3]}</div>
        <div class="plot">{plotly_sections[4]}</div>
        <div class="plot">{plotly_sections[5]}</div>
        <div class="plot">{plotly_sections[6]}</div>
      </div>
    </section>

    <section class="section">
      <h2>D. Soporte colaborativo</h2>
      <p>Qué señales bloquean la entrada al catálogo público y qué ejemplos merecen revisión.</p>
      <div class="plot">{plotly_sections[7]}</div>
      <div class="table-wrap" style="margin-top:16px;">
        {_render_html_table(support_examples, limit=12)}
      </div>
    </section>

    <section class="section">
      <h2>E. Películas excluidas</h2>
      <p>Resumen de razones de exclusión para distinguir contenido descartado por política frente a fallos de enriquecimiento o cobertura.</p>
      <div class="plot">{plotly_sections[8]}</div>
    </section>

    <section class="section">
      <h2>F. Tablas de revisión</h2>
      <p>Se muestran solo muestras pequeñas y accionables, no un volcado masivo del dataset.</p>
      <div class="grid three">
        <div class="card">
          <h3>Top 25 públicas</h3>
          <div class="table-wrap">{_render_html_table(tables["public_top_movies"], limit=25)}</div>
        </div>
        <div class="card">
          <h3>Bottom 25 por standDisplayScore</h3>
          <div class="table-wrap">{_render_html_table(tables["public_low_score_movies"], limit=25)}</div>
        </div>
        <div class="card">
          <h3>Muestra de públicas revisables</h3>
          <div class="table-wrap">{_render_html_table(tables["suspicious_public_movies_sample"], limit=25)}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>G. Gráficos estáticos para documentación</h2>
      <p>Estos PNG quedan listos para README, informes o documentación interna.</p>
      <div class="grid two">
        {chart_gallery}
      </div>
    </section>

    <section class="section">
      <h2>H. Conclusiones automáticas</h2>
      <ul class="conclusions">
        {''.join([f"<li>{escape(line)}</li>" for line in conclusions])}
      </ul>
      <p class="muted" style="margin-top:16px;">
        Archivos adicionales: <a href="summary.md">summary.md</a>,
        <a href="summary.json">summary.json</a>,
        <a href="tables/">tables/</a> y <a href="detailed/">detailed/</a>.
      </p>
    </section>
  </div>
</body>
</html>
"""
    return html


def _build_markdown_summary(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    chart_paths: dict[str, str],
    conclusions: list[str],
) -> str:
    counts = combined_df["auditPartition"].value_counts()
    blocked_terms = tables["blocked_terms_by_partition"]
    blocked_terms = blocked_terms[blocked_terms["auditPartition"] == "collaborative_support"].head(10)
    excluded_reasons = tables["excluded_reasons"].head(10)

    chart_list = "\n".join([f"- `{path}`" for path in chart_paths.values()])
    table_list = "\n".join(
        [
            "- `tables/comparison_by_partition.csv`",
            "- `tables/suitability_by_partition.csv`",
            "- `tables/language_by_partition.csv`",
            "- `tables/decade_by_partition.csv`",
            "- `tables/genre_by_partition.csv`",
            "- `tables/blocked_terms_by_partition.csv`",
            "- `tables/public_exclusion_reasons_by_partition.csv`",
            "- `tables/excluded_reasons.csv`",
            "- `tables/public_top_movies.csv`",
            "- `tables/public_low_score_movies.csv`",
            "- `tables/suspicious_public_movies_sample.csv`",
        ]
    )

    return f"""# Auditoría del dataset offline

## Resumen general

- Películas públicas: {_format_int(int(counts.get("public", 0)))}
- Películas de soporte colaborativo: {_format_int(int(counts.get("collaborative_support", 0)))}
- Películas excluidas: {_format_int(int(counts.get("excluded", 0)))}
- Total analizado: {_format_int(int(len(combined_df)))}
- Ratings colaborativos del manifest: {_format_int(int(manifest.get("counts", {}).get("collaborativeRatings", 0)))}
- Películas públicas revisables: {_format_int(int(len(suspicious_public_df)))}

## Catálogo público

- El catálogo público concentra las películas visibles por la demo.
- Se generaron tablas de top y bottom por `standDisplayScore`.
- También se generó una muestra de películas públicas revisables en `tables/suspicious_public_movies_sample.csv`.

![Conteo por partición]({chart_paths["partition_counts"]})
![Idiomas públicos]({chart_paths["public_languages"]})
![Décadas públicas]({chart_paths["public_decades"]})
![Géneros públicos]({chart_paths["public_genres"]})
![Distribución de standDisplayScore]({chart_paths["stand_display_score_distribution"]})
![ratingCount vs standDisplayScore]({chart_paths["rating_count_vs_stand_score"]})

## Soporte colaborativo

- Se analizaron señales de `publicBlockedTerms` y `publicExclusionReasons`.
- El dashboard incluye ejemplos pequeños de películas bloqueadas para revisión manual.

Top blocked terms:
{_markdown_records(blocked_terms, ["blockedTerm", "movieCount", "exampleTitles"])}

## Películas excluidas

- Las excluidas se resumen sin tocar el dataset portable original.
- Se desglosan `exclusionCategory` y `exclusionReasons` en tablas separadas.

Top exclusion reasons:
{_markdown_records(excluded_reasons, ["exclusionReason", "movieCount", "exampleTitles"])}

## Gráficos generados

{chart_list}

## Tablas generadas

{table_list}

## Conclusiones para mejorar heurística

{chr(10).join([f"- {line}" for line in conclusions])}
"""


def _build_summary_json(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    counts_by_partition = {
        partition: int(count)
        for partition, count in combined_df["auditPartition"].value_counts().items()
    }

    return {
        "countsByPartition": counts_by_partition,
        "manifestMetadata": {
            "datasetName": manifest.get("datasetName"),
            "schemaVersion": manifest.get("schemaVersion"),
            "generatedAt": manifest.get("generatedAt"),
            "sourceDataset": manifest.get("sourceDataset"),
            "metadataSource": manifest.get("metadataSource"),
            "canonicalLanguage": manifest.get("canonicalLanguage"),
            "displayLanguage": manifest.get("displayLanguage"),
            "counts": {
                key: int(value) if isinstance(value, (int, float)) else value
                for key, value in manifest.get("counts", {}).items()
            },
            "downloadedPublicPosters": int(manifest.get("downloadedPublicPosters", 0)),
            "missingPublicPosters": int(manifest.get("missingPublicPosters", 0)),
            "failedPublicPosterDownloads": int(manifest.get("failedPublicPosterDownloads", 0)),
        },
        "suitabilityCounts": _records_from_dataframe(
            tables["suitability_by_partition"],
            limit=100,
        ),
        "languageCounts": _records_from_dataframe(
            tables["language_by_partition"],
            limit=100,
        ),
        "decadeCounts": _records_from_dataframe(
            tables["decade_by_partition"],
            limit=100,
        ),
        "genreCounts": _records_from_dataframe(
            tables["genre_by_partition"],
            limit=120,
        ),
        "topBlockedTerms": _records_from_dataframe(
            tables["blocked_terms_by_partition"].query(
                "auditPartition == 'collaborative_support'"
            ),
            limit=20,
        ),
        "topPublicExclusionReasons": _records_from_dataframe(
            tables["public_exclusion_reasons_by_partition"],
            limit=20,
        ),
        "excludedReasonCounts": _records_from_dataframe(
            tables["excluded_reasons"],
            limit=20,
        ),
        "suspiciousPublicMovieCount": int(len(suspicious_public_df)),
        "topPublicMovieSamples": _records_from_dataframe(
            tables["public_top_movies"],
            limit=10,
        ),
        "bottomPublicMovieSamples": _records_from_dataframe(
            tables["public_low_score_movies"],
            limit=10,
        ),
    }


def _compute_public_audit_flags(public_df: pd.DataFrame) -> pd.Series:
    flag_columns = {
        "low_stand_display_score": public_df["standDisplayScore"].fillna(0) < LOW_STAND_DISPLAY_SCORE,
        "low_rating_count": public_df["ratingCount"].fillna(0) < LOW_RATING_COUNT,
        "low_tmdb_popularity": public_df["tmdbPopularity"].fillna(0) < LOW_TMDB_POPULARITY,
        "old_public_movie": public_df["year"].fillna(0) < OLD_PUBLIC_YEAR,
        "uncommon_original_language": ~public_df["originalLanguage"].isin(COMMON_PUBLIC_LANGUAGES),
        "missing_display_title": public_df["displayTitle"] == "",
        "missing_display_overview": public_df["displayOverview"] == "",
        "empty_genres": public_df["genres"] == "",
    }
    flags_df = pd.DataFrame(flag_columns, index=public_df.index)
    return flags_df.apply(
        lambda row: "|".join([column for column, enabled in row.items() if bool(enabled)]),
        axis=1,
    )


def _count_by_field(
    dataframe: pd.DataFrame,
    *,
    field_name: str,
    value_column: str,
    empty_label: str,
    include_percentage: bool = False,
) -> pd.DataFrame:
    subset_df = dataframe[["auditPartition", field_name, "movieId"]].copy()
    subset_df[value_column] = _normalize_text_series(subset_df[field_name]).replace("", empty_label)
    grouped_df = (
        subset_df.groupby(["auditPartition", value_column], dropna=False)["movieId"]
        .nunique()
        .reset_index(name="movieCount")
        .sort_values(
            by=["auditPartition", "movieCount", value_column],
            ascending=[True, False, True],
            kind="mergesort",
        )
    )
    if include_percentage:
        totals = grouped_df.groupby("auditPartition")["movieCount"].transform("sum")
        grouped_df["percentage"] = (grouped_df["movieCount"] / totals * 100).round(2)
    return grouped_df


def _explode_pipe_field(
    dataframe: pd.DataFrame,
    *,
    field_name: str,
    value_column: str,
    empty_label: str | None = None,
    include_partition: bool = True,
) -> pd.DataFrame:
    columns = ["movieId", "displayLabel", field_name]
    if include_partition:
        columns.insert(0, "auditPartition")
    subset_df = dataframe[columns].copy()
    subset_df[field_name] = _normalize_text_series(subset_df[field_name])
    subset_df[field_name] = subset_df[field_name].str.split("|")
    subset_df = subset_df.explode(field_name)
    subset_df[field_name] = subset_df[field_name].fillna("").astype(str).str.strip()
    if empty_label is None:
        subset_df = subset_df[subset_df[field_name] != ""]
    else:
        subset_df[field_name] = subset_df[field_name].replace("", empty_label)

    group_columns = [value_column]
    if include_partition:
        group_columns.insert(0, "auditPartition")
    subset_df = subset_df.rename(columns={field_name: value_column})

    aggregated_df = (
        subset_df.groupby(group_columns, dropna=False)
        .agg(
            movieCount=("movieId", "nunique"),
            exampleTitles=("displayLabel", _join_example_titles),
        )
        .reset_index()
        .sort_values(
            by=(["auditPartition", "movieCount", value_column] if include_partition else ["movieCount", value_column]),
            ascending=([True, False, True] if include_partition else [False, True]),
            kind="mergesort",
        )
    )
    return aggregated_df


def _select_public_movies(public_df: pd.DataFrame, *, ascending: bool) -> pd.DataFrame:
    if ascending:
        return public_df.sort_values(
            by=["standDisplayScore", "ratingCount", "displayLabel"],
            ascending=[True, True, True],
            na_position="last",
            kind="mergesort",
        )
    return public_df.sort_values(
        by=["standDisplayScore", "ratingCount", "displayLabel"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    )


def _style_axes(ax: Any, *, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=14, pad=14, color="#eef5ff")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def _finalize_chart(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def _save_empty_chart(title: str, path: Path) -> None:
    plt.figure(figsize=(8, 4.5))
    plt.text(0.5, 0.5, "Sin datos disponibles", ha="center", va="center", fontsize=16, color="#eef5ff")
    plt.title(title, color="#eef5ff")
    plt.axis("off")
    _finalize_chart(path)


def _style_plotly_figure(figure: Any) -> None:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor=SINBAD_BG,
        plot_bgcolor=SINBAD_PANEL,
        font={"color": "#eef5ff"},
        margin={"l": 30, "r": 20, "t": 56, "b": 40},
        legend={"orientation": "h", "y": -0.18},
    )


def _write_csv(dataframe: pd.DataFrame, path: Path) -> None:
    output_df = dataframe.copy()
    for column in output_df.columns:
        if pd.api.types.is_integer_dtype(output_df[column].dtype):
            output_df[column] = output_df[column].astype("Int64")
    output_df.to_csv(path, index=False)


def _render_html_table(dataframe: pd.DataFrame, *, limit: int) -> str:
    preview_df = dataframe.head(limit).copy()
    for column in preview_df.columns:
        if pd.api.types.is_float_dtype(preview_df[column].dtype):
            preview_df[column] = preview_df[column].round(4)
    return preview_df.to_html(index=False, classes="audit-table", border=0, escape=True)


def _chart_card_html(title: str, relative_path: str) -> str:
    return (
        f'<div class="card gallery-card"><h3>{escape(title)}</h3>'
        f'<img src="{escape(relative_path)}" alt="{escape(title)}" /></div>'
    )


def _coalesce_text(primary: pd.Series | None, fallback: pd.Series | None) -> pd.Series:
    primary_series = _normalize_text_series(primary if primary is not None else pd.Series(dtype="object"))
    if fallback is None:
        return primary_series
    fallback_series = _normalize_text_series(fallback)
    return primary_series.where(primary_series != "", fallback_series)


def _coalesce_numeric(primary: pd.Series | None, fallback: pd.Series | None) -> pd.Series:
    primary_series = pd.to_numeric(primary, errors="coerce") if primary is not None else pd.Series(dtype="float64")
    if fallback is None:
        return primary_series
    fallback_series = pd.to_numeric(fallback, errors="coerce")
    return primary_series.fillna(fallback_series)


def _normalize_text_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="object")
    return series.fillna("").astype(str).str.strip()


def _year_to_decade_label(year: object) -> str:
    if pd.isna(year):
        return "unknown"
    year_int = int(year)
    return f"{(year_int // 10) * 10}s"


def _join_example_titles(values: pd.Series) -> str:
    unique_titles = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in unique_titles:
            unique_titles.append(normalized)
        if len(unique_titles) >= 8:
            break
    return " | ".join(unique_titles)


def _format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _markdown_records(dataframe: pd.DataFrame, columns: list[str]) -> str:
    if dataframe.empty:
        return "- Sin datos"
    lines = []
    for row in dataframe[columns].head(10).itertuples(index=False):
        parts = [f"{column}={getattr(row, column)}" for column in columns]
        lines.append(f"- {'; '.join(parts)}")
    return "\n".join(lines)


def _records_from_dataframe(dataframe: pd.DataFrame, *, limit: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in dataframe.head(limit).to_dict(orient="records"):
        records.append({key: _json_safe_value(value) for key, value in row.items()})
    return records


def _json_safe_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


if __name__ == "__main__":
    main()
