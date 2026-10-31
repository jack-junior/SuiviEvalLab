"""Read-only dashboard: one self-contained HTML file to send to a partner or a donor.

It holds results only (estimates, intervals, sample sizes, statuses, conclusions),
never a row of data. Breakdown groups smaller than `min_cell` observations are
hidden, so a small group cannot point to a person. The file needs nothing else:
styles, charts (SVG) and the few lines of script are inside it, and it opens in
any browser without a network.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from . import __version__, stattests
from .report import Fmt, T, _design_text, _narrative, f_date

MIN_CELL = 5

S = {
    "fr": {
        "title": "Tableau de bord",
        "readonly": "Lecture seule",
        "generated": "Résultats au {date}, produits avec SuiviEvalLab {version}.",
        "privacy": (
            "Ce fichier ne contient que des résultats agrégés, aucune donnée individuelle. "
            "Les groupes de moins de {n} observations sont masqués."
        ),
        "search": "Rechercher un indicateur",
        "all": "Tous",
        "no_match": "Aucun indicateur ne correspond.",
        "small": "moins de {n} obs.",
        "details": "Désagrégation",
        "data": "Données et méthodes",
        "col_dataset": "Fichier",
        "col_round": "Collecte",
        "col_rows": "Lignes analysées",
        "col_design": "Plan d'enquête",
        "print": "Imprimer",
        "unassigned": "Indicateurs",
    },
    "en": {
        "title": "Dashboard",
        "readonly": "Read only",
        "generated": "Results as of {date}, produced with SuiviEvalLab {version}.",
        "privacy": (
            "This file holds aggregated results only, no individual data. "
            "Groups with fewer than {n} observations are hidden."
        ),
        "search": "Search an indicator",
        "all": "All",
        "no_match": "No indicator matches.",
        "small": "fewer than {n} obs.",
        "details": "Breakdown",
        "data": "Data and methods",
        "col_dataset": "File",
        "col_round": "Round",
        "col_rows": "Rows analysed",
        "col_design": "Survey design",
        "print": "Print",
        "unassigned": "Indicators",
    },
}

STATUS_ORDER = ("achieved", "on_track", "late", "unknown")


def e(text: Any) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def _chart(rounds: list[dict[str, Any]], unit: str, target: float | None, t: dict[str, Any], f: Fmt) -> str:
    """Bars per round with their 95% interval and the target as a dashed line, as SVG."""
    w, h, left, bottom, top = 560, 230, 8, 34, 40
    vals = [r["result"]["estimate"] for r in rounds]
    highs = [r["result"].get("ci_high") for r in rounds]
    top_value = max([v for v in [*vals, *highs, target] if v is not None] or [1])
    # Small shares keep a readable bar: the axis stops a little above the highest value, at most 100 %.
    scale_max = top_value * 1.2 or 1
    if unit == "percent":
        scale_max = min(1.0, scale_max)
    plot_h = h - bottom - top
    slot = (w - 2 * left) / max(len(rounds), 1)
    bar_w = min(96, slot * 0.5)

    def y(v: float) -> float:
        return top + plot_h * (1 - max(0.0, min(v, scale_max)) / scale_max)

    parts = [
        f'<svg viewBox="0 0 {w} {h}" role="img" class="chart" aria-label="{e(t["chart_target"])}">',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{w - left}" y2="{top + plot_h}" class="axis"/>',
    ]
    for i, r in enumerate(rounds):
        res = r["result"]
        cx = left + slot * (i + 0.5)
        v = res["estimate"]
        parts.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{y(v):.1f}" width="{bar_w:.1f}" '
            f'height="{top + plot_h - y(v):.1f}" rx="3" class="bar"/>'
        )
        lo, hi = res.get("ci_low"), res.get("ci_high")
        if lo is not None and hi is not None:
            parts.append(
                f'<path d="M{cx:.1f} {y(lo):.1f}V{y(hi):.1f}M{cx - 7:.1f} {y(lo):.1f}H{cx + 7:.1f}'
                f'M{cx - 7:.1f} {y(hi):.1f}H{cx + 7:.1f}" class="ci"/>'
            )
        label_y = y(hi if hi is not None else v) - 7
        parts.append(f'<text x="{cx:.1f}" y="{max(label_y, 30):.1f}" class="val">{e(f.value(v, unit))}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - 12}" class="lab">{e(t["rounds"][r["round"]])}</text>')
    if target is not None:
        ty = y(target)
        parts.append(f'<line x1="{left}" y1="{ty:.1f}" x2="{w - left}" y2="{ty:.1f}" class="target"/>')
        # Legend in the top left corner, clear of the value labels.
        parts.append(f'<line x1="{left}" y1="10" x2="{left + 22}" y2="10" class="target"/>')
        parts.append(
            f'<text x="{left + 28}" y="14" class="tlab">{e(t["chart_target"])} {e(f.value(target, unit))}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _breakdown(ind: dict[str, Any], rounds: list[dict[str, Any]], s: dict[str, Any], f: Fmt, label: Any) -> str:
    if not ind.get("disaggregation") or not any(r["result"].get("by") for r in rounds):
        return ""
    cols = [ind["disaggregation"], *([ind["disaggregation2"]] if ind.get("disaggregation2") else [])]

    def group_text(g: str) -> str:
        parts = str(g).split(" / ") if len(cols) == 2 else [str(g)]
        if len(parts) != len(cols):
            return str(g)
        return " / ".join(label(c, p) for c, p in zip(cols, parts, strict=True))

    groups = sorted({g["group"] for r in rounds for g in r["result"].get("by", [])}, key=str)
    head = "".join(f"<th>{e(T[f.lang]['rounds'][r['round']])}</th>" for r in rounds)
    body = []
    for g in groups:
        cells = []
        for r in rounds:
            hit = next((x for x in r["result"].get("by", []) if x["group"] == g), None)
            if not hit or hit.get("estimate") is None:
                cells.append(f"<td>{e(f.none)}</td>")
            elif (hit.get("n") or 0) < MIN_CELL:
                cells.append(f'<td class="muted">{e(s["small"].format(n=MIN_CELL))}</td>')
            else:
                cells.append(
                    f"<td>{e(f.value(hit['estimate'], ind['unit']))} "
                    f'<span class="muted">(n = {e(f.num(hit["n"], 0))})</span></td>'
                )
        body.append(f'<tr><th scope="row">{e(group_text(g))}</th>{"".join(cells)}</tr>')
    title = " × ".join(label(c) for c in cols)
    sep = " : " if f.lang == "fr" else ": "
    table = f"<table><thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    return (
        f'<details><summary>{e(s["details"])}{sep}{e(title)}</summary><div class="table-wrap">{table}</div></details>'
    )


def _indicator(ind: dict[str, Any], an: dict[str, Any], node: dict[str, Any], lang: str, f: Fmt, label: Any) -> str:
    t, s = T[lang], S[lang]
    unit = ind["unit"]
    usable = [r for r in an["rounds"] if "error_key" not in r["result"]]
    status = an["status"]
    ach = an.get("achievement")
    width = 0 if ach is None else max(0, min(1, ach)) * 100
    figures = "".join(
        f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>"
        for k, v in (
            (t["col_baseline"], f.value(an.get("baseline"), unit)),
            (t["col_current"], f.value(an.get("current"), unit)),
            (t["col_target"], f.value(an.get("target"), unit)),
            (t["col_rate"], f.pct(ach, 0)),
        )
    )
    text = " ".join(_narrative(ind, an, t, f)) if usable else t["no_data"]
    chart = _chart(usable, unit, an.get("target"), t, f) if usable else ""
    definition = (
        f'<p class="muted small"><strong>{e(t["definition"])}</strong>{e(ind["definition"])}</p>'
        if ind.get("definition")
        else ""
    )
    source = f'<p class="muted small">{e(t["source"])}{e(ind["source"])}</p>' if ind.get("source") else ""
    search = " ".join([ind["name"], node.get("code") or "", node.get("title") or ""]).lower()
    return f"""
<article class="ind" data-status="{status}" data-search="{e(search)}">
  <header class="ind-head">
    <h3>{e(ind["name"])}</h3>
    <span class="tag st-{status}">{e(t["status"][status])}</span>
  </header>
  <dl class="figures">{figures}</dl>
  <div class="track" aria-hidden="true"><span class="fill st-{status}" style="width:{width:.0f}%"></span></div>
  <p>{e(text)}</p>
  {chart}
  {_breakdown(ind, usable, s, f, label)}
  {definition}{source}
</article>"""


def generate(svc: Any, path: Path, lang: str) -> dict[str, Any]:
    t, s = T[lang], S[lang]
    f = Fmt(lang)
    snap = svc.snapshot()
    project = snap["project"]
    label = svc.labeller(lang)
    analyses = {ind["id"]: svc.indicator_analysis(ind["id"]) for ind in snap["indicators"]}
    counts = dict.fromkeys(STATUS_ORDER, 0)
    for an in analyses.values():
        counts[an["status"]] += 1

    sections = []
    for node in snap["framework"]:
        inds = [i for i in snap["indicators"] if i["node_id"] == node["id"]]
        if not inds:
            continue
        sep = " : " if lang == "fr" else ": "
        head = f"{t['levels'][node['level']]} {node['code']}".strip() + sep + node["title"]
        cards = "".join(_indicator(i, analyses[i["id"]], node, lang, f, label) for i in inds)
        sections.append(f'<section class="node"><h2>{e(head)}</h2><div class="grid">{cards}</div></section>')

    tests = []
    for spec in snap.get("tests") or []:
        try:
            res = stattests.run(svc, spec)
            body = " ".join(stattests.conclusion(spec, res, lang, f, label))
            tname = stattests.TEXT[lang]["tests"].get(res.get("test_key"), res.get("test_key"))
            note = t["test_used"].format(test=tname, n=f.num(res.get("n"), 0))
        except Exception as exc:  # noqa: BLE001 - a broken saved test must not stop the dashboard
            body, note = t["test_failed"].format(detail=str(exc)), ""
        tests.append(
            f'<article class="test"><h3>{e(spec.get("title") or t["test_untitled"])}</h3>'
            f'<p>{e(body)}</p><p class="muted small">{e(note)}</p></article>'
        )
    tests_html = (
        f'<section class="node"><h2>{e(t["tests_title"])}</h2><div class="grid">{"".join(tests)}</div></section>'
        if tests
        else ""
    )

    ds_rows = "".join(
        f"<tr><td>{e(ds['name'])}</td><td>{e(t['rounds'][ds['round']])}</td>"
        f"<td>{e(f.num(ds['clean_rows'], 0))}</td><td>{e(_design_text(ds['design'], t))}</td></tr>"
        for ds in snap["datasets"]
    )
    used = sorted(
        {r["result"]["method_key"] for an in analyses.values() for r in an["rounds"] if "method_key" in r["result"]}
    )
    methods = "".join(f"<li>{e(t['methods'][k])}</li>" for k in used if k in t["methods"])
    attributions = "".join(
        f"<li>{e(a)}</li>" for a in dict.fromkeys(ds["attribution"] for ds in snap["datasets"] if ds.get("attribution"))
    )

    chips = (
        f'<button class="chip" aria-pressed="true" data-filter="">{e(s["all"])} ({len(analyses)})</button>'
        + "".join(
            f'<button class="chip" aria-pressed="false" data-filter="{k}">'
            f'<span class="dot st-{k}"></span>{e(t["status"][k])} ({counts[k]})</button>'
            for k in STATUS_ORDER
            if counts[k]
        )
    )
    texts = {"noMatch": s["no_match"]}
    kpis = "".join(
        f'<div class="kpi"><span class="kpi-n">{counts[k]}</span>'
        f'<span class="kpi-l"><span class="dot st-{k}"></span>{e(t["status"][k])}</span></div>'
        for k in STATUS_ORDER
    )

    page = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="SuiviEvalLab {e(__version__)}">
<title>{e(project["name"])} - {e(s["title"])}</title>
<style>{CSS}</style>
</head>
<body>
<header class="top">
  <div class="brand">{LOGO}<div><h1>{e(project["name"])}</h1>
  <p class="muted">{e(t["subtitle"])} <span class="badge">{e(s["readonly"])}</span></p></div></div>
  <button class="btn" onclick="window.print()">{e(s["print"])}</button>
</header>
<main>
  <p class="muted small">{e(s["generated"].format(date=f_date(lang), version=__version__))}
  {e(s["privacy"].format(n=MIN_CELL))}</p>
  <section class="kpis">{kpis}</section>
  <div class="tools"><input type="search" id="q" placeholder="{e(s["search"])}" aria-label="{e(s["search"])}">
  <div class="chips">{chips}</div></div>
  <p id="none" class="muted" hidden></p>
  {"".join(sections)}
  {tests_html}
  <section class="node"><h2>{e(s["data"])}</h2>
    <div class="table-wrap"><table><thead><tr><th>{e(s["col_dataset"])}</th><th>{e(s["col_round"])}</th>
    <th>{e(s["col_rows"])}</th><th>{e(s["col_design"])}</th></tr></thead><tbody>{ds_rows}</tbody></table></div>
    <ul class="small">{methods}</ul>
    <p class="small muted">{e(t["achievement_def"])}</p>
    {f'<h3>{e(t["sources"])}</h3><ul class="small">{attributions}</ul>' if attributions else ""}
  </section>
</main>
<script>const TEXT = {json.dumps(texts, ensure_ascii=False)};{JS}</script>
</body>
</html>
"""
    if path.suffix.lower() not in (".html", ".htm"):
        path = path.with_suffix(".html")
    path.write_text(page, encoding="utf-8")
    return {"path": str(path), "indicators": len(analyses), "bytes": len(page.encode())}


LOGO = (
    '<svg class="logo" viewBox="0 0 64 64" aria-hidden="true"><rect x="2" y="2" width="60" height="60" rx="14" '
    'fill="#1D4F91"/><path d="M15 45 L27 33 L36 39 L48 22" fill="none" stroke="#fff" stroke-width="5.5" '
    'stroke-linecap="round" stroke-linejoin="round"/><circle cx="48" cy="21" r="6.5" fill="#E07A4A" '
    'stroke="#1D4F91" stroke-width="2.5"/></svg>'
)

CSS = """
:root{--fond:#f6f5f2;--surface:#fff;--encre:#1f1e1c;--encre-2:#5f5c57;--ligne:#e3e1db;--action:#1d4f91;
--teinte:#e6ecf5;--laterite:#b4441a;--ok:#2e6b47;--ok-f:#e2efe7;--mid:#875811;--mid-f:#f5ebd8;--late:#a3392b;
--late-f:#f6e3df;--unk:#69665f;--unk-f:#ecebe7;--piste:#e6e4df;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--fond:#1f1e1c;--surface:#282725;--encre:#eceae5;--encre-2:#b6b2aa;
--ligne:#3a3936;--action:#8db3e8;--teinte:#2b3443;--laterite:#e8916b;--ok:#8fc9a5;--ok-f:#24352b;--mid:#e0b46a;
--mid-f:#3a3122;--late:#ee9a8d;--late-f:#3d2723;--unk:#b6b2aa;--unk-f:#33322f;--piste:#3a3936;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--fond);color:var(--encre);font:15px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:20px 32px;
background:var(--surface);border-bottom:1px solid var(--ligne)}
.brand{display:flex;gap:14px;align-items:center}.logo{width:44px;height:44px;flex:none}
h1{font:600 24px/1.2 Georgia,"Times New Roman",serif;margin:0}
h2{font:600 19px/1.3 Georgia,"Times New Roman",serif;margin:32px 0 12px}h3{font-size:16px;margin:0}
main{max-width:1180px;margin:0 auto;padding:20px 32px 48px}
p{margin:6px 0}.muted{color:var(--encre-2)}.small{font-size:13px}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--teinte);color:var(--action);
font-size:12px}
.btn{font:inherit;border:1px solid var(--ligne);background:var(--surface);color:var(--encre);border-radius:6px;
padding:6px 14px;cursor:pointer}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}
.kpi{background:var(--surface);border:1px solid var(--ligne);border-radius:8px;padding:12px 16px;display:grid}
.kpi-n{font:600 28px/1.1 Georgia,serif}.kpi-l{color:var(--encre-2);font-size:13px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:1px}
.dot.st-achieved{background:var(--ok)}.dot.st-on_track{background:var(--mid)}.dot.st-late{background:var(--late)}
.dot.st-unknown{background:var(--unk)}
.tools{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:8px 0}
input[type=search]{font:inherit;padding:7px 12px;border:1px solid var(--ligne);border-radius:6px;min-width:260px;
background:var(--surface);color:var(--encre)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font:inherit;font-size:13px;border:1px solid var(--ligne);background:var(--surface);color:var(--encre);
border-radius:99px;padding:4px 12px;cursor:pointer}.chip[aria-pressed=true]{background:var(--teinte);
border-color:var(--action);color:var(--action)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:14px}
.ind,.test{background:var(--surface);border:1px solid var(--ligne);border-radius:8px;padding:16px 18px;min-width:0}
.ind-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.tag{font-size:12px;padding:2px 9px;border-radius:99px;white-space:nowrap}
.tag.st-achieved{background:var(--ok-f);color:var(--ok)}.tag.st-on_track{background:var(--mid-f);color:var(--mid)}
.tag.st-late{background:var(--late-f);color:var(--late)}.tag.st-unknown{background:var(--unk-f);color:var(--unk)}
.figures{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 8px}
.figures dt{font-size:12px;color:var(--encre-2)}.figures dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
.track{height:6px;background:var(--piste);border-radius:3px;overflow:hidden;margin-bottom:10px}
.fill{display:block;height:100%}.fill.st-achieved{background:var(--ok)}.fill.st-on_track{background:var(--mid)}
.fill.st-late{background:var(--late)}.fill.st-unknown{background:var(--unk)}
.chart{width:100%;height:auto;margin:6px 0}.chart .bar{fill:var(--action)}.chart .axis{stroke:var(--ligne)}
.chart .ci{stroke:var(--encre);stroke-width:1.6;fill:none}.chart .target{stroke:var(--laterite);stroke-width:1.6;
stroke-dasharray:6 4}.chart text{fill:var(--encre);font-size:13px;text-anchor:middle}
.chart .lab{fill:var(--encre-2)}.chart .tlab{fill:var(--laterite);text-anchor:start;font-size:12px}
details{margin:8px 0}summary{cursor:pointer;color:var(--action);font-size:14px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--ligne);vertical-align:top}
thead th{color:var(--encre-2);font-weight:600}td{font-variant-numeric:tabular-nums}
@media (max-width:720px){.top,main{padding-left:16px;padding-right:16px}.top .btn{display:none}
h1{font-size:20px}.kpis{grid-template-columns:repeat(2,1fr)}
.grid{grid-template-columns:1fr}.figures{grid-template-columns:repeat(2,1fr)}input[type=search]{min-width:0;width:100%}}
@media print{.tools,.btn{display:none}body{background:#fff}.ind,.test{break-inside:avoid}}
"""

JS = """
(() => {
  const q = document.getElementById("q");
  const none = document.getElementById("none");
  const chips = [...document.querySelectorAll(".chip")];
  let status = "";
  const apply = () => {
    const text = q.value.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll(".ind").forEach((el) => {
      const ok = (!status || el.dataset.status === status) && (!text || el.dataset.search.includes(text));
      el.hidden = !ok;
      if (ok) shown++;
    });
    document.querySelectorAll(".node").forEach((sec) => {
      const cards = sec.querySelectorAll(".ind");
      if (cards.length) sec.hidden = ![...cards].some((c) => !c.hidden);
    });
    none.hidden = shown > 0;
    none.textContent = TEXT.noMatch;
  };
  q.addEventListener("input", apply);
  window.addEventListener("beforeprint", () => document.querySelectorAll("details").forEach((d) => (d.open = true)));
  chips.forEach((c) => c.addEventListener("click", () => {
    status = c.dataset.filter;
    chips.forEach((x) => x.setAttribute("aria-pressed", String(x === c)));
    apply();
  }));
})();
"""
