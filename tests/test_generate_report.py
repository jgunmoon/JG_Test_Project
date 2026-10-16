# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
import json

import pytest

from scripts import generate_report as gr

CONFIG = {
    "items": [
        {"id": "csi_prediction", "name": "AI/ML CSI Prediction", "release": "Rel-19"},
        {"id": "beam_management", "name": "AI/ML Beam Management", "release": "Rel-19"},
    ]
}


def entry(meeting, item, n, type_="Agreement", text="sample text", ffs=()):
    return {
        "id": f"{meeting}:{item}:{n:03d}",
        "meeting": meeting,
        "item": item,
        "agenda_item": "9.9.9",
        "type": type_,
        "text": text,
        "ffs": list(ffs),
        "source": {
            "doc": f"R1-TEST{n:03d}",
            "kind": "chairman_note",
            "url": f"https://example.invalid/{meeting}/{n}",
        },
    }


def make_db(*entries, meetings=None):
    return {"schema_version": 1, "meetings": meetings or {}, "entries": list(entries)}


def test_meeting_sort_order_handles_bis():
    ids = ["RAN1#118bis", "RAN1#117", "RAN1#118", "RAN1#120"]
    assert sorted(ids, key=gr.meeting_sort_key) == ["RAN1#117", "RAN1#118", "RAN1#118bis", "RAN1#120"]


def test_validate_rejects_entry_without_source_doc():
    bad = entry("RAN1#118", "csi_prediction", 1)
    bad["source"]["doc"] = ""
    with pytest.raises(gr.ValidationError, match="source.doc"):
        gr.validate_db(make_db(bad), CONFIG)


def test_validate_rejects_unknown_type_and_item():
    with pytest.raises(gr.ValidationError, match="type"):
        gr.validate_db(make_db(entry("RAN1#118", "csi_prediction", 1, type_="Proposal")), CONFIG)
    with pytest.raises(gr.ValidationError, match="item"):
        gr.validate_db(make_db(entry("RAN1#118", "unknown_item", 1)), CONFIG)


def test_validate_rejects_duplicate_ids():
    e = entry("RAN1#118", "csi_prediction", 1)
    with pytest.raises(gr.ValidationError, match="duplicate"):
        gr.validate_db(make_db(e, dict(e)), CONFIG)


def test_item_report_is_chronological_and_cites_source():
    db = make_db(
        entry("RAN1#118", "csi_prediction", 2, text="later"),
        entry("RAN1#117", "csi_prediction", 1, text="earlier"),
    )
    md = gr.render_item_report(CONFIG["items"][0], db)
    assert md.index("earlier") < md.index("later")
    assert "[R1-TEST001](https://example.invalid/RAN1#117/1)" in md
    assert "```mermaid" in md


def test_item_report_without_entries_says_so():
    md = gr.render_item_report(CONFIG["items"][1], make_db())
    assert "아직 기록된 합의가 없습니다" in md


def test_text_with_pipes_and_newlines_does_not_break_table():
    db = make_db(entry("RAN1#118", "csi_prediction", 1, text="a | b\nc"))
    md = gr.render_item_report(CONFIG["items"][0], db)
    row = next(l for l in md.splitlines() if "R1-TEST001" in l)
    assert "a \\| b<br>c" in row


def test_dashboard_highlights_latest_meeting_delta():
    db = make_db(
        entry("RAN1#117", "csi_prediction", 1),
        entry("RAN1#118", "csi_prediction", 2),
        entry("RAN1#118", "csi_prediction", 3, type_="Working Assumption", ffs=["FFS: a", "FFS: b"]),
    )
    md = gr.render_dashboard(CONFIG, db)
    assert "최신 회의: RAN1#118" in md
    row = next(l for l in md.splitlines() if "AI/ML CSI Prediction" in l)
    # 최신 회의: Agreement 1건, Working Assumption 1건, 미결 FFS 2건 / 누적 결정 3건
    assert "| 1 | 1 | 2 | 3 |" in row


def test_source_shows_chair_notes_tdoc_and_discussion():
    e = entry("RAN1#118", "csi_prediction", 1)
    e["source"].update(tdoc="R1-2600001", tdoc_url="https://example.invalid/R1-2600001.zip", discussion="118-X")
    md = gr.render_item_report(CONFIG["items"][0], make_db(e))
    assert "[R1-2600001](https://example.invalid/R1-2600001.zip)" in md
    assert "`[118-X]`" in md


def test_write_reports_creates_files(tmp_path):
    db = make_db(entry("RAN1#118bis", "csi_prediction", 1))
    gr.write_reports(CONFIG, db, tmp_path)
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "by_item" / "csi_prediction.md").exists()
    assert (tmp_path / "by_item" / "beam_management.md").exists()
    assert (tmp_path / "by_meeting" / "ran1_118bis.md").exists()


def test_output_is_deterministic(tmp_path):
    db = make_db(entry("RAN1#118", "csi_prediction", 1))
    gr.write_reports(CONFIG, db, tmp_path / "a")
    gr.write_reports(CONFIG, json.loads(json.dumps(db)), tmp_path / "b")
    for f in (tmp_path / "a").rglob("*.md"):
        assert f.read_text() == (tmp_path / "b" / f.relative_to(tmp_path / "a")).read_text()
