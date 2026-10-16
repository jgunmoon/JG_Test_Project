"""누적 DB(data/agreements_db.json)로부터 마크다운 리포트를 생성합니다.

    python -m scripts.generate_report

리포트는 DB와 설정만으로 결정되며(같은 입력이면 같은 출력), 직접 수정하지 않습니다.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TYPES = ("Agreement", "Working Assumption", "Conclusion")
SOURCE_KINDS = ("chairman_note", "tdoc", "tr", "ts")
GENERATED_NOTE = "> 이 파일은 `scripts/generate_report.py`가 자동으로 생성합니다. 직접 수정하지 마세요."


class ValidationError(ValueError):
    pass


def meeting_sort_key(meeting_id):
    m = re.fullmatch(r"RAN1#(\d+)(.*)", meeting_id)
    if not m:
        raise ValidationError(f"meeting id must look like 'RAN1#118': {meeting_id!r}")
    return int(m.group(1)), m.group(2)


def meeting_slug(meeting_id):
    return meeting_id.lower().replace("#", "_")


def validate_db(db, config=None):
    seen = set()
    for e in db["entries"]:
        where = f"entry {e.get('id')!r}"
        if e.get("id") in seen:
            raise ValidationError(f"{where}: duplicate id")
        seen.add(e.get("id"))
        meeting_sort_key(e.get("meeting", ""))
        path = e.get("agenda_path") or []
        if not path or not all(n.get("number") and n.get("title") for n in path):
            raise ValidationError(f"{where}: agenda_path (번호와 제목) is required")
        if e.get("type") not in TYPES:
            raise ValidationError(f"{where}: type must be one of {TYPES}")
        if not e.get("text"):
            raise ValidationError(f"{where}: text is empty")
        source = e.get("source") or {}
        for field in ("doc", "url"):
            if not source.get(field):
                raise ValidationError(f"{where}: source.{field} is required")
        if source.get("kind") not in SOURCE_KINDS:
            raise ValidationError(f"{where}: source.kind must be one of {SOURCE_KINDS}")


def _cell(text):
    return text.strip().replace("|", "\\|").replace("\n", "<br>")


def _source_link(source):
    parts = [f"[{source['doc']}]({source['url']})"]
    if source.get("tdoc"):
        parts.append(f"[{source['tdoc']}]({source['tdoc_url']})" if source.get("tdoc_url") else source["tdoc"])
    if source.get("discussion"):
        parts.append(f"`[{source['discussion']}]`")
    return "<br>".join(parts)


def _sorted_entries(entries):
    return sorted(entries, key=lambda e: (meeting_sort_key(e["meeting"]), e["id"]))


def _meetings(db):
    return sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "agenda"


def all_sections(index):
    """최신 회의의 최상위 Agenda(번호 순) + 최신 회의에는 없는 과거 최상위 Agenda."""
    from scripts import agenda  # agenda가 이 모듈을 import하므로 함수 안에서 불러옵니다

    current = agenda.sections(index)
    keys = {s["key"] for s in current}
    old = {}
    for lin in agenda.retired(index):
        k = agenda.norm(lin["section_title"])
        if k not in keys and k not in old:
            old[k] = {"number": lin["path"][0]["number"], "title": lin["section_title"], "key": k,
                      "retired_after": lin["last_meeting"]}
    return current + list(old.values())


def _short(meeting):
    return meeting.replace("RAN1", "")


def _counts_line(counts, meetings):
    return " · ".join(f"{_short(m)} {counts.get(m, 0)}" for m in meetings)


def render_section_report(section, index, db):
    from scripts import agenda, delta

    meetings = index["meetings"]
    mine = [e for e in db["entries"] if agenda.section_key(e) == section["key"]]
    lines = [f"# {section['number']} {section['title']}", "", GENERATED_NOTE, "",
             "공식 Agenda 기준으로 이 섹션의 결정을 모았습니다. 번호는 최신 회의 기준이며, 회의 간 연결은 "
             "같은 섹션 안의 같은 Agenda 제목으로 합니다.", ""]
    if section.get("retired_after"):
        lines += [f"> 이 섹션은 {section['retired_after']} 이후 Agenda에 없습니다.", ""]

    per = Counter(e["meeting"] for e in mine)
    lines += ["## 회의별 결정 수", "", "```mermaid", "timeline", f"    title {section['title']}"]
    lines += [f"    {m.replace('#', '#35;')} : 결정 {per[m]}" for m in meetings if per[m]]
    lines += ["```", ""]

    if len(meetings) > 1 and not section.get("retired_after"):
        d = delta.compute(db, section["key"], meetings[-2], meetings[-1])
        lines += _render_delta(d)

    rows = [] if section.get("retired_after") else [r for r in agenda.tree(index) if r["section"] == section["key"]]
    by_key = defaultdict(list)
    for e in mine:
        by_key[index["entry_keys"][e["id"]]].append(e)
    for r in rows:
        lines += [f"{'#' * min(2 + r['depth'], 6)} {r['number']} {r['title']}", ""]
        lines.append(f"회의별 결정 수 (하위 Agenda 포함): {_counts_line(r['counts'], meetings)}")
        if r["key"]:
            lin = index["lineages"][r["key"]]
            hist = agenda.number_history(lin, meetings)
            if hist:
                lines.append(f"\n번호 변경: {hist}")
            lines += ["", "| 회의 | 번호 | 구분 | 내용 | 출처 |", "|---|---|---|---|---|"]
            lines += [f"| {e['meeting']} | {e['agenda_item']} | {e['type']} | {_cell(e['text'])} | {_source_link(e['source'])} |"
                      for e in _sorted_entries(by_key[r["key"]])]
        lines.append("")

    old = [lin for lin in agenda.retired(index) if agenda.norm(lin["section_title"]) == section["key"]]
    if old:
        lines += ["## 최신 회의에는 없는 Agenda", "",
                  "삭제됐거나 제목이 바뀐 Agenda입니다. 제목이 바뀐 경우에도 자동으로 잇지 않으니 위 목록과 비교해 보세요.", ""]
        for lin in old:
            lines += [f"### {lin['last_number']} {lin['title']} (마지막: {lin['last_meeting']})", "",
                      f"회의별 결정 수: {_counts_line(lin['counts'], meetings)}", "",
                      "| 회의 | 번호 | 구분 | 내용 | 출처 |", "|---|---|---|---|---|"]
            lines += [f"| {e['meeting']} | {e['agenda_item']} | {e['type']} | {_cell(e['text'])} | {_source_link(e['source'])} |"
                      for e in _sorted_entries(by_key[lin["key"]])]
            lines.append("")
    return "\n".join(lines)


def _render_delta(d):
    from scripts import delta

    lines = [f"## 직전 회의 대비 ({d['prev']} → {d['cur']})", "",
             f"- 신규 결정 {sum(d['new'].values())}건 (Agreement {d['new']['Agreement']}, "
             f"Working Assumption {d['new']['Working Assumption']}, Conclusion {d['new']['Conclusion']})",
             f"- Agenda 신설: {', '.join(d['agenda_new']) or '없음'}",
             f"- Agenda 제외: {', '.join(d['agenda_dropped']) or '없음'}", ""]
    if d["wa_confirmed"]:
        lines += ["**Working Assumption 확정** (원문에 'Confirm ... working assumption' 문구가 있는 결정)", "",
                  "| Agenda | 내용 | 출처 |", "|---|---|---|"]
        lines += [f"| {e['agenda_item']} {_cell(e['agenda_title'])} | {_cell(e['text'])} | {_source_link(e['source'])} |"
                  for e in d["wa_confirmed"]]
        lines.append("")
    if d["ffs_followups"]:
        lines += [f"**FFS 후속 결정 후보** — {d['prev']} FFS와 키워드가 {int(delta.MIN_SCORE * 100)}% 이상 겹치는 "
                  f"같은 Agenda의 {d['cur']} 결정입니다. 자동 매칭 후보이므로 FFS 해소 여부는 원문으로 확인하세요.", "",
                  f"| Agenda | {d['prev']} FFS | {d['cur']} 후보 결정 | 일치율 | 출처 |", "|---|---|---|---|---|"]
        for f in d["ffs_followups"]:
            lines.append(f"| {_cell(f['agenda_title'])} | {_cell(f['ffs'])} | {_cell(f['candidate_text'])} "
                         f"| {int(f['score'] * 100)}% | FFS: {_source_link(f['prev_source'])}<br>"
                         f"후보: {_source_link(f['candidate_source'])} |")
        lines.append("")
    return lines


def render_meeting_report(meeting, config, db):
    lines = [f"# {meeting} 결과 요약", "", GENERATED_NOTE, ""]
    groups = defaultdict(list)
    for e in db["entries"]:
        if e["meeting"] == meeting:
            groups[tuple((n["number"], n["title"]) for n in e["agenda_path"])].append(e)

    def num_key(path):
        return tuple(int(x) for x in path[-1][0].split(".") if x.isdigit())

    for path in sorted(groups, key=num_key):
        number, title = path[-1]
        lines += [f"## {number} {title}", ""]
        if len(path) > 1:
            lines += [" › ".join(f"{n} {t}" for n, t in path[:-1]), ""]
        lines += ["| 구분 | 내용 | 출처 |", "|---|---|---|"]
        lines += [f"| {e['type']} | {_cell(e['text'])} | {_source_link(e['source'])} |" for e in _sorted_entries(groups[path])]
        lines.append("")
    return "\n".join(lines)


def render_dashboard(config, db):
    from scripts import agenda, delta

    lines = ["# RAN1 6G PHY 트래커 대시보드", "", GENERATED_NOTE, ""]
    meetings = _meetings(db)
    if not meetings:
        return "\n".join(lines + ["아직 처리된 회의가 없습니다.", ""])
    index = agenda.build_index(db)
    latest = meetings[-1]
    lines += [f"**최신 회의: {latest}** ([전체 결과](by_meeting/{meeting_slug(latest)}.md)) · "
              f"추적 {meetings[0]}–{_short(latest)} · 누적 결정 {len(db['entries']):,}건", "",
              "공식 Agenda의 최상위 항목(섹션)별 현황입니다. 미결 FFS는 최신 회의 결정 안에 남아 있는 FFS 항목 수입니다.", "",
              "| 섹션 (최신 번호) | 최신 Agreement | 최신 WA | 최신 Conclusion | 미결 FFS | 누적 결정 | 상세 |",
              "|---|---|---|---|---|---|---|"]
    for sec in all_sections(index):
        mine = [e for e in db["entries"] if agenda.section_key(e) == sec["key"]]
        now = [e for e in mine if e["meeting"] == latest]
        c = Counter(e["type"] for e in now)
        name = f"{sec['number']} {sec['title']}" + (f" (~{sec['retired_after']})" if sec.get("retired_after") else "")
        lines.append(f"| {name} | {c['Agreement']} | {c['Working Assumption']} | {c['Conclusion']} "
                     f"| {sum(len(e.get('ffs', [])) for e in now)} | {len(mine)} | [보기](by_agenda/{slug(sec['title'])}.md) |")
    if len(meetings) > 1:
        prev = meetings[-2]
        lines += ["", f"## 직전 회의 대비 ({prev} → {latest})", "",
                  "FFS 후속 결정 후보는 키워드 자동 매칭 결과입니다. 섹션 리포트에서 원문과 함께 확인하세요.", "",
                  "| 섹션 | 신규 결정 | WA 확정 | 직전 FFS | FFS 후속 결정 후보 | Agenda 신설 / 제외 |",
                  "|---|---|---|---|---|---|"]
        for sec in agenda.sections(index):
            d = delta.compute(db, sec["key"], prev, latest)
            lines.append(f"| {sec['number']} {sec['title']} | {sum(d['new'].values())} | {len(d['wa_confirmed'])} "
                         f"| {d['prev_ffs']} | {len(d['ffs_followups'])} | +{len(d['agenda_new'])} / -{len(d['agenda_dropped'])} |")
    lines += ["", "보기 좋은 화면, Agenda 목차, 전체 결정 키워드 검색은 같은 폴더의 `index.html`(HTML 대시보드)을 브라우저로 여세요.",
              "", "## 회의별 리포트", ""]
    lines += [f"- [{m}](by_meeting/{meeting_slug(m)}.md)" for m in reversed(meetings)]
    return "\n".join(lines + [""])


def write_reports(config, db, out_dir):
    import shutil

    from scripts import agenda

    validate_db(db)
    out_dir = Path(out_dir)
    for sub in ("by_agenda", "by_meeting"):
        shutil.rmtree(out_dir / sub, ignore_errors=True)  # 사라진 섹션·회의 파일이 남지 않도록 매번 새로 만듭니다
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir / "by_item", ignore_errors=True)  # 예전 아이템별 리포트
    (out_dir / "README.md").write_text(render_dashboard(config, db), encoding="utf-8")
    if db["entries"]:
        index = agenda.build_index(db)
        for sec in all_sections(index):
            (out_dir / "by_agenda" / f"{slug(sec['title'])}.md").write_text(
                render_section_report(sec, index, db), encoding="utf-8")
    for meeting in _meetings(db):
        (out_dir / "by_meeting" / f"{meeting_slug(meeting)}.md").write_text(
            render_meeting_report(meeting, config, db), encoding="utf-8")
    from scripts.render_html import render_html  # render_html이 이 모듈을 import하므로 함수 안에서 불러옵니다
    (out_dir / "index.html").write_text(render_html(config, db), encoding="utf-8")


def main():
    config = yaml.safe_load((ROOT / "config" / "tracked_items.yaml").read_text(encoding="utf-8"))
    db = json.loads((ROOT / "data" / "agreements_db.json").read_text(encoding="utf-8"))
    try:
        write_reports(config, db, ROOT / "reports")
    except ValidationError as err:
        sys.exit(f"DB 검증 실패: {err}")


if __name__ == "__main__":
    main()
