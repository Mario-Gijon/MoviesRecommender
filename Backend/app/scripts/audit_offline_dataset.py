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


LOW_STAND_DISPLAY_SCORE = 0.25
LOW_RATING_COUNT = 250
LOW_TMDB_POPULARITY = 1.0
OLD_PUBLIC_YEAR = 2000
COMMON_PUBLIC_LANGUAGES = {"en", "es", "ja", "fr", "it", "de"}
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

EXPLANATIONS = {
    "section_partitions": "Resume el reparto entre catálogo público, soporte colaborativo y películas excluidas. Que el soporte colaborativo sea más grande es normal: ayuda a construir perfiles aunque no sea visible en la demo.",
    "partition_chart": "Compara cuántas películas hay en cada partición del dataset offline y permite ver de un vistazo qué parte se dedica a la experiencia visible y qué parte queda como soporte.",
    "section_suitability": "Permite comprobar si el catálogo público se concentra en películas family_friendly y teen, dejando el contenido sensible sobre todo fuera de la parte visible.",
    "suitability_chart": "Si adult_or_sensitive aparece con mucho peso en la parte pública, la separación entre catálogo visible y núcleo de soporte merece revisión.",
    "section_public": "Analiza idioma, década, géneros y señales de atractivo visual del catálogo público para detectar sesgos o títulos débiles en la experiencia del stand.",
    "public_languages_chart": "Ayuda a ver si el catálogo público está demasiado concentrado en pocos idiomas o si entran títulos poco alineados con el público objetivo.",
    "public_decades_chart": "Muestra qué tan reciente o histórica es la selección pública. Una mezcla demasiado antigua puede indicar falta de recencia cultural.",
    "public_genres_chart": "Sirve para comprobar si la oferta visible está equilibrada o si depende demasiado de unos pocos géneros dominantes.",
    "public_score_distribution_chart": "Muestra cómo se reparte la puntuación usada para ordenar visualmente el catálogo público. Muchas películas en valores bajos sugieren una vitrina menos atractiva.",
    "public_scatter_chart": "Relaciona cobertura en MovieLens y atractivo visual del stand. Los títulos con muchos ratings y score alto suelen ser candidatos más sólidos.",
    "section_support": "Explica por qué muchas películas útiles colaborativamente no llegan al catálogo público y ayuda a revisar bloqueos sin alterar el papel del soporte.",
    "support_blocked_terms_chart": "Si pocos blocked terms concentran muchos casos, describen con bastante claridad el tipo de contenido que se está apartando del catálogo visible.",
    "section_excluded": "Resume las causas de exclusión total. Si predominan fallos técnicos o de enriquecimiento, el problema está en el pipeline más que en la lógica de recomendación.",
    "excluded_reasons_chart": "Distingue exclusiones por política de contenido frente a exclusiones por cobertura, metadatos incompletos o errores de enriquecimiento.",
    "section_collaborative": "Estas métricas describen el núcleo colaborativo completo: películas públicas más películas de soporte colaborativo. Las excluidas no forman parte de `collaborative_ratings.csv`.",
    "collaborative_rating_distribution_chart": "Muestra si los usuarios tienden a puntuar demasiado alto, demasiado bajo o de forma muy concentrada, algo útil para entender sesgos del núcleo colaborativo.",
    "collaborative_user_buckets_chart": "Agrupa usuarios por número de ratings emitidos. Más peso en los tramos altos implica perfiles más fuertes para alimentar el recomendador.",
    "collaborative_year_chart": "Cuenta ratings por año en el núcleo colaborativo y ayuda a ver si la actividad está repartida o concentrada en pocas oleadas temporales.",
    "collaborative_top_movies_chart": "Muestra qué películas del núcleo colaborativo concentran más ratings filtrados. Si unas pocas dominan demasiado, la señal puede quedar muy sesgada.",
    "section_tables": "Muestra solo muestras pequeñas y accionables. Las tablas completas siguen disponibles en CSV dentro de `audit/tables/` y `audit/detailed/`.",
    "section_static": "Expone las versiones PNG de los gráficos para README e informes, de modo que el análisis pueda reutilizarse sin depender del dashboard interactivo.",
    "section_conclusions": "Resume hallazgos automáticos derivados de los datos. No son reglas de producto: son señales rápidas para orientar revisión de pipeline y heurísticas futuras.",
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
        "support_examples": support_df[
            [
                "movieId",
                "displayLabel",
                "year",
                "publicBlockedTerms",
                "publicExclusionReasons",
            ]
        ].head(100).rename(columns={"displayLabel": "displayTitle"}),
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
        if table_name == "support_examples":
            continue
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
        "public_languages": "charts/public_languages.png",
        "public_decades": "charts/public_decades.png",
        "public_genres": "charts/public_genres.png",
        "support_blocked_terms": "charts/support_blocked_terms.png",
        "stand_display_score_distribution": "charts/stand_display_score_distribution.png",
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

    public_languages = tables["language_by_partition"]
    public_languages = public_languages[public_languages["auditPartition"] == "public"]
    top_language = (
        str(public_languages.iloc[0]["originalLanguage"])
        if not public_languages.empty
        else "unknown"
    )

    public_decades = tables["decade_by_partition"]
    public_decades = public_decades[public_decades["auditPartition"] == "public"]
    top_decade = str(public_decades.iloc[0]["decade"]) if not public_decades.empty else "unknown"

    blocked_terms = tables["blocked_terms_by_partition"]
    blocked_terms = blocked_terms[blocked_terms["auditPartition"] == "collaborative_support"]
    top_blocked_term = (
        str(blocked_terms.iloc[0]["blockedTerm"])
        if not blocked_terms.empty
        else "sin señal dominante"
    )

    excluded_reasons = tables["excluded_reasons"]
    top_excluded_reason = (
        str(excluded_reasons.iloc[0]["exclusionReason"])
        if not excluded_reasons.empty
        else "sin razón dominante"
    )

    collaborative_ratings_manifest = int(manifest.get("counts", {}).get("collaborativeRatings", 0))
    density_percent = round(collaborative_signals["matrixDensity"] * 100, 4)

    return [
        (
            "El balance general muestra "
            f"{int(counts.get('public', 0))} películas públicas, "
            f"{int(counts.get('collaborative_support', 0))} de soporte colaborativo y "
            f"{int(counts.get('excluded', 0))} excluidas."
        ),
        (
            "El dataset offline conserva una señal colaborativa grande: "
            f"{_format_int(collaborative_signals['totalRatings'])} ratings procesados "
            f"frente a {_format_int(collaborative_ratings_manifest)} declarados en el manifest."
        ),
        (
            "La matriz usuario-película sigue siendo muy dispersa "
            f"({density_percent}% de densidad), lo que es esperable en recomendación colaborativa."
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
        (
            "Los perfiles colaborativos tienen una media de "
            f"{round(collaborative_signals['averageRatingsPerUser'], 2)} ratings por usuario y una mediana de "
            f"{round(collaborative_signals['medianRatingsPerUser'], 2)}."
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
    comparison_df = _with_partition_labels(tables["comparison_by_partition"])
    suitability_df = _with_partition_labels(tables["suitability_by_partition"])
    support_examples = tables["support_examples"].copy()
    support_examples = support_examples[
        (support_examples["publicBlockedTerms"].fillna("") != "")
        | (support_examples["publicExclusionReasons"].fillna("") != "")
    ].head(12)

    counts = combined_df["auditPartition"].value_counts()
    collaborative_ratings_manifest = int(manifest.get("counts", {}).get("collaborativeRatings", 0))

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
        title="Categorías de suitability",
    )
    _style_plotly_figure(suitability_fig)

    public_languages_fig = px.bar(
        tables["language_by_partition"].query("auditPartition == 'public'").head(10),
        x="originalLanguage",
        y="movieCount",
        color_discrete_sequence=[SINBAD_BLUE],
        title="Idiomas del catálogo público",
    )
    _style_plotly_figure(public_languages_fig)

    public_decades_fig = px.bar(
        tables["decade_by_partition"].query("auditPartition == 'public'"),
        x="decade",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Décadas del catálogo público",
    )
    _style_plotly_figure(public_decades_fig)

    public_genres_fig = px.bar(
        tables["genre_by_partition"].query("auditPartition == 'public'").head(12),
        x="genre",
        y="movieCount",
        color_discrete_sequence=[SINBAD_CYAN],
        title="Géneros del catálogo público",
    )
    _style_plotly_figure(public_genres_fig)

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
        hover_data=["displayLabel", "year", "tmdbPopularity"],
        log_x=True,
        title="ratingCount vs standDisplayScore",
        color_discrete_sequence=[SINBAD_BLUE, SINBAD_GOLD, SINBAD_CYAN, SINBAD_RED],
    )
    _style_plotly_figure(scatter_fig)

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

    excluded_reasons_fig = px.bar(
        tables["excluded_reasons"].head(12),
        x="exclusionReason",
        y="movieCount",
        color_discrete_sequence=[SINBAD_GOLD],
        title="Razones de exclusión más frecuentes",
    )
    _style_plotly_figure(excluded_reasons_fig)

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
        tables["top_movies_by_filtered_ratings"].head(15).sort_values(
            by="filteredRatingCount",
            ascending=True,
        ),
        x="filteredRatingCount",
        y="displayLabel",
        orientation="h",
        color_discrete_sequence=[SINBAD_CYAN],
        title="Top películas por número de ratings filtrados",
    )
    _style_plotly_figure(top_movies_fig)

    plotly_config = {"responsive": True, "displaylogo": False}
    plot_blocks = [
        partition_fig.to_html(
            full_html=False,
            include_plotlyjs="inline",
            config=plotly_config,
        ),
        suitability_fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config),
        public_languages_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        public_decades_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        public_genres_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        score_dist_fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config),
        scatter_fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config),
        support_blocked_terms_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        excluded_reasons_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        rating_distribution_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        user_buckets_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        ratings_by_year_fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config=plotly_config,
        ),
        top_movies_fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config),
    ]

    headline_kpis = [
        ("Películas públicas", _format_int(int(counts.get("public", 0)))),
        (
            "Soporte colaborativo",
            _format_int(int(counts.get("collaborative_support", 0))),
        ),
        ("Películas excluidas", _format_int(int(counts.get("excluded", 0)))),
        ("Total analizado", _format_int(int(len(combined_df)))),
        ("Ratings colaborativos", _format_int(collaborative_ratings_manifest)),
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
        (
            "Mediana ratings/película",
            f"{collaborative_signals['medianRatingsPerMovie']:.2f}",
        ),
    ]

    chart_gallery = "".join(
        [
            _chart_card_html("Conteo por partición", chart_paths["partition_counts"]),
            _chart_card_html("Suitability por partición", chart_paths["suitability_by_partition"]),
            _chart_card_html("Idiomas públicos", chart_paths["public_languages"]),
            _chart_card_html("Décadas públicas", chart_paths["public_decades"]),
            _chart_card_html("Géneros públicos", chart_paths["public_genres"]),
            _chart_card_html("Blocked terms de soporte", chart_paths["support_blocked_terms"]),
            _chart_card_html(
                "Distribución de standDisplayScore",
                chart_paths["stand_display_score_distribution"],
            ),
            _chart_card_html(
                "ratingCount vs standDisplayScore",
                chart_paths["rating_count_vs_stand_score"],
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

    headline_kpis_html = "".join(
        [
            f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
            for label, value in headline_kpis
        ]
    )
    collaborative_kpis_html = "".join(
        [
            f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
            for label, value in collaborative_kpis
        ]
    )
    conclusions_html = "".join([f"<li>{escape(line)}</li>" for line in conclusions])

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
    .section {{
      width: 100%;
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
    .chart-card {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      width: 100%;
      min-width: 0;
    }}
    .card {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      width: 100%;
      min-width: 0;
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
      border: 1px solid #223252;
      background: rgba(8, 17, 31, 0.74);
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
    @media (max-width: 1200px) {{
      .row-3,
      .row-4 {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
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
      <div class="grid kpis">{headline_kpis_html}</div>
    </section>

    <section class="section">
      <h2>A. Particiones principales</h2>
      {_explanation_html("section_partitions")}
      <div class="row row-1">
        <div class="chart-card full-width">
          {_explanation_html("partition_chart")}
          <div class="plot">{plot_blocks[0]}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>B. Comparación de suitability</h2>
      {_explanation_html("section_suitability")}
      <div class="row row-1">
        <div class="chart-card full-width">
          {_explanation_html("suitability_chart")}
          <div class="plot">{plot_blocks[1]}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>C. Catálogo público</h2>
      {_explanation_html("section_public")}
      <div class="row row-2">
        <div class="chart-card">
          {_explanation_html("public_languages_chart")}
          <div class="plot">{plot_blocks[2]}</div>
        </div>
        <div class="chart-card">
          {_explanation_html("public_decades_chart")}
          <div class="plot">{plot_blocks[3]}</div>
        </div>
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        <div class="chart-card full-width">
          {_explanation_html("public_genres_chart")}
          <div class="plot">{plot_blocks[4]}</div>
        </div>
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        <div class="chart-card full-width">
          {_explanation_html("public_score_distribution_chart")}
          <div class="plot">{plot_blocks[5]}</div>
        </div>
      </div>
      <div class="row row-1" style="margin-top: 18px;">
        <div class="chart-card full-width">
          {_explanation_html("public_scatter_chart")}
          <div class="plot">{plot_blocks[6]}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>D. Soporte colaborativo</h2>
      {_explanation_html("section_support")}
      <div class="row row-2">
        <div class="chart-card">
          {_explanation_html("support_blocked_terms_chart")}
          <div class="plot">{plot_blocks[7]}</div>
        </div>
        <div class="chart-card">
          <div class="table-wrap">{_render_html_table(support_examples, limit=12)}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>E. Películas excluidas</h2>
      {_explanation_html("section_excluded")}
      <div class="row row-1">
        <div class="chart-card full-width">
          {_explanation_html("excluded_reasons_chart")}
          <div class="plot">{plot_blocks[8]}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>I. Señales colaborativas</h2>
      {_explanation_html("section_collaborative")}
      <div class="grid kpis">{collaborative_kpis_html}</div>
      <div class="row row-2" style="margin-top: 18px;">
        <div class="chart-card">
          {_explanation_html("collaborative_rating_distribution_chart")}
          <div class="plot">{plot_blocks[9]}</div>
        </div>
        <div class="chart-card">
          {_explanation_html("collaborative_user_buckets_chart")}
          <div class="plot">{plot_blocks[10]}</div>
        </div>
      </div>
      <div class="row row-2" style="margin-top: 18px;">
        <div class="chart-card">
          {_explanation_html("collaborative_year_chart")}
          <div class="plot">{plot_blocks[11]}</div>
        </div>
        <div class="chart-card">
          {_explanation_html("collaborative_top_movies_chart")}
          <div class="plot">{plot_blocks[12]}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>F. Tablas de revisión</h2>
      {_explanation_html("section_tables")}
      <div class="row row-3">
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
      {_explanation_html("section_static")}
      <div class="gallery-grid">{chart_gallery}</div>
    </section>

    <section class="section">
      <h2>H. Conclusiones automáticas</h2>
      {_explanation_html("section_conclusions")}
      <ul class="conclusions">{conclusions_html}</ul>
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
    collaborative_signals: dict[str, Any],
) -> str:
    counts = combined_df["auditPartition"].value_counts()
    blocked_terms = tables["blocked_terms_by_partition"]
    blocked_terms = blocked_terms[blocked_terms["auditPartition"] == "collaborative_support"].head(10)
    excluded_reasons = tables["excluded_reasons"].head(10)
    top_movies = tables["top_movies_by_filtered_ratings"].head(10)

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
            "- `tables/collaborative_summary.csv`",
            "- `tables/rating_distribution.csv`",
            "- `tables/ratings_by_year.csv`",
            "- `tables/ratings_per_user_buckets.csv`",
            "- `tables/top_movies_by_filtered_ratings.csv`",
            "- `tables/top_users_by_rating_count.csv`",
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

- Qué muestra: idioma, década, géneros y señales de score del catálogo visible.
- Cómo interpretarlo: ayuda a detectar sesgos de idioma, exceso de títulos antiguos o demasiados títulos con señal visual baja.

![Conteo por partición]({chart_paths["partition_counts"]})
![Idiomas públicos]({chart_paths["public_languages"]})
![Décadas públicas]({chart_paths["public_decades"]})
![Géneros públicos]({chart_paths["public_genres"]})
![Distribución de standDisplayScore]({chart_paths["stand_display_score_distribution"]})
![ratingCount vs standDisplayScore]({chart_paths["rating_count_vs_stand_score"]})

## Soporte colaborativo

- Qué muestra: por qué muchas películas útiles para perfilar usuarios no llegan al catálogo público.
- Cómo interpretarlo: los blocked terms y razones de exclusión pública orientan mejoras futuras de heurística sin tocar la lógica actual.

Top blocked terms:
{_markdown_records(blocked_terms, ["blockedTerm", "movieCount", "exampleTitles"])}

## Películas excluidas

- Qué muestra: razones de exclusión total del dataset visible y de soporte.
- Cómo interpretarlo: si dominan fallos técnicos o de enriquecimiento, el problema es de pipeline y no de recomendación.

Top exclusion reasons:
{_markdown_records(excluded_reasons, ["exclusionReason", "movieCount", "exampleTitles"])}

## Señales colaborativas

- Total ratings: {_format_int(collaborative_signals["totalRatings"])}
- Usuarios únicos: {_format_int(collaborative_signals["uniqueUsers"])}
- Películas con ratings: {_format_int(collaborative_signals["uniqueRatedMovies"])}
- Densidad de matriz: {collaborative_signals["matrixDensity"] * 100:.4f}%
- Media ratings/usuario: {collaborative_signals["averageRatingsPerUser"]:.2f}
- Mediana ratings/usuario: {collaborative_signals["medianRatingsPerUser"]:.2f}
- Máximo ratings/usuario: {_format_int(collaborative_signals["maxRatingsPerUser"])}
- Media ratings/película: {collaborative_signals["averageRatingsPerMovie"]:.2f}
- Mediana ratings/película: {collaborative_signals["medianRatingsPerMovie"]:.2f}

- El núcleo colaborativo está formado por las películas públicas y las películas de soporte colaborativo.
- Las películas excluidas no forman parte de `collaborative_ratings.csv`.
- Qué muestra: fuerza de perfiles, sesgo de valores de rating y dispersión de la matriz usuario-película.
- Cómo interpretarlo: una matriz muy dispersa es normal, pero perfiles demasiado débiles o una distribución sesgada pueden limitar el valor colaborativo.

![Distribución de ratings]({chart_paths["rating_distribution"]})
![Ratings por usuario]({chart_paths["ratings_per_user_buckets"]})
![Ratings por año]({chart_paths["ratings_by_year"]})
![Top películas por filtered ratings]({chart_paths["top_movies_by_filtered_ratings"]})

Top películas por filtered ratings:
{_markdown_records(top_movies, ["displayLabel", "filteredRatingCount", "datasetRoleLabel"])}

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
    collaborative_signals: dict[str, Any],
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
        "suitabilityCounts": _records_from_dataframe(tables["suitability_by_partition"], limit=100),
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
        "topPublicMovieSamples": _records_from_dataframe(tables["public_top_movies"], limit=10),
        "bottomPublicMovieSamples": _records_from_dataframe(
            tables["public_low_score_movies"],
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
