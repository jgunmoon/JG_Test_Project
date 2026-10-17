"""추출 이상 감지: 회의 하나를 처리한 뒤 결정이 조용히 누락됐을 가능성을 점검합니다.

- warning(확인 필요): 결정이 빠졌을 가능성이 높아 원문 확인이 필요한 경우
- info(참고): 문서 특성이거나 정상일 가능성이 높지만 알아둘 만한 경우
"""
import statistics
from collections import Counter

from scripts.agenda import norm, section_key
from scripts.generate_report import meeting_sort_key

DROP_RATIO = 0.5        # 직전 회의들 평균의 이 비율 미만이면 결정 수 급감
DROP_WINDOW = 3         # 비교할 직전 회의 수
SECTION_MIN = 5         # 직전 회의에 이만큼 이상 결정이 있던 섹션이 0건이 되면 점검
SAMPLES = 5


def _issue(level, code, message, samples=()):
    return {"level": level, "code": code, "message": message, "samples": list(samples)[:SAMPLES]}


def check(meeting, db, stats, warnings, agenda):
    """meeting: 방금 처리한 회의, db: 그 회의가 반영된 DB, stats: parse_chair_notes가 채운 수치,
    warnings: 파서 경고, agenda: 공식 agenda.csv({번호: 제목}) 또는 None."""
    issues = []
    unrec = stats.get("unrecognized", [])
    if unrec:
        issues.append(_issue(
            "warning", "unrecognized_markers",
            f"결정 표시처럼 보이지만 읽지 못한 줄 {len(unrec)}개 (예: 'Agreement: 본문'처럼 같은 줄에 쓴 형식). "
            "이 결정들은 DB에 없을 수 있습니다.",
            [f"{u['agenda']} · {u['text'][:100]}" for u in unrec]))
    if stats.get("empty"):
        issues.append(_issue("warning", "empty_decisions",
                             f"결정 표시는 있는데 본문을 읽지 못한 경우 {stats['empty']}개"))
    if stats.get("outside"):
        issues.append(_issue("warning", "outside_agenda",
                             f"첫 Agenda 제목 이전에 있어 기록하지 않은 결정 {stats['outside']}개"))

    meetings = sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)
    before = [m for m in meetings if meeting_sort_key(m) < meeting_sort_key(meeting)]
    per_meeting = Counter(e["meeting"] for e in db["entries"])
    if before:
        recent = [per_meeting[m] for m in before[-DROP_WINDOW:]]
        baseline = statistics.mean(recent)
        now = per_meeting[meeting]
        if now < DROP_RATIO * baseline:
            issues.append(_issue("warning", "count_drop",
                                 f"결정 수 {now}건이 직전 {len(recent)}개 회의 평균 {baseline:.0f}건의 "
                                 f"{int(DROP_RATIO * 100)}% 미만입니다."))

        prev = before[-1]
        prev_sections = Counter(section_key(e) for e in db["entries"] if e["meeting"] == prev)
        now_sections = {section_key(e) for e in db["entries"] if e["meeting"] == meeting}
        titles = {section_key(e): e["agenda_path"][0]["title"] for e in db["entries"] if e["meeting"] == prev}
        official = {norm(t) for n, t in (agenda or {}).items() if "." not in n} if agenda else None
        for sec, n in sorted(prev_sections.items()):
            if n < SECTION_MIN or sec in now_sections:
                continue
            if official is not None and sec not in official:
                issues.append(_issue("info", "section_dropped",
                                     f"'{titles[sec]}' 섹션이 공식 Agenda에서 빠졌습니다 ({prev}에는 결정 {n}건)."))
            else:
                issues.append(_issue("warning", "section_vanished",
                                     f"'{titles[sec]}' 섹션의 결정이 0건입니다 ({prev}에는 {n}건). "
                                     + ("공식 Agenda에는 남아 있습니다." if official is not None
                                        else "공식 Agenda 파일이 없어 섹션이 빠진 것인지 확인할 수 없습니다.")))
    if warnings:
        issues.append(_issue("info", "parser_warnings", f"파서 경고 {len(warnings)}개", warnings))
    return issues


def summary(issues):
    w = sum(1 for i in issues if i["level"] == "warning")
    n = sum(1 for i in issues if i["level"] == "info")
    if not issues:
        return "이상 없음"
    return " · ".join(part for part in (f"확인 필요 {w}건" if w else "", f"참고 {n}건" if n else "") if part)
