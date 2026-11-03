"""Local-only operations dashboard. Shows headlines and per-run pipeline
activity, so it is never published and never committed (see
docs/adr/0005-data-licensing-and-leakage.md) — it is a debugging tool for
the person running the pipeline, not part of the public track record."""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from forecaster import calibration, scoring
from forecaster.config import Settings
from forecaster.db import Article, Forecast, Question
from forecaster.timeutil import utcnow

# Categorical slots from the validated default palette (dataviz skill),
# assigned in fixed order — never cycled, never reassigned by filtering.
SERIES = {
    "blue": ("#2a78d6", "#3987e5"),
    "aqua": ("#1baf7a", "#199e70"),
    "yellow": ("#eda100", "#c98500"),
    "green": ("#008300", "#008300"),
}
STATUS = {
    "good": ("#0ca30c", "#0ca30c"),
    "muted": ("#898781", "#898781"),
}


@dataclass
class DashboardData:
    total_questions: int
    open_count: int
    resolved_count: int
    forecasts_total: int
    forecasts_today: int
    calibrator_label: str
    brier_bars: list[tuple[str, float, str]]  # (label, value, series_key)
    activity_series: list[tuple[str, int]]  # (date_label, forecast_count)
    questions_table: list[dict]
    recent_headlines: list[dict]


def _calibrator_label(settings: Settings) -> str:
    if not os.path.exists(settings.CALIBRATOR_PATH):
        return "identity (no calibrator fit yet)"
    _, version = calibration.load(settings.CALIBRATOR_PATH)
    return f"{version['method']}, fit on {version['n_train']} forecasts ({version['date'][:10]})"


def gather(session_factory: sessionmaker[Session], settings: Settings) -> DashboardData:
    now = utcnow()
    with session_factory() as session:
        questions = session.scalars(select(Question)).all()
        all_forecasts = session.scalars(select(Forecast).order_by(Forecast.created_at)).all()
        recent_articles = session.scalars(
            select(Article).order_by(Article.fetched_at.desc()).limit(25)
        ).all()

        latest_forecast_by_question: dict[str, Forecast] = {}
        for f in all_forecasts:
            latest_forecast_by_question[f.question_id] = f  # ascending order -> last write wins

        forecast_counts: dict[str, int] = {}
        for f in all_forecasts:
            forecast_counts[f.question_id] = forecast_counts.get(f.question_id, 0) + 1

        headline_counts: dict[str, int] = {}
        for a in session.scalars(select(Article)).all():
            headline_counts[a.question_id] = headline_counts.get(a.question_id, 0) + 1

        questions_table = []
        raw_probs, calibrated_probs, outcomes, market_probs = [], [], [], []
        for q in questions:
            latest = latest_forecast_by_question.get(q.id)
            questions_table.append(
                {
                    "title": q.title,
                    "status": q.status,
                    "market_prob": q.market_prob,
                    "raw_prob": latest.raw_prob if latest else None,
                    "calibrated_prob": latest.calibrated_prob if latest else None,
                    "resolution": q.resolution,
                    "forecast_count": forecast_counts.get(q.id, 0),
                    "headline_count": headline_counts.get(q.id, 0),
                }
            )
            if q.status == "resolved" and q.resolution is not None and latest is not None:
                raw_probs.append(latest.raw_prob)
                calibrated_probs.append(
                    latest.calibrated_prob
                    if latest.calibrated_prob is not None
                    else latest.raw_prob
                )
                outcomes.append(q.resolution)
                if q.market_prob is not None:
                    market_probs.append(q.market_prob)

        recent_headlines = [
            {
                "title": a.title,
                "domain": a.domain,
                "published_at": a.published_at.isoformat(),
                "question_title": next(
                    (q.title for q in questions if q.id == a.question_id), a.question_id
                ),
            }
            for a in recent_articles
        ]

        brier_bars: list[tuple[str, float, str]] = []
        if outcomes:
            brier_bars.append(("Pipeline (raw)", scoring.brier_score(raw_probs, outcomes), "blue"))
            brier_bars.append(
                ("Pipeline (calibrated)", scoring.brier_score(calibrated_probs, outcomes), "aqua")
            )
            brier_bars.append(
                ("Always 50%", scoring.brier_score([0.5] * len(outcomes), outcomes), "yellow")
            )
            base_rate = sum(outcomes) / len(outcomes)
            brier_bars.append(
                ("Base rate", scoring.brier_score([base_rate] * len(outcomes), outcomes), "green")
            )
            if len(market_probs) == len(outcomes):
                brier_bars.append(
                    ("Market price", scoring.brier_score(market_probs, outcomes), "muted")
                )

        activity: dict[str, int] = {}
        window_start = now.date() - timedelta(days=29)
        day = window_start
        while day <= now.date():
            activity[day.isoformat()] = 0
            day += timedelta(days=1)
        for f in all_forecasts:
            key = f.created_at.date().isoformat()
            if key in activity:
                activity[key] += 1
        activity_series = sorted(activity.items())

        return DashboardData(
            total_questions=len(questions),
            open_count=sum(1 for q in questions if q.status == "open"),
            resolved_count=sum(1 for q in questions if q.status == "resolved"),
            forecasts_total=len(all_forecasts),
            forecasts_today=sum(1 for f in all_forecasts if f.created_at.date() == now.date()),
            calibrator_label=_calibrator_label(settings),
            brier_bars=brier_bars,
            activity_series=activity_series,
            questions_table=questions_table,
            recent_headlines=recent_headlines,
        )


# --- SVG rendering -----------------------------------------------------

BAR_HEIGHT = 24
BAR_GAP = 12


def _svg_bar_chart(bars: list[tuple[str, float, str]]) -> str:
    if not bars:
        return (
            "<p class='empty'>No resolved questions yet — scores need at least one resolution.</p>"
        )
    width = 560
    label_w = 160
    plot_w = width - label_w - 60
    max_val = max(v for _, v, _ in bars) or 1.0
    row_h = BAR_HEIGHT + BAR_GAP
    height = row_h * len(bars) + BAR_GAP

    rows = []
    for i, (label, value, color_key) in enumerate(bars):
        y = BAR_GAP + i * row_h
        bar_w = max((value / max_val) * plot_w, 2)
        light, dark = SERIES.get(color_key, STATUS.get(color_key, SERIES["blue"]))
        rows.append(
            f'<g class="bar-row">'
            f'<text x="{label_w - 10}" y="{y + BAR_HEIGHT / 2}" text-anchor="end" '
            f'dominant-baseline="middle" class="bar-label">{html.escape(label)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bar_w:.1f}" height="{BAR_HEIGHT}" rx="4" '
            f'class="bar-fill bar-{color_key}" data-light="{light}" data-dark="{dark}">'
            f"<title>{html.escape(label)}: {value:.3f}</title></rect>"
            f'<text x="{label_w + bar_w + 8}" y="{y + BAR_HEIGHT / 2}" dominant-baseline="middle" '
            f'class="bar-value">{value:.3f}</text>'
            f"</g>"
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Brier score comparison">{"".join(rows)}</svg>'
    )


def _svg_line_chart(series: list[tuple[str, int]]) -> str:
    if not series:
        return "<p class='empty'>No activity yet.</p>"
    width, height = 640, 160
    pad_l, pad_r, pad_t, pad_b = 8, 8, 16, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    values = [v for _, v in series]
    max_val = max(values) or 1
    n = len(series)
    step = plot_w / max(n - 1, 1)

    def xy(i: int, v: int) -> tuple[float, float]:
        x = pad_l + i * step
        y = pad_t + plot_h - (v / max_val) * plot_h
        return x, y

    points = [xy(i, v) for i, (_, v) in enumerate(series)]
    path_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    area_d = (
        path_d + f" L {points[-1][0]:.1f} {pad_t + plot_h} L {points[0][0]:.1f} {pad_t + plot_h} Z"
    )

    gridlines = "".join(
        f'<line x1="{pad_l}" y1="{pad_t + plot_h * f:.1f}" x2="{pad_l + plot_w}" '
        f'y2="{pad_t + plot_h * f:.1f}" class="gridline" />'
        for f in (0.0, 0.5, 1.0)
    )

    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="line-dot" '
        f'data-date="{html.escape(series[i][0])}" data-value="{series[i][1]}" />'
        for i, (x, y) in enumerate(points)
    )

    last_x, last_y = points[-1]
    end_label = (
        f'<text x="{last_x:.1f}" y="{last_y - 10:.1f}" text-anchor="end" class="line-end-label">'
        f"{series[-1][1]} today</text>"
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'class="line-chart" role="img" aria-label="Forecasts made per day, last 30 days">'
        f"{gridlines}"
        f'<path d="{area_d}" class="line-area" />'
        f'<path d="{path_d}" class="line-stroke" />'
        f"{dots}{end_label}"
        f'<text x="{pad_l}" y="{height - 4}" class="axis-label">{series[0][0]}</text>'
        f'<text x="{pad_l + plot_w}" y="{height - 4}" text-anchor="end" '
        f'class="axis-label">{series[-1][0]}</text>'
        f"<desc>Daily tooltip values: hover a point.</desc>"
        f"</svg>"
    )


def _status_chip(status: str) -> str:
    color, _ = STATUS["good"] if status == "resolved" else STATUS["muted"]
    return f'<span class="chip" style="--chip-color:{color}">● {status}</span>'


def _fmt_prob(p: float | None) -> str:
    return f"{p:.2f}" if p is not None else "—"


def render_html(data: DashboardData) -> str:
    bar_svg = _svg_bar_chart(data.brier_bars)
    line_svg = _svg_line_chart(data.activity_series)

    question_rows = (
        "\n".join(
            f"<tr><td>{html.escape(q['title'])}</td>"
            f"<td>{_status_chip(q['status'])}</td>"
            f"<td>{_fmt_prob(q['market_prob'])}</td>"
            f"<td>{_fmt_prob(q['raw_prob'])}</td>"
            f"<td>{_fmt_prob(q['calibrated_prob'])}</td>"
            f"<td>{q['resolution'] if q['resolution'] is not None else '—'}</td>"
            f"<td>{q['forecast_count']}</td>"
            f"<td>{q['headline_count']}</td></tr>"
            for q in data.questions_table
        )
        or "<tr><td colspan='8' class='empty'>No questions ingested yet.</td></tr>"
    )

    headline_rows = (
        "\n".join(
            f"<tr><td>{html.escape(h['title'])}</td><td>{html.escape(h['domain'])}</td>"
            f"<td>{h['published_at'][:16]}</td><td>{html.escape(h['question_title'])}</td></tr>"
            for h in data.recent_headlines
        )
        or "<tr><td colspan='4' class='empty'>No headlines fetched yet.</td></tr>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forecast Pipeline — Ops Dashboard (local only)</title>
<style>
  :root {{
    --surface-1: #fcfcfb; --page: #f9f9f7;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #898781;
    --gridline: #e1e0d9; --border: rgba(11,11,11,0.10);
    --series-blue: #2a78d6; --series-aqua: #1baf7a;
    --series-yellow: #eda100; --series-green: #008300; --series-muted: #898781;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface-1: #1a1a19; --page: #0d0d0d;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #898781;
      --gridline: #2c2c2a; --border: rgba(255,255,255,0.10);
      --series-blue: #3987e5; --series-aqua: #199e70;
      --series-yellow: #c98500; --series-green: #008300; --series-muted: #898781;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px; background: var(--page); color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 13px; margin: 0 0 24px; }}
  .banner {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary); margin-bottom: 24px;
  }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .tile {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px;
  }}
  .tile .label {{ font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }}
  .tile .value {{ font-size: 28px; font-weight: 600; }}
  .panel {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; margin-bottom: 24px; overflow-x: auto;
  }}
  .panel h2 {{ font-size: 14px; margin: 0 0 16px; color: var(--text-secondary); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: var(--text-muted); font-weight: 500; padding: 6px 10px;
        border-bottom: 1px solid var(--gridline); white-space: nowrap; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid var(--gridline); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .empty {{ color: var(--text-muted); text-align: center; padding: 16px; }}
  .chip {{ font-size: 12px; }}
  .chip::before {{ content: ''; }}
  .bar-label, .bar-value, .axis-label {{ font-size: 11px; fill: var(--text-secondary); }}
  .bar-blue {{ fill: var(--series-blue); }}
  .bar-aqua {{ fill: var(--series-aqua); }}
  .bar-yellow {{ fill: var(--series-yellow); }}
  .bar-green {{ fill: var(--series-green); }}
  .bar-muted {{ fill: var(--series-muted); }}
  .gridline {{ stroke: var(--gridline); stroke-width: 1; }}
  .line-stroke {{ fill: none; stroke: var(--series-blue); stroke-width: 2; }}
  .line-area {{ fill: var(--series-blue); opacity: 0.1; stroke: none; }}
  .line-dot {{
    fill: var(--series-blue); stroke: var(--surface-1); stroke-width: 2; cursor: pointer;
  }}
  .line-end-label {{ font-size: 12px; fill: var(--text-primary); font-weight: 600; }}
  #tooltip {{
    position: fixed; display: none; background: var(--text-primary); color: var(--surface-1);
    font-size: 12px; padding: 4px 8px; border-radius: 4px; pointer-events: none; z-index: 10;
  }}
</style>
</head>
<body>
<h1>Forecast Pipeline — Ops Dashboard</h1>
<p class="subtitle">Local only — generated {html.escape(data.calibrator_label)}</p>
<div class="banner">
  Not published. Shows raw headlines and internal activity for debugging —
  the public GitHub Pages track record never includes this content
  (docs/adr/0005-data-licensing-and-leakage.md).
</div>

<div class="grid">
  <div class="tile"><div class="label">Questions tracked</div>
    <div class="value">{data.total_questions}</div></div>
  <div class="tile"><div class="label">Open / resolved</div>
    <div class="value">{data.open_count} / {data.resolved_count}</div></div>
  <div class="tile"><div class="label">Forecasts made (today)</div>
    <div class="value">{data.forecasts_today}</div></div>
  <div class="tile"><div class="label">Forecasts made (total)</div>
    <div class="value">{data.forecasts_total}</div></div>
</div>

<div class="panel">
  <h2>Brier score vs. baselines (lower is better)</h2>
  {bar_svg}
</div>

<div class="panel">
  <h2>Forecasts made per day — last 30 days</h2>
  {line_svg}
</div>

<div class="panel">
  <h2>Questions</h2>
  <table>
    <thead><tr><th>Question</th><th>Status</th><th>Market</th><th>Raw</th><th>Calibrated</th>
    <th>Resolution</th><th>Forecasts</th><th>Headlines</th></tr></thead>
    <tbody>{question_rows}</tbody>
  </table>
</div>

<div class="panel">
  <h2>Recent headlines fetched (private model input — never published)</h2>
  <table>
    <thead><tr><th>Headline</th><th>Domain</th><th>Published</th><th>For question</th></tr></thead>
    <tbody>{headline_rows}</tbody>
  </table>
</div>

<div id="tooltip"></div>
<script>
  const tooltip = document.getElementById('tooltip');
  document.querySelectorAll('.line-dot').forEach((dot) => {{
    dot.addEventListener('mouseenter', (e) => {{
      tooltip.textContent = dot.dataset.date + ': ' + dot.dataset.value + ' forecasts';
      tooltip.style.display = 'block';
    }});
    dot.addEventListener('mousemove', (e) => {{
      tooltip.style.left = (e.clientX + 12) + 'px';
      tooltip.style.top = (e.clientY - 12) + 'px';
    }});
    dot.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
  }});
</script>
</body>
</html>
"""


def render_dashboard(
    session_factory: sessionmaker[Session], settings: Settings, output_dir: str = "./ops"
) -> str:
    data = gather(session_factory, settings)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "dashboard.html")
    with open(path, "w") as f:
        f.write(render_html(data))
    return path
