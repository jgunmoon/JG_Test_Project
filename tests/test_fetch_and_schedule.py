# FTP 목록·파일은 모두 코드로 만든 가상 데이터입니다 (네트워크 사용 안 함).
import io
import zipfile

from scripts import check_schedule as cs
from scripts import fetch_ftp_docs as ff

BASE = "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/"


def listing(url, names):
    """3GPP FTP 목록 페이지와 같은 형식의 HTML."""
    links = "".join(
        f'<a class="file" href="{url}{n.replace(" ", "%20").replace("#", "%23")}">{n}</a>\n' for n in names)
    return f'<html><a href="{url.rsplit("/", 2)[0]}/">parent</a>{links}</html>'


def test_list_dir_returns_unquoted_child_names_only():
    url = BASE + "TSGR1_126/Inbox/Chair_notes/"
    html = listing(url, ["Chair notes RAN1#126_eom1.docx", "Sub"])
    assert ff.parse_listing(html, url) == ["Chair notes RAN1#126_eom1.docx", "Sub"]


def test_final_chair_notes_picks_highest_eom_and_ignores_drafts():
    names = [
        "Chair notes RAN1#124bis_eom.docx", "Chair notes RAN1#124bis_eom5.docx",
        "Chair notes RAN1#124bis_eom2.docx", "Chair notes RAN1#124bis_v15.docx",
        "Draft Chair notes RAN1#124bis_eom9.docx", "RAN1#124b online and offline schedules - v00.docx",
    ]
    assert ff.pick_final_chair_notes(names) == "Chair notes RAN1#124bis_eom5.docx"


def test_final_chair_notes_accepts_zip_with_space_separator():
    assert ff.pick_final_chair_notes(["Chair notes RAN1#122 v14.zip", "Chair notes RAN1#122 eom.zip"]) \
        == "Chair notes RAN1#122 eom.zip"


def test_final_chair_notes_name_variants_seen_on_ftp():
    cases = {
        "TSGR1_120b": (["Chair notes RAN1#120bis v19.zip", "Chair notes RAN1#120bis eom0.zip"], "eom0.zip"),
        "TSGR1_122b": (["Chair notes RAN1#122b eom.docx", "Chair notes RAN1#122b eom4.docx"], "eom4.docx"),
        "TSGR1_123": (["Chair notes RAN1#123 - v09.docx", "Chair notes RAN1#123 - eom3.docx"], "eom3.docx"),
        "TSGR1_124": (["Chair notes RAN1#124 - eom.docx", "Chair notes RAN1#124 - eom_03.docx",
                       "Chair notes RAN1#124 - eom_01.docx", "Chair notes RAN1#124 - v10.docx"], "eom_03.docx"),
    }
    for folder, (names, expected) in cases.items():
        assert ff.pick_final_chair_notes(names).endswith(expected), folder


def test_chair_notes_folder_name_is_case_insensitive():
    tree = {"TSGR1_122b": ["Inbox"], "TSGR1_122b/Inbox": ["Chair_Notes"],
            "TSGR1_122b/Inbox/Chair_Notes": ["Chair notes RAN1#122b eom4.docx"]}
    _, url = ff.find_final_chair_notes("TSGR1_122b", lister=tree.__getitem__)
    assert "/Inbox/Chair_Notes/" in url


def test_no_final_chair_notes_while_meeting_is_running():
    assert ff.pick_final_chair_notes(["Chair notes RAN1#126bis_v00.docx",
                                      "Draft Chair notes RAN1#126bis_v01.docx"]) is None


def test_zip_download_extracts_the_docx_safely(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../evil/Chair notes.docx", b"DOCX")   # zip 경로 탈출 시도
        z.writestr("readme.txt", b"x")
    path = ff.save_download("Chair notes RAN1#122 eom.zip", buf.getvalue(), tmp_path)
    assert path == tmp_path / "Chair notes.docx"
    assert path.read_bytes() == b"DOCX"
    assert not (tmp_path.parent / "evil").exists()


def test_docx_download_is_saved_as_is(tmp_path):
    path = ff.save_download("Chair notes RAN1#126_eom1.docx", b"DOCX", tmp_path)
    assert path.read_bytes() == b"DOCX"


def test_find_final_returns_none_when_chair_notes_folder_is_missing():
    tree = {"TSGR1_128": ["Agenda", "Inbox"], "TSGR1_128/Inbox": ["drafts"]}
    assert ff.find_final_chair_notes("TSGR1_128", lister=tree.__getitem__) is None


def test_status_explains_why_there_is_no_final_yet():
    tree = {"TSGR1_126b": ["Inbox"], "TSGR1_126b/Inbox": ["Chair_notes", "drafts"],
            "TSGR1_126b/Inbox/Chair_notes": ["Chair notes RAN1#126bis_v00.docx",
                                              "Draft Chair notes RAN1#126bis_v01.docx",
                                              "RAN1#126b online and offline schedules - v00.docx"]}
    st = ff.chair_notes_status("TSGR1_126b", lister=tree.__getitem__)
    assert st["final"] is None
    assert st["reason"] == ("회의 종료본(eom) Chair notes가 아직 없음 (지금 있는 Chair notes: "
                            "Chair notes RAN1#126bis_v00.docx, Draft Chair notes RAN1#126bis_v01.docx)")
    assert "Chair_notes 폴더" in ff.chair_notes_status(
        "TSGR1_128", lister={"TSGR1_128": ["Inbox"], "TSGR1_128/Inbox": []}.__getitem__)["reason"]
    assert "Inbox" in ff.chair_notes_status("TSGR1_129", lister={"TSGR1_129": ["Agenda"]}.__getitem__)["reason"]


def test_find_final_returns_quoted_ftp_url():
    tree = {"TSGR1_126": ["Inbox"], "TSGR1_126/Inbox": ["Chair_notes"],
            "TSGR1_126/Inbox/Chair_notes": ["Chair notes RAN1#126_eom1.docx"]}
    name, url = ff.find_final_chair_notes("TSGR1_126", lister=tree.__getitem__)
    assert url == BASE + "TSGR1_126/Inbox/Chair_notes/Chair%20notes%20RAN1%23126_eom1.docx"


def fake_finder(table):
    def status(folder):
        name = table.get(folder)
        if not name:
            return {"final": None, "reason": "회의 종료본(eom) Chair notes가 아직 없음"}
        return {"final": (name, f"{BASE}{folder}/Inbox/Chair_notes/{name}"), "reason": None}
    return status


def test_pending_meetings_are_new_or_updated_finals_since_start():
    folders = ["TSGR1_124b", "TSGR1_125", "TSGR1_126", "TSGR1_126b", "TSGR1_AH"]
    finder = fake_finder({
        "TSGR1_124b": "Chair notes RAN1#124bis_eom5.docx",   # 시작 회의 이전 → 제외
        "TSGR1_125": "Chair notes RAN1#125_eom.docx",        # 이미 처리됨 → 제외
        "TSGR1_126": "Chair notes RAN1#126_eom1.docx",       # eom → eom1 갱신 → 재처리
        "TSGR1_126b": None,                                   # 회의 중 → 제외
    })
    v = cs.PARSER_VERSION
    db = {"meetings": {
        "RAN1#125": {"chair_notes_url": f"{BASE}TSGR1_125/Inbox/Chair_notes/Chair notes RAN1#125_eom.docx",
                     "parser_version": v},
        "RAN1#126": {"chair_notes_url": f"{BASE}TSGR1_126/Inbox/Chair_notes/Chair notes RAN1#126_eom.docx",
                     "parser_version": v},
    }}
    skipped = []
    pending = cs.pending_meetings(db, folders, finder, since="RAN1#125", skipped=skipped)
    assert [(p["folder"], p["meeting"]) for p in pending] == [("TSGR1_126", "RAN1#126")]
    assert skipped == [
        {"meeting": "RAN1#125", "status": "반영됨", "reason": "같은 문서를 이미 반영함 (Chair notes RAN1#125_eom.docx)"},
        {"meeting": "RAN1#126bis", "status": "대기", "reason": "회의 종료본(eom) Chair notes가 아직 없음"},
    ]


def test_meeting_is_reprocessed_when_parser_version_changes():
    url = f"{BASE}TSGR1_125/Inbox/Chair_notes/Chair notes RAN1#125_eom.docx"
    finder = fake_finder({"TSGR1_125": "Chair notes RAN1#125_eom.docx"})
    old = {"meetings": {"RAN1#125": {"chair_notes_url": url, "parser_version": cs.PARSER_VERSION - 1}}}
    same = {"meetings": {"RAN1#125": {"chair_notes_url": url, "parser_version": cs.PARSER_VERSION}}}
    assert len(cs.pending_meetings(old, ["TSGR1_125"], finder, since="RAN1#125")) == 1
    assert cs.pending_meetings(same, ["TSGR1_125"], finder, since="RAN1#125") == []


def test_finder_is_not_called_for_meetings_before_start():
    calls = []

    def finder(folder):
        calls.append(folder)
        return {"final": None, "reason": "x"}

    cs.pending_meetings({"meetings": {}}, ["TSGR1_100", "TSGR1_126"], finder, since="RAN1#126")
    assert calls == ["TSGR1_126"]


def test_fetch_agenda_csv_only_when_present():
    tree = {"TSGR1_123": ["Agenda"], "TSGR1_123/Agenda": ["R1-2509000.zip"],
            "TSGR1_124": ["Agenda"], "TSGR1_124/Agenda": ["agenda.csv"]}
    assert ff.fetch_agenda_csv("TSGR1_123", lister=tree.__getitem__) is None
    text = ff.fetch_agenda_csv("TSGR1_124", lister=tree.__getitem__,
                               getter=lambda url: '\ufeff"1","Opening"'.encode("utf-8"))
    assert text == '"1","Opening"'
