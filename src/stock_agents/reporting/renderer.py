from __future__ import annotations

from html import escape

from stock_agents.schemas.outputs import PortfolioDecisionOutput

_KOREAN_DISCLAIMER = "이 리포트는 리서치 보조 자료이며 투자 조언이 아닙니다. 데이터와 판단을 독립적으로 검증하고 필요하면 자격 있는 전문가와 상담하세요."
_ENGLISH_DISCLAIMER = "This report is research assistance, not financial advice. Verify data independently and consult a qualified professional if needed."


def render_final_report(decision: PortfolioDecisionOutput, *, language: str = "Korean") -> str:
    disclaimer = _KOREAN_DISCLAIMER if language.lower().startswith("korean") else _ENGLISH_DISCLAIMER
    evidence_lines = [
        f"- {item.source_type}: {item.quote} (confidence {item.confidence:.2f})"
        for item in decision.supporting_evidence
    ]
    risks = [f"- {risk}" for risk in decision.major_risks]
    heading = f"# {decision.ticker} 분석 리포트" if language.lower().startswith("korean") else f"# {decision.ticker} Analysis Report"
    return "\n".join(
        [
            heading,
            "",
            f"- Date: {decision.trade_date.isoformat()}",
            f"- Rating: {decision.rating.value}",
            f"- Action: {decision.action.value}",
            f"- Confidence: {decision.confidence:.2f}",
            "",
            "## Executive Summary",
            decision.executive_summary,
            "",
            "## Investment Thesis",
            decision.investment_thesis,
            "",
            "## Major Risks",
            *(risks or ["- No major risks were supplied."]),
            "",
            "## Supporting Evidence",
            *(evidence_lines or ["- No supporting evidence was supplied."]),
            "",
            "## Role Detail",
            decision.report_markdown,
            "",
            "## Disclaimer",
            disclaimer,
            "",
        ]
    )


def render_final_report_html(decision: PortfolioDecisionOutput, *, language: str = "Korean") -> str:
    korean = language.lower().startswith("korean")
    title = f"{decision.ticker} 분석 리포트" if korean else f"{decision.ticker} Analysis Report"
    disclaimer = _KOREAN_DISCLAIMER if korean else _ENGLISH_DISCLAIMER
    labels = {
        "date": "기준일" if korean else "Date",
        "rating": "등급" if korean else "Rating",
        "action": "액션" if korean else "Action",
        "confidence": "신뢰도" if korean else "Confidence",
        "summary": "핵심 요약" if korean else "Executive Summary",
        "thesis": "투자 판단" if korean else "Investment Thesis",
        "risks": "주요 리스크" if korean else "Major Risks",
        "evidence": "근거" if korean else "Supporting Evidence",
        "detail": "역할별 상세" if korean else "Role Detail",
        "disclaimer": "면책 고지" if korean else "Disclaimer",
        "source": "출처" if korean else "Source",
        "quote": "내용" if korean else "Evidence",
        "evidence_date": "일자" if korean else "Date",
    }

    risk_items = "".join(f"<li>{escape(risk)}</li>" for risk in decision.major_risks)
    if not risk_items:
        risk_items = f"<li>{'제공된 주요 리스크가 없습니다.' if korean else 'No major risks were supplied.'}</li>"

    evidence_rows = "".join(_render_evidence_row(item, labels=labels) for item in decision.supporting_evidence)
    if not evidence_rows:
        evidence_rows = (
            f"<tr><td colspan=\"4\">{escape('제공된 근거가 없습니다.' if korean else 'No supporting evidence was supplied.')}</td></tr>"
        )

    position_sizing = ""
    if decision.position_sizing:
        heading = "포지션 해석" if korean else "Position Sizing"
        position_sizing = f"""
        <section class="panel">
          <h2>{heading}</h2>
          <p>{escape(decision.position_sizing)}</p>
        </section>
        """

    return f"""<!doctype html>
<html lang="{'ko' if korean else 'en'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --surface: #ffffff;
      --surface-2: #f0f3f6;
      --text: #182029;
      --muted: #647181;
      --line: #d8dee6;
      --accent: #126b59;
      --accent-soft: #e1f3ee;
      --warning: #a15c00;
      --danger: #b43434;
      --shadow: 0 18px 50px rgba(22, 32, 41, 0.10);
      --sans: "Segoe UI", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
      --mono: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      line-height: 1.65;
    }}
    main {{
      width: min(1160px, calc(100% - 32px));
      margin: 0 auto;
      padding: 34px 0 54px;
    }}
    .hero {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: clamp(22px, 4vw, 38px);
    }}
    .eyebrow {{
      color: var(--accent);
      font: 700 12px/1.2 var(--mono);
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{
      margin-bottom: 18px;
      font-size: clamp(30px, 5vw, 54px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    h2 {{
      margin-bottom: 12px;
      font-size: clamp(20px, 3vw, 28px);
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h3 {{
      margin-bottom: 10px;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}
    .metric {{
      min-height: 96px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      padding: 14px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .metric strong {{
      display: block;
      font-size: clamp(18px, 3vw, 25px);
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border-radius: 999px;
      padding: 0 10px;
      background: var(--accent-soft);
      color: var(--accent);
      font: 700 12px/1 var(--mono);
    }}
    .badge.danger {{ background: #ffe8e8; color: var(--danger); }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 14px;
      margin-top: 14px;
      align-items: start;
    }}
    .panel {{
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: clamp(18px, 3vw, 24px);
    }}
    .panel p:last-child, .panel ul:last-child {{ margin-bottom: 0; }}
    ul {{ padding-left: 22px; }}
    li + li {{ margin-top: 8px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}
    th, td {{
      padding: 12px 13px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: var(--surface-2);
      color: var(--muted);
      font: 700 12px/1.4 var(--mono);
    }}
    tr:last-child td {{ border-bottom: 0; }}
    td code {{
      color: var(--muted);
      font-family: var(--mono);
      font-size: 12px;
    }}
    a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    .detail {{
      border-left: 4px solid var(--accent);
    }}
    .detail h1, .detail h2, .detail h3 {{ margin-top: 22px; }}
    .detail h1:first-child, .detail h2:first-child, .detail h3:first-child {{ margin-top: 0; }}
    .disclaimer {{
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 820px) {{
      main {{ width: min(100% - 20px, 1160px); padding-top: 14px; }}
      .metrics, .grid {{ grid-template-columns: 1fr; }}
      th, td {{ display: block; width: 100%; }}
      th {{ display: none; }}
      tr {{ display: block; border-bottom: 1px solid var(--line); }}
      tr:last-child {{ border-bottom: 0; }}
      td {{ border-bottom: 0; padding: 9px 12px; }}
    }}
    @media print {{
      body {{ background: white; }}
      main {{ width: 100%; padding: 0; }}
      .hero, .panel {{ box-shadow: none; break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">stock-agents report</div>
      <h1>{escape(title)}</h1>
      <div class="metrics">
        <div class="metric"><span>{labels['date']}</span><strong>{decision.trade_date.isoformat()}</strong></div>
        <div class="metric"><span>{labels['rating']}</span><strong>{escape(decision.rating.value)}</strong></div>
        <div class="metric"><span>{labels['action']}</span><strong><span class="badge {_action_badge_class(decision.action.value)}">{escape(decision.action.value)}</span></strong></div>
        <div class="metric"><span>{labels['confidence']}</span><strong>{decision.confidence:.2f}</strong></div>
      </div>
    </section>

    <div class="grid">
      <section class="panel">
        <h2>{labels['summary']}</h2>
        <p>{escape(decision.executive_summary)}</p>
      </section>
      <section class="panel">
        <h2>{labels['thesis']}</h2>
        <p>{escape(decision.investment_thesis)}</p>
      </section>
    </div>

    {position_sizing}

    <section class="panel">
      <h2>{labels['risks']}</h2>
      <ul>{risk_items}</ul>
    </section>

    <section class="panel">
      <h2>{labels['evidence']}</h2>
      <table>
        <thead>
          <tr>
            <th>{labels['source']}</th>
            <th>{labels['quote']}</th>
            <th>{labels['evidence_date']}</th>
            <th>{labels['confidence']}</th>
          </tr>
        </thead>
        <tbody>{evidence_rows}</tbody>
      </table>
    </section>

    <section class="panel detail">
      <h2>{labels['detail']}</h2>
      {_render_markdown_fragment(decision.report_markdown)}
    </section>

    <section class="panel disclaimer">
      <h2>{labels['disclaimer']}</h2>
      <p>{escape(disclaimer)}</p>
    </section>
  </main>
</body>
</html>
"""


def _render_evidence_row(item, *, labels: dict[str, str]) -> str:
    source = escape(item.source_type)
    if item.source_path:
        source = f"{source}<br><code>{escape(item.source_path)}</code>"
    quote = escape(item.quote)
    if item.url:
        quote = f"{quote}<br><a href=\"{escape(item.url, quote=True)}\">source link</a>"
    date = escape(item.date or "")
    return (
        "<tr>"
        f"<td>{source}</td>"
        f"<td>{quote}</td>"
        f"<td>{date}</td>"
        f"<td>{item.confidence:.2f}</td>"
        "</tr>"
    )


def _render_markdown_fragment(markdown: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue
        if line.startswith("### "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h3>{escape(line[4:])}</h3>")
            continue
        if line.startswith("## "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h3>{escape(line[3:])}</h3>")
            continue
        if line.startswith("# "):
            flush_paragraph()
            close_list()
            blocks.append(f"<h3>{escape(line[2:])}</h3>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{escape(line[2:])}</li>")
            continue
        paragraph.append(escape(line))

    flush_paragraph()
    close_list()
    return "\n".join(blocks) if blocks else "<p></p>"


def _action_badge_class(action: str) -> str:
    return "danger" if action.lower() == "sell" else ""
