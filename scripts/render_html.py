"""누적 DB로 팀 공용 HTML 대시보드(reports/index.html)를 만듭니다.

generate_report가 마크다운 리포트와 함께 호출합니다. 외부 스크립트 없이 한 파일로 동작하며
(글꼴만 Google Fonts, 없으면 시스템 글꼴), 같은 DB면 같은 HTML이 나옵니다.
상세 리포트 링크는 config의 report_base_url 기준입니다 (비우면 reports/ 기준 상대 경로).
"""
import json
from collections import Counter, defaultdict
from html import escape

from scripts import agenda, delta
from scripts.generate_report import TYPES, all_sections, meeting_slug, meeting_sort_key, slug

TITLE = "RAN1 6G PHY Tracker"
TYPE_LABEL = {"Agreement": "Agreement", "Working Assumption": "WA", "Conclusion": "Conclusion"}

CSS = """
/* 레이아웃: 검색 → 직전 회의 대비 → Agenda 목차(펼치면 결정) → 섹션 카드(작은 막대그래프) → Delta 상세 → 회의 목록 */
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #14181f; --ink-2: #4a5260; --ink-3: #737b88;
  --rule: #dfe3e9; --accent: #2a78d6; --accent-soft: #b9d2f1; --candidate: #8a5a00; --candidate-bg: #fff3d6;
  --confirmed: #0d6b3c; --confirmed-bg: #dcf3e6; --mark: #ffe08a;
  --font-body: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  --font-data: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11141a; --panel: #181c24; --ink: #eef1f5; --ink-2: #b8c0cc; --ink-3: #8b94a3;
  --rule: #2a313d; --accent: #3987e5; --accent-soft: #2c4a72; --candidate: #f2c46b; --candidate-bg: #3a2f14;
  --confirmed: #7fd9a6; --confirmed-bg: #173526; --mark: #6b5208; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11141a; --panel: #181c24; --ink: #eef1f5; --ink-2: #b8c0cc; --ink-3: #8b94a3;
  --rule: #2a313d; --accent: #3987e5; --accent-soft: #2c4a72; --candidate: #f2c46b; --candidate-bg: #3a2f14;
  --confirmed: #7fd9a6; --confirmed-bg: #173526; --mark: #6b5208; color-scheme: dark; }
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
details { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; min-width: 0; }
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
.search { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; display: grid; gap: 12px; min-width: 0; }
.search input[type=search] { width: 100%; box-sizing: border-box; font: inherit; font-size: 16px; padding: 10px 12px;
  border: 1px solid var(--rule); border-radius: 6px; background: var(--bg); color: var(--ink); }
.search input[type=search]:focus-visible, .search select:focus-visible, .search button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; font-size: 13px; }
.filters label { display: inline-flex; gap: 6px; align-items: center; color: var(--ink-2); }
.filters select { font: inherit; font-size: 13px; padding: 4px 6px; border: 1px solid var(--rule); border-radius: 6px; background: var(--bg); color: var(--ink); max-width: 100%; }
.presets { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 13px; color: var(--ink-3); }
.presets button, .more { font: inherit; font-size: 13px; padding: 3px 10px; border: 1px solid var(--rule); border-radius: 999px;
  background: var(--bg); color: var(--accent); cursor: pointer; }
.summary-line { font-size: 13px; color: var(--ink-2); }
.summary-line .num { color: var(--ink); }
.results { display: grid; gap: 10px; min-width: 0; }
.result { border-top: 1px solid var(--rule); padding-top: 10px; display: grid; gap: 6px; min-width: 0; }
.result-head { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; font-size: 13px; }
.result-head .type { font-size: 12px; color: var(--ink-3); }
.result .src { font-size: 12px; color: var(--ink-3); overflow-wrap: anywhere; }
mark { background: var(--mark); color: inherit; border-radius: 2px; padding: 0 1px; }
table.tree td { padding-top: 6px; padding-bottom: 6px; }
table.tree td.agenda { min-width: 28ch; }
table.tree .depth-0 td { background: var(--bg); font-weight: 600; }
.agenda-num { font-family: var(--font-data); font-size: 13px; margin-right: 8px; }
.hist { display: block; font-size: 12px; color: var(--ink-3); }
.toggle { font: inherit; font-size: 12px; padding: 2px 8px; border: 1px solid var(--rule); border-radius: 999px;
  background: var(--panel); color: var(--accent); cursor: pointer; white-space: nowrap; }
.agenda-entries { display: grid; gap: 10px; padding: 4px 4px 8px; }
.cell-text { white-space: pre-line; max-height: 9em; overflow-y: auto; min-width: 24ch; overflow-wrap: anywhere; }
.counts { font-family: var(--font-data); font-size: 12px; color: var(--ink-3); }
footer { font-size: 13px; color: var(--ink-3); border-top: 1px solid var(--rule); padding-top: 16px; }
#tip { position: fixed; pointer-events: none; z-index: 20; background: var(--ink); color: var(--bg);
  font-family: var(--font-data); font-size: 12px; padding: 6px 8px; border-radius: 4px; white-space: pre; }
@media (max-width: 520px) { h1 { font-size: 24px; } .stats { grid-template-columns: repeat(2, 1fr); } }
@media (prefers-reduced-motion: no-preference) { details > summary { transition: background-color .15s; } }
"""

SCRIPT = r"""
(() => {
  const dataEl = document.getElementById('decisions');
  if (!dataEl) return;
  const DATA = JSON.parse(dataEl.textContent);
  const $ = id => document.getElementById(id);
  const q = $('q'), fSection = $('f-section'), fMeeting = $('f-meeting'), fType = $('f-type'), fWord = $('f-word');
  const out = $('results'), summary = $('summary'), PAGE = 50;
  let hits = [], shown = 0, timer;
  const opt = (sel, value, label) => { const o = document.createElement('option'); o.value = value; o.textContent = label; sel.append(o); };
  DATA.sections.forEach(([key, label]) => opt(fSection, key, label));
  [...DATA.meetings].reverse().forEach(m => opt(fMeeting, m, m));
  const esc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = (t, word) => word ? `(?<![A-Za-z0-9])${esc(t)}(?![A-Za-z0-9])` : esc(t);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const link = (url, label) => { if (!/^https:\/\//.test(url || '')) return el('span', null, label);
    const a = el('a', null, label); a.href = url; a.target = '_blank'; a.rel = 'noopener'; return a; };
  function highlight(node, text, re) {
    if (!re) { node.textContent = text; return; }
    let last = 0;
    for (const m of text.matchAll(re)) {
      if (!m[0]) continue;
      node.append(text.slice(last, m.index), el('mark', null, m[0]));
      last = m.index + m[0].length;
    }
    node.append(text.slice(last));
  }
  function render(e, re) {
    const box = el('article', 'result');
    const head = el('div', 'result-head');
    head.append(el('span', 'mono', e.meeting), el('span', 'mono', e.agenda_item),
      el('span', 'muted', e.agenda_title), el('span', 'type', e.type));
    const text = el('div', 'cell-text small'); highlight(text, e.text, re);
    const src = el('div', 'src'); const s = e.source;
    src.append(link(s.url, s.doc));
    if (s.tdoc) src.append(' · ', link(s.tdoc_url, s.tdoc));
    if (s.discussion) src.append(' · ', el('span', 'mono', `[${s.discussion}]`));
    box.append(head, text, src);
    return box;
  }
  function showMore(re) {
    out.querySelector('.more')?.remove();
    hits.slice(shown, shown + PAGE).forEach(e => out.append(render(e, re)));
    shown = Math.min(shown + PAGE, hits.length);
    if (shown < hits.length) {
      const b = el('button', 'more', `더 보기 (남은 ${hits.length - shown}건)`);
      b.type = 'button'; b.addEventListener('click', () => showMore(re)); out.append(b);
    }
  }
  function run() {
    // 'A B | C' 또는 'A B OR C' → (A 그리고 B) 또는 C. 대문자 OR만 연산자로 봅니다.
    const groups = q.value.trim().split(/\s+OR\s+|\s*\|\s*/).map(g => g.split(/\s+/).filter(Boolean)).filter(g => g.length);
    const terms = groups.flat();
    const filtered = fSection.value || fMeeting.value || fType.value;
    out.replaceChildren(); shown = 0;
    if (!terms.length && !filtered) {
      summary.textContent = `검색어를 입력하거나 필터를 고르세요. 전체 ${DATA.entries.length.toLocaleString()}건에서 찾습니다.`;
      hits = []; return;
    }
    const groupRes = groups.map(g => g.map(t => new RegExp(pattern(t, fWord.checked), 'i')));
    const has = (e, r) => r.test(e.text) || r.test(e.agenda_title);
    const re = terms.length ? new RegExp(terms.map(t => pattern(t, fWord.checked)).join('|'), 'gi') : null;
    hits = DATA.entries.filter(e =>
      (!fSection.value || e.section === fSection.value) && (!fMeeting.value || e.meeting === fMeeting.value) &&
      (!fType.value || e.type === fType.value) &&
      (!groupRes.length || groupRes.some(g => g.every(r => has(e, r))))).reverse();
    const per = {}; hits.forEach(e => { per[e.meeting] = (per[e.meeting] || 0) + 1; });
    summary.replaceChildren(el('span', 'num', `${hits.length.toLocaleString()}건`),
      hits.length ? ' · 회의별 ' + DATA.meetings.filter(m => per[m]).map(m => `${m.replace('RAN1#', '#')} ${per[m]}`).join(' · ')
                  : ' · 일치하는 결정이 없습니다. 철자나 필터를 확인하세요.');
    showMore(re);
  }
  [q].forEach(n => n.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 150); }));
  [fSection, fMeeting, fType, fWord].forEach(n => n.addEventListener('change', run));
  // Agenda 목차: '결정 보기'를 누르면 그 Agenda의 결정을 최신 회의부터 펼칩니다 (회의 간 같은 Agenda 포함).
  document.querySelectorAll('[data-agenda]').forEach(btn => btn.addEventListener('click', () => {
    const row = btn.closest('tr').nextElementSibling, box = row.querySelector('.agenda-entries');
    if (!box.childElementCount) DATA.entries.filter(e => e.key === btn.dataset.agenda).reverse().forEach(e => box.append(render(e, null)));
    row.hidden = !row.hidden;
    btn.setAttribute('aria-expanded', String(!row.hidden));
    btn.textContent = (row.hidden ? '결정 보기' : '접기') + ` (${btn.dataset.count})`;
  }));
  document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => { q.value = b.dataset.preset; run(); q.focus(); }));
  run();
})();
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


def _bar_chart(label, entries, meetings):
    per = {m: [e for e in entries if e["meeting"] == m] for m in meetings}
    counts = [len(per[m]) for m in meetings]
    top = max(counts) if counts else 0
    if not top:
        return '<div class="empty">아직 기록된 결정이 없습니다</div>'
    w, h, pad_l, pad_b, pad_t = 300, 110, 26, 18, 14
    slot = (w - pad_l) / len(meetings)
    bw = min(26, slot * 0.6)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" '
           f'aria-label="{_e(label)} 회의별 결정 수 (최대 {top}건)">',
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


def _section_card(sec, entries, meetings, base):
    latest = meetings[-1]
    now = [e for e in entries if e["meeting"] == latest]
    types = Counter(e["type"] for e in now)
    ffs = sum(len(e.get("ffs", [])) for e in now)
    return f"""<article class="card">
  <div class="card-head"><h3>{_e(sec["title"])}</h3><span class="rel">Agenda {_e(sec["number"])}</span></div>
  <dl class="stats">
    <div><dt>Agreement</dt><dd>{types["Agreement"]}</dd></div>
    <div><dt>WA</dt><dd>{types["Working Assumption"]}</dd></div>
    <div><dt>미결 FFS</dt><dd>{ffs}</dd></div>
    <div><dt>누적 결정</dt><dd>{len(entries)}</dd></div>
  </dl>
  <span class="basis">앞의 세 값은 {_e(latest)} 기준, 누적은 {_e(_short(meetings[0]))}부터</span>
  {_bar_chart(sec["title"], entries, meetings)}
  <div class="card-foot"><span class="muted">회의별 결정 수 · 막대에 올리면 구분별 건수</span>
    {_link(f"{base}by_agenda/{slug(sec['title'])}.md", "섹션 리포트")}</div>
</article>"""


def _delta_detail(name, d):
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
    return f"""<details>
  <summary><h3>{_e(name)}</h3><span class="small muted">WA 확정 {len(d["wa_confirmed"])} ·
    FFS 후속 후보 {len(d["ffs_followups"])} · Agenda +{len(d["agenda_new"])}/−{len(d["agenda_dropped"])}</span></summary>
  <div class="detail-body">{"".join(blocks)}</div>
</details>"""


def _toggle(key, count, cols):
    return (f'<td><button type="button" class="toggle" data-agenda="{_e(key)}" data-count="{count}" '
            f'aria-expanded="false">결정 보기 ({count})</button></td></tr>'
            f'<tr class="agenda-detail" hidden><td colspan="{cols}"><div class="agenda-entries"></div></td></tr>')


def _agenda_tree(index, sections, meetings, base):
    heads = "".join(f'<th class="num">{_e(_short(m))}</th>' for m in meetings)
    cols = len(meetings) + 3
    blocks = []
    rows_by_section = defaultdict(list)
    for r in agenda.tree(index):
        rows_by_section[r["section"]].append(r)
    section_counts = defaultdict(lambda: defaultdict(int))
    for e in index["entries"]:
        section_counts[agenda.section_key(e)][e["meeting"]] += 1
    for sec in sections:
        rows = rows_by_section.get(sec["key"], [])
        total = section_counts[sec["key"]]  # 최신 회의에 없는 Agenda의 결정까지 포함한 섹션 전체
        body = []
        for r in rows:
            lin = index["lineages"].get(r["key"]) if r["key"] else None
            hist = agenda.number_history(lin, meetings) if lin else ""
            label = (f'<span class="agenda-num">{_e(r["number"])}</span>{_e(r["title"])}'
                     + (f'<span class="hist">번호 변경 {_e(hist)}</span>' if hist else ""))
            cells = "".join(_num(r["counts"].get(m, 0)) for m in meetings)
            row = (f'<tr class="depth-{r["depth"]}"><td class="agenda" style="padding-left: {12 + 18 * r["depth"]}px">'
                   f'{label}</td>{cells}{_num(sum(r["counts"].values()))}')
            own = sum(lin["counts"].values()) if lin else 0
            body.append(row + (_toggle(r["key"], own, cols) if lin else "<td></td></tr>"))
        blocks.append(f"""<details>
  <summary><h3><span class="agenda-num">{_e(sec["number"])}</span>{_e(sec["title"])}</h3>
    <span class="counts">섹션 전체 {sum(total.values())}건 · {" · ".join(f"{_e(_short(m))} {total.get(m, 0)}" for m in meetings)}</span>
    <span class="small">{_link(f"{base}by_agenda/{slug(sec['title'])}.md", "섹션 리포트")}</span></summary>
  <div class="table-scroll"><table class="tree">
    <thead><tr><th>Agenda ({_e(meetings[-1])} 번호)</th>{heads}<th class="num">합계</th><th></th></tr></thead>
    <tbody>{"".join(body)}</tbody>
  </table></div>
</details>""")

    old = agenda.retired(index)
    if old:
        body = []
        for lin in old:
            cells = "".join(_num(lin["counts"].get(m, 0)) for m in meetings)
            body.append(f'<tr><td class="agenda"><span class="agenda-num">{_e(lin["last_number"])}</span>{_e(lin["title"])}'
                        f'<span class="hist">{_e(lin["section_title"])} · 마지막 {_e(lin["last_meeting"])}</span></td>'
                        f'{cells}{_num(sum(lin["counts"].values()))}' + _toggle(lin["key"], sum(lin["counts"].values()), cols))
        blocks.append(f"""<details>
  <summary><h3>최신 회의에는 없는 Agenda</h3><span class="small muted">{len(old)}개 · 삭제됐거나 제목이 바뀐 Agenda (자동으로 잇지 않음)</span></summary>
  <div class="table-scroll"><table class="tree">
    <thead><tr><th>Agenda (마지막 번호)</th>{heads}<th class="num">합계</th><th></th></tr></thead>
    <tbody>{"".join(body)}</tbody>
  </table></div>
</details>""")
    return f"""<section id="agenda">
  <h2>Agenda 목차</h2>
  <p class="lede">{_e(meetings[-1])}의 공식 Agenda 목차입니다. 표의 숫자는 회의별 결정 수이며 상위 Agenda는 하위 Agenda를 합친 값입니다.
    회의 간에는 같은 섹션 안의 같은 Agenda 제목끼리 이어 붙이고, 번호가 바뀐 경우 함께 표시합니다.
    {_e(meetings[-1])}에 없는 Agenda(삭제·통합·제목 변경)의 결정은 표에서 빠지고 맨 아래 '최신 회의에는 없는 Agenda'에 따로 모았습니다.
    그래서 섹션 제목 옆의 '섹션 전체' 건수가 표의 합계보다 클 수 있습니다.</p>
  {"".join(blocks)}
</section>"""


def _json_for_script(data):
    # 본문에 '</script>'나 '<!--'가 있어도 스크립트 태그가 끝나지 않도록 막습니다.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")


def _search_section(config, db, index, sections, meetings):
    keep = ("meeting", "agenda_item", "agenda_title", "type", "text", "source")
    data = {
        "sections": [[s["key"], f'{s["number"]} {s["title"]}'] for s in sections],
        "meetings": meetings,
        "entries": [{**{k: e.get(k, "") for k in keep}, "key": index["entry_keys"][e["id"]],
                     "section": agenda.section_key(e)}
                    for e in sorted(db["entries"], key=lambda e: (meeting_sort_key(e["meeting"]), e["id"]))],
    }
    presets = "".join(f'<button type="button" data-preset="{_e(p)}">{_e(p)}</button>'
                      for p in config.get("search_presets", []))
    types = "".join(f'<option value="{_e(t)}">{_e(t)}</option>' for t in TYPES)
    return f"""<section id="search">
  <h2>결정 검색</h2>
  <div class="search" role="search">
    <input type="search" id="q" placeholder="예: DMRS | DM-RS, PDCCH REG bundle, codebook OR precoder" autocomplete="off"
      aria-label="결정 원문과 Agenda 제목에서 찾을 키워드">
    <div class="filters">
      <label>섹션 <select id="f-section"><option value="">전체</option></select></label>
      <label>회의 <select id="f-meeting"><option value="">전체</option></select></label>
      <label>구분 <select id="f-type"><option value="">전체</option>{types}</select></label>
      <label><input type="checkbox" id="f-word" checked> 단어 단위로만 찾기</label>
    </div>
    {f'<div class="presets">추천 검색어 {presets}</div>' if presets else ""}
    <div class="summary-line" id="summary" aria-live="polite"></div>
    <div class="results" id="results"></div>
  </div>
  <p class="lede">띄어 쓰면 모두 포함(AND), <span class="mono">|</span> 또는 대문자 <span class="mono">OR</span>로 나누면 하나라도 포함(OR)된 결정을 찾습니다.
    예: <span class="mono">PDCCH REG | PT-RS</span>는 "PDCCH와 REG를 모두 포함" 또는 "PT-RS 포함"입니다. 대소문자는 구분하지 않고, 최신 회의부터 보여줍니다.</p>
  <script type="application/json" id="decisions">{_json_for_script(data)}</script>
</section>"""


def render_body(config, db):
    meetings = sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)
    base = config.get("report_base_url", "")
    if not meetings:
        return f'<main class="wrap"><header><h1>{TITLE}</h1></header><p class="empty">아직 처리된 회의가 없습니다</p></main>'
    index = agenda.build_index(db)
    current = agenda.sections(index)
    every = all_sections(index)
    by_section = defaultdict(list)
    for e in db["entries"]:
        by_section[agenda.section_key(e)].append(e)
    latest = meetings[-1]
    parts = [f"""<main class="wrap">
<header>
  <span class="eyebrow">3GPP TSG RAN WG1 · Chair notes 기준 · 공식 Agenda별</span>
  <h1>{TITLE}</h1>
  <dl class="facts">
    <div><dt>최신 회의</dt><dd>{_e(latest)}</dd></div>
    <div><dt>추적 범위</dt><dd>{_e(meetings[0])} – {_e(_short(latest))} ({len(meetings)}회)</dd></div>
    <div><dt>누적 결정</dt><dd>{len(db["entries"]):,}</dd></div>
  </dl>
</header>"""]
    parts.append(_search_section(config, db, index, every, meetings))

    deltas = []
    if len(meetings) > 1:
        prev = meetings[-2]
        deltas = [(f'{s["number"]} {s["title"]}', delta.compute(db, s["key"], prev, latest)) for s in current]
        rows = "".join(
            f"<tr><td>{_e(name)}</td>{_num(sum(d['new'].values()))}{_num(len(d['wa_confirmed']))}"
            f"{_num(d['prev_ffs'])}{_num(len(d['ffs_followups']))}"
            f"<td class=\"num\">+{len(d['agenda_new'])} / −{len(d['agenda_dropped'])}</td></tr>"
            for name, d in deltas)
        parts.append(f"""<section>
  <h2>직전 회의 대비 <span class="mono muted">{_e(prev)} → {_e(latest)}</span></h2>
  <p class="lede">공식 Agenda 최상위 항목(섹션)별 변화입니다. WA 확정은 합의 원문에 "Confirm … working assumption" 문구가 있는 경우입니다.
    FFS 후속 결정 후보는 직전 회의 FFS와 키워드가 겹치는 같은 Agenda의 결정을 자동으로 찾은 것이라, 해소 여부는 원문으로 확인해야 합니다.</p>
  <div class="table-scroll"><table>
    <thead><tr><th>섹션</th><th class="num">신규 결정</th><th class="num">WA 확정</th><th class="num">직전 FFS</th>
      <th class="num">FFS 후속 후보</th><th class="num">Agenda 신설 / 제외</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>""")

    parts.append(_agenda_tree(index, current, meetings, base))

    cards = "".join(_section_card(s, by_section[s["key"]], meetings, base) for s in current)
    parts.append(f'<section><h2>섹션별 추이</h2><div class="cards">{cards}</div></section>')

    details = "".join(_delta_detail(name, d) for name, d in deltas)
    if details:
        parts.append(f'<section><h2>Delta 상세 <span class="mono muted">{_e(meetings[-2])} → {_e(latest)}</span></h2>'
                     f'<p class="lede">섹션을 열면 원문 문장과 FTP 출처를 나란히 볼 수 있습니다.</p>{details}</section>')

    body = []
    for m in reversed(meetings):
        n = sum(1 for e in db["entries"] if e["meeting"] == m)
        cn = db.get("meetings", {}).get(m, {}).get("chair_notes_url")
        body.append(f'<tr><td class="mono">{_link(f"{base}by_meeting/{meeting_slug(m)}.md", m)}</td>{_num(n)}'
                    f'<td>{_link(cn, "Chair notes") if cn else ""}</td></tr>')
    parts.append(f"""<section>
  <h2>회의별 리포트</h2>
  <div class="table-scroll"><table>
    <thead><tr><th>회의</th><th class="num">결정 수</th><th>원문</th></tr></thead>
    <tbody>{"".join(body)}</tbody>
  </table></div>
</section>
<footer>모든 수치는 3GPP FTP의 회의 종료본 Chair notes에서 추출한 Agreement · Working Assumption · Conclusion입니다.
  분류는 공식 Agenda를 그대로 따릅니다. 이 페이지는 scripts/render_html.py가 자동으로 생성합니다.</footer>
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
