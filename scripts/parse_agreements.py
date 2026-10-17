"""Chair notes(.docx)에서 Agreement / Working Assumption / Conclusion을 추출해 DB에 반영합니다.

    python -m scripts.parse_agreements <chair_notes.docx> --folder TSGR1_126 --url <FTP 원문 URL>

Chair notes 구조 (RAN1#126 기준으로 확인):
- Agenda 번호는 제목 텍스트에 없고 Word 자동 번호의 레벨(ilvl)로만 표현됩니다.
  Heading 스타일 이름(Heading 1~4)은 실제 계층과 다를 수 있어 ilvl을 기준으로 삼습니다.
- 구간마다 다른 번호 목록(numId)을 쓰지만 Agenda 번호는 문서 전체에서 이어지므로,
  번호가 붙은 제목을 모두 하나의 계층으로 셉니다. 계산 결과는 FL summary 제목에 적힌
  Agenda 번호와 대조해 어긋나면 경고합니다.
- 공식 Agenda(agenda.csv, RAN1#124부터 FTP에 있음)가 있으면 제목을 대조해 공식 번호를 씁니다.
  공식 Agenda에는 Word 번호로 표현할 수 없는 '10.5.0 General aspects' 같은 0번 항목이 있습니다.
- 각 결정은 'Agreement:' 같은 표시 줄로 시작하고, 다음 표시 줄 / TDoc 줄 / 제목에서 끝납니다.
- 결정 바로 앞의 굵은 TDoc 줄(주로 FL summary)이 그 결정의 근거 문서입니다.
- FFS는 별도 결정이 아니라 결정 안의 하위 줄로 들어 있습니다.
"""
import argparse
import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from scripts.generate_report import ROOT, meeting_sort_key

# 파싱 결과가 달라지는 수정을 하면 올립니다. DB의 회의별 parser_version과 다르면 자동 실행 때 다시 처리합니다.
PARSER_VERSION = 6

# 결정 표시 줄. 표시만 있는 한 줄('Agreement:')이 기본이고, 아래 변형도 결정으로 읽습니다.
# - 같은 줄 본문: 'Agreement: Adopt the following changes…' (콜론 중복 'Agreement::', 세미콜론 'Agreement;' 포함)
# - 괄호 설명: 'Agreement (updated on Wednesday)'. 괄호에 'RAN1#…'이 있으면 이전 회의 합의 인용이라 제외합니다.
# - 설명 붙은 표시: 'Conclusion for UL SPS with multi-TBS (after offline):' (줄 끝 콜론 필수)
# - 문단 안 줄바꿈: 'Agreement:⏎본문' (첫 줄만 표시로 보고 나머지는 본문)
MARKER = re.compile(
    r"(?P<kind>agreements?|conclusions?|working assumptions?)\s*(?:\((?P<ref>[^)]*)\))?\s*(?:[:;]+\s*(?P<rest>.*))?",
    re.I)
DESC_MARKER = re.compile(r"(?P<kind>agreements?|conclusions?|working assumptions?)\s+(?P<ref>[^:;]{1,100}?)\s*:", re.I)
QUOTED = re.compile(r"RAN1\s*#", re.I)
# 결정 표시처럼 보이지만 위 형식으로 읽지 못한 줄. 추출 점검 대상으로 보고합니다.
NEAR_MARKER = re.compile(
    r"(?:agreements?|conclusions?|working\s+assumptions?)\b(?:\s*\([^)]*\))?\s*[:;]"
    r"|(?:agreements?|conclusions?|working\s+assumptions?)\b[^\n]{0,100}:\s*$", re.I)
END_MARKER = re.compile(r"(observations?|decision)\s*:?", re.I)
TDOC = re.compile(r"R1-\d{7}\b")
# 'FL summary 1 on 9.1.1', 'Summary of proposals for 9.1.1' 등. TS 번호(38.214)는 걸리지 않도록 자릿수를 제한합니다.
# 6GR 등에서 합의를 묶는 이메일 토론 태그, 예: '[126-R20-6GR-Beam management] Email discussion ...'
DISCUSSION = re.compile(r"\[(\d+[^\]]*)\]\s*Email discussion", re.I)
SUMMARY_AGENDA = re.compile(r"summary\b.*?\b(?:on|for)\s+(?:AI\s+)?(\d{1,2}(?:\.\d{1,2})+)\b", re.I)
TYPE_NAMES = {"agreement": "Agreement", "conclusion": "Conclusion", "working assumption": "Working Assumption"}


def parse_agenda_csv(text):
    """FTP의 agenda.csv("번호","제목" 형식)를 {번호: 제목}으로 읽습니다."""
    rows = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    return {r[0].strip(): r[1].strip() for r in rows if len(r) >= 2 and re.fullmatch(r"\d+(\.\d+)*", r[0].strip())}


def _norm_title(title):
    title = title.replace("“", '"').replace("”", '"').replace("’", "'")
    return " ".join(title.lower().split()).rstrip(" .:")


def _official_number(title, parent, agenda_index):
    """제목과 상위 번호로 공식 Agenda 번호를 찾습니다. 못 찾으면 None."""
    t = _norm_title(title)
    exact = [n for n, a in agenda_index if a == t]
    # 'Opening of the meeting (Day 1: 9:00 am)'처럼 Chair notes 제목에 설명이 덧붙은 경우
    candidates = exact or [n for n, a in agenda_index if a and t.startswith(a)]
    same_parent = [n for n in candidates if n.rpartition(".")[0] == parent]
    if len(same_parent) == 1:
        return same_parent[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def meeting_id_from_folder(folder):
    m = re.fullmatch(r"TSGR1_(\d+)(b?)(?:[-_](e))?", folder)
    if not m:
        raise ValueError(f"unexpected meeting folder name: {folder!r}")
    return f"RAN1#{m.group(1)}{'bis' if m.group(2) else ''}{'-e' if m.group(3) else ''}"


def _num_pr(paragraph):
    """문단 자체 또는 스타일 상속 체인에서 (numId, ilvl)을 찾습니다."""
    sources = [paragraph._p.pPr]
    style = paragraph.style
    while style is not None:
        sources.append(style.element.pPr)
        style = style.base_style
    for ppr in sources:
        if ppr is not None and ppr.numPr is not None:
            num_id = ppr.numPr.find(qn("w:numId"))
            ilvl = ppr.numPr.find(qn("w:ilvl"))
            return (num_id.get(qn("w:val")) if num_id is not None else None,
                    int(ilvl.get(qn("w:val"))) if ilvl is not None else None)
    return None


def _iter_blocks(document):
    """본문의 문단과 표를 문서 순서대로 돌려줍니다."""
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _is_heading(paragraph):
    return paragraph.style.name.startswith("Heading")


def _agenda_level(paragraph):
    """Agenda 제목이면 계층 레벨(0부터)을, 아니면 None을 돌려줍니다."""
    num = _num_pr(paragraph) if _is_heading(paragraph) else None
    if not num:
        return None
    level = num[1] or 0
    style_level = re.search(r"\d+", paragraph.style.name)
    # 최상위 Agenda는 항상 Heading 1입니다. 'Heading 2'인데 번호 레벨이 0인 제목(예: Call for IPR)은
    # 잘못 매겨진 번호라 Agenda로 보지 않습니다. (Heading 4에 레벨 2처럼 스타일보다 얕은 경우는 정상)
    if level == 0 and style_level and int(style_level.group(0)) > 1:
        return None
    return level


def _starts_bold(paragraph):
    # 결정의 근거가 되는 TDoc 줄은 문서 번호 부분만 굵게 표시되어 있습니다 (나머지 제목·회사명은 일반).
    runs = [r for r in paragraph.runs if r.text.strip()]
    return bool(runs) and bool(runs[0].bold)


def _marker(text):
    """결정 표시 줄이면 (유형, 인용 여부, 본문 줄 목록)을, 아니면 None을 돌려줍니다."""
    first, *more = text.split("\n")
    first = first.strip()
    m = MARKER.fullmatch(first) or DESC_MARKER.fullmatch(first)
    if not m:
        return None
    kind = TYPE_NAMES[re.sub(r"s$", "", m.group("kind").lower())]
    ref = m.group("ref") or ""
    rest = m.groupdict().get("rest") or ""
    body = [line.strip() for line in [rest] + more if line.strip()]
    return kind, bool(QUOTED.search(ref)), body


def _table_lines(table):
    lines = []
    for row in table.rows:
        cells = [" ".join(c.text.split()) for c in row.cells]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def parse_chair_notes(path, meeting, source_url, agenda=None, stats=None):
    """stats에 dict를 넘기면 추출 점검용 수치를 채웁니다 (scripts/health.py가 사용).

    markers: 결정 표시 줄 수, extracted: 기록한 결정 수, quoted: 이전 회의 합의 인용(제외),
    empty: 본문을 못 읽은 표시, outside: 첫 Agenda 이전의 결정, unrecognized: 결정 표시처럼 보이지만 읽지 못한 줄
    """
    stats = {} if stats is None else stats
    stats.update(markers=0, extracted=0, quoted=0, empty=0, outside=0, unrecognized=[])
    document = docx.Document(str(path))
    agenda_index = [(n, _norm_title(t)) for n, t in (agenda or {}).items()]
    meeting_base = re.match(r"(.*/WG1_RL1/[^/]+/)", source_url)
    doc_name = Path(unquote(source_url.rsplit("/", 1)[-1])).stem

    entries, warnings, per_agenda = [], [], Counter()
    counters, titles, numbers = [], [], []  # numbers: 레벨별 최종 Agenda 번호
    unverified = {}  # 공식 Agenda로 확인하지 못한 번호 → 제목
    tdoc = discussion = None
    block = None  # {"type", "lines", "ffs", "skip"}

    def close():
        nonlocal block
        # Agenda 제목 아래에 있는 결정은 모두 기록합니다 (첫 Agenda 제목 이전의 서문은 제외).
        if block and not block["skip"] and not block["lines"]:
            stats["empty"] += 1
        if block and not block["skip"] and block["lines"] and not numbers:
            stats["outside"] += 1
        if block and not block["skip"] and block["lines"]:
            if numbers:
                agenda = numbers[-1] if numbers else ""
                per_agenda[agenda] += 1
                if agenda in unverified:
                    warnings.append(f"공식 Agenda에 없는 번호 {agenda}(계산값)에 결정 기록: {unverified.pop(agenda)}")
                source = {"doc": doc_name, "kind": "chairman_note", "url": source_url}
                if discussion:
                    source["discussion"] = discussion
                if tdoc:
                    source["tdoc"] = tdoc
                    if meeting_base:
                        source["tdoc_url"] = f"{meeting_base.group(1)}Docs/{tdoc}.zip"
                entries.append({
                    "id": f"{meeting}:{agenda}:{per_agenda[agenda]:03d}",
                    "meeting": meeting,
                    "agenda_item": agenda,
                    "agenda_title": titles[-1],
                    "agenda_path": [{"number": n, "title": t} for n, t in zip(numbers, titles)],
                    "type": block["type"],
                    "text": "\n".join(block["lines"]),
                    "ffs": block["ffs"],
                    "source": source,
                })
        block = None

    for b in _iter_blocks(document):
        if isinstance(b, Table):
            if block:
                block["lines"].extend(_table_lines(b))
            continue

        text = b.text.strip()
        level = _agenda_level(b)
        if level is not None:
            close()
            counters = (counters + [0] * (level + 1))[:level + 1]
            counters[level] += 1
            titles = (titles + [""] * (level + 1))[:level + 1]
            titles[level] = text
            numbers = (numbers + [""] * (level + 1))[:level + 1]
            parent = numbers[level - 1] if level else ""
            official = _official_number(text, parent, agenda_index) if agenda_index else None
            numbers[level] = official or (f"{parent}." if parent else "") + str(counters[level])
            # 제목 표기가 달라도('ISAC' vs 'Integrated Sensing And Communication (ISAC)') 계산한 번호가
            # 공식 Agenda에 있으면 위치가 맞는 것으로 봅니다. 없을 때만, 그리고 결정이 기록될 때만 경고합니다.
            if agenda_index and not official and numbers[level] not in agenda:
                unverified[numbers[level]] = text
            tdoc = discussion = None
            continue
        if _is_heading(b) or not text:
            continue

        marker = _marker(text)
        num = _num_pr(b)
        # 결정 안 하위 목록의 '- Working assumption: 본문'은 그 결정의 일부입니다 (새 결정이 아님).
        nested = bool(block and marker and marker[2] and num and num[1])
        if marker and not nested:
            close()
            kind, quoted, body = marker
            # 'Agreement (RAN1#124bis)'처럼 이전 회의 합의를 인용한 것은 신규 결정이 아닙니다.
            block = {"type": kind, "lines": body, "ffs": [l for l in body if l.upper().startswith("FFS")],
                     "skip": quoted}
            stats["markers"] += 1
            stats["quoted"] += quoted
            continue
        if NEAR_MARKER.match(text) and not nested:
            stats["unrecognized"].append({"agenda": numbers[-1] if numbers else "", "text": " ".join(text.split())})
        # 'Agreement' 바로 다음의 굵지 않은 TDoc 줄('R1-2509494 is endorsed …', 승인 문서 목록)은 결정 본문입니다.
        # 굵은 TDoc 줄은 다음 결정의 근거 문서이므로 결정을 닫습니다.
        if (block and TDOC.match(text) and not _starts_bold(b)
                and all(TDOC.match(line) for line in block["lines"])):
            block["lines"].append(text)
            continue
        if TDOC.match(text) or END_MARKER.fullmatch(text):
            close()
            if TDOC.match(text):
                stated = SUMMARY_AGENDA.search(text)
                computed = numbers[-1] if numbers else ""
                warning = f"{TDOC.match(text).group(0)}: 제목의 Agenda {stated.group(1)} ≠ 문서 위치 {computed}" if stated else None
                if stated and stated.group(1) != computed and warning not in warnings:
                    warnings.append(warning)
                if _starts_bold(b):
                    tdoc = TDOC.match(text).group(0)
            continue

        tag = DISCUSSION.match(text)
        if tag:
            close()
            discussion = tag.group(1)
            continue

        if block:
            if num:
                line = "  " * (num[1] or 0) + "- " + text
            else:
                line = text
            block["lines"].append(line)
            if text.upper().startswith("FFS"):
                block["ffs"].append(text)
    close()
    stats["extracted"] = len(entries)
    return entries, warnings


def merge_meeting(db, meeting, entries, meta):
    """해당 회의의 기존 항목을 새 결과로 교체합니다 (같은 문서를 다시 돌려도 결과가 같음)."""
    kept = [e for e in db["entries"] if e["meeting"] != meeting]
    db["entries"] = sorted(kept + list(entries), key=lambda e: meeting_sort_key(e["meeting"]))
    db["meetings"][meeting] = meta
    db["meetings"] = dict(sorted(db["meetings"].items(), key=lambda kv: meeting_sort_key(kv[0])))
    return db


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docx", type=Path)
    ap.add_argument("--folder", required=True, help="FTP 회의 폴더 이름 (예: TSGR1_126)")
    ap.add_argument("--url", required=True, help="Chair notes 원문의 FTP URL")
    ap.add_argument("--agenda", type=Path, help="공식 agenda.csv (있으면 공식 Agenda 번호 사용)")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "agreements_db.json")
    args = ap.parse_args()

    meeting = meeting_id_from_folder(args.folder)
    agenda = parse_agenda_csv(args.agenda.read_text(encoding="utf-8")) if args.agenda else None
    entries, warnings = parse_chair_notes(args.docx, meeting, args.url, agenda=agenda)
    for w in warnings:
        print(f"경고: {w}")
    db = json.loads(args.db.read_text(encoding="utf-8"))
    merge_meeting(db, meeting, entries, {
        "ftp_dir": args.folder,
        "chair_notes_url": args.url,
        "agenda_source": "agenda.csv" if agenda else "chair_notes_numbering",
        "parser_version": PARSER_VERSION,
    })
    args.db.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{meeting}: {len(entries)}건 추출 → {args.db}")
    for top, n in Counter(e["agenda_path"][0]["title"] for e in entries).most_common():
        print(f"  {top}: {n}")


if __name__ == "__main__":
    main()
