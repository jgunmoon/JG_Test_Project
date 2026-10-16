"""3GPP FTP에서 회의 폴더 목록과 회의 종료본 Chair notes를 찾아 내려받습니다.

    python -m scripts.fetch_ftp_docs TSGR1_126      # 해당 회의의 최종 Chair notes를 downloads/에 저장

- 3GPP 서버(Cloudflare)는 기본 User-Agent를 403으로 거부하므로 브라우저 User-Agent를 보냅니다.
- 회의 종료본은 'Chair notes RAN1#<번호>_eom<N>.docx' 형식이며, N이 가장 큰 것이 최종입니다.
  과거 회의는 'Chair notes RAN1#122 eom.zip'처럼 zip으로 올라온 경우도 있습니다.
"""
import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote

import requests

BASE_URL = "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"
# 실제 이름 예: '..._eom1.docx', '... eom.zip', '... - eom3.docx', '... - eom_03.docx', '... eom0.zip'
FINAL_CHAIR_NOTES = re.compile(r"Chair notes RAN1#\S+?(?:\s+-\s+|[ _])eom_?(\d*)\.(docx|docm|zip)", re.I)


def http_get(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    resp.raise_for_status()
    return resp


def parse_listing(html, url):
    """FTP 목록 페이지에서 바로 아래 항목 이름(디코딩된 값)만 돌려줍니다."""
    names = []
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(url) and href != url:
            name = unquote(href[len(url):].rstrip("/"))
            if name and "/" not in name and name not in names:
                names.append(name)
    return names


def list_dir(path):
    url = BASE_URL + path.strip("/") + "/" if path else BASE_URL
    return parse_listing(http_get(url).text, url)


def list_meeting_folders():
    return [n for n in list_dir("") if n.startswith("TSGR1_")]


def pick_final_chair_notes(names):
    """회의 종료본 중 가장 최신(eom 번호가 가장 큰) 파일 이름. 없으면 None (회의 중이거나 미업로드)."""
    finals = []
    for name in names:
        m = FINAL_CHAIR_NOTES.fullmatch(name)
        if m:
            finals.append((int(m.group(1) or 0), name))
    return max(finals)[1] if finals else None


def find_final_chair_notes(folder, lister=list_dir):
    """(파일 이름, FTP URL) 또는 None."""
    # 3GPP 서버는 없는 폴더에 404가 아니라 403을 돌려줘서 접속 차단과 구분되지 않습니다.
    # 그래서 상위 목록에서 폴더가 있는지 먼저 확인합니다.
    # 폴더 이름은 회의에 따라 'Chair_notes' 또는 'Chair_Notes'입니다.
    if "Inbox" not in lister(folder):
        return None
    sub = next((n for n in lister(f"{folder}/Inbox") if n.lower() == "chair_notes"), None)
    if not sub:
        return None
    name = pick_final_chair_notes(lister(f"{folder}/Inbox/{sub}"))
    if not name:
        return None
    return name, f"{BASE_URL}{folder}/Inbox/{sub}/{quote(name)}"


def fetch_agenda_csv(folder, lister=list_dir, getter=None):
    """공식 agenda.csv 내용(문자열). 없으면 None (RAN1#124 이전 회의에는 없음)."""
    if "Agenda" not in lister(folder) or "agenda.csv" not in lister(f"{folder}/Agenda"):
        return None
    getter = getter or (lambda url: http_get(url).content)
    raw = getter(f"{BASE_URL}{folder}/Agenda/agenda.csv")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def save_download(name, content, dest_dir):
    """내려받은 내용을 저장하고 파싱할 .docx 경로를 돌려줍니다. zip이면 안의 Word 파일을 꺼냅니다."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not name.lower().endswith(".zip"):
        path = dest_dir / Path(name).name
        path.write_bytes(content)
        return path
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        members = [i for i in z.infolist() if i.filename.lower().endswith((".docx", ".docm"))]
        if not members:
            raise ValueError(f"{name}: zip 안에 Word 파일이 없습니다")
        member = max(members, key=lambda i: i.file_size)
        # zip 안의 경로는 믿지 않고 파일 이름만 씁니다 (경로 탈출 방지).
        path = dest_dir / Path(member.filename.replace("\\", "/")).name
        path.write_bytes(z.read(member))
        return path


def download_chair_notes(folder, name, url, dest_root=DOWNLOAD_DIR):
    return save_download(name, http_get(url).content, Path(dest_root) / folder)


def main():
    if len(sys.argv) != 2:
        sys.exit("사용법: python -m scripts.fetch_ftp_docs TSGR1_<번호>")
    folder = sys.argv[1]
    final = find_final_chair_notes(folder)
    if not final:
        sys.exit(f"{folder}: 회의 종료본 Chair notes가 아직 없습니다")
    path = download_chair_notes(folder, *final)
    print(f"{final[0]} → {path}")
    print(f"URL: {final[1]}")


if __name__ == "__main__":
    main()
