# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
import json

import pytest

from scripts import generate_report as gr

CONFIG = {}
SIXGR = [("10", "Rel-20 Study of 6GR"), ("10.5", "Multi-antenna system")]


def entry(meeting, n, leaf=("10.5.2", "MIMO operation"), type_="Agreement", text="sample text", ffs=(), top=None):
    path = (top or SIXGR) + [leaf]
    return {
        "id": f"{meeting}:{leaf[0]}:{n:03d}",
        "meeting": meeting,
        "agenda_item": leaf[0],
        "agenda_title": leaf[1],
        "agenda_path": [{"number": a, "title": b} for a, b in path],
        "type": type_,
        "text": text,
        "ffs": list(ffs),
        "source": {"doc": f"R1-TEST{n:03d}", "kind": "chairman_note", "url": f"https://example.invalid/{meeting}/{n}"},
    }


def make_db(*entries):
    return {"schema_version": 1, "meetings": {}, "entries": list(entries)}


def test_meeting_sort_order_handles_bis():
    ids = ["RAN1#118bis", "RAN1#117", "RAN1#118", "RAN1#120"]
    assert sorted(ids, key=gr.meeting_sort_key) == ["RAN1#117", "RAN1#118", "RAN1#118bis", "RAN1#120"]


def test_validate_rejects_entry_without_source_doc():
    bad = entry("RAN1#118", 1)
    bad["source"]["doc"] = ""
    with pytest.raises(gr.ValidationError, match="source.doc"):
        gr.validate_db(make_db(bad))


def test_validate_rejects_unknown_type_and_missing_agenda_path():
    with pytest.raises(gr.ValidationError, match="type"):
        gr.validate_db(make_db(entry("RAN1#118", 1, type_="Proposal")))
    bad = entry("RAN1#118", 1)
    bad["agenda_path"] = []
    with pytest.raises(gr.ValidationError, match="agenda_path"):
        gr.validate_db(make_db(bad))


def test_validate_rejects_duplicate_ids():
    e = entry("RAN1#118", 1)
    with pytest.raises(gr.ValidationError, match="duplicate"):
        gr.validate_db(make_db(e, dict(e)))


def test_section_report_follows_agenda_tree_and_cites_sources(tmp_path):
    db = make_db(entry("RAN1#117", 1, text="earlier"), entry("RAN1#118", 1, text="later"),
                 entry("RAN1#118", 1, leaf=("8.1", "Maintenance on AI/ML"), top=[("8", "Maintenance on Rel-19")]))
    gr.write_reports(CONFIG, db, tmp_path)
    md = (tmp_path / "by_agenda" / "rel-20-study-of-6gr.md").read_text()
    assert md.startswith("# 10 Rel-20 Study of 6GR")
    assert "### 10.5 Multi-antenna system" in md and "#### 10.5.2 MIMO operation" in md
    assert md.index("earlier") < md.index("later")
    assert "[R1-TEST001](https://example.invalid/RAN1#117/1)" in md
    assert "```mermaid" in md
    assert (tmp_path / "by_agenda" / "maintenance-on-rel-19.md").exists()


def test_number_change_is_shown_and_retired_agenda_listed(tmp_path):
    db = make_db(entry("RAN1#117", 1, leaf=("10.5.2.4", "Beam management")),
                 entry("RAN1#118", 1, leaf=("10.5.3.4", "Beam management")),
                 entry("RAN1#117", 2, leaf=("10.5.0", "General aspects")))
    gr.write_reports(CONFIG, db, tmp_path)
    md = (tmp_path / "by_agenda" / "rel-20-study-of-6gr.md").read_text()
    assert "번호 변경: #117: 10.5.2.4 → #118: 10.5.3.4" in md
    assert "## 최신 회의에는 없는 Agenda" in md and "10.5.0 General aspects (마지막: RAN1#117)" in md


def test_text_with_pipes_and_newlines_does_not_break_table(tmp_path):
    gr.write_reports(CONFIG, make_db(entry("RAN1#118", 1, text="a | b\nc")), tmp_path)
    md = (tmp_path / "by_agenda" / "rel-20-study-of-6gr.md").read_text()
    row = next(l for l in md.splitlines() if "R1-TEST001" in l)
    assert "a \\| b<br>c" in row


def test_dashboard_lists_sections_with_latest_counts():
    db = make_db(entry("RAN1#117", 1), entry("RAN1#118", 1),
                 entry("RAN1#118", 2, type_="Working Assumption", ffs=["FFS: a", "FFS: b"]))
    md = gr.render_dashboard(CONFIG, db)
    assert "최신 회의: RAN1#118" in md
    row = next(l for l in md.splitlines() if l.startswith("| 10 Rel-20 Study of 6GR") and "보기" in l)
    assert "| 1 | 1 | 0 | 2 | 3 |" in row                       # Agreement, WA, Conclusion, 미결 FFS, 누적
    assert "(by_agenda/rel-20-study-of-6gr.md)" in row


def test_delta_section_in_dashboard():
    prev = entry("RAN1#117", 1, ffs=["FFS: maximum number of DCI container sizes per UE"])
    cur = entry("RAN1#118", 2, text="Maximum number of DCI container sizes per UE is 4")
    wa = entry("RAN1#118", 3, text="Confirm the following working assumption: X")
    dash = gr.render_dashboard(CONFIG, make_db(prev, cur, wa))
    assert "## 직전 회의 대비 (RAN1#117 → RAN1#118)" in dash
    row = next(l for l in dash.splitlines() if l.startswith("| 10 Rel-20 Study of 6GR") and "보기" not in l)
    assert "| 2 | 1 | 1 | 1 |" in row   # 신규 결정, WA 확정, 직전 FFS, 후속 후보


def test_meeting_report_groups_by_agenda_number():
    db = make_db(entry("RAN1#118", 1, leaf=("10.5.3", "CSI")), entry("RAN1#118", 1, leaf=("10.5.2", "MIMO")))
    md = gr.render_meeting_report("RAN1#118", CONFIG, db)
    assert md.index("## 10.5.2 MIMO") < md.index("## 10.5.3 CSI")
    assert "10 Rel-20 Study of 6GR › 10.5 Multi-antenna system" in md


def test_write_reports_removes_stale_files(tmp_path):
    (tmp_path / "by_item").mkdir()
    (tmp_path / "by_item" / "old.md").write_text("x")
    gr.write_reports(CONFIG, make_db(entry("RAN1#118", 1)), tmp_path)
    assert not (tmp_path / "by_item").exists()
    assert (tmp_path / "README.md").exists() and (tmp_path / "index.html").exists()
    assert (tmp_path / "by_meeting" / "ran1_118.md").exists()


def test_output_is_deterministic(tmp_path):
    db = make_db(entry("RAN1#118", 1))
    gr.write_reports(CONFIG, db, tmp_path / "a")
    gr.write_reports(CONFIG, json.loads(json.dumps(db)), tmp_path / "b")
    for f in (tmp_path / "a").rglob("*.*"):
        assert f.read_text() == (tmp_path / "b" / f.relative_to(tmp_path / "a")).read_text()


HEALTH = {"summary": "확인 필요 1건", "stats": {"markers": 3, "extracted": 2},
          "issues": [{"level": "warning", "code": "unrecognized_markers", "message": "읽지 못한 줄 1개",
                      "samples": ["9.1 · Agreement: Adopt X"]}]}


def test_readme_and_meeting_report_show_extraction_check():
    db = make_db(entry("RAN1#118", 1))
    db["meetings"] = {"RAN1#118": {"health": HEALTH}}
    md = gr.render_dashboard(CONFIG, db)
    assert "## 추출 점검" in md and "| RAN1#118 | 확인 필요 1건 | 읽지 못한 줄 1개 |" in md
    rep = gr.render_meeting_report("RAN1#118", CONFIG, db)
    assert "> **추출 점검: 확인 필요 1건**" in rep and "9.1 · Agreement: Adopt X" in rep


def test_meeting_without_health_record_is_shown_as_not_checked():
    db = make_db(entry("RAN1#118", 1))
    assert "| RAN1#118 | 점검 기록 없음 |" in gr.render_dashboard(CONFIG, db)


def test_provisional_meeting_is_labelled_everywhere(tmp_path):
    db = make_db(entry("RAN1#117", 1), entry("RAN1#118", 1, text="draft decision"))
    db["meetings"] = {"RAN1#118": {"provisional": {"doc": "Draft Chair notes RAN1#118_v02.docx", "reason": "r"}}}
    gr.write_reports(CONFIG, db, tmp_path)
    readme = (tmp_path / "README.md").read_text()
    assert "**최신 회의: RAN1#118 (잠정)**" in readme
    assert "RAN1#118는 잠정 결과입니다" in readme and "`Draft Chair notes RAN1#118_v02.docx`" in readme
    assert "- [RAN1#118 (잠정)](by_meeting/ran1_118.md)" in readme
    rep = (tmp_path / "by_meeting" / "ran1_118.md").read_text()
    assert rep.startswith("# RAN1#118 (잠정) 결과 요약") and "자동으로 교체됩니다" in rep
    assert "# RAN1#117 결과 요약" in (tmp_path / "by_meeting" / "ran1_117.md").read_text()
    sec = (tmp_path / "by_agenda" / "rel-20-study-of-6gr.md").read_text()
    assert "| RAN1#118 (잠정) | 10.5.2 |" in sec and "| RAN1#117 | 10.5.2 |" in sec


def test_last_update_time_is_shown_in_korean_time():
    assert gr.format_kst("2026-10-17T01:52:52+00:00") == "2026-10-17 10:52 KST"
    assert gr.format_kst("2026-10-19T23:47:00+00:00") == "2026-10-20 08:47 KST"   # 날짜가 넘어가는 경우
    assert gr.format_kst(None) is None
    db = make_db(entry("RAN1#118", 1))
    db["updated_at"] = "2026-10-17T01:52:52+00:00"
    assert "**마지막 업데이트: 2026-10-17 10:52 KST**" in gr.render_dashboard(CONFIG, db)
    assert "마지막 업데이트" not in gr.render_dashboard(CONFIG, make_db(entry("RAN1#118", 1)))
