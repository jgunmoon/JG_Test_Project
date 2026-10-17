"""공식 Agenda를 기준으로 결정을 묶고, 회의를 넘어 같은 Agenda를 이어 붙입니다.

Agenda 번호와 위치는 회의마다 바뀝니다 (예: 6GR Beam management #125 10.5.2.4 → #126 10.5.3.4).
그래서 회의 간 연결은 번호가 아니라 '최상위 Agenda(섹션) 제목 + 그 Agenda 제목'으로 합니다.
같은 회의 안에 같은 제목이 여러 번 나오면(예: 'Other aspects') 상위 제목 전체 경로로 구분합니다.
제목이 바뀐 Agenda는 억지로 잇지 않고 별개로 둡니다 (최신 회의에 없으면 '이전 회의에만 있던 Agenda').
"""
from collections import defaultdict

from scripts.generate_report import meeting_sort_key


def norm(title):
    title = title.replace("“", '"').replace("”", '"').replace("’", "'")
    return " ".join(title.lower().split()).rstrip(" .:")


def number_key(number):
    return tuple(int(x) for x in number.split(".") if x.isdigit())


def _key(path_titles, unique_leaf):
    section, leaf = norm(path_titles[0]), norm(path_titles[-1])
    return f"{section} || {leaf}" if unique_leaf else f"{section} || " + " > ".join(norm(t) for t in path_titles[1:])


def build_index(db):
    meetings = sorted({e["meeting"] for e in db["entries"]}, key=meeting_sort_key)
    # 회의 안에서 (섹션, 제목)이 서로 다른 번호에 두 번 이상 나오면 제목만으로는 구분할 수 없습니다.
    seen = defaultdict(set)
    for e in db["entries"]:
        p = e["agenda_path"]
        seen[(e["meeting"], norm(p[0]["title"]), norm(p[-1]["title"]))].add(p[-1]["number"])

    lineages, entry_keys = {}, {}
    for e in sorted(db["entries"], key=lambda x: meeting_sort_key(x["meeting"])):
        p = e["agenda_path"]
        titles = [n["title"] for n in p]
        unique = len(seen[(e["meeting"], norm(titles[0]), norm(titles[-1]))]) == 1
        key = _key(titles, unique)
        entry_keys[e["id"]] = key
        lin = lineages.setdefault(key, {"key": key, "numbers": {}, "counts": {}})
        lin["numbers"][e["meeting"]] = p[-1]["number"]
        lin["counts"][e["meeting"]] = lin["counts"].get(e["meeting"], 0) + 1
        # 표시용 제목·경로는 가장 최근 회의 기준
        lin.update(title=titles[-1], path=p, section_title=titles[0], last_meeting=e["meeting"],
                   last_number=p[-1]["number"])
    return {"meetings": meetings, "lineages": lineages, "entry_keys": entry_keys, "entries": db["entries"]}


def number_history(lineage, meetings):
    """번호가 바뀐 경우 '#125: 10.5.2.4 → #126: 10.5.3.4' 형태, 바뀐 적 없으면 빈 문자열."""
    runs = []
    for m in meetings:
        n = lineage["numbers"].get(m)
        if n and (not runs or runs[-1][1] != n):
            runs.append((m, n))
    if len(runs) < 2:
        return ""
    return " → ".join(f"{m.replace('RAN1', '')}: {n}" for m, n in runs)


def tree(index):
    """최신 회의의 Agenda 목차(결정이 있는 Agenda와 그 상위 제목)를 번호 순으로 돌려줍니다.

    각 행의 counts는 그 Agenda와 하위 Agenda의 회의별 결정 수 합계이고 (이전 회의 이력 포함),
    keys는 그 합계에 들어간 연결 키 목록입니다.
    """
    latest = index["meetings"][-1]
    nodes = {}
    for e in index["entries"]:
        if e["meeting"] != latest:
            continue
        for depth, n in enumerate(e["agenda_path"]):
            nodes.setdefault(n["number"], {"number": n["number"], "title": n["title"], "depth": depth, "key": None,
                                           "section": section_key(e), "counts": defaultdict(int), "keys": set()})
        nodes[e["agenda_path"][-1]["number"]]["key"] = index["entry_keys"][e["id"]]
    current = {lin["key"]: lin for lin in index["lineages"].values() if lin["last_meeting"] == latest}
    for lin in current.values():
        num = lin["last_number"]
        for row in nodes.values():
            if num == row["number"] or num.startswith(row["number"] + "."):
                row["keys"].add(lin["key"])
                for m, c in lin["counts"].items():
                    row["counts"][m] += c
    rows = sorted(nodes.values(), key=lambda r: number_key(r["number"]))
    for r in rows:
        r["counts"] = dict(r["counts"])
        r["keys"] = sorted(r["keys"])  # 이 행과 하위 Agenda의 연결 키 (회의별 숫자를 눌렀을 때 펼칠 범위)
    return rows


def retired(index):
    """최신 회의에는 없는 Agenda (삭제됐거나 제목이 바뀐 것). 마지막으로 나온 회의가 최근인 순."""
    latest = index["meetings"][-1]
    old = [lin for lin in index["lineages"].values() if lin["last_meeting"] != latest]
    return sorted(old, key=lambda lin: (-index["meetings"].index(lin["last_meeting"]), number_key(lin["last_number"])))


def sections(index):
    """최신 회의의 최상위 Agenda (번호 순)."""
    latest = index["meetings"][-1]
    found = {}
    for e in index["entries"]:
        if e["meeting"] == latest:
            top = e["agenda_path"][0]
            found.setdefault(top["number"], {"number": top["number"], "title": top["title"], "key": norm(top["title"])})
    return sorted(found.values(), key=lambda s: number_key(s["number"]))


def section_key(entry):
    return norm(entry["agenda_path"][0]["title"])
