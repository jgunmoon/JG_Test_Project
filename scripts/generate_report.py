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


def validate_db(db, config):
    item_ids = {i["id"] for i in config["items"]}
    seen = set()
    for e in db["entries"]:
        where = f"entry {e.get('id')!r}"
        if e.get("id") in seen:
            raise ValidationError(f"{where}: duplicate id")
        seen.add(e.get("id"))
        meeting_sort_key(e.get("meeting", ""))
        if e.get("item") not in item_ids:
            raise ValidationError(f"{where}: item {e.get('item')!r} is not in config")
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


def render_item_report(item, db):
    entries = _sorted_entries(e for e in db["entries"] if e["item"] == item["id"])
    lines = [f"# {item['name']} ({item.get('release', '')})", "", GENERATED_NOTE, ""]
    if not entries:
        return "\n".join(lines + ["아직 기록된 합의가 없습니다.", ""])

    by_meeting = defaultdict(Counter)
    for e in entries:
        by_meeting[e["meeting"]][e["type"]] += 1
        by_meeting[e["meeting"]]["FFS"] += len(e.get("ffs", []))
    lines += ["## 회의별 진행", "", "```mermaid", "timeline", f"    title {item['name']}"]
    for meeting in sorted(by_meeting, key=meeting_sort_key):
        counts = " : ".join(f"{t} {by_meeting[meeting][t]}" for t in TYPES + ("FFS",) if by_meeting[meeting][t])
        # '#'은 Mermaid에서 엔티티 코드로 써야 그대로 표시됩니다.
        lines.append(f"    {meeting.replace('#', '#35;')} : {counts}")
    lines += ["```", ""]
    lines += _render_item_delta(item, db)
    lines += ["## 누적 히스토리", "",
              "| 회의 | Agenda | 구분 | 내용 | 출처 |", "|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['meeting']} | {e.get('agenda_item', '')} | {e['type']} "
                     f"| {_cell(e['text'])} | {_source_link(e['source'])} |")
    return "\n".join(lines + [""])


def _render_item_delta(item, db):
    from scripts import delta  # delta가 이 모듈을 import하므로 순환 import를 피해 함수 안에서 불러옵니다

    pairs = delta.meeting_pairs(db)
    if not pairs:
        return []
    deltas = [delta.compute(db, item["id"], p, c) for p, c in pairs]
    lines = ["## 회의 간 변화 (Delta)", "",
             "| 직전 → 최신 | 신규 결정 | WA 확정 | 직전 FFS | FFS 후속 결정 후보 | Agenda 신설 / 제외 |",
             "|---|---|---|---|---|---|"]
    for d in reversed(deltas):
        lines.append(f"| {d['prev']} → {d['cur']} | {sum(d['new'].values())} | {len(d['wa_confirmed'])} "
                     f"| {d['prev_ffs']} | {len(d['ffs_followups'])} | +{len(d['agenda_new'])} / -{len(d['agenda_dropped'])} |")
    last = deltas[-1]
    lines += ["", f"### 최신 Delta 상세 ({last['prev']} → {last['cur']})", ""]
    if last["agenda_new"] or last["agenda_dropped"]:
        lines += [f"- Agenda 신설: {', '.join(last['agenda_new']) or '없음'}",
                  f"- Agenda 제외: {', '.join(last['agenda_dropped']) or '없음'}", ""]
    if last["wa_confirmed"]:
        lines += ["**Working Assumption 확정** (원문에 'Confirm ... working assumption' 문구가 있는 결정)", "",
                  "| Agenda | 내용 | 출처 |", "|---|---|---|"]
        lines += [f"| {e.get('agenda_item', '')} | {_cell(e['text'])} | {_source_link(e['source'])} |"
                  for e in last["wa_confirmed"]]
        lines.append("")
    if last["ffs_followups"]:
        lines += [f"**FFS 후속 결정 후보** — {last['prev']} FFS와 키워드가 {int(delta.MIN_SCORE * 100)}% 이상 겹치는 "
                  f"같은 Agenda의 {last['cur']} 결정입니다. 자동 매칭 후보이므로 FFS 해소 여부는 원문으로 확인하세요.", "",
                  f"| Agenda | {last['prev']} FFS | {last['cur']} 후보 결정 | 일치율 | 출처 |", "|---|---|---|---|---|"]
        for f in last["ffs_followups"]:
            lines.append(f"| {_cell(f['agenda_title'])} | {_cell(f['ffs'])} | {_cell(f['candidate_text'])} "
                         f"| {int(f['score'] * 100)}% | FFS: {_source_link(f['prev_source'])}<br>"
                         f"후보: {_source_link(f['candidate_source'])} |")
        lines.append("")
    if not (last["agenda_new"] or last["agenda_dropped"] or last["wa_confirmed"] or last["ffs_followups"]):
        lines += ["직전 회의 대비 Agenda 변화, WA 확정, FFS 후속 후보가 없습니다.", ""]
    return lines


def render_meeting_report(meeting, config, db):
    lines = [f"# {meeting} 결과 요약", "", GENERATED_NOTE, ""]
    for item in config["items"]:
        entries = _sorted_entries(e for e in db["entries"]
                                  if e["meeting"] == meeting and e["item"] == item["id"])
        if not entries:
            continue
        lines += [f"## {item['name']}", "", "| 구분 | 내용 | 출처 |", "|---|---|---|"]
        lines += [f"| {e['type']} | {_cell(e['text'])} | {_source_link(e['source'])} |" for e in entries]
        lines.append("")
    return "\n".join(lines)


def render_dashboard(config, db):
    lines = ["# RAN1 6G PHY 트래커 대시보드", "", GENERATED_NOTE, ""]
    meetings = _meetings(db)
    if not meetings:
        return "\n".join(lines + ["아직 처리된 회의가 없습니다.", ""])

    latest = meetings[-1]
    lines += [f"**최신 회의: {latest}** ([전체 결과](by_meeting/{meeting_slug(latest)}.md))", "",
              "미결 FFS는 최신 회의 결정 안에 남아 있는 FFS 항목 수입니다.", "",
              "| 아이템 | 릴리스 | 신규 Agreement | 신규 Working Assumption | 미결 FFS | 누적 결정 | 상세 |",
              "|---|---|---|---|---|---|---|"]
    for item in config["items"]:
        mine = [e for e in db["entries"] if e["item"] == item["id"]]
        latest_mine = [e for e in mine if e["meeting"] == latest]
        new = Counter(e["type"] for e in latest_mine)
        ffs = sum(len(e.get("ffs", [])) for e in latest_mine)
        lines.append(f"| {item['name']} | {item.get('release', '')} | {new['Agreement']} "
                     f"| {new['Working Assumption']} | {ffs} | {len(mine)} "
                     f"| [보기](by_item/{item['id']}.md) |")
    if len(meetings) > 1:
        from scripts import delta
        prev = meetings[-2]
        lines += ["", f"## 직전 회의 대비 ({prev} → {latest})", "",
                  "FFS 후속 결정 후보는 키워드 자동 매칭 결과입니다. 아이템 리포트에서 원문과 함께 확인하세요.", "",
                  "| 아이템 | 신규 결정 | WA 확정 | 직전 FFS | FFS 후속 결정 후보 | Agenda 신설 / 제외 |",
                  "|---|---|---|---|---|---|"]
        for item in config["items"]:
            d = delta.compute(db, item["id"], prev, latest)
            lines.append(f"| {item['name']} | {sum(d['new'].values())} | {len(d['wa_confirmed'])} | {d['prev_ffs']} "
                         f"| {len(d['ffs_followups'])} | +{len(d['agenda_new'])} / -{len(d['agenda_dropped'])} |")
    lines += ["", "보기 좋은 화면과 전체 결정 키워드 검색은 같은 폴더의 `index.html`(HTML 대시보드)을 브라우저로 여세요.",
              "", "## 회의별 리포트", ""]
    lines += [f"- [{m}](by_meeting/{meeting_slug(m)}.md)" for m in reversed(meetings)]
    return "\n".join(lines + [""])


def write_reports(config, db, out_dir):
    validate_db(db, config)
    out_dir = Path(out_dir)
    (out_dir / "by_item").mkdir(parents=True, exist_ok=True)
    (out_dir / "by_meeting").mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text(render_dashboard(config, db), encoding="utf-8")
    for item in config["items"]:
        (out_dir / "by_item" / f"{item['id']}.md").write_text(render_item_report(item, db), encoding="utf-8")
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
