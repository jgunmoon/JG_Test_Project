# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
from scripts import render_html as rh

CONFIG = {
    "report_base_url": "https://example.invalid/reports/",
    "items": [
        {"id": "bm", "name": "Beam <Management>", "release": "Rel-20"},
        {"id": "isac", "name": "ISAC", "release": "Rel-20"},
    ],
}


def e(meeting, n, text="t", item="bm", ffs=(), type_="Agreement", title="Beam management"):
    return {"id": f"{meeting}:10.5.2.4:{n:03d}", "meeting": meeting, "item": item, "agenda_item": "10.5.2.4",
            "agenda_title": title, "type": type_, "text": text, "ffs": list(ffs),
            "source": {"doc": "Chair notes", "kind": "chairman_note", "url": f"https://ftp.invalid/{meeting}.docx"}}


DB = {"schema_version": 1, "meetings": {
    "RAN1#125": {"chair_notes_url": "https://ftp.invalid/RAN1#125.docx"},
    "RAN1#126": {"chair_notes_url": "https://ftp.invalid/RAN1#126.docx"},
}, "entries": [
    e("RAN1#125", 1, ffs=["FFS: maximum number of DCI container sizes per UE"]),
    e("RAN1#126", 1, text="Maximum number of DCI container sizes per UE is 4"),
    e("RAN1#126", 2, text="Confirm the following working assumption: <X>", type_="Working Assumption"),
]}


def test_standalone_page_is_a_full_document_and_fragment_is_not():
    page = rh.render_html(CONFIG, DB)
    assert page.startswith("<!doctype html>") and "<title>RAN1 6G PHY Tracker</title>" in page
    frag = rh.render_html(CONFIG, DB, standalone=False)
    assert "<!doctype" not in frag and "<html" not in frag and "<title>RAN1 6G PHY Tracker</title>" in frag


def test_text_from_documents_is_escaped():
    page = rh.render_html(CONFIG, DB)
    assert "Beam &lt;Management&gt;" in page and "<Management>" not in page
    assert "&lt;X&gt;" in page


def test_shows_latest_meeting_delta_and_source_links():
    page = rh.render_html(CONFIG, DB)
    assert "RAN1#125 → RAN1#126" in page
    assert "https://ftp.invalid/RAN1#126.docx" in page            # 출처 링크
    assert "https://example.invalid/reports/by_item/bm.md" in page  # 상세 리포트 링크
    assert "확인 필요" in page                                       # FFS 후속 후보는 후보로 표시


def test_bar_chart_has_one_bar_per_meeting_with_value_labels():
    page = rh.render_html(CONFIG, DB)
    assert page.count('<g class="bar') == 2          # 결정이 있는 아이템(bm)만, 회의마다 막대 1개
    assert page.count('<g class="bar latest"') == 1   # 최신 회의 막대는 강조
    assert 'data-tip="RAN1#126: 결정 2건' in page
    assert "아직 기록된 결정이 없습니다" in page        # 결정이 없는 아이템(isac)은 빈 상태 표시


def test_output_is_deterministic():
    assert rh.render_html(CONFIG, DB) == rh.render_html(CONFIG, DB)
