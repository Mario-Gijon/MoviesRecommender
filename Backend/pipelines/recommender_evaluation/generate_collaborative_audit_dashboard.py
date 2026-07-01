import argparse
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import RECOMMENDER_AUDIT_DIR


MODE_CONFIGS = (
    {
        "mode_id": "model_evaluation",
        "label": "Model evaluation",
        "description": (
            "Leakage-free model-quality audit trained from split train ratings and "
            "evaluated on held-out users/cases with a public + support candidate universe."
        ),
    },
    {
        "mode_id": "stand_simulation",
        "label": "Stand simulation",
        "description": (
            "Leakage-free stand/app simulation trained from split train ratings with "
            "public-only recommendations."
        ),
    },
    {
        "mode_id": "production_diagnostic",
        "label": "Production diagnostic",
        "description": (
            "Diagnostic check of current app/development artifacts with public-only "
            "recommendations. This is not the scientific leakage-free model evaluation."
        ),
    },
)

SUMMARY_FIELDS = [
    "candidateUniverse",
    "candidateMovieCount",
    "recommendationConstraint",
    "leakageFree",
    "caseAuditMode",
    "caseCount",
    "skipApi",
    "runtimeRepeats",
]

RANKING_COLUMNS = [
    "algorithmId",
    "algorithmLabel",
    "variantId",
    "hitRateAt10",
    "recallAt10",
    "precisionAt10",
    "ndcgAt10",
    "mrrAt10",
    "mapAt10",
    "catalogCoveragePct",
    "fallbackUsedPct",
    "predictionCoveragePct",
    "maeRegularized",
    "rmseRegularized",
]

RUNTIME_COLUMNS = [
    "algorithmId",
    "variantId",
    "avgRuntimeMs",
    "p50RuntimeMs",
    "p95RuntimeMs",
    "p99RuntimeMs",
    "maxRuntimeMs",
    "avgPersonalizedRuntimeMs",
    "avgFallbackRuntimeMs",
    "avgTotalRuntimeMs",
]

API_COLUMNS = [
    "algorithmId",
    "variantId",
    "avgApiMs",
    "p50ApiMs",
    "p95ApiMs",
    "p99ApiMs",
    "maxApiMs",
    "avgResponseSizeKb",
    "statusCodeErrorCount",
]

BUILD_ARTIFACT_COLUMNS = [
    "algorithmId",
    "variantId",
    "buildTimeSeconds",
    "modelArtifactSizeMb",
    "neighborsSqliteSizeMb",
    "rankingSqliteSizeMb",
    "neighborRows",
    "rankingRows",
    "ratings",
    "users",
    "movies",
    "publicMovies",
    "supportMovies",
]

MS_COLUMNS = {
    "avgRuntimeMs",
    "p50RuntimeMs",
    "p95RuntimeMs",
    "p99RuntimeMs",
    "maxRuntimeMs",
    "avgPersonalizedRuntimeMs",
    "avgFallbackRuntimeMs",
    "avgTotalRuntimeMs",
    "avgApiMs",
    "p50ApiMs",
    "p95ApiMs",
    "p99ApiMs",
    "maxApiMs",
}

SIX_DECIMAL_COLUMNS = {
    "maeRegularized",
    "rmseRegularized",
}

THREE_DECIMAL_COLUMNS = {
    "hitRateAt10",
    "recallAt10",
    "precisionAt10",
    "ndcgAt10",
    "mrrAt10",
    "mapAt10",
    "catalogCoveragePct",
    "fallbackUsedPct",
    "predictionCoveragePct",
    "avgResponseSizeKb",
    "buildTimeSeconds",
    "modelArtifactSizeMb",
    "neighborsSqliteSizeMb",
    "rankingSqliteSizeMb",
}


@dataclass(frozen=True)
class ModeDashboardData:
    mode_id: str
    label: str
    description: str
    metrics_dir: Path
    summary: dict[str, Any] | None
    rows: list[dict[str, Any]] | None
    warning: str | None

    @property
    def generated(self) -> bool:
        return self.summary is not None and self.rows is not None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=(
            RECOMMENDER_AUDIT_DIR
            / "collaborative_comparison"
            / "current"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_dashboard(root_dir=args.root_dir)


def generate_dashboard(*, root_dir: Path) -> Path:
    modes = [load_mode_dashboard_data(root_dir=root_dir, config=config) for config in MODE_CONFIGS]
    output_path = root_dir / "index.html"
    output_path.write_text(build_dashboard_html(root_dir=root_dir, modes=modes), encoding="utf-8")
    print(f"Generated collaborative audit dashboard: {output_path}")
    return output_path


def load_mode_dashboard_data(*, root_dir: Path, config: dict[str, str]) -> ModeDashboardData:
    metrics_dir = root_dir / config["mode_id"] / "metrics"
    summary_path = metrics_dir / "comparison_summary.json"
    rows_path = metrics_dir / "variant_metrics.json"

    if not summary_path.exists() or not rows_path.exists():
        return ModeDashboardData(
            mode_id=config["mode_id"],
            label=config["label"],
            description=config["description"],
            metrics_dir=metrics_dir,
            summary=None,
            rows=None,
            warning="Not generated yet.",
        )

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        rows = json.loads(rows_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ModeDashboardData(
            mode_id=config["mode_id"],
            label=config["label"],
            description=config["description"],
            metrics_dir=metrics_dir,
            summary=None,
            rows=None,
            warning=f"Could not load generated metrics: {exc}",
        )

    if not isinstance(rows, list):
        return ModeDashboardData(
            mode_id=config["mode_id"],
            label=config["label"],
            description=config["description"],
            metrics_dir=metrics_dir,
            summary=summary,
            rows=None,
            warning="variant_metrics.json does not contain a list.",
        )

    return ModeDashboardData(
        mode_id=config["mode_id"],
        label=config["label"],
        description=config["description"],
        metrics_dir=metrics_dir,
        summary=summary,
        rows=rows,
        warning=None,
    )


def build_dashboard_html(*, root_dir: Path, modes: list[ModeDashboardData]) -> str:
    tab_buttons = "".join(
        (
            f'<button class="tab-button{" is-active" if index == 0 else ""}" '
            f'data-target="{escape(mode.mode_id)}">{escape(mode.label)}</button>'
        )
        for index, mode in enumerate(modes)
    )
    sections = "".join(
        build_mode_section(mode=mode, is_active=index == 0)
        for index, mode in enumerate(modes)
    )
    generated_count = sum(1 for mode in modes if mode.generated)
    missing_count = len(modes) - generated_count

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Collaborative audit dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --panel: #101a2f;
      --panel-strong: #14213b;
      --text: #eaf2ff;
      --muted: #9fb1c9;
      --border: rgba(148, 163, 184, 0.24);
      --border-strong: rgba(103, 217, 255, 0.32);
      --accent: #67d9ff;
      --warning: #f5b942;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(77, 163, 255, 0.16), transparent 34rem),
        linear-gradient(180deg, #08111f 0%, #0a1221 46%, #070d18 100%);
      color: var(--text);
      line-height: 1.5;
    }}
    main {{ max-width: 1520px; margin: 0 auto; padding: 28px; }}
    header, section {{
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012)), var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 22px;
      margin: 18px 0;
    }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; }}
    p {{ margin: 0 0 12px; color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}
    .metric-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 15px 17px;
    }}
    .metric-label {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 5px;
      font-weight: 700;
    }}
    .metric-value {{ font-weight: 800; font-size: 18px; }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 20px 0 16px;
    }}
    .tab-button {{
      border: 1px solid rgba(77, 163, 255, 0.28);
      background: rgba(77, 163, 255, 0.12);
      color: var(--text);
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }}
    .tab-button.is-active {{
      background: linear-gradient(180deg, rgba(103, 217, 255, 0.3), rgba(77, 163, 255, 0.2));
      border-color: var(--border-strong);
    }}
    .mode-panel {{ display: none; }}
    .mode-panel.is-active {{ display: block; }}
    .warning {{
      border: 1px solid rgba(245, 185, 66, 0.35);
      background: rgba(245, 185, 66, 0.12);
      color: #ffe3a5;
      border-radius: 16px;
      padding: 14px 16px;
      margin: 16px 0;
      font-weight: 600;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(8, 17, 31, 0.48);
    }}
    .section-block {{
      margin-top: 20px;
    }}
    .section-block h3 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .section-note {{
      margin-bottom: 10px;
      font-size: 13px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1180px;
      font-size: 13px;
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{
      text-align: left;
    }}
    th {{
      background: linear-gradient(180deg, rgba(77, 163, 255, 0.22), rgba(77, 163, 255, 0.10)), var(--panel-strong);
      position: sticky;
      top: 0;
      border-bottom: 1px solid var(--border-strong);
    }}
    .links a {{
      display: inline-flex;
      align-items: center;
      margin: 5px 9px 5px 0;
      padding: 8px 11px;
      color: #dbeafe;
      background: rgba(77, 163, 255, 0.12);
      border: 1px solid rgba(77, 163, 255, 0.28);
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Collaborative audit dashboard</h1>
    <p>Aggregate view across model evaluation, stand simulation, and production diagnostic runs.</p>
  </header>
  <div class="grid">
    {metric_card("Root", str(root_dir))}
    {metric_card("Modes available", generated_count)}
    {metric_card("Modes missing", missing_count)}
  </div>
  <section>
    <div class="tabs">{tab_buttons}</div>
    {sections}
  </section>
</main>
<script>
  const buttons = Array.from(document.querySelectorAll('.tab-button'));
  const panels = Array.from(document.querySelectorAll('.mode-panel'));
  buttons.forEach((button) => {{
    button.addEventListener('click', () => {{
      const target = button.dataset.target;
      buttons.forEach((item) => item.classList.toggle('is-active', item === button));
      panels.forEach((panel) => panel.classList.toggle('is-active', panel.dataset.mode === target));
    }});
  }});
</script>
</body>
</html>
"""


def build_mode_section(*, mode: ModeDashboardData, is_active: bool) -> str:
    classes = "mode-panel is-active" if is_active else "mode-panel"
    warning = (
        f'<div class="warning">{escape(mode.warning)}</div>'
        if mode.warning is not None
        else ""
    )
    links = "".join(
        f'<a href="{escape(filename)}">{escape(label)}</a>'
        for filename, label in build_mode_links(mode)
    )
    metadata_grid = (
        build_summary_grid(mode.summary)
        if mode.summary is not None
        else ""
    )
    tables = build_mode_tables(mode.rows) if mode.rows is not None else ""
    return f"""
    <section class="{classes}" data-mode="{escape(mode.mode_id)}">
      <h2>{escape(mode.label)}</h2>
      <p>{escape(mode.description)}</p>
      {warning}
      <div class="links">{links}</div>
      {metadata_grid}
      {tables}
    </section>
    """


def build_summary_grid(summary: dict[str, Any]) -> str:
    cards = "".join(
        metric_card(label=field, value=summary.get(field))
        for field in SUMMARY_FIELDS
    )
    return f'<div class="grid">{cards}</div>'


def build_mode_links(mode: ModeDashboardData) -> list[tuple[str, str]]:
    return [
        (f"{mode.mode_id}/metrics/index.html", "Per-mode HTML"),
        (f"{mode.mode_id}/metrics/report.md", "Per-mode Markdown"),
        (f"{mode.mode_id}/metrics/comparison_summary.json", "Summary JSON"),
        (f"{mode.mode_id}/metrics/variant_metrics.json", "Metrics JSON"),
        (f"{mode.mode_id}/metrics/variant_metrics.csv", "Metrics CSV"),
    ]


def metric_card(label: str, value: object) -> str:
    return (
        '<div class="metric-card">'
        f'<span class="metric-label">{escape(label)}</span>'
        f'<span class="metric-value">{escape(format_value(value))}</span>'
        "</div>"
    )


def build_mode_tables(rows: list[dict[str, Any]]) -> str:
    sections = [
        ("Ranking quality", "", RANKING_COLUMNS),
        (
            "Runtime",
            "Runtime is the recommender execution time inside the backend and now includes any explanation generation performed inside recommend().",
            RUNTIME_COLUMNS,
        ),
        (
            "API",
            "API time is only available when the audit is run without --skip-api.",
            API_COLUMNS,
        ),
        ("Build and artifacts", "", BUILD_ARTIFACT_COLUMNS),
    ]
    return "".join(
        build_table_section(title=title, note=note, rows=rows, columns=columns)
        for title, note, columns in sections
    )


def build_table_section(*, title: str, note: str, rows: list[dict[str, Any]], columns: list[str]) -> str:
    note_html = f'<p class="section-note">{escape(note)}</p>' if note else ""
    table = html_rows_table(rows, columns)
    return (
        '<div class="section-block">'
        f"<h3>{escape(title)}</h3>"
        f"{note_html}"
        f"{table}"
        "</div>"
    )


def html_rows_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{escape(format_column_value(column, row.get(column)))}</td>"
            for column in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return f'<div class="table-wrap"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def format_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format_float(value, decimals=3)
    return str(value)


def format_column_value(column: str, value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if column in MS_COLUMNS:
            return f"{format_float(value, decimals=3)} ms"
        if column in SIX_DECIMAL_COLUMNS:
            return format_float(value, decimals=6)
        if column in THREE_DECIMAL_COLUMNS:
            return format_float(value, decimals=3)
        return format_float(value, decimals=3)
    return str(value)


def format_float(value: float, *, decimals: int) -> str:
    return f"{value:.{decimals}f}"


if __name__ == "__main__":
    main()
