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
    lines += ["```", "", "## 누적 히스토리", "",
              "| 회의 | Agenda | 구분 | 내용 | 출처 |", "|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['meeting']} | {e.get('agenda_item', '')} | {e['type']} "
                     f"| {_cell(e['text'])} | {_source_link(e['source'])} |")
    return "\n".join(lines + [""])


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
    lines += ["", "## 회의별 리포트", ""]
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


def main():
    config = yaml.safe_load((ROOT / "config" / "tracked_items.yaml").read_text(encoding="utf-8"))
    db = json.loads((ROOT / "data" / "agreements_db.json").read_text(encoding="utf-8"))
    try:
        write_reports(config, db, ROOT / "reports")
    except ValidationError as err:
        sys.exit(f"DB 검증 실패: {err}")


if __name__ == "__main__":
    main()
