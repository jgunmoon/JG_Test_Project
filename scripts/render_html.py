"""누적 DB로 팀 공용 HTML 대시보드(reports/index.html)를 만듭니다.

generate_report가 마크다운 리포트와 함께 호출합니다. 외부 스크립트 없이 한 파일로 동작하며
(글꼴만 Google Fonts, 없으면 시스템 글꼴), 같은 DB면 같은 HTML이 나옵니다.
상세 리포트 링크는 config의 report_base_url 기준입니다 (비우면 reports/ 기준 상대 경로).
"""
from collections import Counter
from html import escape

from scripts import delta, topics
from scripts.generate_report import TYPES, meeting_slug, meeting_sort_key

TITLE = "RAN1 6G PHY Tracker"
TYPE_LABEL = {"Agreement": "Agreement", "Working Assumption": "WA", "Conclusion": "Conclusion"}

CSS = """
/* 레이아웃: 요약(직전 회의 대비) → 아이템 카드(작은 막대그래프) → Delta 상세 → 회의 목록 */
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #14181f; --ink-2: #4a5260; --ink-3: #737b88;
  --rule: #dfe3e9; --accent: #2a78d6; --accent-soft: #b9d2f1; --candidate: #8a5a00; --candidate-bg: #fff3d6;
  --confirmed: #0d6b3c; --confirmed-bg: #dcf3e6;
  --font-body: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  --font-data: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11141a; --panel: #181c24; --ink: #eef1f5; --ink-2: #b8c0cc; --ink-3: #8b94a3;
  --rule: #2a313d; --accent: #3987e5; --accent-soft: #2c4a72; --candidate: #f2c46b; --candidate-bg: #3a2f14;
  --confirmed: #7fd9a6; --confirmed-bg: #173526; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11141a; --panel: #181c24; --ink: #eef1f5; --ink-2: #b8c0cc; --ink-3: #8b94a3;
  --rule: #2a313d; --accent: #3987e5; --accent-soft: #2c4a72; --candidate: #f2c46b; --candidate-bg: #3a2f14;
  --confirmed: #7fd9a6; --confirmed-bg: #173526; color-scheme: dark; }
body { background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 15px; line-height: 1.55; margin: 0; }
.wrap { max-width: 1120px; margin: 0 auto; padding-block: 32px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 40px; }
h1, h2, h3 { text-wrap: balance; margin: 0; line-height: 1.25; }
h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.01em; }
h2 { font-size: 19px; font-weight: 600; }
h3 { font-size: 15px; font-weight: 600; }
a { color: var(--accent); text-underline-offset: 2px; }
a:focus-visible, summary:focus-visible, .bar:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.eyebrow { font-family: var(--font-data); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); }
.mono, .num { font-family: var(--font-data); font-variant-numeric: tabular-nums; }
.muted { color: var(--ink-2); }
.small { font-size: 13px; }
header { display: grid; gap: 10px; }
.facts { display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 4px 0 0; }
.facts div { display: grid; gap: 2px; }
.facts dt { font-size: 12px; color: var(--ink-3); }
.facts dd { margin: 0; font-family: var(--font-data); font-size: 18px; font-variant-numeric: tabular-nums; }
section { display: grid; gap: 14px; min-width: 0; }
.lede { margin: 0; max-width: 68ch; color: var(--ink-2); font-size: 14px; }
.table-scroll { overflow-x: auto; border: 1px solid var(--rule); border-radius: 8px; background: var(--panel); }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--rule); vertical-align: top; }
th { font-size: 12px; font-weight: 600; color: var(--ink-3); white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; white-space: nowrap; }
.zero { color: var(--ink-3); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 330px), 1fr)); gap: 14px; }
.card { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; display: grid; gap: 10px; min-width: 0; }
.card-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.card-head .rel { font-family: var(--font-data); font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.stats div { display: grid; gap: 1px; }
.stats dt { font-size: 11px; color: var(--ink-3); }
.stats dd { margin: 0; font-family: var(--font-data); font-size: 17px; font-variant-numeric: tabular-nums; }
svg.chart { width: 100%; height: auto; display: block; overflow: visible; }
svg.chart text { fill: var(--ink-3); font-family: var(--font-data); font-size: 10px; }
svg.chart .grid { stroke: var(--rule); stroke-width: 1; }
svg.chart .bar path { fill: var(--accent-soft); }
svg.chart .bar.latest path { fill: var(--accent); }
svg.chart .bar .hit { fill: transparent; }
svg.chart text.val { fill: var(--ink); font-size: 11px; }
.card-foot { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; flex-wrap: wrap; }
.empty { color: var(--ink-3); font-size: 13px; padding: 20px 0; text-align: center; border: 1px dashed var(--rule); border-radius: 6px; }
details { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; }
details > summary { cursor: pointer; padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: baseline; }
details > summary h3 { display: inline; }
details[open] > summary { border-bottom: 1px solid var(--rule); }
.detail-body { padding: 14px 16px; display: grid; gap: 16px; min-width: 0; }
.chip { display: inline-block; font-size: 12px; font-weight: 600; padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
.chip.candidate { color: var(--candidate); background: var(--candidate-bg); }
.chip.confirmed { color: var(--confirmed); background: var(--confirmed-bg); }
.pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 10px; }
.quote { margin: 0; padding: 10px 12px; border: 1px solid var(--rule); border-radius: 6px; font-size: 13px; overflow-wrap: anywhere; min-width: 0; display: grid; gap: 6px; }
.quote .text { white-space: pre-line; max-height: 14em; overflow-y: auto; }
.quote .src { font-size: 12px; }
table.matrix th.num { white-space: normal; min-width: 7ch; max-width: 16ch; text-align: right; }
.basis { font-size: 12px; color: var(--ink-3); }
.items-list { display: grid; gap: 10px; }
.agenda-change { margin: 0; font-size: 13px; }
.topic-nav { display: flex; flex-wrap: wrap; gap: 8px; }
.topic-nav a { font-size: 13px; padding: 3px 10px; border: 1px solid var(--rule); border-radius: 999px; background: var(--panel); text-decoration: none; }
.topic-nav a .num { color: var(--ink-3); margin-left: 4px; }
.cell-text { white-space: pre-line; max-height: 9em; overflow-y: auto; min-width: 24ch; overflow-wrap: anywhere; }
.counts { font-family: var(--font-data); font-size: 12px; color: var(--ink-3); }
footer { font-size: 13px; color: var(--ink-3); border-top: 1px solid var(--rule); padding-top: 16px; }
#tip { position: fixed; pointer-events: none; z-index: 20; background: var(--ink); color: var(--bg);
  font-family: var(--font-data); font-size: 12px; padding: 6px 8px; border-radius: 4px; white-space: pre; }
@media (max-width: 520px) { h1 { font-size: 24px; } .stats { grid-template-columns: repeat(2, 1fr); } }
@media (prefers-reduced-motion: no-preference) { details > summary { transition: background-color .15s; } }
"""

SCRIPT = """
(() => {
  const openHash = () => { const d = location.hash && document.getElementById(location.hash.slice(1));
    if (d && d.tagName === 'DETAILS') d.open = true; };
  addEventListener('hashchange', openHash); openHash();
  const tip = document.getElementById('tip');
  const show = (el, x, y) => { tip.textContent = el.dataset.tip; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(x + 12, innerWidth - w - 8)) + 'px';
    tip.style.top = Math.max(8, y - h - 12) + 'px'; };
  document.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('pointermove', ev => show(el, ev.clientX, ev.clientY));
    el.addEventListener('pointerleave', () => { tip.hidden = true; });
    el.addEventListener('focus', () => { const r = el.getBoundingClientRect(); show(el, r.left, r.top); });
    el.addEventListener('blur', () => { tip.hidden = true; });
  });
})();
"""


def _e(text):
    return escape(str(text), quote=True)


def _short(meeting):
    return meeting.replace("RAN1#", "").replace("bis", "b")


def _link(url, label):
    return f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(label)}</a>'


def _source(source):
    parts = [_link(source["url"], source["doc"])]
    if source.get("tdoc"):
        parts.append(_link(source["tdoc_url"], source["tdoc"]) if source.get("tdoc_url") else _e(source["tdoc"]))
    if source.get("discussion"):
        parts.append(f'<span class="mono">[{_e(source["discussion"])}]</span>')
    return " · ".join(parts)


def _num(n):
    return f'<td class="num{" zero" if not n else ""}">{n}</td>'


def _bar_chart(item, db, meetings):
    per = {m: [e for e in db["entries"] if e["item"] == item["id"] and e["meeting"] == m] for m in meetings}
    counts = [len(per[m]) for m in meetings]
    top = max(counts) if counts else 0
    if not top:
        return '<div class="empty">아직 기록된 결정이 없습니다</div>'
    w, h, pad_l, pad_b, pad_t = 300, 110, 26, 18, 14
    slot = (w - pad_l) / len(meetings)
    bw = min(26, slot * 0.6)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" '
           f'aria-label="{_e(item["name"])} 회의별 결정 수 (최대 {top}건)">',
           f'<line class="grid" x1="{pad_l}" x2="{w}" y1="{pad_t}" y2="{pad_t}"/>',
           f'<line class="grid" x1="{pad_l}" x2="{w}" y1="{h - pad_b}" y2="{h - pad_b}"/>',
           f'<text x="{pad_l - 4}" y="{pad_t + 3}" text-anchor="end">{top}</text>',
           f'<text x="{pad_l - 4}" y="{h - pad_b + 3}" text-anchor="end">0</text>']
    for i, m in enumerate(meetings):
        n = counts[i]
        x = pad_l + slot * i + (slot - bw) / 2
        bh = (h - pad_b - pad_t) * n / top
        y = h - pad_b - bh
        r = min(4, bh / 2, bw / 2)
        types = Counter(e["type"] for e in per[m])
        ffs = sum(len(e.get("ffs", [])) for e in per[m])
        tip = f"{m}: 결정 {n}건\n" + " / ".join(f"{TYPE_LABEL[t]} {types[t]}" for t in TYPES) + f"\n미결 FFS {ffs}"
        latest = " latest" if i == len(meetings) - 1 else ""
        path = (f"M{x:.1f},{h - pad_b} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                f"H{x + bw - r:.1f} Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{h - pad_b} Z") if n else ""
        out.append(f'<g class="bar{latest}" tabindex="0" data-tip="{_e(tip)}"><title>{_e(tip)}</title>'
                   f'<rect class="hit" x="{pad_l + slot * i:.1f}" y="{pad_t}" width="{slot:.1f}" height="{h - pad_t:.1f}"/>'
                   + (f'<path d="{path}"/>' if n else "") + "</g>")
        out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 4}" text-anchor="middle">{_e(_short(m))}</text>')
        if latest and n:
            out.append(f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle">{n}</text>')
    out.append("</svg>")
    return "".join(out)


def db_first(db):
    return min((e["meeting"] for e in db["entries"]), key=meeting_sort_key)


def _item_card(item, db, meetings, base):
    latest = meetings[-1]
    mine = [e for e in db["entries"] if e["item"] == item["id"]]
    now = [e for e in mine if e["meeting"] == latest]
    types = Counter(e["type"] for e in now)
    ffs = sum(len(e.get("ffs", [])) for e in now)
    return f"""<article class="card">
  <div class="card-head"><h3>{_e(item["name"])}</h3><span class="rel">{_e(item.get("release", ""))}</span></div>
  <dl class="stats">
    <div><dt>Agreement</dt><dd>{types["Agreement"]}</dd></div>
    <div><dt>WA</dt><dd>{types["Working Assumption"]}</dd></div>
    <div><dt>미결 FFS</dt><dd>{ffs}</dd></div>
    <div><dt>누적 결정</dt><dd>{len(mine)}</dd></div>
  </dl>
  <span class="basis">앞의 세 값은 {_e(latest)} 기준, 누적은 {_e(_short(db_first(db)))}부터</span>
  {_bar_chart(item, db, meetings)}
  <div class="card-foot"><span class="muted">회의별 결정 수 · 막대에 올리면 구분별 건수</span>
    {_link(f"{base}by_item/{item['id']}.md", "상세 리포트")}</div>
</article>"""


def _delta_detail(item, d):
    blocks = []
    if d["agenda_new"] or d["agenda_dropped"]:
        blocks.append(f'<p class="agenda-change"><strong>Agenda 신설</strong> {_e(", ".join(d["agenda_new"]) or "없음")}<br>'
                      f'<strong>Agenda 제외</strong> {_e(", ".join(d["agenda_dropped"]) or "없음")}</p>')
    for e in d["wa_confirmed"]:
        blocks.append(f'<div class="items-list"><div><span class="chip confirmed">WA 확정</span> '
                      f'<span class="mono small">{_e(e.get("agenda_item", ""))}</span> '
                      f'<span class="small muted">{_e(e.get("agenda_title", ""))}</span></div>'
                      f'<p class="quote"><span class="text">{_e(e["text"])}</span><span class="src">{_source(e["source"])}</span></p></div>')
    for f in d["ffs_followups"]:
        blocks.append(f"""<div class="items-list">
  <div><span class="chip candidate">후속 결정 후보 · 확인 필요</span>
    <span class="small muted">{_e(f["agenda_title"])} · 키워드 일치 {int(f["score"] * 100)}%</span></div>
  <div class="pair">
    <p class="quote"><span class="eyebrow">{_e(d["prev"])} FFS</span>
<span class="text">{_e(f["ffs"])}</span><span class="src">{_source(f["prev_source"])}</span></p>
    <p class="quote"><span class="eyebrow">{_e(d["cur"])} 결정</span>
<span class="text">{_e(f["candidate_text"])}</span><span class="src">{_source(f["candidate_source"])}</span></p>
  </div>
</div>""")
    if not blocks:
        return ""
    count = len(d["wa_confirmed"]) + len(d["ffs_followups"])
    return f"""<details>
  <summary><h3>{_e(item["name"])}</h3><span class="small muted">WA 확정 {len(d["wa_confirmed"])} ·
    FFS 후속 후보 {len(d["ffs_followups"])} · Agenda +{len(d["agenda_new"])}/−{len(d["agenda_dropped"])}</span></summary>
  <div class="detail-body">{"".join(blocks)}</div>
</details>""" if count or d["agenda_new"] or d["agenda_dropped"] else ""


def _topics_section(config, db, meetings, base):
    names = {i["id"]: i["name"] for i in config["items"]}
    nav, blocks = [], []
    for t in config["topics"]:
        found = topics.entries_for(db, t)
        per = Counter(e["meeting"] for e in found)
        nav.append(f'<a href="#topic-{_e(t["id"])}">{_e(t["name"])}<span class="num">{len(found)}</span></a>')
        counts = " · ".join(f"{_e(_short(m))} {per[m]}" for m in meetings)
        rows = "".join(
            f'<tr><td class="mono">{_e(e["meeting"])}</td>'
            f'<td><span class="mono">{_e(e.get("agenda_item", ""))}</span><br><span class="small muted">{_e(e.get("agenda_title", ""))}</span></td>'
            f'<td class="small">{_e(names.get(e["item"], e["item"]))}</td><td class="small">{_e(e["type"])}</td>'
            f'<td><div class="cell-text small">{_e(e["text"])}</div></td><td class="small">{_source(e["source"])}</td></tr>'
            for e in reversed(found))
        body = (f'<div class="table-scroll"><table><thead><tr><th>회의</th><th>Agenda</th><th>아이템</th><th>구분</th>'
                f'<th>내용</th><th>출처</th></tr></thead><tbody>{rows}</tbody></table></div>'
                if found else '<p class="empty">해당 결정이 없습니다</p>')
        blocks.append(f"""<details id="topic-{_e(t["id"])}">
  <summary><h3>{_e(t["name"])}</h3><span class="small muted">{len(found)}건 · 키워드 {_e(", ".join(t["keywords"]))}</span>
    <span class="counts">{counts}</span></summary>
  <div class="detail-body">{body}
    <span class="small">{_link(f"{base}by_topic/{t['id']}.md", "마크다운 리포트")}</span></div>
</details>""")
    return f"""<section>
  <h2>주제별 보기</h2>
  <p class="lede">Agenda와 관계없이 본문이나 Agenda 제목에 키워드가 나오는 결정을 모았습니다. 한 결정이 여러 주제에 들어갈 수 있습니다.
    주제는 config/tracked_items.yaml의 topics에 추가합니다.</p>
  <nav class="topic-nav">{"".join(nav)}</nav>
  {"".join(blocks)}
</section>"""


def render_body(config, db):
    meetings = sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)
    base = config.get("report_base_url", "")
    if not meetings:
        return f'<main class="wrap"><header><h1>{TITLE}</h1></header><p class="empty">아직 처리된 회의가 없습니다</p></main>'
    latest = meetings[-1]
    total = len(db["entries"])
    parts = [f"""<main class="wrap">
<header>
  <span class="eyebrow">3GPP TSG RAN WG1 · Chair notes 기준</span>
  <h1>{TITLE}</h1>
  <dl class="facts">
    <div><dt>최신 회의</dt><dd>{_e(latest)}</dd></div>
    <div><dt>추적 범위</dt><dd>{_e(meetings[0])} – {_e(_short(latest))} ({len(meetings)}회)</dd></div>
    <div><dt>누적 결정</dt><dd>{total:,}</dd></div>
  </dl>
</header>"""]

    deltas = []
    if len(meetings) > 1:
        prev = meetings[-2]
        deltas = [(item, delta.compute(db, item["id"], prev, latest)) for item in config["items"]]
        rows = "".join(
            f"<tr><td>{_e(item['name'])}</td>{_num(sum(d['new'].values()))}{_num(len(d['wa_confirmed']))}"
            f"{_num(d['prev_ffs'])}{_num(len(d['ffs_followups']))}"
            f"<td class=\"num\">+{len(d['agenda_new'])} / −{len(d['agenda_dropped'])}</td></tr>"
            for item, d in deltas)
        parts.append(f"""<section>
  <h2>직전 회의 대비 <span class="mono muted">{_e(prev)} → {_e(latest)}</span></h2>
  <p class="lede">WA 확정은 합의 원문에 "Confirm … working assumption" 문구가 있는 경우입니다.
    FFS 후속 결정 후보는 직전 회의 FFS와 키워드가 겹치는 같은 Agenda의 결정을 자동으로 찾은 것이라, 해소 여부는 원문으로 확인해야 합니다.</p>
  <div class="table-scroll"><table>
    <thead><tr><th>아이템</th><th class="num">신규 결정</th><th class="num">WA 확정</th><th class="num">직전 FFS</th>
      <th class="num">FFS 후속 후보</th><th class="num">Agenda 신설 / 제외</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>""")

    cards = "".join(_item_card(item, db, meetings, base) for item in config["items"])
    parts.append(f'<section><h2>아이템별 현황</h2><div class="cards">{cards}</div></section>')

    details = "".join(_delta_detail(item, d) for item, d in deltas)
    if details:
        parts.append(f'<section><h2>Delta 상세 <span class="mono muted">{_e(meetings[-2])} → {_e(latest)}</span></h2>'
                     f'<p class="lede">아이템을 열면 원문 문장과 FTP 출처를 나란히 볼 수 있습니다.</p>{details}</section>')

    if config.get("topics"):
        parts.append(_topics_section(config, db, meetings, base))

    head = "".join(f'<th class="num">{_e(item["name"])}</th>' for item in config["items"])
    body = []
    for m in reversed(meetings):
        c = Counter(e["item"] for e in db["entries"] if e["meeting"] == m)
        cn = db.get("meetings", {}).get(m, {}).get("chair_notes_url")
        body.append(f'<tr><td class="mono">{_link(f"{base}by_meeting/{meeting_slug(m)}.md", m)}</td>'
                    + "".join(_num(c[item["id"]]) for item in config["items"])
                    + _num(sum(c.values()))
                    + f'<td>{_link(cn, "Chair notes") if cn else ""}</td></tr>')
    parts.append(f"""<section>
  <h2>회의별 결정 수</h2>
  <div class="table-scroll"><table class="matrix">
    <thead><tr><th>회의</th>{head}<th class="num">합계</th><th>원문</th></tr></thead>
    <tbody>{"".join(body)}</tbody>
  </table></div>
</section>
<footer>모든 수치는 3GPP FTP의 회의 종료본 Chair notes에서 추출한 Agreement · Working Assumption · Conclusion입니다.
  이 페이지는 scripts/render_html.py가 자동으로 생성합니다.</footer>
</main>
<div id="tip" hidden></div>""")
    return "\n".join(parts)


def render_html(config, db, standalone=True):
    fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
             '&family=IBM+Plex+Sans+KR:wght@400;600;700&display=swap">')
    inner = (f"<title>{TITLE}</title>\n"
             f'<meta name="claude:viewport-fit-sides" content="cover">\n{fonts}\n<style>{CSS}</style>\n'
             f"{render_body(config, db)}\n<script>{SCRIPT}</script>\n")
    if not standalone:
        return inner
    return ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{inner.split('<style>')[0]}<style>{CSS}</style>\n</head>\n<body>\n"
            f"{render_body(config, db)}\n<script>{SCRIPT}</script>\n</body>\n</html>\n")
