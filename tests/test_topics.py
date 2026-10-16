# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
from scripts import generate_report as gr
from scripts import render_html as rh
from scripts import topics

TOPICS = [
    {"id": "dmrs", "name": "DMRS", "keywords": ["DMRS", "DM-RS"]},
    {"id": "srs", "name": "SRS", "keywords": ["SRS"]},
]
CONFIG = {"items": [{"id": "bm", "name": "Beam", "release": "Rel-20"}], "topics": TOPICS}


def e(meeting, n, text, title="DL shared"):
    return {"id": f"{meeting}:10.5.2.2:{n:03d}", "meeting": meeting, "item": "bm", "agenda_item": "10.5.2.2",
            "agenda_title": title, "type": "Agreement", "text": text, "ffs": [],
            "source": {"doc": "Chair notes", "kind": "chairman_note", "url": f"https://ftp.invalid/{meeting}"}}


DB = {"schema_version": 1, "meetings": {}, "entries": [
    e("RAN1#125", 1, "Support 6GR DL DMRS type 1"),
    e("RAN1#126", 1, "Study DM-RS ports for co-scheduled UEs"),
    e("RAN1#126", 2, "SRS repetition with TD-OCC"),
    e("RAN1#126", 3, "Use pdmrsx and SRSabc"),          # 단어 일부만 같으면 제외
    e("RAN1#126", 4, "Nothing related"),
]}


def test_keywords_match_whole_terms_only():
    assert [x["id"] for x in topics.entries_for(DB, TOPICS[0])] == ["RAN1#125:10.5.2.2:001", "RAN1#126:10.5.2.2:001"]
    assert [x["id"] for x in topics.entries_for(DB, TOPICS[1])] == ["RAN1#126:10.5.2.2:002"]


def test_keyword_match_is_case_insensitive_and_checks_agenda_title():
    db = {"entries": [e("RAN1#126", 9, "Some text", title="dmrs design")]}
    assert len(topics.entries_for(db, TOPICS[0])) == 1


def test_markdown_topic_report_written(tmp_path):
    gr.write_reports(CONFIG, DB, tmp_path)
    md = (tmp_path / "by_topic" / "dmrs.md").read_text()
    assert "# 주제: DMRS" in md and "Study DM-RS ports" in md and "https://ftp.invalid/RAN1#126" in md
    assert "[DMRS](by_topic/dmrs.md)" in (tmp_path / "README.md").read_text()


def test_html_has_topic_section_with_counts_and_sources():
    page = rh.render_html(CONFIG, DB)
    assert 'id="topic-dmrs"' in page
    assert "DMRS" in page and "2건" in page
    assert "Study DM-RS ports for co-scheduled UEs" in page


def test_no_topics_configured_means_no_section():
    page = rh.render_html({"items": CONFIG["items"]}, DB)
    assert "주제별 보기" not in page
