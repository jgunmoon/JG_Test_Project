# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
from scripts import delta


def e(meeting, n, text, agenda="10.5.2.4", title="Beam management", type_="Agreement", ffs=(), section="6GR"):
    return {"id": f"{meeting}:{agenda}:{n:03d}", "meeting": meeting, "agenda_item": agenda,
            "agenda_title": title, "type": type_, "text": text, "ffs": list(ffs),
            "agenda_path": [{"number": "10", "title": section}, {"number": agenda, "title": title}],
            "source": {"doc": "cn", "kind": "chairman_note", "url": f"https://x/{meeting}"}}


def db(*entries):
    return {"schema_version": 1, "meetings": {}, "entries": list(entries)}


PREV, CUR = "RAN1#125", "RAN1#126"


def test_counts_new_decisions_by_type():
    d = delta.compute(db(e(PREV, 1, "a"), e(CUR, 1, "b"), e(CUR, 2, "c", type_="Working Assumption")), "6gr", PREV, CUR)
    assert d["new"] == {"Agreement": 1, "Working Assumption": 1, "Conclusion": 0}


def test_ffs_followup_candidate_matches_same_agenda_title_even_if_number_changed():
    data = db(
        e(PREV, 1, "x", ffs=["FFS: maximum number of DCI container sizes for a UE"]),
        e(CUR, 1, "Study DCI container size determination: maximum number of sizes per UE is 4",
          agenda="10.5.3.4"),                       # Agenda 번호가 바뀌어도 제목이 같으면 비교
        e(CUR, 2, "Unrelated text about PRACH", agenda="10.5.1.2", title="PRACH"),
    )
    (c,) = delta.compute(data, "6gr", PREV, CUR)["ffs_followups"]
    assert c["ffs"].startswith("FFS: maximum number")
    assert c["prev_id"] == f"{PREV}:10.5.2.4:001"
    assert c["candidate_id"] == f"{CUR}:10.5.3.4:001"
    assert 0.6 <= c["score"] <= 1


def test_weak_or_too_short_ffs_gets_no_candidate():
    data = db(
        e(PREV, 1, "x", ffs=["FFS: details", "FFS: value of the parameter for sounding reference signal"]),
        e(CUR, 1, "Support periodic beam reporting"),
    )
    assert delta.compute(data, "6gr", PREV, CUR)["ffs_followups"] == []


def test_detects_working_assumption_confirmation_from_wording():
    data = db(e(PREV, 1, "x"), e(CUR, 1, "Confirm the working assumption made in RAN1#125 with the following revision."),
              e(CUR, 2, "The working assumption is not discussed"))
    assert [x["id"] for x in delta.compute(data, "6gr", PREV, CUR)["wa_confirmed"]] == [f"{CUR}:10.5.2.4:001"]


def test_agenda_structure_changes():
    data = db(e(PREV, 1, "x", title="Old topic", agenda="10.1"), e(PREV, 2, "y"),
              e(CUR, 1, "z"), e(CUR, 2, "w", title="New topic", agenda="10.9"))
    d = delta.compute(data, "6gr", PREV, CUR)
    assert d["agenda_new"] == ["New topic"]
    assert d["agenda_dropped"] == ["Old topic"]


def test_meeting_pairs_follow_db_meeting_order():
    data = db(e("RAN1#124bis", 1, "a"), e(PREV, 1, "b"), e(CUR, 1, "c"))
    assert delta.meeting_pairs(data) == [("RAN1#124bis", PREV), (PREV, CUR)]


def test_working_assumption_wording_seen_in_real_chair_notes():
    confirmed = [
        "Confirm the following working assumption in RAN1#124bis with the following changes",
        "For initial access, confirm the RAN1#125 Working Assumption that the frequency location is fixed",
        "Reply LS: Agreement Confirm the following working assumption with modifications",
    ]
    not_confirmed = [
        "Note: whether the working assumption can be confirmed relies on SA4's response",
        "Working Assumption from RAN1#124 is not necessarily to be confirmed.",
        "- RAN1 to confirm the working assumption on REG bundle",
    ]
    assert all(delta.WA_CONFIRM.search(t) for t in confirmed)
    assert not any(delta.WA_CONFIRM.search(t) for t in not_confirmed)


def test_section_filter_and_all_sections():
    data = db(e(CUR, 1, "a"), e(CUR, 2, "b", section="Maintenance on Rel-19"))
    assert sum(delta.compute(data, "6gr", PREV, CUR)["new"].values()) == 1
    assert sum(delta.compute(data, None, PREV, CUR)["new"].values()) == 2
