"""직전 회의(RAN1 #N-1) 대비 최신 회의(#N)의 변경분(Delta)을 최상위 Agenda(섹션)별로 DB에서 계산합니다.

DB만으로 결정되는 값이라 따로 저장하지 않고 리포트를 만들 때마다 계산합니다.

- new            : 신규 결정 수 (구분별)
- agenda_new/dropped : 새로 생기거나 사라진 Agenda (번호는 회의마다 바뀔 수 있어 제목으로 비교)
- wa_confirmed   : 합의 원문에 'confirm ... working assumption' 문구가 있는 결정
- ffs_followups  : 직전 회의 FFS와 키워드가 많이 겹치는 같은 Agenda의 최신 회의 결정.
                   자동 매칭 '후보'일 뿐이며 FFS가 해소됐다는 뜻이 아닙니다. 원문 확인이 필요합니다.
"""
import re

from scripts.agenda import section_key
from scripts.generate_report import TYPES, meeting_sort_key

MIN_SCORE = 0.6       # FFS 키워드 중 후보 결정에 들어 있어야 하는 비율
MIN_KEYWORDS = 3      # 키워드가 이보다 적은 FFS('FFS: details' 등)는 비교하지 않음
# 'Confirm the (following) (RAN1#125) working assumption ...'처럼 확정을 선언하는 명령형 문장만 인정합니다.
# 'whether the working assumption can be confirmed', 'is not necessarily to be confirmed' 등은 확정이 아닙니다.
WA_CONFIRM = re.compile(
    r"(?:^|[.:,]\s*|\bagreement\s*:?\s*)(?:-\s*)?confirm\s+(?:the\s+)?(?:following\s+)?"
    r"(?:RAN1\s*#\s*\S+\s+)?working\s+assumptions?\b", re.I | re.M)
STOPWORDS = set("""
the and for with from that this which are can not other details detail whether how what when where any
following be is of to in on a an or by as at ffs also further study need needed if support supported
use used value values between per its their than more
""".split())


def keywords(text):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS}


def _title(entry):
    return " ".join(entry.get("agenda_title", "").lower().split())


def meeting_pairs(db):
    meetings = sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)
    return list(zip(meetings, meetings[1:]))


def compute(db, section, prev, cur):
    """section: 최상위 Agenda 제목(agenda.section_key 값). None이면 전체."""
    mine = [e for e in db["entries"] if section is None or section_key(e) == section]
    prev_entries = [e for e in mine if e["meeting"] == prev]
    cur_entries = [e for e in mine if e["meeting"] == cur]

    new = {t: sum(1 for e in cur_entries if e["type"] == t) for t in TYPES}
    prev_titles = {_title(e): e.get("agenda_title", "") for e in prev_entries}
    cur_titles = {_title(e): e.get("agenda_title", "") for e in cur_entries}

    followups = []
    for p in prev_entries:
        same_agenda = [c for c in cur_entries if _title(c) == _title(p)]
        for ffs in p.get("ffs", []):
            kw = keywords(ffs)
            if len(kw) < MIN_KEYWORDS or not same_agenda:
                continue
            best = max(same_agenda, key=lambda c: len(kw & keywords(c["text"])))
            score = len(kw & keywords(best["text"])) / len(kw)
            if score >= MIN_SCORE:
                followups.append({"ffs": ffs, "prev_id": p["id"], "prev_source": p["source"],
                                  "candidate_id": best["id"], "candidate_source": best["source"],
                                  "candidate_text": best["text"], "agenda_title": p.get("agenda_title", ""),
                                  "score": round(score, 2)})

    return {
        "prev": prev,
        "cur": cur,
        "new": new,
        "agenda_new": sorted(v for k, v in cur_titles.items() if k not in prev_titles),
        "agenda_dropped": sorted(v for k, v in prev_titles.items() if k not in cur_titles),
        "wa_confirmed": [e for e in cur_entries if WA_CONFIRM.search(e["text"])],
        "prev_ffs": sum(len(p.get("ffs", [])) for p in prev_entries),
        "ffs_followups": followups,
    }
