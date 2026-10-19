# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
import re

from scripts import render_html as rh

CONFIG = {"report_base_url": "https://example.invalid/reports/"}
SIXGR = [("10", "Rel-20 Study of 6GR"), ("10.5", "Multi-antenna <system>")]


def e(meeting, n, leaf, text="t", ffs=(), type_="Agreement", top=None):
    path = (top or SIXGR) + [leaf]
    return {"id": f"{meeting}:{leaf[0]}:{n:03d}", "meeting": meeting, "agenda_item": leaf[0], "agenda_title": leaf[1],
            "agenda_path": [{"number": a, "title": b} for a, b in path], "type": type_, "text": text,
            "ffs": list(ffs),
            "source": {"doc": "Chair notes", "kind": "chairman_note", "url": f"https://ftp.invalid/{meeting}.docx"}}


BM_125 = ("10.5.2.4", "Beam management")
BM_126 = ("10.5.3.4", "Beam management")
DB = {"schema_version": 1, "meetings": {
    "RAN1#125": {"chair_notes_url": "https://ftp.invalid/RAN1#125.docx"},
    "RAN1#126": {"chair_notes_url": "https://ftp.invalid/RAN1#126.docx"},
}, "entries": [
    e("RAN1#125", 1, BM_125, ffs=["FFS: maximum number of DCI container sizes per UE"]),
    e("RAN1#126", 1, BM_126, text="Maximum number of DCI container sizes per UE is 4"),
    e("RAN1#126", 2, BM_126, text="Confirm the following working assumption: <X>", type_="Working Assumption"),
    e("RAN1#125", 2, ("10.5.0", "General aspects")),
]}


def html_part(page):
    # 검색용 JSON 블록은 HTML로 해석되지 않으므로 제외하고 검사합니다 (블록 탈출은 test_search에서 확인).
    return re.sub(r'<script type="application/json".*?</script>', "", page, flags=re.S)


def test_standalone_page_is_a_full_document_and_fragment_is_not():
    page = rh.render_html(CONFIG, DB)
    assert page.startswith("<!doctype html>") and "<title>RAN1 Decision Tracker</title>" in page
    frag = rh.render_html(CONFIG, DB, standalone=False)
    assert "<!doctype" not in frag and "<html" not in frag and "<title>RAN1 Decision Tracker</title>" in frag


def test_text_from_documents_is_escaped():
    page = html_part(rh.render_html(CONFIG, DB))
    assert "Multi-antenna &lt;system&gt;" in page and "<system>" not in page
    assert "&lt;X&gt;" in page


def test_agenda_tree_uses_latest_numbers_and_shows_moves():
    page = html_part(rh.render_html(CONFIG, DB))
    assert 'id="agenda"' in page
    assert '<span class="agenda-num">10.5.3.4</span>Beam management' in page
    assert "번호 변경 #125: 10.5.2.4 → #126: 10.5.3.4" in page
    assert 'data-agenda="rel-20 study of 6gr || beam management" data-count="3"' in page


def test_agenda_missing_from_latest_meeting_is_listed_separately():
    page = html_part(rh.render_html(CONFIG, DB))
    assert "최신 회의에는 없는 Agenda" in page
    assert '<span class="agenda-num">10.5.0</span>General aspects' in page


def test_delta_and_source_links():
    page = rh.render_html(CONFIG, DB)
    assert "RAN1#125 → RAN1#126" in page
    assert "https://ftp.invalid/RAN1#126.docx" in page
    assert "https://example.invalid/reports/by_agenda/rel-20-study-of-6gr.md" in page
    assert "확인 필요" in page and "WA 확정" in page


def test_section_card_chart_has_one_bar_per_meeting():
    page = rh.render_html(CONFIG, DB)
    assert page.count('<g class="bar') == 2 and page.count('<g class="bar latest"') == 1
    assert 'data-tip="RAN1#126: 결정 2건' in page


def test_output_is_deterministic():
    assert rh.render_html(CONFIG, DB) == rh.render_html(CONFIG, DB)


def test_meeting_counts_in_agenda_tree_are_buttons_for_that_meeting():
    page = html_part(rh.render_html(CONFIG, DB))
    # 숫자 셀은 해당 회의 결정만 펼치는 버튼, 0건은 버튼이 아님
    assert '<button type="button" class="cell" data-meet="RAN1#126" aria-pressed="false">2</button>' in page
    assert 'data-keys="[&quot;rel-20 study of 6gr || beam management&quot;]"' in page   # JSON 배열 (키에 '||' 포함)
    assert page.count('class="agenda-detail"') >= 4          # 모든 행 아래에 펼침 영역


def test_meetings_table_shows_extraction_check():
    db = {**DB, "meetings": {**DB["meetings"], "RAN1#126": {
        **DB["meetings"]["RAN1#126"],
        "health": {"summary": "확인 필요 1건", "stats": {}, "issues": [
            {"level": "warning", "code": "x", "message": "읽지 못한 줄 <1>개", "samples": ["9.1 · Agreement: A"]}]}}}}
    page = html_part(rh.render_html(CONFIG, db))
    assert '<span class="chip candidate">확인 필요 1건</span>' in page
    assert "읽지 못한 줄 &lt;1&gt;개" in page and "9.1 · Agreement: A" in page
    assert "점검 기록 없음" in page            # RAN1#125에는 점검 기록이 없음


def test_provisional_meeting_has_notice_and_chips():
    db = {**DB, "meetings": {**DB["meetings"], "RAN1#126": {
        **DB["meetings"]["RAN1#126"], "provisional": {"doc": "Draft Chair notes RAN1#126_v01.docx", "reason": "r"}}}}
    page = rh.render_html(CONFIG, db)
    html = html_part(page)
    assert 'class="notice small"' in html and "Draft Chair notes RAN1#126_v01.docx" in html
    assert html.count('<span class="chip candidate">잠정</span>') >= 3   # 안내, 최신 회의, 회의 목록
    assert '"provisional":["RAN1#126"]' in page
    assert 'class="notice small"' not in html_part(rh.render_html(CONFIG, DB))


def test_last_update_is_at_the_top_with_a_slot_for_the_check_time():
    page = html_part(rh.render_html(CONFIG, {**DB, "updated_at": "2026-10-17T01:52:52+00:00"}))
    header = page[page.index("<header>"):]
    assert header.index('<p class="updated">') < header.index("<h1>")
    # Pages 게시 단계(auto_tracker.yml)가 이 자리 표시를 그대로 찾아 바꾸므로 형식이 바뀌면 안 됩니다.
    assert '마지막 업데이트 <b>2026-10-17 10:52 KST</b><span class="checked" hidden>__CHECKED_AT__</span>' in page
    assert "마지막 업데이트 <b>기록 없음</b>" in html_part(rh.render_html(CONFIG, DB))


def test_workflow_stamps_the_exact_placeholder():
    from pathlib import Path
    workflow = (Path(__file__).parent.parent / ".github" / "workflows" / "auto_tracker.yml").read_text()
    assert rh.CHECKED_AT.replace('"', '\\"') in workflow
