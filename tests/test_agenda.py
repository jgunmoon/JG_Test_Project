# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
from scripts import agenda

SIXGR = ("10", "Rel-20 Study of 6GR")


def e(meeting, n, *path):
    path = [SIXGR] + list(path)
    return {"id": f"{meeting}:{path[-1][0]}:{n:03d}", "meeting": meeting, "type": "Agreement", "text": "t",
            "ffs": [], "agenda_item": path[-1][0], "agenda_title": path[-1][1],
            "agenda_path": [{"number": a, "title": b} for a, b in path],
            "source": {"doc": "cn", "kind": "chairman_note", "url": "https://x"}}


MIMO_125 = ("10.5.2", "MIMO operation")
CSI_126 = ("10.5.3", "CSI acquisition and report")
MA = ("10.5", "Multi-antenna system")


def db(*entries):
    return {"schema_version": 1, "meetings": {}, "entries": list(entries)}


def test_same_title_in_same_section_is_one_lineage_even_if_number_moved():
    # 실제 사례: 6GR Beam management가 #125 10.5.2.4 → #126 10.5.3.4로 이동
    data = db(e("RAN1#125", 1, MA, MIMO_125, ("10.5.2.4", "Beam management for downlink and uplink")),
              e("RAN1#126", 1, MA, CSI_126, ("10.5.3.4", "Beam  Management for downlink and uplink")))
    idx = agenda.build_index(data)
    (key,) = {idx["entry_keys"][x["id"]] for x in data["entries"]}
    lin = idx["lineages"][key]
    assert lin["numbers"] == {"RAN1#125": "10.5.2.4", "RAN1#126": "10.5.3.4"}
    assert lin["counts"] == {"RAN1#125": 1, "RAN1#126": 1}
    assert agenda.number_history(lin, idx["meetings"]) == "#125: 10.5.2.4 → #126: 10.5.3.4"


def test_repeated_leaf_title_within_a_meeting_is_kept_apart():
    # 실제 사례: 'Other aspects'가 같은 회의 안에서 여러 상위 Agenda 아래에 있음
    data = db(e("RAN1#126", 1, MA, CSI_126, ("10.5.3.3", "Other aspects")),
              e("RAN1#126", 1, ("10.6", "WUS"), ("10.6.3", "Other aspects")))
    idx = agenda.build_index(data)
    assert len({idx["entry_keys"][x["id"]] for x in data["entries"]}) == 2


def test_tree_follows_latest_meeting_and_sums_descendants():
    data = db(e("RAN1#125", 1, MA, MIMO_125, ("10.5.2.4", "Beam management")),
              e("RAN1#126", 1, MA, CSI_126, ("10.5.3.4", "Beam management")),
              e("RAN1#126", 2, MA, CSI_126, ("10.5.3.4", "Beam management")),
              e("RAN1#126", 1, MA, CSI_126, ("10.5.3.1", "DL CSI")))
    idx = agenda.build_index(data)
    rows = agenda.tree(idx)
    assert [(r["number"], r["depth"]) for r in rows] == [
        ("10", 0), ("10.5", 1), ("10.5.3", 2), ("10.5.3.1", 3), ("10.5.3.4", 3)]
    bm = rows[-1]
    assert bm["counts"] == {"RAN1#125": 1, "RAN1#126": 2} and bm["key"]
    assert rows[0]["counts"] == {"RAN1#125": 1, "RAN1#126": 3}     # 하위 Agenda 합계 (이전 회의 이력 포함)
    assert rows[2]["key"] is None                                   # 결정이 직접 기록되지 않은 상위 제목
    assert rows[2]["keys"] == sorted({bm["key"], rows[3]["key"]})   # 상위 행은 하위 Agenda 연결 키를 모두 가짐
    assert bm["keys"] == [bm["key"]]


def test_agendas_missing_from_latest_meeting_are_listed_separately():
    data = db(e("RAN1#125", 1, MA, ("10.5.0", "General aspects and frameworks")),
              e("RAN1#126", 1, MA, ("10.5.1", "Initial access")))
    idx = agenda.build_index(data)
    (old,) = agenda.retired(idx)
    assert old["title"] == "General aspects and frameworks"
    assert old["last_meeting"] == "RAN1#125" and old["last_number"] == "10.5.0"


def test_sections_are_top_level_agendas_of_latest_meeting():
    data = db(e("RAN1#126", 1, MA, ("10.5.1", "x")))
    data["entries"].append({**e("RAN1#126", 2, MA, ("10.5.1", "x")),
                            "agenda_path": [{"number": "8", "title": "Maintenance on Rel-19 NR"}],
                            "agenda_item": "8", "agenda_title": "Maintenance on Rel-19 NR", "id": "RAN1#126:8:001"})
    idx = agenda.build_index(data)
    assert [(s["number"], s["title"]) for s in agenda.sections(idx)] == [
        ("8", "Maintenance on Rel-19 NR"), ("10", "Rel-20 Study of 6GR")]
