# 테스트용 데이터는 모두 가상의 값입니다 (실제 3GPP 합의 내용이 아님).
import json
import re

from scripts import generate_report as gr
from scripts import render_html as rh

CONFIG = {"items": [{"id": "bm", "name": "Beam", "release": "Rel-20"}],
          "search_presets": ["DMRS", "PT-RS"]}


def e(meeting, n, text):
    return {"id": f"{meeting}:10.5.2.2:{n:03d}", "meeting": meeting, "item": "bm", "agenda_item": "10.5.2.2",
            "agenda_title": "DL shared", "type": "Agreement", "text": text, "ffs": [],
            "source": {"doc": "Chair notes", "kind": "chairman_note", "url": f"https://ftp.invalid/{meeting}",
                       "tdoc": "R1-2600001", "tdoc_url": "https://ftp.invalid/R1-2600001.zip"}}


DB = {"schema_version": 1, "meetings": {}, "entries": [
    e("RAN1#125", 1, "Support 6GR DL DMRS type 1"),
    e("RAN1#126", 1, "Text with </script><img src=x onerror=alert(1)> inside"),
]}


def embedded(page):
    m = re.search(r'<script type="application/json" id="decisions">(.*?)</script>', page, re.S)
    return json.loads(m.group(1))


def test_all_decisions_are_embedded_for_in_browser_search():
    data = embedded(rh.render_html(CONFIG, DB))
    assert len(data["entries"]) == 2
    first = data["entries"][0]
    assert first["meeting"] == "RAN1#125" and first["text"] == "Support 6GR DL DMRS type 1"
    assert first["source"]["tdoc"] == "R1-2600001"
    assert data["items"] == {"bm": "Beam"}
    assert data["meetings"] == ["RAN1#125", "RAN1#126"]


def test_embedded_text_cannot_close_the_script_tag():
    page = rh.render_html(CONFIG, DB)
    assert page.count("</script>") == page.count("<script")   # 본문의 </script>가 태그를 닫지 않음
    assert "<\\/script>" in page
    assert embedded(page)["entries"][1]["text"].startswith("Text with </script>")


def test_search_controls_and_presets():
    page = rh.render_html(CONFIG, DB)
    for el in ('id="q"', 'id="f-item"', 'id="f-meeting"', 'id="f-type"', 'id="f-word"', 'id="results"'):
        assert el in page
    assert 'data-preset="DMRS"' in page and 'data-preset="PT-RS"' in page


def test_topic_reports_are_no_longer_written(tmp_path):
    gr.write_reports(CONFIG, DB, tmp_path)
    assert not (tmp_path / "by_topic").exists()
    assert "검색" in (tmp_path / "README.md").read_text()
