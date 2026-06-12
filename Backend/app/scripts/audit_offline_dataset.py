import json
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
from plotly.offline import get_plotlyjs

from app.domain.catalog_heuristics.constants import (
    PUBLIC_MIN_STAND_DISPLAY_SCORE,
    PUBLIC_STAND_ACCESSIBILITY_PROTECTED_GENRES,
    PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_DISPLAY_SCORE,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_RATING_COUNT,
    PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_TMDB_POPULARITY,
    SENSITIVE_GENRES,
)
from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_AUDIT_CHARTS_DIR,
    OFFLINE_DATASET_AUDIT_DASHBOARD_PATH,
    OFFLINE_DATASET_AUDIT_DETAILED_DIR,
    OFFLINE_DATASET_AUDIT_DIR,
    OFFLINE_DATASET_AUDIT_INDEX_PATH,
    OFFLINE_DATASET_AUDIT_TABLES_DIR,
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


AUDIT_TOP_TABLE_LIMIT = 100
RATINGS_CHUNK_SIZE = 1_000_000

SUMMARY_MD_PATH = OFFLINE_DATASET_AUDIT_DIR / "summary.md"
SUMMARY_JSON_PATH = OFFLINE_DATASET_AUDIT_DIR / "summary.json"

PARTITION_ORDER = ["public", "collaborative_support", "excluded"]
PARTITION_LABELS = {
    "public": "Catálogo público",
    "collaborative_support": "Soporte colaborativo",
    "excluded": "Excluidas",
}
PARTITION_COLORS = {
    "Catálogo público": "#4da3ff",
    "Soporte colaborativo": "#e3b341",
    "Excluidas": "#ff6b6b",
}
DATASET_ROLE_LABELS = {
    "public": "Catálogo público",
    "collaborative_support": "Soporte colaborativo",
    "excluded": "Excluidas",
}
USER_BUCKET_ORDER = ["1-4", "5-9", "10-24", "25-49", "50-99", "100-249", "250+"]
RATING_VALUE_ORDER = [value / 2 for value in range(1, 11)]

SINBAD_BLUE = "#4da3ff"
SINBAD_GOLD = "#e3b341"
SINBAD_CYAN = "#67d9ff"
SINBAD_RED = "#ff6b6b"
SINBAD_GREEN = "#6bd6a7"
SINBAD_BG = "#08111f"
SINBAD_PANEL = "#101a2f"

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
    "standDisplayReasons",
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
    "standDisplayReasons",
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

EXPLANATIONS = {
    "section_executive_summary": "Resume el tamaño del dataset offline, el reparto entre particiones y varias señales de revisión rápida para entender qué partes del catálogo son visibles y cuáles quedan como soporte.",
    "section_dataset_overview": "Describe el equilibrio general del dataset por partición, suitability, idioma, década y género. Sirve para inspeccionar cobertura y mezcla de contenido sin interpretar todavía la calidad del ranking.",
    "partition_chart": "Compara cuántas películas hay en cada partición del dataset offline y ayuda a distinguir la parte visible de la base colaborativa de soporte.",
    "suitability_partition_chart": "Muestra la distribución de suitabilityCategory por partición. Permite revisar dónde se concentra el contenido family_friendly, teen, unknown y adult_or_sensitive.",
    "language_partition_table": "Resume el idioma original por partición. Ayuda a revisar la cobertura lingüística del dataset completo y del catálogo visible.",
    "genre_partition_table": "Muestra qué géneros aparecen con más frecuencia en cada partición y permite inspeccionar si el catálogo visible y el soporte colaborativo se están separando como se espera.",
    "section_public_quality": "Agrupa señales del catálogo público que ayudan a inspeccionar la experiencia visible del stand: suitability, score, reconocimiento, idioma, década y géneros.",
    "public_suitability_chart": "Muestra la distribución de películas por suitabilityCategory dentro del catálogo público.",
    "public_languages_chart": "Muestra el idioma original de las películas públicas y ayuda a revisar qué idiomas llegan a la parte visible del dataset.",
    "public_decades_chart": "Muestra la distribución por década del catálogo público y permite inspeccionar la mezcla temporal de la selección visible.",
    "public_genres_chart": "Muestra los géneros más frecuentes del catálogo público y ayuda a revisar la mezcla temática que verá el usuario en el stand.",
    "public_score_distribution_chart": "Muestra la distribución de standDisplayScore dentro del catálogo público y permite inspeccionar cómo se reparte la señal usada para ordenar la vitrina.",
    "public_scatter_chart": "Relaciona ratingCount y standDisplayScore dentro del catálogo público. Ayuda a revisar si la parte visible combina reconocimiento colaborativo y señal de presentación.",
    "public_stand_score_by_suitability_chart": "Compara standDisplayScore por suitabilityCategory dentro del catálogo público. Permite revisar cómo se ordenan family_friendly y teen cuando ambos aparecen en la parte visible.",
    "public_top_table": "Lista películas públicas con mayor standDisplayScore para inspeccionar qué títulos quedan más arriba en la vitrina.",
    "public_bottom_table": "Lista películas públicas con menor standDisplayScore para inspeccionar qué títulos quedan en la parte baja del catálogo visible.",
    "section_teen_sensitive_control": "Resume cómo se comportan las películas teen con géneros sensibles dentro del catálogo público, sin cambiar la elegibilidad ni la clasificación.",
    "teen_sensitive_chart": "Cuenta géneros sensibles dentro de las películas públicas teen. Permite revisar si las señales sensibles siguen presentes en posiciones visibles.",
    "teen_sensitive_table": "Lista películas públicas teen con géneros sensibles para revisar sus razones de suitability y sus razones de standDisplayScore.",
    "section_low_stand_accessibility": "Describe películas retiradas del catálogo público por baja accesibilidad de stand. Estas películas pueden seguir siendo útiles en soporte colaborativo.",
    "low_accessibility_chart": "Cuenta casos de low_stand_accessibility por idioma original y ayuda a revisar qué idiomas aparecen con más frecuencia en esta regla de filtrado público.",
    "low_accessibility_examples_table": "Lista ejemplos con baja accesibilidad de stand y permite revisar ratingCount, popularidad TMDB y standDisplayScore sin sacarlos del dataset colaborativo.",
    "section_stand_reasons": "Resume las razones que alimentan standDisplayReasons. Sirve para inspeccionar qué señales empujan el ranking visible sin añadir nuevos campos al dataset exportado.",
    "stand_reasons_chart": "Cuenta standDisplayReasons dentro del catálogo público y permite revisar qué señales de ranking aparecen con más frecuencia.",
    "family_certified_teen_table": "Lista ejemplos públicos con `stand_family_certified_teen_suitability` para revisar títulos con certificación familiar resueltos como teen por señales sensibles.",
    "section_family_only_simulation": "Simula cómo quedaría el catálogo público si solo se mostrasen películas family_friendly, sin regenerar el dataset.",
    "family_only_chart": "Compara la mezcla family_friendly y teen en el catálogo público actual y en los primeros tramos del ranking visible.",
    "family_only_table": "Resume la proporción de películas family_friendly y teen en el catálogo público actual y en los top 100 y top 250 por standDisplayScore.",
    "section_support": "Explica por qué muchas películas útiles colaborativamente no llegan al catálogo público y permite revisar razones de soporte sin tocar la lógica del recomendador.",
    "support_blocked_terms_chart": "Cuenta blocked terms dentro del soporte colaborativo y ayuda a inspeccionar qué temas alejan películas del catálogo público visible.",
    "support_examples_table": "Muestra ejemplos de soporte colaborativo con razones de exclusión pública o blocked terms para revisar por qué siguen siendo útiles fuera del catálogo visible.",
    "section_excluded": "Resume las películas excluidas por completo del dataset visible y colaborativo, con foco en causas mecánicas o de cobertura.",
    "excluded_reasons_chart": "Cuenta razones de exclusión total y permite revisar si dominan problemas de enriquecimiento, cobertura o señal insuficiente.",
    "excluded_examples_table": "Muestra ejemplos de películas excluidas con sus razones para revisar casos concretos de exclusión total.",
    "section_collaborative": "Estas métricas describen el núcleo colaborativo completo: películas públicas más películas de soporte colaborativo. Las excluidas no forman parte de `collaborative_ratings.csv`.",
    "collaborative_rating_distribution_chart": "Muestra la distribución de valores de rating y ayuda a inspeccionar el sesgo de puntuaciones del núcleo colaborativo.",
    "collaborative_user_buckets_chart": "Agrupa usuarios por número de ratings emitidos y ayuda a revisar la fuerza de los perfiles colaborativos.",
    "collaborative_year_chart": "Cuenta ratings por año y permite revisar la distribución temporal de la actividad colaborativa.",
    "collaborative_top_movies_chart": "Lista qué películas concentran más ratings filtrados y ayuda a inspeccionar qué títulos aportan más señal colaborativa.",
    "section_static": "Expone las versiones PNG de los gráficos para README e informes, de modo que el análisis pueda reutilizarse sin depender del dashboard interactivo.",
    "section_tables": "Resume las tablas CSV disponibles para revisión manual. Las tablas detalladas siguen disponibles en `audit/tables/` y `audit/detailed/`.",
    "section_conclusions": "Resume observaciones mecánicas del dataset actual. Sirve como recordatorio rápido de balance, señales públicas y salud colaborativa.",
}


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
    collaborative_signals = _analyze_collaborative_ratings(combined_df)

    _write_detailed_outputs(combined_df, suspicious_public_df)

    tables = _build_summary_tables(
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        collaborative_signals=collaborative_signals,
    )
    _write_summary_tables(tables)

    chart_paths = _generate_static_charts(
        combined_df=combined_df,
        tables=tables,
        collaborative_signals=collaborative_signals,
    )
    conclusions = _build_conclusions(
        manifest=manifest,
        combined_df=combined_df,
        tables=tables,
        suspicious_public_df=suspicious_public_df,
        collaborative_signals=collaborative_signals,
    )

    dashboard_html = _build_dashboard_html(
        manifest=manifest,
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        tables=tables,
        chart_paths=chart_paths,
        conclusions=conclusions,
        collaborative_signals=collaborative_signals,
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
        collaborative_signals=collaborative_signals,
    )
    SUMMARY_MD_PATH.write_text(summary_markdown, encoding="utf-8")

    summary_json = _build_summary_json(
        manifest=manifest,
        combined_df=combined_df,
        suspicious_public_df=suspicious_public_df,
        tables=tables,
        collaborative_signals=collaborative_signals,
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Audit dashboard written: {OFFLINE_DATASET_AUDIT_DASHBOARD_PATH}")
    print(f"Audit index written: {OFFLINE_DATASET_AUDIT_INDEX_PATH}")
    print(f"Summary written: {SUMMARY_MD_PATH}")
    print(f"Tables written: {OFFLINE_DATASET_AUDIT_TABLES_DIR}")
    print(f"Detailed files written: {OFFLINE_DATASET_AUDIT_DETAILED_DIR}")
    print(f"Charts written: {OFFLINE_DATASET_AUDIT_CHARTS_DIR}")
    print("Backend route: /audit/")


def _ensure_required_inputs() -> None:
    required_paths = [
        OFFLINE_DATASET_MANIFEST_PATH,
        OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
        OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
        OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
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

    combined_df["title"] = _coalesce_text(combined_df.get("title"), combined_df.get("summaryTitle"))
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
    combined_df["partitionLabel"] = combined_df["auditPartition"].map(PARTITION_LABELS)
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


def _split_pipe_values(value: object) -> list[str]:
    normalized = str(value).strip()
    if not normalized:
        return []
    return [part.strip() for part in normalized.split("|") if part.strip()]


def _series_contains_pipe_token(series: pd.Series, token: str) -> pd.Series:
    return series.fillna("").astype(str).apply(lambda value: token in _split_pipe_values(value))


def _series_intersects_pipe_values(series: pd.Series, values: set[str]) -> pd.Series:
    return series.fillna("").astype(str).apply(
        lambda value: bool(set(_split_pipe_values(value)) & values)
    )


def _compute_public_partition_metrics(public_df: pd.DataFrame) -> dict[str, int | float]:
    family_count = int((public_df["suitabilityCategory"] == "family_friendly").sum())
    teen_count = int((public_df["suitabilityCategory"] == "teen").sum())

    ordered_public_df = _select_public_movies(public_df, ascending=False)
    top_100 = ordered_public_df.head(100)
    top_250 = ordered_public_df.head(250)

    current_public_movies = int(len(public_df))
    public_share_family = round((family_count / current_public_movies) * 100, 2) if current_public_movies else 0.0
    public_share_teen = round((teen_count / current_public_movies) * 100, 2) if current_public_movies else 0.0

    return {
        "currentPublicMovies": current_public_movies,
        "familyFriendlyPublicMovies": family_count,
        "teenPublicMovies": teen_count,
        "publicShareFamilyFriendlyPercent": public_share_family,
        "publicShareTeenPercent": public_share_teen,
        "top100FamilyFriendlyCount": int((top_100["suitabilityCategory"] == "family_friendly").sum()),
        "top100TeenCount": int((top_100["suitabilityCategory"] == "teen").sum()),
        "top250FamilyFriendlyCount": int((top_250["suitabilityCategory"] == "family_friendly").sum()),
        "top250TeenCount": int((top_250["suitabilityCategory"] == "teen").sum()),
    }


def _build_family_only_simulation_table(public_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([_compute_public_partition_metrics(public_df)])


def _analyze_collaborative_ratings(combined_df: pd.DataFrame) -> dict[str, Any]:
    total_ratings = 0
    unique_movie_ids: set[int] = set()
    user_counts: dict[int, int] = defaultdict(int)
    rating_value_counts: dict[float, int] = defaultdict(int)
    ratings_by_year: dict[int, int] = defaultdict(int)

    for chunk_df in pd.read_csv(
        OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
        usecols=["userId", "movieId", "rating", "timestamp"],
        dtype={
            "userId": "int64",
            "movieId": "int64",
            "rating": "float64",
            "timestamp": "int64",
        },
        chunksize=RATINGS_CHUNK_SIZE,
    ):
        total_ratings += int(len(chunk_df))
        unique_movie_ids.update(int(movie_id) for movie_id in chunk_df["movieId"].unique().tolist())

        user_chunk = chunk_df.groupby("userId", sort=False).size()
        for user_id, count in user_chunk.items():
            user_counts[int(user_id)] += int(count)

        rating_chunk = chunk_df["rating"].value_counts(sort=False)
        for rating_value, count in rating_chunk.items():
            rating_value_counts[float(rating_value)] += int(count)

        years = pd.to_datetime(chunk_df["timestamp"], unit="s", utc=True, errors="coerce").dt.year
        year_chunk = years.dropna().astype(int).value_counts(sort=False)
        for year, count in year_chunk.items():
            ratings_by_year[int(year)] += int(count)

    user_counts_series = pd.Series(user_counts, dtype="int64")
    movie_counts_series = combined_df["filteredRatingCount"].dropna()
    movie_counts_series = movie_counts_series[movie_counts_series > 0]

    unique_users = int(len(user_counts_series))
    unique_rated_movies = int(len(unique_movie_ids))
    matrix_density = (
        total_ratings / (unique_users * unique_rated_movies)
        if unique_users > 0 and unique_rated_movies > 0
        else 0.0
    )

    rating_distribution_df = _build_rating_distribution_table(rating_value_counts, total_ratings)
    ratings_by_year_df = _build_ratings_by_year_table(ratings_by_year, total_ratings)
    user_buckets_df = _build_user_buckets_table(user_counts_series)
    top_users_df = _build_top_users_table(user_counts_series)
    top_movies_df = _build_top_movies_by_filtered_ratings_table(combined_df)
    collaborative_summary_df = _build_collaborative_summary_table(
        total_ratings=total_ratings,
        unique_users=unique_users,
        unique_rated_movies=unique_rated_movies,
        matrix_density=matrix_density,
        average_ratings_per_user=float(user_counts_series.mean()) if not user_counts_series.empty else 0.0,
        median_ratings_per_user=float(user_counts_series.median()) if not user_counts_series.empty else 0.0,
        max_ratings_per_user=int(user_counts_series.max()) if not user_counts_series.empty else 0,
        average_ratings_per_movie=float(movie_counts_series.mean()) if not movie_counts_series.empty else 0.0,
        median_ratings_per_movie=float(movie_counts_series.median()) if not movie_counts_series.empty else 0.0,
    )

    summary_records = collaborative_summary_df.set_index("metric")["value"].to_dict()

    return {
        "totalRatings": int(total_ratings),
        "uniqueUsers": unique_users,
        "uniqueRatedMovies": unique_rated_movies,
        "matrixDensity": round(matrix_density, 8),
        "averageRatingsPerUser": round(float(summary_records["averageRatingsPerUser"]), 4),
        "medianRatingsPerUser": round(float(summary_records["medianRatingsPerUser"]), 4),
        "maxRatingsPerUser": int(summary_records["maxRatingsPerUser"]),
        "averageRatingsPerMovie": round(float(summary_records["averageRatingsPerMovie"]), 4),
        "medianRatingsPerMovie": round(float(summary_records["medianRatingsPerMovie"]), 4),
        "tables": {
            "collaborative_summary": collaborative_summary_df,
            "rating_distribution": rating_distribution_df,
            "ratings_by_year": ratings_by_year_df,
            "ratings_per_user_buckets": user_buckets_df,
            "top_movies_by_filtered_ratings": top_movies_df,
            "top_users_by_rating_count": top_users_df,
        },
    }


def _build_rating_distribution_table(
    rating_value_counts: dict[float, int],
    total_ratings: int,
) -> pd.DataFrame:
    rows = []
    for rating_value in RATING_VALUE_ORDER:
        count = int(rating_value_counts.get(rating_value, 0))
        share = round((count / total_ratings) * 100, 4) if total_ratings else 0.0
        rows.append(
            {
                "ratingValue": float(rating_value),
                "ratingLabel": f"{rating_value:.1f}",
                "ratingCount": count,
                "sharePercent": share,
            }
        )
    return pd.DataFrame(rows)


def _build_ratings_by_year_table(
    ratings_by_year: dict[int, int],
    total_ratings: int,
) -> pd.DataFrame:
    rows = []
    for year in sorted(ratings_by_year):
        count = int(ratings_by_year[year])
        share = round((count / total_ratings) * 100, 4) if total_ratings else 0.0
        rows.append({"year": int(year), "ratingCount": count, "sharePercent": share})
    return pd.DataFrame(rows)


def _build_user_buckets_table(user_counts_series: pd.Series) -> pd.DataFrame:
    bucket_counts: dict[str, int] = {bucket: 0 for bucket in USER_BUCKET_ORDER}
    for count in user_counts_series.tolist():
        bucket_counts[_bucket_user_count(int(count))] += 1

    total_users = int(len(user_counts_series))
    rows = []
    for bucket in USER_BUCKET_ORDER:
        user_count = int(bucket_counts[bucket])
        share = round((user_count / total_users) * 100, 4) if total_users else 0.0
        rows.append(
            {
                "bucket": bucket,
                "userCount": user_count,
                "sharePercent": share,
            }
        )
    return pd.DataFrame(rows)


def _build_top_users_table(user_counts_series: pd.Series) -> pd.DataFrame:
    if user_counts_series.empty:
        return pd.DataFrame(columns=["userId", "ratingCount"])
    top_users = user_counts_series.sort_values(ascending=False).head(100)
    return pd.DataFrame(
        {
            "userId": [int(user_id) for user_id in top_users.index.tolist()],
            "ratingCount": [int(value) for value in top_users.tolist()],
        }
    )


def _build_top_movies_by_filtered_ratings_table(combined_df: pd.DataFrame) -> pd.DataFrame:
    movie_df = combined_df[combined_df["filteredRatingCount"].fillna(0) > 0].copy()
    movie_df["datasetRoleLabel"] = movie_df["auditPartition"].map(DATASET_ROLE_LABELS)
    movie_df = movie_df.sort_values(
        by=["filteredRatingCount", "filteredAverageRating", "displayLabel"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    )
    return movie_df[
        [
            "movieId",
            "displayLabel",
            "datasetRoleLabel",
            "filteredRatingCount",
            "filteredAverageRating",
            "ratingCount",
            "averageRating",
        ]
    ].head(100)


def _build_collaborative_summary_table(
    *,
    total_ratings: int,
    unique_users: int,
    unique_rated_movies: int,
    matrix_density: float,
    average_ratings_per_user: float,
    median_ratings_per_user: float,
    max_ratings_per_user: int,
    average_ratings_per_movie: float,
    median_ratings_per_movie: float,
) -> pd.DataFrame:
    rows = [
        ("totalRatings", total_ratings),
        ("uniqueUsers", unique_users),
        ("uniqueRatedMovies", unique_rated_movies),
        ("matrixDensity", round(matrix_density, 8)),
        ("averageRatingsPerUser", round(average_ratings_per_user, 4)),
        ("medianRatingsPerUser", round(median_ratings_per_user, 4)),
        ("maxRatingsPerUser", max_ratings_per_user),
        ("averageRatingsPerMovie", round(average_ratings_per_movie, 4)),
        ("medianRatingsPerMovie", round(median_ratings_per_movie, 4)),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


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
    collaborative_signals: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    public_df = combined_df[combined_df["auditPartition"] == "public"].copy()
    support_df = combined_df[combined_df["auditPartition"] == "collaborative_support"].copy()
    excluded_df = combined_df[combined_df["auditPartition"] == "excluded"].copy()
    low_accessibility_mask = (
        combined_df["auditPartition"].isin(["collaborative_support", "excluded"])
        & _series_contains_pipe_token(
            combined_df["publicExclusionReasons"],
            "low_stand_accessibility",
        )
    )
    public_teen_sensitive_mask = (
        (public_df["suitabilityCategory"] == "teen")
        & _series_intersects_pipe_values(public_df["genres"], SENSITIVE_GENRES)
    )
    family_certified_teen_mask = _series_contains_pipe_token(
        public_df["standDisplayReasons"],
        "stand_family_certified_teen_suitability",
    )

    comparison_by_partition = (
        combined_df.groupby("auditPartition", dropna=False)
        .agg(
            movieCount=("movieId", "nunique"),
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
    stand_display_reasons_by_partition = _explode_pipe_field(
        combined_df,
        field_name="standDisplayReasons",
        value_column="standDisplayReason",
    )
    stand_display_reasons_public = _explode_pipe_field(
        public_df,
        field_name="standDisplayReasons",
        value_column="standDisplayReason",
        include_partition=False,
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
    public_suitability_counts = _count_by_field(
        public_df,
        field_name="suitabilityCategory",
        value_column="suitabilityCategory",
        empty_label="unknown",
        include_percentage=True,
    )

    low_stand_accessibility_movies = combined_df.loc[low_accessibility_mask].copy()
    low_stand_accessibility_movies = low_stand_accessibility_movies.sort_values(
        by=["standDisplayScore", "ratingCount", "tmdbPopularity", "displayLabel"],
        ascending=[True, True, True, True],
        na_position="last",
        kind="mergesort",
    )
    low_stand_accessibility_by_language = (
        low_stand_accessibility_movies.assign(
            originalLanguageLabel=low_stand_accessibility_movies["originalLanguage"].replace(
                "",
                "unknown",
            )
        )
        .groupby("originalLanguageLabel", dropna=False)["movieId"]
        .nunique()
        .reset_index(name="movieCount")
        .rename(columns={"originalLanguageLabel": "originalLanguage"})
        .sort_values(
            by=["movieCount", "originalLanguage"],
            ascending=[False, True],
            kind="mergesort",
        )
    )
    low_stand_accessibility_by_suitability = (
        low_stand_accessibility_movies.assign(
            suitabilityLabel=low_stand_accessibility_movies["suitabilityCategory"].replace(
                "",
                "unknown",
            )
        )
        .groupby("suitabilityLabel", dropna=False)["movieId"]
        .nunique()
        .reset_index(name="movieCount")
        .rename(columns={"suitabilityLabel": "suitabilityCategory"})
        .sort_values(
            by=["movieCount", "suitabilityCategory"],
            ascending=[False, True],
            kind="mergesort",
        )
    )
    low_stand_accessibility_examples = low_stand_accessibility_movies.head(AUDIT_TOP_TABLE_LIMIT)

    public_top_movies = _select_public_movies(public_df, ascending=False).head(AUDIT_TOP_TABLE_LIMIT)
    public_low_score_movies = _select_public_movies(public_df, ascending=True).head(
        AUDIT_TOP_TABLE_LIMIT
    )
    public_teen_sensitive_movies = public_df.loc[public_teen_sensitive_mask].copy()
    public_teen_sensitive_movies = public_teen_sensitive_movies.sort_values(
        by=["standDisplayScore", "ratingCount", "tmdbPopularity", "displayLabel"],
        ascending=[False, False, False, True],
        na_position="last",
        kind="mergesort",
    ).head(AUDIT_TOP_TABLE_LIMIT)
    public_family_certified_teen_movies = public_df.loc[family_certified_teen_mask].copy()
    public_family_certified_teen_movies = public_family_certified_teen_movies.sort_values(
        by=["standDisplayScore", "ratingCount", "displayLabel"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    ).head(AUDIT_TOP_TABLE_LIMIT)
    family_only_simulation_summary = _build_family_only_simulation_table(public_df)
    teen_sensitive_genres = _explode_pipe_field(
        public_df.loc[public_teen_sensitive_mask],
        field_name="genres",
        value_column="genre",
        include_partition=False,
    )
    teen_sensitive_genres = teen_sensitive_genres[
        teen_sensitive_genres["genre"].isin(SENSITIVE_GENRES)
    ].sort_values(
        by=["movieCount", "genre"],
        ascending=[False, True],
        kind="mergesort",
    )

    suspicious_public_movies_sample = suspicious_public_df.head(AUDIT_TOP_TABLE_LIMIT)
    support_examples = support_df[
        (support_df["publicBlockedTerms"].fillna("").astype(str) != "")
        | (support_df["publicExclusionReasons"].fillna("").astype(str) != "")
    ].copy()
    support_examples = support_examples.sort_values(
        by=["filteredRatingCount", "ratingCount", "displayLabel"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    ).head(AUDIT_TOP_TABLE_LIMIT)
    excluded_examples = excluded_df.sort_values(
        by=["exclusionReasons", "displayLabel"],
        ascending=[True, True],
        na_position="last",
        kind="mergesort",
    ).head(AUDIT_TOP_TABLE_LIMIT)

    return {
        "comparison_by_partition": comparison_by_partition,
        "suitability_by_partition": suitability_by_partition,
        "public_suitability_counts": public_suitability_counts,
        "language_by_partition": language_by_partition,
        "decade_by_partition": decade_by_partition,
        "genre_by_partition": genre_by_partition,
        "blocked_terms_by_partition": blocked_terms_by_partition,
        "stand_display_reasons_by_partition": stand_display_reasons_by_partition,
        "stand_display_reasons_public": stand_display_reasons_public,
        "public_exclusion_reasons_by_partition": public_exclusion_reasons_by_partition,
        "excluded_reasons": excluded_reasons,
        "low_stand_accessibility_movies": low_stand_accessibility_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "suitabilityCategory",
                "ratingCount",
                "tmdbPopularity",
                "standDisplayScore",
                "publicExclusionReasons",
                "filteredRatingCount",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "low_stand_accessibility_by_language": low_stand_accessibility_by_language,
        "low_stand_accessibility_by_suitability": low_stand_accessibility_by_suitability,
        "low_stand_accessibility_examples": low_stand_accessibility_examples[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "suitabilityCategory",
                "ratingCount",
                "tmdbPopularity",
                "standDisplayScore",
                "publicExclusionReasons",
                "filteredRatingCount",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_top_movies": public_top_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "standDisplayScore",
                "ratingCount",
                "suitabilityCategory",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_low_score_movies": public_low_score_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "standDisplayScore",
                "ratingCount",
                "suitabilityCategory",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_top_by_stand_score": public_top_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "suitabilityCategory",
                "standDisplayScore",
                "ratingCount",
                "tmdbPopularity",
                "standDisplayReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_bottom_by_stand_score": public_low_score_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "suitabilityCategory",
                "standDisplayScore",
                "ratingCount",
                "tmdbPopularity",
                "standDisplayReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_teen_sensitive_movies": public_teen_sensitive_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "genres",
                "originalLanguage",
                "standDisplayScore",
                "ratingCount",
                "tmdbPopularity",
                "suitabilityReasons",
                "standDisplayReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "public_family_certified_teen_movies": public_family_certified_teen_movies[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "standDisplayScore",
                "ratingCount",
                "tmdbPopularity",
                "suitabilityReasons",
                "standDisplayReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "family_only_simulation_summary": family_only_simulation_summary,
        "teen_sensitive_genres": teen_sensitive_genres,
        "suspicious_public_movies_sample": suspicious_public_movies_sample[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "standDisplayScore",
                "ratingCount",
                "auditFlags",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "support_examples": support_examples[
            [
                "movieId",
                "displayLabel",
                "year",
                "suitabilityCategory",
                "publicBlockedTerms",
                "publicExclusionReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "excluded_examples": excluded_examples[
            [
                "movieId",
                "displayLabel",
                "year",
                "originalLanguage",
                "genres",
                "exclusionCategory",
                "exclusionReasons",
            ]
        ].rename(columns={"displayLabel": "displayTitle"}),
        "collaborative_summary": collaborative_signals["tables"]["collaborative_summary"],
        "rating_distribution": collaborative_signals["tables"]["rating_distribution"],
        "ratings_by_year": collaborative_signals["tables"]["ratings_by_year"],
        "ratings_per_user_buckets": collaborative_signals["tables"]["ratings_per_user_buckets"],
        "top_movies_by_filtered_ratings": collaborative_signals["tables"][
            "top_movies_by_filtered_ratings"
        ],
        "top_users_by_rating_count": collaborative_signals["tables"]["top_users_by_rating_count"],
}


def _write_summary_tables(tables: dict[str, pd.DataFrame]) -> None:
    for table_name, dataframe in tables.items():
        _write_csv(dataframe, OFFLINE_DATASET_AUDIT_TABLES_DIR / f"{table_name}.csv")


def _generate_static_charts(
    *,
    combined_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    collaborative_signals: dict[str, Any],
) -> dict[str, str]:
    del collaborative_signals

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
        "public_suitability_counts": "charts/public_suitability_counts.png",
        "public_languages": "charts/public_languages.png",
        "public_decades": "charts/public_decades.png",
        "public_genres": "charts/public_genres.png",
        "support_blocked_terms": "charts/support_blocked_terms.png",
        "stand_display_score_distribution": "charts/stand_display_score_distribution.png",
        "public_stand_score_by_suitability": "charts/public_stand_score_by_suitability.png",
        "public_stand_display_reasons": "charts/public_stand_display_reasons.png",
        "public_exclusion_reasons": "charts/public_exclusion_reasons.png",
        "low_stand_accessibility_languages": "charts/low_stand_accessibility_languages.png",
        "teen_sensitive_genres": "charts/teen_sensitive_genres.png",
        "family_only_simulation": "charts/family_only_simulation.png",
        "excluded_reasons": "charts/excluded_reasons.png",
        "rating_count_vs_stand_score": "charts/rating_count_vs_stand_score.png",
        "rating_distribution": "charts/rating_distribution.png",
        "ratings_per_user_buckets": "charts/ratings_per_user_buckets.png",
        "ratings_by_year": "charts/ratings_by_year.png",
        "top_movies_by_filtered_ratings": "charts/top_movies_by_filtered_ratings.png",
    }

    comparison_df = _with_partition_labels(tables["comparison_by_partition"])
    if comparison_df.empty:
        _save_empty_chart("Conteo por partición", OFFLINE_DATASET_AUDIT_CHARTS_DIR / "partition_counts.png")
    else:
        plt.figure(figsize=(10, 5.5))
        ax = sns.barplot(
            data=comparison_df,
            x="partitionLabel",
            y="movieCount",
            hue="partitionLabel",
            order=list(PARTITION_COLORS.keys()),
            hue_order=list(PARTITION_COLORS.keys()),
            palette=PARTITION_COLORS,
            legend=False,
        )
        _style_axes(
            ax,
            title="Películas analizadas por partición",
            xlabel="Partición",
            ylabel="Películas",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "partition_counts.png")

    suitability_df = _with_partition_labels(tables["suitability_by_partition"])
    if suitability_df.empty:
        _save_empty_chart(
            "Suitability por partición",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "suitability_by_partition.png",
        )
    else:
        pivot_df = suitability_df.pivot(
            index="suitabilityCategory",
            columns="partitionLabel",
            values="movieCount",
        ).fillna(0)
        ordered_columns = [label for label in PARTITION_COLORS if label in pivot_df.columns]
        pivot_df = pivot_df[ordered_columns]
        ax = pivot_df.plot(
            kind="bar",
            color=[PARTITION_COLORS[label] for label in ordered_columns],
            figsize=(12, 6),
        )
        _style_axes(
            ax,
            title="Distribución de suitabilityCategory por partición",
            xlabel="Suitability",
            ylabel="Películas",
        )
        ax.legend(title="Partición")
        plt.xticks(rotation=35, ha="right")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "suitability_by_partition.png")

    public_suitability_df = tables["public_suitability_counts"].copy()
    if public_suitability_df.empty:
        _save_empty_chart(
            "Suitability del catálogo público",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_suitability_counts.png",
        )
    else:
        plt.figure(figsize=(10, 5))
        ax = sns.barplot(
            data=public_suitability_df,
            x="suitabilityCategory",
            y="movieCount",
            color=SINBAD_BLUE,
        )
        _style_axes(
            ax,
            title="Distribución de suitabilityCategory en el catálogo público",
            xlabel="Suitability",
            ylabel="Películas",
        )
        plt.xticks(rotation=25, ha="right")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_suitability_counts.png")

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
        plt.figure(figsize=(12, 6))
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
        plt.figure(figsize=(12, 6))
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
        plt.figure(figsize=(12, 5.5))
        ax = sns.histplot(
            public_df["standDisplayScore"].dropna(),
            bins=22,
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

    score_by_suitability_df = public_df.dropna(
        subset=["standDisplayScore", "suitabilityCategory"]
    ).copy()
    if score_by_suitability_df.empty:
        _save_empty_chart(
            "standDisplayScore por suitability",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_stand_score_by_suitability.png",
        )
    else:
        plt.figure(figsize=(12, 5.5))
        ax = sns.boxplot(
            data=score_by_suitability_df,
            x="suitabilityCategory",
            y="standDisplayScore",
            color=SINBAD_GOLD,
        )
        _style_axes(
            ax,
            title="standDisplayScore por suitabilityCategory en catálogo público",
            xlabel="Suitability",
            ylabel="standDisplayScore",
        )
        plt.xticks(rotation=25, ha="right")
        _finalize_chart(
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_stand_score_by_suitability.png"
        )

    public_reason_df = tables["stand_display_reasons_public"].copy().head(15)
    if public_reason_df.empty:
        _save_empty_chart(
            "standDisplayReasons del catálogo público",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_stand_display_reasons.png",
        )
    else:
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(
            data=public_reason_df,
            x="movieCount",
            y="standDisplayReason",
            color=SINBAD_CYAN,
        )
        _style_axes(
            ax,
            title="standDisplayReasons más frecuentes en catálogo público",
            xlabel="Películas",
            ylabel="standDisplayReason",
        )
        _finalize_chart(
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_stand_display_reasons.png"
        )

    scatter_df = public_df.dropna(subset=["ratingCount", "standDisplayScore"]).copy()
    if scatter_df.empty:
        _save_empty_chart(
            "ratingCount vs standDisplayScore",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "rating_count_vs_stand_score.png",
        )
    else:
        plt.figure(figsize=(13.5, 6.5))
        ax = sns.scatterplot(
            data=scatter_df,
            x="ratingCount",
            y="standDisplayScore",
            hue="suitabilityCategory",
            palette="crest",
            alpha=0.75,
            s=58,
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

    public_exclusion_df = (
        tables["public_exclusion_reasons_by_partition"]
        .groupby("publicExclusionReason", dropna=False)["movieCount"]
        .sum()
        .reset_index()
        .sort_values(
            by=["movieCount", "publicExclusionReason"],
            ascending=[False, True],
            kind="mergesort",
        )
        .head(15)
    )
    if public_exclusion_df.empty:
        _save_empty_chart(
            "Razones de exclusión pública",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_exclusion_reasons.png",
        )
    else:
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(
            data=public_exclusion_df,
            x="movieCount",
            y="publicExclusionReason",
            color=SINBAD_RED,
        )
        _style_axes(
            ax,
            title="Razones de exclusión pública más frecuentes",
            xlabel="Películas",
            ylabel="publicExclusionReason",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "public_exclusion_reasons.png")

    excluded_reasons_df = tables["excluded_reasons"].copy().head(15)
    if excluded_reasons_df.empty:
        _save_empty_chart(
            "Razones de exclusión total",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "excluded_reasons.png",
        )
    else:
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(
            data=excluded_reasons_df,
            x="movieCount",
            y="exclusionReason",
            color=SINBAD_GOLD,
        )
        _style_axes(
            ax,
            title="Razones de exclusión total más frecuentes",
            xlabel="Películas",
            ylabel="exclusionReason",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "excluded_reasons.png")

    low_access_language_df = tables["low_stand_accessibility_by_language"].copy().head(15)
    if low_access_language_df.empty:
        _save_empty_chart(
            "Idiomas con baja accesibilidad de stand",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "low_stand_accessibility_languages.png",
        )
    else:
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(
            data=low_access_language_df,
            x="originalLanguage",
            y="movieCount",
            color=SINBAD_GOLD,
        )
        _style_axes(
            ax,
            title="Idiomas en casos de low_stand_accessibility",
            xlabel="Idioma original",
            ylabel="Películas",
        )
        plt.xticks(rotation=35, ha="right")
        _finalize_chart(
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "low_stand_accessibility_languages.png"
        )

    teen_sensitive_df = tables["teen_sensitive_genres"].copy().head(15)
    if teen_sensitive_df.empty:
        _save_empty_chart(
            "Géneros sensibles en públicas teen",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "teen_sensitive_genres.png",
        )
    else:
        plt.figure(figsize=(11, 5.5))
        ax = sns.barplot(
            data=teen_sensitive_df,
            x="genre",
            y="movieCount",
            color=SINBAD_RED,
        )
        _style_axes(
            ax,
            title="Géneros sensibles dentro de películas públicas teen",
            xlabel="Género sensible",
            ylabel="Películas",
        )
        plt.xticks(rotation=30, ha="right")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "teen_sensitive_genres.png")

    family_simulation_df = pd.DataFrame(
        [
            {"scope": "Catálogo público", "group": "family_friendly", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["familyFriendlyPublicMovies"])},
            {"scope": "Catálogo público", "group": "teen", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["teenPublicMovies"])},
            {"scope": "Top 100", "group": "family_friendly", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["top100FamilyFriendlyCount"])},
            {"scope": "Top 100", "group": "teen", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["top100TeenCount"])},
            {"scope": "Top 250", "group": "family_friendly", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["top250FamilyFriendlyCount"])},
            {"scope": "Top 250", "group": "teen", "movieCount": int(tables["family_only_simulation_summary"].iloc[0]["top250TeenCount"])},
        ]
    )
    if family_simulation_df.empty:
        _save_empty_chart(
            "Simulación family-only",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "family_only_simulation.png",
        )
    else:
        plt.figure(figsize=(11, 5.5))
        ax = sns.barplot(
            data=family_simulation_df,
            x="scope",
            y="movieCount",
            hue="group",
            palette=[SINBAD_BLUE, SINBAD_GOLD],
        )
        _style_axes(
            ax,
            title="Composición family_friendly y teen en catálogo público y tramos altos",
            xlabel="Tramo",
            ylabel="Películas",
        )
        ax.legend(title="Suitability")
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "family_only_simulation.png")

    rating_distribution_df = tables["rating_distribution"].copy()
    if rating_distribution_df.empty:
        _save_empty_chart(
            "Distribución de ratings",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "rating_distribution.png",
        )
    else:
        plt.figure(figsize=(11, 5))
        ax = sns.barplot(
            data=rating_distribution_df,
            x="ratingLabel",
            y="ratingCount",
            color=SINBAD_GREEN,
        )
        _style_axes(
            ax,
            title="Distribución de valores de rating",
            xlabel="Valor de rating",
            ylabel="Ratings",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "rating_distribution.png")

    user_buckets_df = tables["ratings_per_user_buckets"].copy()
    if user_buckets_df.empty:
        _save_empty_chart(
            "Ratings por usuario",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "ratings_per_user_buckets.png",
        )
    else:
        plt.figure(figsize=(11, 5))
        ax = sns.barplot(
            data=user_buckets_df,
            x="bucket",
            y="userCount",
            color=SINBAD_GOLD,
            order=USER_BUCKET_ORDER,
        )
        _style_axes(
            ax,
            title="Usuarios agrupados por número de ratings",
            xlabel="Bucket de ratings por usuario",
            ylabel="Usuarios",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "ratings_per_user_buckets.png")

    ratings_by_year_df = tables["ratings_by_year"].copy()
    if ratings_by_year_df.empty:
        _save_empty_chart(
            "Ratings por año",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "ratings_by_year.png",
        )
    else:
        plt.figure(figsize=(12, 5))
        ax = sns.lineplot(
            data=ratings_by_year_df,
            x="year",
            y="ratingCount",
            marker="o",
            color=SINBAD_BLUE,
        )
        _style_axes(
            ax,
            title="Ratings colaborativos por año",
            xlabel="Año",
            ylabel="Ratings",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "ratings_by_year.png")

    top_movies_df = tables["top_movies_by_filtered_ratings"].copy().head(15)
    if top_movies_df.empty:
        _save_empty_chart(
            "Top películas por filtered ratings",
            OFFLINE_DATASET_AUDIT_CHARTS_DIR / "top_movies_by_filtered_ratings.png",
        )
    else:
        plt.figure(figsize=(13, 6.5))
        ax = sns.barplot(
            data=top_movies_df,
            x="filteredRatingCount",
            y="displayLabel",
            color=SINBAD_CYAN,
        )
        _style_axes(
            ax,
            title="Top películas por filteredRatingCount",
            xlabel="filteredRatingCount",
            ylabel="Película",
        )
        _finalize_chart(OFFLINE_DATASET_AUDIT_CHARTS_DIR / "top_movies_by_filtered_ratings.png")

    return chart_paths


def _build_conclusions(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    suspicious_public_df: pd.DataFrame,
    collaborative_signals: dict[str, Any],
) -> list[str]:
    counts = combined_df["auditPartition"].value_counts()
    family_metrics = tables["family_only_simulation_summary"].iloc[0].to_dict()
    public_exclusion_reasons = (
        tables["public_exclusion_reasons_by_partition"]
        .groupby("publicExclusionReason", dropna=False)["movieCount"]
        .sum()
        .reset_index()
        .sort_values(
            by=["movieCount", "publicExclusionReason"],
            ascending=[False, True],
            kind="mergesort",
        )
    )
    top_public_exclusion_reason = (
        str(public_exclusion_reasons.iloc[0]["publicExclusionReason"])
        if not public_exclusion_reasons.empty
        else "sin razón dominante"
    )
    collaborative_ratings_manifest = int(manifest.get("counts", {}).get("collaborativeRatings", 0))
    density_percent = round(collaborative_signals["matrixDensity"] * 100, 4)
    low_accessibility_count = int(len(tables["low_stand_accessibility_movies"]))
    public_teen_sensitive_count = int(len(tables["public_teen_sensitive_movies"]))
    family_certified_teen_public_count = int(len(tables["public_family_certified_teen_movies"]))

    return [
        (
            "El balance general muestra "
            f"{int(counts.get('public', 0))} películas públicas, "
            f"{int(counts.get('collaborative_support', 0))} de soporte colaborativo y "
            f"{int(counts.get('excluded', 0))} excluidas."
        ),
        (
            "Dentro del catálogo público actual hay "
            f"{int(family_metrics['familyFriendlyPublicMovies'])} películas family_friendly y "
            f"{int(family_metrics['teenPublicMovies'])} películas teen."
        ),
        (
            "La revisión de accesibilidad de stand identifica "
            f"{low_accessibility_count} películas fuera de la partición pública con la razón "
            "`low_stand_accessibility`."
        ),
        (
            "Las películas públicas teen con géneros sensibles suman "
            f"{public_teen_sensitive_count} casos y "
            f"{family_certified_teen_public_count} de ellas incluyen la razón "
            "`stand_family_certified_teen_suitability`."
        ),
        (
            "En los primeros 100 títulos por standDisplayScore aparecen "
            f"{int(family_metrics['top100FamilyFriendlyCount'])} películas family_friendly y "
            f"{int(family_metrics['top100TeenCount'])} películas teen."
        ),
        (
            "La razón pública más frecuente en las particiones no públicas es "
            f"{top_public_exclusion_reason}."
        ),
        (
            "El dataset offline conserva "
            f"{_format_int(collaborative_signals['totalRatings'])} ratings procesados "
            f"frente a {_format_int(collaborative_ratings_manifest)} declarados en el manifest."
        ),
        (
            "La matriz usuario-película del núcleo colaborativo presenta "
            f"{density_percent}% de densidad, con una media de "
            f"{round(collaborative_signals['averageRatingsPerUser'], 2)} ratings por usuario."
        ),
        (
            "La muestra de revisión pública incluye "
            f"{len(suspicious_public_df)} películas con auditFlags no vacíos."
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
    collaborative_signals: dict[str, Any],
) -> str:
    public_df = combined_df[combined_df["auditPartition"] == "public"].copy()
    counts = combined_df["auditPartition"].value_counts()
    collaborative_ratings_manifest = int(manifest.get("counts", {}).get("collaborativeRatings", 0))
    family_metrics = tables["family_only_simulation_summary"].iloc[0]

    comparison_df = _with_partition_labels(tables["comparison_by_partition"])
    suitability_df = _with_partition_labels(tables["suitability_by_partition"])
    public_languages_df = tables["language_by_partition"].query("auditPartition == 'public'").head(10)
    public_decades_df = tables["decade_by_partition"].query("auditPartition == 'public'")
    public_genres_df = tables["genre_by_partition"].query("auditPartition == 'public'").head(12)
    public_suitability_df = tables["public_suitability_counts"].copy()
    public_reason_df = tables["stand_display_reasons_public"].copy().head(15)
    low_access_language_df = tables["low_stand_accessibility_by_language"].copy().head(15)
    teen_sensitive_df = tables["teen_sensitive_genres"].copy().head(15)
    excluded_reasons_df = tables["excluded_reasons"].copy().head(15)
    public_exclusion_df = (
        tables["public_exclusion_reasons_by_partition"]
        .groupby("publicExclusionReason", dropna=False)["movieCount"]
        .sum()
        .reset_index()
        .sort_values(
            by=["movieCount", "publicExclusionReason"],
            ascending=[False, True],
            kind="mergesort",
        )
        .head(15)
    )
    top_movies_chart_df = (
        tables["top_movies_by_filtered_ratings"]
        .head(15)
        .sort_values(by="filteredRatingCount", ascending=True, kind="mergesort")
    )
    family_only_chart_df = pd.DataFrame(
        [
            {
                "scope": "Catálogo público",
                "group": "family_friendly",
                "movieCount": int(family_metrics["familyFriendlyPublicMovies"]),
            },
            {
                "scope": "Catálogo público",
                "group": "teen",
                "movieCount": int(family_metrics["teenPublicMovies"]),
            },
            {
                "scope": "Top 100",
                "group": "family_friendly",
                "movieCount": int(family_metrics["top100FamilyFriendlyCount"]),
            },
            {
                "scope": "Top 100",
                "group": "teen",
                "movieCount": int(family_metrics["top100TeenCount"]),
            },
            {
                "scope": "Top 250",
                "group": "family_friendly",
                "movieCount": int(family_metrics["top250FamilyFriendlyCount"]),
            },
            {
                "scope": "Top 250",
                "group": "teen",
                "movieCount": int(family_metrics["top250TeenCount"]),
            },
        ]
    )
    public_family_teen_chart_df = pd.DataFrame(
        [
            {
                "group": "family_friendly",
                "movieCount": int(family_metrics["familyFriendlyPublicMovies"]),
            },
            {"group": "teen", "movieCount": int(family_metrics["teenPublicMovies"])},
        ]
    )

    partition_fig = px.bar(
        comparison_df,
        x="partitionLabel",
        y="movieCount",
        color="partitionLabel",
        category_orders={"partitionLabel": list(PARTITION_COLORS.keys())},
        color_discrete_map=PARTITION_COLORS,
        title="Películas por partición",
    )
    _style_plotly_figure(partition_fig)

    suitability_fig = px.bar(
        suitability_df,
        x="suitabilityCategory",
        y="movieCount",
        color="partitionLabel",
        barmode="group",
        category_orders={"partitionLabel": list(PARTITION_COLORS.keys())},
        color_discrete_map=PARTITION_COLORS,
        title="Suitability por partición",
    )
    _style_plotly_figure(suitability_fig)

    public_suitability_fig = px.bar(
        public_suitability_df,
        x="suitabilityCategory",
        y="movieCount",
        color="suitabilityCategory",
        title="Suitability del catálogo público",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_CYAN, SINBAD_RED],
    )
    _style_plotly_figure(public_suitability_fig)

    public_languages_fig = px.bar(
        public_languages_df,
        x="originalLanguage",
        y="movieCount",
        color_discrete_sequence=[SINBAD_BLUE],
        title="Idiomas del catálogo público",
    )
    _style_plotly_figure(public_languages_fig)

    public_decades_fig = px.bar(
        public_decades_df,
        x="decade",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Décadas del catálogo público",
    )
    _style_plotly_figure(public_decades_fig)

    public_genres_fig = px.bar(
        public_genres_df,
        x="genre",
        y="movieCount",
        color_discrete_sequence=[SINBAD_CYAN],
        title="Géneros del catálogo público",
    )
    _style_plotly_figure(public_genres_fig)

    public_family_teen_fig = px.bar(
        public_family_teen_chart_df,
        x="group",
        y="movieCount",
        color="group",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD],
        title="Películas públicas family_friendly y teen",
    )
    _style_plotly_figure(public_family_teen_fig)

    score_dist_fig = px.histogram(
        public_df.dropna(subset=["standDisplayScore"]),
        x="standDisplayScore",
        nbins=24,
        title="Distribución de standDisplayScore",
        color_discrete_sequence=[SINBAD_BLUE],
    )
    _style_plotly_figure(score_dist_fig)

    stand_score_by_suitability_fig = px.box(
        public_df.dropna(subset=["standDisplayScore", "suitabilityCategory"]),
        x="suitabilityCategory",
        y="standDisplayScore",
        color="suitabilityCategory",
        title="standDisplayScore por suitability",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_CYAN, SINBAD_RED],
    )
    _style_plotly_figure(stand_score_by_suitability_fig)

    scatter_fig = px.scatter(
        public_df.dropna(subset=["ratingCount", "standDisplayScore"]),
        x="ratingCount",
        y="standDisplayScore",
        color="suitabilityCategory",
        hover_data=["displayLabel", "year", "tmdbPopularity"],
        log_x=True,
        title="ratingCount vs standDisplayScore",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_CYAN, SINBAD_RED],
    )
    _style_plotly_figure(scatter_fig)

    teen_sensitive_fig = px.bar(
        teen_sensitive_df,
        x="genre",
        y="movieCount",
        color_discrete_sequence=[SINBAD_RED],
        title="Géneros sensibles en películas públicas teen",
    )
    _style_plotly_figure(teen_sensitive_fig)

    low_accessibility_fig = px.bar(
        low_access_language_df,
        x="originalLanguage",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Idiomas en low_stand_accessibility",
    )
    _style_plotly_figure(low_accessibility_fig)

    stand_reasons_fig = px.bar(
        public_reason_df.sort_values(by="movieCount", ascending=True, kind="mergesort"),
        x="movieCount",
        y="standDisplayReason",
        orientation="h",
        color_discrete_sequence=[SINBAD_CYAN],
        title="standDisplayReasons del catálogo público",
    )
    _style_plotly_figure(stand_reasons_fig)

    support_blocked_terms_fig = px.bar(
        tables["blocked_terms_by_partition"]
        .query("auditPartition == 'collaborative_support'")
        .head(12),
        x="blockedTerm",
        y="movieCount",
        color_discrete_sequence=[SINBAD_RED],
        title="Blocked terms del soporte colaborativo",
    )
    _style_plotly_figure(support_blocked_terms_fig)

    rating_distribution_fig = px.bar(
        tables["rating_distribution"],
        x="ratingLabel",
        y="ratingCount",
        color_discrete_sequence=[SINBAD_GREEN],
        title="Distribución de valores de rating",
    )
    _style_plotly_figure(rating_distribution_fig)

    user_buckets_fig = px.bar(
        tables["ratings_per_user_buckets"],
        x="bucket",
        y="userCount",
        category_orders={"bucket": USER_BUCKET_ORDER},
        color_discrete_sequence=[SINBAD_GOLD],
        title="Usuarios agrupados por número de ratings",
    )
    _style_plotly_figure(user_buckets_fig)

    ratings_by_year_fig = px.line(
        tables["ratings_by_year"],
        x="year",
        y="ratingCount",
        markers=True,
        title="Ratings por año en el núcleo colaborativo",
    )
    ratings_by_year_fig.update_traces(line_color=SINBAD_BLUE)
    _style_plotly_figure(ratings_by_year_fig)

    top_movies_fig = px.bar(
        top_movies_chart_df,
        x="filteredRatingCount",
        y="displayLabel",
        orientation="h",
        color_discrete_sequence=[SINBAD_CYAN],
        title="Top películas por filteredRatingCount",
    )
    _style_plotly_figure(top_movies_fig)

    excluded_reasons_fig = px.bar(
        excluded_reasons_df,
        x="exclusionReason",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Razones de exclusión total",
    )
    _style_plotly_figure(excluded_reasons_fig)

    public_exclusion_fig = px.bar(
        public_exclusion_df,
        x="publicExclusionReason",
        y="movieCount",
        color_discrete_sequence=[SINBAD_RED],
        title="Razones de exclusión pública",
    )
    _style_plotly_figure(public_exclusion_fig)

    family_only_fig = px.bar(
        family_only_chart_df,
        x="scope",
        y="movieCount",
        color="group",
        barmode="group",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD],
        title="Simulación family-only y mezcla actual",
    )
    _style_plotly_figure(family_only_fig)

    plotly_config = {"responsive": True, "displaylogo": False}

    def plot_html(fig: Any) -> str:
        return fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config)

    headline_kpis = [
        ("Películas públicas", _format_int(int(counts.get("public", 0)))),
        (
            "Soporte colaborativo",
            _format_int(int(counts.get("collaborative_support", 0))),
        ),
        ("Películas excluidas", _format_int(int(counts.get("excluded", 0)))),
        ("Ratings colaborativos", _format_int(collaborative_ratings_manifest)),
        (
            "Públicas family_friendly",
            _format_int(int(family_metrics["familyFriendlyPublicMovies"])),
        ),
        ("Públicas teen", _format_int(int(family_metrics["teenPublicMovies"]))),
        (
            "low_stand_accessibility",
            _format_int(int(len(tables["low_stand_accessibility_movies"]))),
        ),
        ("Públicas revisables", _format_int(int(len(suspicious_public_df)))),
    ]
    collaborative_kpis = [
        ("Usuarios únicos", _format_int(collaborative_signals["uniqueUsers"])),
        ("Películas con ratings", _format_int(collaborative_signals["uniqueRatedMovies"])),
        ("Densidad matriz", f"{collaborative_signals['matrixDensity'] * 100:.4f}%"),
        (
            "Media ratings/usuario",
            f"{collaborative_signals['averageRatingsPerUser']:.2f}",
        ),
        (
            "Mediana ratings/usuario",
            f"{collaborative_signals['medianRatingsPerUser']:.2f}",
        ),
        (
            "Media ratings/película",
            f"{collaborative_signals['averageRatingsPerMovie']:.2f}",
        ),
        ("Mediana ratings/película", f"{collaborative_signals['medianRatingsPerMovie']:.2f}"),
    ]

    chart_gallery = "".join(
        [
            _chart_card_html("Conteo por partición", chart_paths["partition_counts"]),
            _chart_card_html("Suitability por partición", chart_paths["suitability_by_partition"]),
            _chart_card_html(
                "Suitability del catálogo público",
                chart_paths["public_suitability_counts"],
            ),
            _chart_card_html("Idiomas públicos", chart_paths["public_languages"]),
            _chart_card_html("Décadas públicas", chart_paths["public_decades"]),
            _chart_card_html("Géneros públicos", chart_paths["public_genres"]),
            _chart_card_html(
                "Distribución de standDisplayScore",
                chart_paths["stand_display_score_distribution"],
            ),
            _chart_card_html(
                "standDisplayScore por suitability",
                chart_paths["public_stand_score_by_suitability"],
            ),
            _chart_card_html(
                "standDisplayReasons públicas",
                chart_paths["public_stand_display_reasons"],
            ),
            _chart_card_html(
                "Razones de exclusión pública",
                chart_paths["public_exclusion_reasons"],
            ),
            _chart_card_html(
                "Razones de exclusión total",
                chart_paths["excluded_reasons"],
            ),
            _chart_card_html(
                "Idiomas en low_stand_accessibility",
                chart_paths["low_stand_accessibility_languages"],
            ),
            _chart_card_html(
                "Géneros sensibles en públicas teen",
                chart_paths["teen_sensitive_genres"],
            ),
            _chart_card_html("Blocked terms de soporte", chart_paths["support_blocked_terms"]),
            _chart_card_html(
                "ratingCount vs standDisplayScore",
                chart_paths["rating_count_vs_stand_score"],
            ),
            _chart_card_html(
                "Simulación family-only",
                chart_paths["family_only_simulation"],
            ),
            _chart_card_html("Distribución de ratings", chart_paths["rating_distribution"]),
            _chart_card_html(
                "Ratings por usuario",
                chart_paths["ratings_per_user_buckets"],
            ),
            _chart_card_html("Ratings por año", chart_paths["ratings_by_year"]),
            _chart_card_html(
                "Top películas por filtered ratings",
                chart_paths["top_movies_by_filtered_ratings"],
            ),
        ]
    )

    def interactive_card(title: str, html: str, explanation_key: str, wide: bool = False) -> str:
        return (
            f'<div class="subtle-card{" wide-card" if wide else ""}">'
            f"<h3>{escape(title)}</h3>"
            f"{_explanation_html(explanation_key)}"
            f'<div class="plot">{html}</div>'
            "</div>"
        )

    def table_card(title: str, dataframe: pd.DataFrame, explanation_key: str, *, limit: int, wide: bool = False) -> str:
        return (
            f'<div class="subtle-card{" wide-card" if wide else ""}">'
            f"<h3>{escape(title)}</h3>"
            f"{_explanation_html(explanation_key)}"
            f'<p class="table-note">Muestra {min(limit, len(dataframe))} filas. El CSV completo está disponible en <code>audit/tables/</code>.</p>'
            f'<div class="table-wrap">{_render_html_table(dataframe, limit=limit)}</div>'
            "</div>"
        )

    headline_kpis_html = "".join(
        [
            f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
            for label, value in headline_kpis
        ]
    )
    executive_nav_html = "".join(
        [
            '<a href="#resumen">Resumen</a>',
            '<a href="#dataset">Dataset</a>',
            '<a href="#catalogo-publico">Catálogo público</a>',
            '<a href="#teen">Teen</a>',
            '<a href="#accesibilidad">Accesibilidad</a>',
            '<a href="#stand-score">Stand score</a>',
            '<a href="#colaborativo">Colaborativo</a>',
            '<a href="#excluidas">Excluidas</a>',
            '<a href="#family-only">Family-only</a>',
        ]
    )
    collaborative_kpis_html = "".join(
        [
            f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
            for label, value in collaborative_kpis
        ]
    )
    conclusions_html = "".join([f"<li>{escape(line)}</li>" for line in conclusions])
    plotly_js_bundle = get_plotlyjs()

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
      --green: {SINBAD_GREEN};
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
      width: 100%;
      max-width: none;
      margin: 0;
      padding: 28px clamp(18px, 2.2vw, 42px) 44px;
    }}
    .hero {{
      width: 100%;
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
      max-width: 1280px;
      font-size: 17px;
      line-height: 1.6;
    }}
    .section-panel {{
      width: 100%;
      margin-top: 34px;
      padding: 26px 0 0;
      border-top: 1px solid rgba(77, 163, 255, 0.12);
    }}
    .section-shell {{
      padding: 24px;
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(16, 26, 47, 0.9), rgba(12, 20, 36, 0.86));
      box-shadow: var(--shadow);
    }}
    .section-panel h2 {{
      margin: 0 0 14px;
      font-size: 28px;
    }}
    .section-panel p {{
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
    .row {{
      display: grid;
      gap: 18px;
      width: 100%;
    }}
    .row-1 {{
      grid-template-columns: minmax(0, 1fr);
    }}
    .row-2 {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .row-3 {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .row-4 {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .section-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .section-nav a {{
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(11, 19, 35, 0.92);
      border: 1px solid rgba(77, 163, 255, 0.2);
      color: var(--text);
      text-decoration: none;
      font-size: 14px;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .subtle-card {{
      background: rgba(10, 18, 33, 0.6);
      border: 1px solid rgba(77, 163, 255, 0.08);
      border-radius: 18px;
      padding: 16px;
      width: 100%;
      min-width: 0;
    }}
    .wide-card {{
      grid-column: 1 / -1;
    }}
    .full-width {{
      grid-column: 1 / -1;
    }}
    .plot {{
      overflow: hidden;
      border-radius: 16px;
      background: rgba(8, 17, 31, 0.85);
      border: 1px solid #1d2d4e;
    }}
    .plot,
    .plot > div,
    .plot .plotly-graph-div,
    .js-plotly-plot {{
      width: 100% !important;
      max-width: 100% !important;
    }}
    .explanation {{
      margin: 0 0 14px;
      padding: 12px 15px;
      border-radius: 16px;
      border: 1px solid rgba(77, 163, 255, 0.08);
      background: rgba(8, 17, 31, 0.44);
    }}
    .explanation p {{
      margin: 0;
      color: var(--text);
      line-height: 1.6;
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
    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
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
      border: 1px solid rgba(77, 163, 255, 0.08);
      background: rgba(8, 17, 31, 0.72);
    }}
    .table-wrap table thead th {{
      position: sticky;
      top: 0;
      background: #0f1a2d;
      z-index: 1;
    }}
    .table-note {{
      margin: 0 0 10px;
      font-size: 13px;
      color: var(--muted);
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
    @media (max-width: 1200px) {{
      .row-3,
      .row-4 {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .chart-grid {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}
    @media (max-width: 900px) {{
      .row-2,
        .row-3,
      .row-4 {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .wrap {{
        padding: 16px 12px 28px;
      }}
      .section,
      .hero {{
        padding: 18px;
      }}
    }}
  </style>
  <script>
{plotly_js_bundle}
  </script>
</head>
<body>
  <div class="wrap">
    <section class="hero" id="resumen">
      <div class="eyebrow">SINBAD Offline Audit</div>
      <h1>Auditoría del dataset offline</h1>
      <p class="subtitle">
        Este panel analiza el dataset portable offline del recomendador y resume cómo se distribuyen
        las películas públicas, el soporte colaborativo y las exclusiones, sin tocar heurísticas ni lógica de recomendación.
      </p>
      <div class="grid kpis">{headline_kpis_html}</div>
      <nav class="section-nav">{executive_nav_html}</nav>
    </section>

    <section class="section-panel">
      <div class="section-shell">
      <h2>A. Resumen ejecutivo</h2>
      {_explanation_html("section_executive_summary")}
      <div class="row row-2">
        <div class="subtle-card">
          <h3>Observaciones automáticas</h3>
          {_explanation_html("section_conclusions")}
          <ul class="conclusions">{conclusions_html}</ul>
        </div>
        <div class="subtle-card">
          <h3>Métricas colaborativas</h3>
          <div class="metric-grid">{collaborative_kpis_html}</div>
        </div>
      </div>
      </div>
    </section>

    <section class="section-panel" id="dataset">
      <div class="section-shell">
      <h2>B. Descripción general del dataset</h2>
      {_explanation_html("section_dataset_overview")}
      <div class="chart-grid">
        {interactive_card("Películas por partición", plot_html(partition_fig), "partition_chart")}
        {interactive_card("Suitability por partición", plot_html(suitability_fig), "suitability_partition_chart")}
      </div>
      <div class="row row-2" style="margin-top: 18px;">
        <div class="subtle-card">
          <h3>Idiomas por partición</h3>
          {_explanation_html("language_partition_table")}
          <div class="table-wrap">{_render_html_table(tables["language_by_partition"], limit=18)}</div>
        </div>
        <div class="subtle-card">
          <h3>Géneros por partición</h3>
          {_explanation_html("genre_partition_table")}
          <div class="table-wrap">{_render_html_table(tables["genre_by_partition"], limit=18)}</div>
        </div>
      </div>
      <div class="row row-2" style="margin-top: 18px;">
        <div class="subtle-card">
          <h3>Resumen de ratings y usuarios</h3>
          <div class="table-wrap">{_render_html_table(tables["collaborative_summary"], limit=12)}</div>
        </div>
        <div class="subtle-card">
          <h3>Décadas por partición</h3>
          <div class="table-wrap">{_render_html_table(tables["decade_by_partition"], limit=18)}</div>
        </div>
      </div>
      </div>
    </section>

    <section class="section-panel" id="catalogo-publico">
      <div class="section-shell">
      <h2>C. Catálogo público</h2>
      {_explanation_html("section_public_quality")}
      <div class="chart-grid">
        {interactive_card("Suitability del catálogo público", plot_html(public_suitability_fig), "public_suitability_chart")}
        {interactive_card("Películas públicas family_friendly y teen", plot_html(public_family_teen_fig), "public_suitability_chart")}
        {interactive_card("Idiomas del catálogo público", plot_html(public_languages_fig), "public_languages_chart")}
        {interactive_card("Décadas del catálogo público", plot_html(public_decades_fig), "public_decades_chart")}
        {interactive_card("Géneros del catálogo público", plot_html(public_genres_fig), "public_genres_chart")}
        {interactive_card("Distribución de standDisplayScore", plot_html(score_dist_fig), "public_score_distribution_chart")}
        {interactive_card("standDisplayScore por suitability", plot_html(stand_score_by_suitability_fig), "public_stand_score_by_suitability_chart")}
        {interactive_card("ratingCount vs standDisplayScore", plot_html(scatter_fig), "public_scatter_chart", wide=True)}
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        {table_card("Top 15 públicas por standDisplayScore", tables["public_top_by_stand_score"], "public_top_table", limit=15, wide=True)}
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        {table_card("Bottom 15 públicas por standDisplayScore", tables["public_bottom_by_stand_score"], "public_bottom_table", limit=15, wide=True)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="teen">
      <div class="section-shell">
      <h2>D. Control de películas teen</h2>
      {_explanation_html("section_teen_sensitive_control")}
      <div class="metric-grid">
        <div class="kpi"><div class="label">Públicas teen</div><div class="value">{_format_int(int(family_metrics["teenPublicMovies"]))}</div></div>
        <div class="kpi"><div class="label">Teen con géneros sensibles</div><div class="value">{_format_int(int(len(tables["public_teen_sensitive_movies"])))}</div></div>
        <div class="kpi"><div class="label">Teen con señal familiar certificada</div><div class="value">{_format_int(int(len(tables["public_family_certified_teen_movies"])))}</div></div>
      </div>
      <div class="chart-grid" style="margin-top: 18px;">
        {interactive_card("Géneros sensibles en películas públicas teen", plot_html(teen_sensitive_fig), "teen_sensitive_chart")}
        {table_card("Películas públicas teen con géneros sensibles", tables["public_teen_sensitive_movies"], "teen_sensitive_table", limit=15)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="accesibilidad">
      <div class="section-shell">
      <h2>E. Accesibilidad del stand</h2>
      {_explanation_html("section_low_stand_accessibility")}
      <div class="metric-grid">
        <div class="kpi"><div class="label">Casos low_stand_accessibility</div><div class="value">{_format_int(int(len(tables["low_stand_accessibility_movies"])))}</div></div>
        <div class="kpi"><div class="label">Idiomas comunes protegidos</div><div class="value">{escape(", ".join(sorted(PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES)))}</div></div>
        <div class="kpi"><div class="label">Géneros protegidos</div><div class="value">{escape(", ".join(sorted(PUBLIC_STAND_ACCESSIBILITY_PROTECTED_GENRES)))}</div></div>
      </div>
      <div class="chart-grid" style="margin-top: 18px;">
        {interactive_card("Idiomas en low_stand_accessibility", plot_html(low_accessibility_fig), "low_accessibility_chart")}
        {interactive_card("Razones de exclusión pública", plot_html(public_exclusion_fig), "low_accessibility_chart")}
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        {table_card("Ejemplos con baja accesibilidad de stand", tables["low_stand_accessibility_examples"], "low_accessibility_examples_table", limit=15, wide=True)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="stand-score">
      <div class="section-shell">
      <h2>F. Señales de standDisplayScore</h2>
      {_explanation_html("section_stand_reasons")}
      <div class="chart-grid" style="margin-top: 18px;">
        {interactive_card("standDisplayReasons del catálogo público", plot_html(stand_reasons_fig), "stand_reasons_chart")}
        {table_card("Películas públicas con señal family-certified teen", tables["public_family_certified_teen_movies"], "family_certified_teen_table", limit=15)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="colaborativo">
      <div class="section-shell">
      <h2>G. Soporte colaborativo</h2>
      {_explanation_html("section_support")}
      <div class="chart-grid">
        {interactive_card("Blocked terms del soporte colaborativo", plot_html(support_blocked_terms_fig), "support_blocked_terms_chart")}
        {interactive_card("Distribución de valores de rating", plot_html(rating_distribution_fig), "collaborative_rating_distribution_chart")}
        {interactive_card("Usuarios agrupados por número de ratings", plot_html(user_buckets_fig), "collaborative_user_buckets_chart")}
        {interactive_card("Ratings por año en el núcleo colaborativo", plot_html(ratings_by_year_fig), "collaborative_year_chart")}
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        {interactive_card("Top películas por filteredRatingCount", plot_html(top_movies_fig), "collaborative_top_movies_chart", wide=True)}
      </div>
      <div class="row row-2" style="margin-top: 18px;">
        {table_card("Top películas por filtered ratings", tables["top_movies_by_filtered_ratings"], "collaborative_top_movies_chart", limit=15)}
        {table_card("Ejemplos de soporte colaborativo", tables["support_examples"], "support_examples_table", limit=15)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="excluidas">
      <div class="section-shell">
      <h2>H. Excluidas</h2>
      {_explanation_html("section_excluded")}
      <div class="chart-grid">
        {interactive_card("Razones de exclusión total", plot_html(excluded_reasons_fig), "excluded_reasons_chart")}
        {table_card("Muestra de películas excluidas", tables["excluded_examples"], "excluded_examples_table", limit=15)}
      </div>
      </div>
    </section>

    <section class="section-panel" id="family-only">
      <div class="section-shell">
      <h2>I. Simulación family-only</h2>
      {_explanation_html("section_family_only_simulation")}
      <div class="metric-grid">
        <div class="kpi"><div class="label">Catálogo público actual</div><div class="value">{_format_int(int(family_metrics["currentPublicMovies"]))}</div></div>
        <div class="kpi"><div class="label">Family-friendly públicas</div><div class="value">{_format_int(int(family_metrics["familyFriendlyPublicMovies"]))}</div></div>
        <div class="kpi"><div class="label">Teen públicas</div><div class="value">{_format_int(int(family_metrics["teenPublicMovies"]))}</div></div>
        <div class="kpi"><div class="label">% family-friendly</div><div class="value">{float(family_metrics["publicShareFamilyFriendlyPercent"]):.2f}%</div></div>
        <div class="kpi"><div class="label">% teen</div><div class="value">{float(family_metrics["publicShareTeenPercent"]):.2f}%</div></div>
      </div>
      <div class="row row-2" style="margin-top: 18px;">
        {interactive_card("Comparación actual y simulación family-only", plot_html(family_only_fig), "family_only_chart")}
        <div class="subtle-card">
          <h3>Archivos de revisión disponibles</h3>
          {_explanation_html("section_tables")}
          <div class="table-wrap">{_render_html_table(tables["suspicious_public_movies_sample"], limit=15)}</div>
          <p class="table-note">Los CSV completos siguen disponibles en <code>audit/tables/</code> y <code>audit/detailed/</code>.</p>
        </div>
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        <div class="subtle-card wide-card">
          <h3>Gráficos estáticos generados</h3>
          {_explanation_html("section_static")}
          <div class="gallery-grid">{chart_gallery}</div>
        </div>
      </div>
      </div>
    </section>
    <p class="muted" style="margin-top:16px;">
      Archivos adicionales: <a href="summary.md">summary.md</a>,
      <a href="summary.json">summary.json</a>,
      <a href="tables/">tables/</a> y <a href="detailed/">detailed/</a>.
    </p>
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
    collaborative_signals: dict[str, Any],
) -> str:
    counts = combined_df["auditPartition"].value_counts()
    family_metrics = tables["family_only_simulation_summary"].iloc[0]

    chart_list = "\n".join([f"- `{path}`" for path in chart_paths.values()])
    table_list = "\n".join(
        [
            "- `tables/comparison_by_partition.csv`",
            "- `tables/suitability_by_partition.csv`",
            "- `tables/public_suitability_counts.csv`",
            "- `tables/language_by_partition.csv`",
            "- `tables/decade_by_partition.csv`",
            "- `tables/genre_by_partition.csv`",
            "- `tables/blocked_terms_by_partition.csv`",
            "- `tables/stand_display_reasons_by_partition.csv`",
            "- `tables/stand_display_reasons_public.csv`",
            "- `tables/public_exclusion_reasons_by_partition.csv`",
            "- `tables/excluded_reasons.csv`",
            "- `tables/low_stand_accessibility_movies.csv`",
            "- `tables/low_stand_accessibility_by_language.csv`",
            "- `tables/low_stand_accessibility_by_suitability.csv`",
            "- `tables/low_stand_accessibility_examples.csv`",
            "- `tables/public_top_movies.csv`",
            "- `tables/public_low_score_movies.csv`",
            "- `tables/public_top_by_stand_score.csv`",
            "- `tables/public_bottom_by_stand_score.csv`",
            "- `tables/public_teen_sensitive_movies.csv`",
            "- `tables/public_family_certified_teen_movies.csv`",
            "- `tables/family_only_simulation_summary.csv`",
            "- `tables/suspicious_public_movies_sample.csv`",
            "- `tables/support_examples.csv`",
            "- `tables/excluded_examples.csv`",
            "- `tables/collaborative_summary.csv`",
            "- `tables/rating_distribution.csv`",
            "- `tables/ratings_by_year.csv`",
            "- `tables/ratings_per_user_buckets.csv`",
            "- `tables/top_movies_by_filtered_ratings.csv`",
            "- `tables/top_users_by_rating_count.csv`",
        ]
    )

    return f"""# Auditoría del dataset offline

## Balance del dataset

- Películas públicas: {_format_int(int(counts.get("public", 0)))}
- Películas de soporte colaborativo: {_format_int(int(counts.get("collaborative_support", 0)))}
- Películas excluidas: {_format_int(int(counts.get("excluded", 0)))}
- Total analizado: {_format_int(int(len(combined_df)))}
- Ratings colaborativos del manifest: {_format_int(int(manifest.get("counts", {}).get("collaborativeRatings", 0)))}
- Películas públicas revisables: {_format_int(int(len(suspicious_public_df)))}

## Catálogo público

- Películas family_friendly públicas: {_format_int(int(family_metrics["familyFriendlyPublicMovies"]))}
- Películas teen públicas: {_format_int(int(family_metrics["teenPublicMovies"]))}
- Top 100 públicas: {_format_int(int(family_metrics["top100FamilyFriendlyCount"]))} family_friendly y {_format_int(int(family_metrics["top100TeenCount"]))} teen
- Top 250 públicas: {_format_int(int(family_metrics["top250FamilyFriendlyCount"]))} family_friendly y {_format_int(int(family_metrics["top250TeenCount"]))} teen
- Qué muestra: suitability, idiomas, décadas, géneros y señales de standDisplayScore del catálogo visible.
- Qué ayuda a inspeccionar: si el catálogo público mezcla reconocimiento, accesibilidad y señales de stand de forma consistente.

![Suitability público]({chart_paths["public_suitability_counts"]})
![Idiomas públicos]({chart_paths["public_languages"]})
![Décadas públicas]({chart_paths["public_decades"]})
![Géneros públicos]({chart_paths["public_genres"]})
![Distribución de standDisplayScore]({chart_paths["stand_display_score_distribution"]})
![ratingCount vs standDisplayScore]({chart_paths["rating_count_vs_stand_score"]})
![standDisplayScore por suitability]({chart_paths["public_stand_score_by_suitability"]})

## Control teen/sensitive

- Películas públicas teen con géneros sensibles: {_format_int(int(len(tables["public_teen_sensitive_movies"])))}
- Películas públicas con `stand_family_certified_teen_suitability`: {_format_int(int(len(tables["public_family_certified_teen_movies"])))}
- Qué muestra: géneros sensibles presentes en películas públicas teen y razones de stand asociadas.
- Qué ayuda a inspeccionar: si las películas teen con señales sensibles siguen estando controladas en la parte visible.

![Géneros sensibles en públicas teen]({chart_paths["teen_sensitive_genres"]})
![standDisplayReasons públicas]({chart_paths["public_stand_display_reasons"]})

## Accesibilidad del stand

- Casos con `low_stand_accessibility`: {_format_int(int(len(tables["low_stand_accessibility_movies"])))}
- Qué muestra: películas que salen del catálogo público por baja accesibilidad de stand pero pueden seguir en soporte colaborativo.
- Qué ayuda a inspeccionar: cómo afectan idioma original, ratingCount, popularidad TMDB y standDisplayScore a ese filtro.

![Idiomas en low_stand_accessibility]({chart_paths["low_stand_accessibility_languages"]})

## Salud colaborativa

- Total ratings: {_format_int(collaborative_signals["totalRatings"])}
- Usuarios únicos: {_format_int(collaborative_signals["uniqueUsers"])}
- Películas con ratings: {_format_int(collaborative_signals["uniqueRatedMovies"])}
- Densidad de matriz: {collaborative_signals["matrixDensity"] * 100:.4f}%
- Media ratings/usuario: {collaborative_signals["averageRatingsPerUser"]:.2f}
- Mediana ratings/usuario: {collaborative_signals["medianRatingsPerUser"]:.2f}
- Media ratings/película: {collaborative_signals["averageRatingsPerMovie"]:.2f}
- Mediana ratings/película: {collaborative_signals["medianRatingsPerMovie"]:.2f}
- Qué muestra: distribución de ratings, fuerza de perfiles y concentración de señal en el núcleo colaborativo.
- Qué ayuda a inspeccionar: si el soporte colaborativo sigue siendo útil para perfilar usuarios aunque parte del catálogo no sea público.

![Distribución de ratings]({chart_paths["rating_distribution"]})
![Ratings por usuario]({chart_paths["ratings_per_user_buckets"]})
![Ratings por año]({chart_paths["ratings_by_year"]})
![Top películas por filtered ratings]({chart_paths["top_movies_by_filtered_ratings"]})

## Tablas de revisión disponibles

- `public_top_by_stand_score.csv` y `public_bottom_by_stand_score.csv`: extremos del ranking público visible.
- `public_teen_sensitive_movies.csv`: películas públicas teen con géneros sensibles y sus razones.
- `public_family_certified_teen_movies.csv`: casos con señal `stand_family_certified_teen_suitability`.
- `low_stand_accessibility_examples.csv`: ejemplos que salen del público por baja accesibilidad de stand.
- `support_examples.csv` y `excluded_examples.csv`: muestras manuales de soporte colaborativo y exclusión total.
- `family_only_simulation_summary.csv`: simulación del catálogo público si solo se mostrasen películas family_friendly.

## Gráficos generados

{chart_list}

## Tablas generadas

{table_list}

## Observaciones automáticas

{chr(10).join([f"- {line}" for line in conclusions])}
"""


def _build_summary_json(
    *,
    manifest: dict[str, Any],
    combined_df: pd.DataFrame,
    suspicious_public_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    collaborative_signals: dict[str, Any],
) -> dict[str, Any]:
    counts_by_partition = {
        partition: int(count)
        for partition, count in combined_df["auditPartition"].value_counts().items()
    }
    family_only_simulation = tables["family_only_simulation_summary"].iloc[0].to_dict()

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
        "suitabilityCounts": _records_from_dataframe(tables["suitability_by_partition"], limit=100),
        "publicSuitabilityCounts": _records_from_dataframe(
            tables["public_suitability_counts"],
            limit=20,
        ),
        "languageCounts": _records_from_dataframe(tables["language_by_partition"], limit=100),
        "decadeCounts": _records_from_dataframe(tables["decade_by_partition"], limit=100),
        "genreCounts": _records_from_dataframe(tables["genre_by_partition"], limit=120),
        "topBlockedTerms": _records_from_dataframe(
            tables["blocked_terms_by_partition"].query("auditPartition == 'collaborative_support'"),
            limit=20,
        ),
        "topPublicExclusionReasons": _records_from_dataframe(
            tables["public_exclusion_reasons_by_partition"],
            limit=20,
        ),
        "excludedReasonCounts": _records_from_dataframe(tables["excluded_reasons"], limit=20),
        "suspiciousPublicMovieCount": int(len(suspicious_public_df)),
        "lowStandAccessibilityCount": int(len(tables["low_stand_accessibility_movies"])),
        "publicTeenSensitiveCount": int(len(tables["public_teen_sensitive_movies"])),
        "familyCertifiedTeenPublicCount": int(
            len(tables["public_family_certified_teen_movies"])
        ),
        "familyOnlySimulation": {
            key: _json_safe_value(value)
            for key, value in family_only_simulation.items()
        },
        "topPublicMovieSamples": _records_from_dataframe(tables["public_top_movies"], limit=10),
        "topPublicMovies": _records_from_dataframe(tables["public_top_by_stand_score"], limit=10),
        "bottomPublicMovieSamples": _records_from_dataframe(
            tables["public_low_score_movies"],
            limit=10,
        ),
        "lowStandAccessibilityExamples": _records_from_dataframe(
            tables["low_stand_accessibility_examples"],
            limit=10,
        ),
        "collaborativeSignals": {
            "totalRatings": int(collaborative_signals["totalRatings"]),
            "uniqueUsers": int(collaborative_signals["uniqueUsers"]),
            "uniqueRatedMovies": int(collaborative_signals["uniqueRatedMovies"]),
            "matrixDensity": float(collaborative_signals["matrixDensity"]),
            "averageRatingsPerUser": float(collaborative_signals["averageRatingsPerUser"]),
            "medianRatingsPerUser": float(collaborative_signals["medianRatingsPerUser"]),
            "maxRatingsPerUser": int(collaborative_signals["maxRatingsPerUser"]),
            "averageRatingsPerMovie": float(collaborative_signals["averageRatingsPerMovie"]),
            "medianRatingsPerMovie": float(collaborative_signals["medianRatingsPerMovie"]),
            "ratingDistribution": _records_from_dataframe(tables["rating_distribution"], limit=20),
            "ratingsByYear": _records_from_dataframe(tables["ratings_by_year"], limit=100),
            "userRatingBuckets": _records_from_dataframe(
                tables["ratings_per_user_buckets"],
                limit=20,
            ),
        },
    }


def _compute_public_audit_flags(public_df: pd.DataFrame) -> pd.Series:
    low_rating_count = (
        public_df["ratingCount"].fillna(0) < PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_RATING_COUNT
    )
    low_tmdb_popularity = (
        public_df["tmdbPopularity"].fillna(0) < PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_TMDB_POPULARITY
    )
    low_stand_display_score = (
        public_df["standDisplayScore"].fillna(0)
        < PUBLIC_MIN_STAND_DISPLAY_SCORE
    )
    uncommon_original_language = (
        ~public_df["originalLanguage"].isin(PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES)
    ) & (low_rating_count | low_tmdb_popularity | low_stand_display_score)
    teen_with_sensitive_genres = (
        (public_df["suitabilityCategory"] == "teen")
        & _series_intersects_pipe_values(public_df["genres"], SENSITIVE_GENRES)
    )
    family_certified_teen = _series_contains_pipe_token(
        public_df["standDisplayReasons"],
        "stand_family_certified_teen_suitability",
    )
    low_public_recognition = low_rating_count & low_tmdb_popularity & low_stand_display_score

    flag_columns = {
        "low_rating_count": low_rating_count,
        "low_tmdb_popularity": low_tmdb_popularity,
        "low_stand_display_score": low_stand_display_score,
        "uncommon_original_language": uncommon_original_language,
        "teen_with_sensitive_genres": teen_with_sensitive_genres,
        "family_certified_teen": family_certified_teen,
        "low_public_recognition": low_public_recognition,
        "missing_display_overview": public_df["displayOverview"] == "",
        "missing_display_title": public_df["displayTitle"] == "",
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
            by=(
                ["auditPartition", "movieCount", value_column]
                if include_partition
                else ["movieCount", value_column]
            ),
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


def _with_partition_labels(dataframe: pd.DataFrame) -> pd.DataFrame:
    display_df = dataframe.copy()
    display_df["partitionLabel"] = display_df["auditPartition"].map(PARTITION_LABELS)
    display_df["partitionLabel"] = pd.Categorical(
        display_df["partitionLabel"],
        categories=list(PARTITION_COLORS.keys()),
        ordered=True,
    )
    return display_df.sort_values("partitionLabel", kind="mergesort")


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
    plt.text(
        0.5,
        0.5,
        "Sin datos disponibles",
        ha="center",
        va="center",
        fontsize=16,
        color="#eef5ff",
    )
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


def _explanation_html(key: str) -> str:
    text = EXPLANATIONS[key]
    return f'<div class="explanation"><p>{escape(text)}</p></div>'


def _coalesce_text(primary: pd.Series | None, fallback: pd.Series | None) -> pd.Series:
    primary_series = _normalize_text_series(
        primary if primary is not None else pd.Series(dtype="object")
    )
    if fallback is None:
        return primary_series
    fallback_series = _normalize_text_series(fallback)
    return primary_series.where(primary_series != "", fallback_series)


def _coalesce_numeric(primary: pd.Series | None, fallback: pd.Series | None) -> pd.Series:
    primary_series = (
        pd.to_numeric(primary, errors="coerce")
        if primary is not None
        else pd.Series(dtype="float64")
    )
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
    unique_titles: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in unique_titles:
            unique_titles.append(normalized)
        if len(unique_titles) >= 8:
            break
    return " | ".join(unique_titles)


def _bucket_user_count(count: int) -> str:
    if count <= 4:
        return "1-4"
    if count <= 9:
        return "5-9"
    if count <= 24:
        return "10-24"
    if count <= 49:
        return "25-49"
    if count <= 99:
        return "50-99"
    if count <= 249:
        return "100-249"
    return "250+"


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
    if isinstance(value, (list, dict)):
        return value
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


if __name__ == "__main__":
    main()
