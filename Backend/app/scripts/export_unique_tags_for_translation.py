import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


LIST_SEPARATOR = "|"
EXPORT_PART_SIZE = 800
BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPORT_DIR = BACKEND_DIR / "tmp" / "tag_translation_exports"
SUMMARY_PATH = EXPORT_DIR / "tag_translation_export_summary.json"
EXPORT_FILENAME_TEMPLATE = "tags_to_translate_part_{part_number:03d}.csv"
TAG_LIKE_COLUMNS = [
    "keywords",
    "userTags",
    "publicBlockedTerms",
    "standDisplayReasons",
    "publicExclusionReasons",
    "suitabilityReasons",
]
DATASET_SOURCES = [
    ("public", OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH),
    ("collaborative_support", OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH),
]


@dataclass
class TagAggregate:
    tag: str
    count: int = 0
    sources: set[str] = field(default_factory=set)
    dataset_roles: set[str] = field(default_factory=set)


def main() -> None:
    _ensure_input_files_exist()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    _clear_previous_exports()

    tag_aggregates = _collect_tag_aggregates()
    ordered_rows = _build_ordered_rows(tag_aggregates)
    exported_files = _write_export_parts(ordered_rows)
    summary = _build_summary(tag_aggregates=tag_aggregates, exported_files=exported_files)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Output directory: {EXPORT_DIR}")
    print(f"Unique tags exported: {len(ordered_rows)}")
    print(f"CSV parts written: {len(exported_files)}")
    print(f"Summary path: {SUMMARY_PATH}")


def _ensure_input_files_exist() -> None:
    missing_paths = [str(path) for _role, path in DATASET_SOURCES if not path.exists()]
    if missing_paths:
        missing_text = ", ".join(missing_paths)
        raise RuntimeError(
            "Offline dataset CSV files are missing. "
            f"Expected: {missing_text}."
        )


def _clear_previous_exports() -> None:
    for path in EXPORT_DIR.glob("tags_to_translate_part_*.csv"):
        path.unlink()
    if SUMMARY_PATH.exists():
        SUMMARY_PATH.unlink()


def _collect_tag_aggregates() -> dict[str, TagAggregate]:
    aggregates: dict[str, TagAggregate] = {}

    for dataset_role, csv_path in DATASET_SOURCES:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise RuntimeError(f"CSV file has no header: {csv_path}")

            present_columns = [
                column_name for column_name in TAG_LIKE_COLUMNS if column_name in reader.fieldnames
            ]

            for row in reader:
                row_tags: dict[str, RowTagData] = {}
                for column_name in present_columns:
                    for raw_tag in _split_pipe_values(row.get(column_name)):
                        normalized_tag = _normalize_tag(raw_tag)
                        if not normalized_tag:
                            continue
                        tag_data = row_tags.get(normalized_tag)
                        if tag_data is None:
                            row_tags[normalized_tag] = RowTagData(
                                representative_tag=raw_tag.strip(),
                                sources={column_name},
                            )
                            continue
                        tag_data.sources.add(column_name)

                for normalized_tag, row_tag_data in row_tags.items():
                    aggregate = aggregates.get(normalized_tag)
                    if aggregate is None:
                        aggregate = TagAggregate(tag=row_tag_data.representative_tag)
                        aggregates[normalized_tag] = aggregate
                    aggregate.count += 1
                    aggregate.sources.update(row_tag_data.sources)
                    aggregate.dataset_roles.add(dataset_role)

    return aggregates


@dataclass
class RowTagData:
    representative_tag: str
    sources: set[str]


def _build_ordered_rows(tag_aggregates: dict[str, TagAggregate]) -> list[dict[str, str | int]]:
    ordered_items = sorted(
        tag_aggregates.values(),
        key=lambda item: (-item.count, item.tag.casefold()),
    )
    return [
        {
            "tag": item.tag,
            "count": item.count,
            "sources": LIST_SEPARATOR.join(sorted(item.sources)),
            "datasetRoles": LIST_SEPARATOR.join(sorted(item.dataset_roles)),
        }
        for item in ordered_items
    ]


def _write_export_parts(rows: list[dict[str, str | int]]) -> list[str]:
    exported_files: list[str] = []
    if not rows:
        return exported_files

    for start_index in range(0, len(rows), EXPORT_PART_SIZE):
        part_number = (start_index // EXPORT_PART_SIZE) + 1
        output_path = EXPORT_DIR / EXPORT_FILENAME_TEMPLATE.format(part_number=part_number)
        part_rows = rows[start_index : start_index + EXPORT_PART_SIZE]
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["tag", "count", "sources", "datasetRoles"],
            )
            writer.writeheader()
            writer.writerows(part_rows)
        exported_files.append(str(output_path))

    return exported_files


def _build_summary(
    *,
    tag_aggregates: dict[str, TagAggregate],
    exported_files: list[str],
) -> dict:
    ordered_top_tags = sorted(
        tag_aggregates.values(),
        key=lambda item: (-item.count, item.tag.casefold()),
    )[:20]
    return {
        "totalUniqueTags": len(tag_aggregates),
        "totalTagOccurrences": sum(item.count for item in tag_aggregates.values()),
        "exportedFiles": exported_files,
        "topTags": [
            {
                "tag": item.tag,
                "count": item.count,
                "sources": sorted(item.sources),
                "datasetRoles": sorted(item.dataset_roles),
            }
            for item in ordered_top_tags
        ],
    }


def _split_pipe_values(value: str | None) -> list[str]:
    if value is None:
        return []
    text = value.strip()
    if not text:
        return []
    return [part.strip() for part in text.split(LIST_SEPARATOR) if part.strip()]


def _normalize_tag(value: str) -> str:
    return " ".join(value.strip().lower().split())


if __name__ == "__main__":
    main()
