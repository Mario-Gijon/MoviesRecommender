"""Repartition an exported offline catalogue without rerunning MovieLens stages."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.catalog import collaborative_sort_key, public_sort_key
from .export_offline_dataset_from_movielens_32m import (
    PUBLIC_MOVIE_COLUMNS,
    SUPPORT_MOVIE_COLUMNS,
)


POLICIES = {
    "family_only": {"family_friendly"},
    "family_and_teen": {"family_friendly", "teen"},
    "all_classified": {"family_friendly", "teen", "adult_or_sensitive"},
}
CATALOG_COLUMNS = SUPPORT_MOVIE_COLUMNS + [
    "basePublicEligible",
    "basePublicExclusionReasons",
    "audiencePolicyExclusionReason",
]
AUDIENCE_REASONS = {
    "adult_or_sensitive",
    "unknown_suitability",
    "family_only_excludes_teen",
    "audience_policy_excludes_category",
}


class OfflineDatasetReconfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconfigurationSummary:
    dataset_dir: Path
    current_policy: str
    new_policy: str
    current_public_movies: int
    new_public_movies: int
    current_support_movies: int
    new_support_movies: int
    total_movies: int
    moved_to_support: int


def preview(dataset_dir: Path, policy: str) -> ReconfigurationSummary:
    canonical, current_public, current_support, manifest = _load_catalogue(dataset_dir)
    public_rows, support_rows = _partition(canonical, policy, _public_min_runtime(manifest))
    return ReconfigurationSummary(
        dataset_dir=dataset_dir,
        current_policy=str(manifest.get("publicAudiencePolicy") or "family_and_teen"),
        new_policy=policy,
        current_public_movies=len(current_public), new_public_movies=len(public_rows),
        current_support_movies=len(current_support), new_support_movies=len(support_rows),
        total_movies=len(canonical),
        moved_to_support=len({row["movieId"] for row in current_public} - {row["movieId"] for row in public_rows}),
    )


def reconfigure(dataset_dir: Path, policy: str, *, regenerate_audit: Callable[[], None] | None = None) -> ReconfigurationSummary:
    canonical, current_public, current_support, manifest = _load_catalogue(dataset_dir)
    current_policy = str(manifest.get("publicAudiencePolicy") or "family_and_teen")
    public_rows, support_rows = _partition(canonical, policy, _public_min_runtime(manifest))
    _validate_partition(canonical, public_rows, support_rows, policy)
    manifest = dict(manifest)
    counts = dict(manifest.get("counts") or {})
    counts.update(publicMovies=len(public_rows), collaborativeSupportMovies=len(support_rows))
    manifest["counts"] = counts
    manifest["publicAudiencePolicy"] = policy
    manifest["reconfiguredAt"] = _utc_timestamp()
    files = dict(manifest.get("files") or {})
    files["catalogMovies"] = "csv/catalog_movies.csv"
    manifest["files"] = files
    _atomic_replace(
        dataset_dir,
        {
            "csv/catalog_movies.csv": (CATALOG_COLUMNS, canonical),
            "csv/public_movies.csv": (PUBLIC_MOVIE_COLUMNS, public_rows),
            "csv/collaborative_support_movies.csv": (SUPPORT_MOVIE_COLUMNS, support_rows),
            "manifest.json": json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        },
    )
    if regenerate_audit:
        regenerate_audit()
    return ReconfigurationSummary(dataset_dir, current_policy, policy, len(current_public), len(public_rows), len(current_support), len(support_rows), len(canonical), len({r["movieId"] for r in current_public} - {r["movieId"] for r in public_rows}))


def _load_catalogue(dataset_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict]:
    csv_dir = dataset_dir / "csv"
    required = [dataset_dir / "manifest.json", csv_dir / "public_movies.csv", csv_dir / "collaborative_support_movies.csv", csv_dir / "excluded_movies.csv", csv_dir / "movie_ratings_summary.csv", csv_dir / "collaborative_ratings.csv"]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise OfflineDatasetReconfigurationError("Offline dataset is incomplete; required files are missing or empty: " + ", ".join(missing))
    try:
        manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineDatasetReconfigurationError("Offline dataset manifest is unreadable.") from exc
    public = _read_csv(csv_dir / "public_movies.csv", PUBLIC_MOVIE_COLUMNS)
    support = _read_csv(csv_dir / "collaborative_support_movies.csv", SUPPORT_MOVIE_COLUMNS)
    catalog_path = csv_dir / "catalog_movies.csv"
    canonical = _read_csv(catalog_path, CATALOG_COLUMNS) if catalog_path.exists() else _migrate_legacy(public, support)
    _validate_unique(canonical, "canonical catalogue")
    return canonical, public, support, manifest


def _read_csv(path: Path, required_columns: list[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None or not set(required_columns).issubset(reader.fieldnames):
                raise OfflineDatasetReconfigurationError(f"Offline dataset is incompatible: {path.name} is missing required CSV columns.")
            rows = [{column: (row.get(column) or "") for column in required_columns} for row in reader]
    except OSError as exc:
        raise OfflineDatasetReconfigurationError(f"Could not read {path}.") from exc
    _validate_unique(rows, path.name)
    return rows


def _migrate_legacy(public: list[dict[str, str]], support: list[dict[str, str]]) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in public + support:
        movie_id = row.get("movieId", "")
        if not movie_id:
            raise OfflineDatasetReconfigurationError("Offline dataset is incompatible: a catalogue row has no movieId.")
        if movie_id in by_id:
            raise OfflineDatasetReconfigurationError(f"Offline dataset is incompatible: conflicting duplicate movieId {movie_id}.")
        base_reasons = _split(row.get("publicExclusionReasons"))
        non_audience_reasons = [reason for reason in base_reasons if reason not in AUDIENCE_REASONS]
        # Public rows are the authoritative proof of base eligibility in legacy exports.
        base_eligible = row in public or not non_audience_reasons
        canonical = {column: row.get(column, "") for column in SUPPORT_MOVIE_COLUMNS}
        canonical["basePublicEligible"] = "true" if base_eligible else "false"
        canonical["basePublicExclusionReasons"] = _join(non_audience_reasons)
        canonical["audiencePolicyExclusionReason"] = ""
        by_id[movie_id] = canonical
    return list(by_id.values())


def _partition(canonical: list[dict[str, str]], policy: str, public_min_runtime: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if policy not in POLICIES:
        raise OfflineDatasetReconfigurationError(f"Unsupported public audience policy: {policy}.")
    public: list[dict[str, str]] = []
    support: list[dict[str, str]] = []
    for row in canonical:
        policy_reasons = _catalogue_policy_reasons(row, public_min_runtime)
        base_reasons = _split(row.get("basePublicExclusionReasons"))
        for reason in policy_reasons:
            if reason not in base_reasons:
                base_reasons.append(reason)
        row["basePublicExclusionReasons"] = _join(base_reasons)
        eligible = row.get("basePublicEligible") == "true" and not policy_reasons
        allowed = row.get("suitabilityCategory") in POLICIES[policy]
        if eligible and allowed:
            row["audiencePolicyExclusionReason"] = ""
            public.append({key: row.get(key, "") for key in PUBLIC_MOVIE_COLUMNS})
            continue
        row["audiencePolicyExclusionReason"] = (
            "audience_policy_excludes_category" if not allowed else ""
        )
        support_row = {key: row.get(key, "") for key in SUPPORT_MOVIE_COLUMNS}
        reasons = base_reasons
        if row["audiencePolicyExclusionReason"]:
            reasons.append("audience_policy_excludes_category")
        support_row["publicExclusionReasons"] = _join(reasons)
        support.append(support_row)
    public.sort(key=_public_row_sort_key)
    support.sort(key=_support_row_sort_key)
    return public, support


def _validate_partition(canonical: list[dict[str, str]], public: list[dict[str, str]], support: list[dict[str, str]], policy: str) -> None:
    _validate_unique(public, "public partition")
    _validate_unique(support, "support partition")
    public_ids, support_ids = {r["movieId"] for r in public}, {r["movieId"] for r in support}
    if public_ids & support_ids or public_ids | support_ids != {r["movieId"] for r in canonical}:
        raise OfflineDatasetReconfigurationError("Generated catalogue partition is inconsistent.")
    for row in public:
        if row["suitabilityCategory"] not in POLICIES[policy]:
            raise OfflineDatasetReconfigurationError("Generated public catalogue contains a disallowed suitability category.")


def _atomic_replace(dataset_dir: Path, contents: dict[str, object]) -> None:
    staged: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix="offline-reconfigure-", dir=dataset_dir) as temporary:
        temporary_dir = Path(temporary)
        for relative, content in contents.items():
            target = dataset_dir / relative
            staged_path = temporary_dir / relative
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, tuple):
                fields, rows = content
                with staged_path.open("w", encoding="utf-8", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=fields)
                    writer.writeheader(); writer.writerows(rows)
            else:
                staged_path.write_text(str(content), encoding="utf-8")
            staged.append((staged_path, target))
        backups: list[tuple[Path, Path]] = []
        try:
            for staged_path, target in staged:
                backup = temporary_dir / (target.name + ".backup")
                if target.exists(): os.replace(target, backup); backups.append((backup, target))
                os.replace(staged_path, target)
        except OSError as exc:
            for backup, target in reversed(backups):
                if backup.exists(): os.replace(backup, target)
            raise OfflineDatasetReconfigurationError("Could not safely replace offline dataset files.") from exc


def _validate_unique(rows: list[dict[str, str]], label: str) -> None:
    ids = [row.get("movieId", "") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise OfflineDatasetReconfigurationError(f"Offline dataset is incompatible: {label} has missing or duplicate movieId values.")


def _split(value: str | None) -> list[str]: return [part for part in (value or "").split("|") if part]
def _public_min_runtime(manifest: dict) -> int:
    try: return int((manifest.get("publicCataloguePolicy") or {}).get("publicMinRuntime", 60))
    except (TypeError, ValueError): return 60
def _catalogue_policy_reasons(row: dict[str, str], public_min_runtime: int) -> list[str]:
    genres = {value.strip().casefold() for value in _split(row.get("genres"))}
    reasons = ["documentary"] if "documentary" in genres else []
    try: runtime = float(row.get("runtime") or "")
    except ValueError: runtime = None
    if runtime is not None and runtime < public_min_runtime: reasons.append("short_runtime")
    return reasons
def _join(values: list[str]) -> str: return "|".join(dict.fromkeys(values))
def _public_row_sort_key(row: dict[str, str]) -> tuple:
    item = dict(row); item["tmdb"] = {"popularity": row.get("tmdbPopularity")}
    return public_sort_key(item)
def _support_row_sort_key(row: dict[str, str]) -> tuple: return collaborative_sort_key(row)
def _utc_timestamp() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
