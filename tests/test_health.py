# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
from scripts import health


def e(meeting, n, section="Rel-20 Study of 6GR"):
    return {"id": f"{meeting}:10.1:{n:03d}", "meeting": meeting, "agenda_item": "10.1", "agenda_title": "x",
            "agenda_path": [{"number": "10", "title": section}, {"number": "10.1", "title": "x"}],
            "type": "Agreement", "text": "t", "ffs": [], "source": {"doc": "d", "kind": "chairman_note", "url": "u"}}


def many(meeting, n, section="Rel-20 Study of 6GR", start=0):
    return [e(meeting, start + i, section) for i in range(n)]


def stats(**kw):
    base = {"markers": 10, "extracted": 10, "quoted": 0, "empty": 0, "outside": 0, "unrecognized": []}
    return {**base, **kw}


def codes(issues):
    return [i["code"] for i in issues]


def test_clean_meeting_has_no_issues():
    db = {"entries": many("RAN1#125", 10) + many("RAN1#126", 10)}
    assert health.check("RAN1#126", db, stats(), warnings=[], agenda=None) == []


def test_unrecognized_marker_lines_are_a_warning_with_samples():
    unrec = [{"agenda": "9.1", "text": f"Agreement: Adopt change {i}"} for i in range(7)]
    (issue,) = health.check("RAN1#126", {"entries": many("RAN1#126", 10)}, stats(unrecognized=unrec), [], None)
    assert issue["level"] == "warning" and issue["code"] == "unrecognized_markers"
    assert "7" in issue["message"] and len(issue["samples"]) == 5
    assert issue["samples"][0] == "9.1 · Agreement: Adopt change 0"


def test_empty_and_outside_blocks_are_reported():
    issues = health.check("RAN1#126", {"entries": many("RAN1#126", 10)}, stats(empty=2, outside=1), [], None)
    assert codes(issues) == ["empty_decisions", "outside_agenda"]


def test_sharp_drop_in_decision_count_is_a_warning():
    db = {"entries": many("RAN1#124", 300) + many("RAN1#125", 320) + many("RAN1#126", 100)}
    (issue,) = health.check("RAN1#126", db, stats(), [], None)
    assert issue["code"] == "count_drop" and "100" in issue["message"] and "310" in issue["message"]


def test_vanished_section_is_a_warning_unless_dropped_from_official_agenda():
    db = {"entries": many("RAN1#125", 20) + many("RAN1#125", 8, section="Rel-19 UE Features", start=100)
          + many("RAN1#126", 20)}
    (issue,) = health.check("RAN1#126", db, stats(), [], agenda=None)
    assert issue["code"] == "section_vanished" and issue["level"] == "warning"
    still_listed = {"9": "Rel-19 UE Features", "10": "Rel-20 Study of 6GR"}
    (issue,) = health.check("RAN1#126", db, stats(), [], agenda=still_listed)
    assert issue["level"] == "warning"
    removed = {"10": "Rel-20 Study of 6GR"}
    (issue,) = health.check("RAN1#126", db, stats(), [], agenda=removed)
    assert issue["level"] == "info"      # 공식 Agenda에서 빠진 섹션은 정상 (참고용)


def test_parser_warnings_are_carried_over():
    (issue,) = health.check("RAN1#126", {"entries": many("RAN1#126", 10)}, stats(),
                            ["R1-2606528: 제목의 Agenda 10.5.4.2 ≠ 문서 위치 10.5.4.3"], None)
    assert issue["code"] == "parser_warnings" and issue["level"] == "info"


def test_summary_counts_warnings():
    issues = [{"level": "warning"}, {"level": "info"}, {"level": "warning"}]
    assert health.summary(issues) == "확인 필요 2건 · 참고 1건"
    assert health.summary([]) == "이상 없음"
