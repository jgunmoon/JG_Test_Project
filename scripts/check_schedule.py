"""새로 끝난 회의를 찾아 수집 → 파싱 → 리포트 생성까지 한 번에 실행합니다 (자동 실행 진입점).

    python -m scripts.check_schedule              # 처리할 회의가 있으면 DB와 리포트 갱신
    python -m scripts.check_schedule --dry-run    # 처리할 회의만 출력
    python -m scripts.check_schedule --since RAN1#122   # 시작 회의를 바꿔 과거 회의 채우기

'회의 종료 다음 날' 판단은 일정표 날짜가 아니라 FTP 상태로 합니다.
회의 종료본 Chair notes(_eom)가 새로 올라왔거나(_eom → _eom1 등) 갱신된 회의만 처리하므로,
매일 실행하면 최종본이 올라온 다음 실행에서 반영됩니다. 같은 문서를 같은 파서 버전으로
이미 처리했으면 건너뛰고, 파서 버전(PARSER_VERSION)이 바뀌면 다시 처리합니다.
"""
import argparse
import json
import os

import yaml

from scripts import fetch_ftp_docs as ff
from scripts import health
from scripts.generate_report import ROOT, meeting_sort_key, write_reports
from scripts.parse_agreements import (PARSER_VERSION, meeting_id_from_folder, merge_meeting, parse_agenda_csv,
                                     parse_chair_notes)

CONFIG_PATH = ROOT / "config" / "tracked_items.yaml"
DB_PATH = ROOT / "data" / "agreements_db.json"


def pending_meetings(db, folders, finder, since):
    """처리가 필요한 회의 목록 (오래된 순)."""
    start = meeting_sort_key(since)
    candidates = []
    for folder in folders:
        try:
            meeting = meeting_id_from_folder(folder)
        except ValueError:
            continue  # TSGR1_AH 같은 회의가 아닌 폴더
        if meeting_sort_key(meeting) >= start:
            candidates.append((meeting, folder))

    pending = []
    for meeting, folder in sorted(candidates, key=lambda c: meeting_sort_key(c[0])):
        final = finder(folder)
        if not final:
            continue
        name, url = final
        done = db["meetings"].get(meeting, {})
        if done.get("chair_notes_url") == url and done.get("parser_version") == PARSER_VERSION:
            continue  # 같은 문서를 같은 파서로 이미 처리함
        pending.append({"meeting": meeting, "folder": folder, "name": name, "url": url})
    return pending


def report_issues(meeting, issues):
    """점검 결과를 출력합니다. GitHub Actions에서는 '확인 필요'를 실행 화면의 경고로도 띄웁니다."""
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for i in issues:
        mark = "확인 필요" if i["level"] == "warning" else "참고"
        print(f"    [{mark}] {i['message']}")
        for sample in i["samples"]:
            print(f"        - {sample}")
        if in_actions and i["level"] == "warning":
            print(f"::warning title={meeting} 추출 점검::{i['message']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="처리할 회의만 출력")
    ap.add_argument("--since", help="이 회의부터 확인 (기본값: config의 track_from)")
    args = ap.parse_args()

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    since = args.since or config["track_from"]

    pending = pending_meetings(db, ff.list_meeting_folders(), ff.find_final_chair_notes, since)
    if not pending:
        print(f"{since} 이후 새로 처리할 회의가 없습니다.")
        return
    for p in pending:
        status = "갱신" if p["meeting"] in db["meetings"] else "신규"
        print(f"[{status}] {p['meeting']}: {p['name']}")
    if args.dry_run:
        return

    for p in pending:
        path = ff.download_chair_notes(p["folder"], p["name"], p["url"])
        agenda_csv = ff.fetch_agenda_csv(p["folder"])
        agenda = parse_agenda_csv(agenda_csv) if agenda_csv else None
        stats = {}
        entries, warnings = parse_chair_notes(path, p["meeting"], p["url"], agenda=agenda, stats=stats)
        meta = {
            "ftp_dir": p["folder"],
            "chair_notes_url": p["url"],
            "agenda_source": "agenda.csv" if agenda else "chair_notes_numbering",
            "parser_version": PARSER_VERSION,
        }
        merge_meeting(db, p["meeting"], entries, meta)
        issues = health.check(p["meeting"], db, stats, warnings, agenda)
        meta["health"] = {"summary": health.summary(issues), "issues": issues,
                          "stats": {k: v for k, v in stats.items() if k != "unrecognized"}}
        print(f"  {p['meeting']}: {len(entries)}건 추출 · 추출 점검: {meta['health']['summary']}")
        report_issues(p["meeting"], issues)

    write_reports(config, db, ROOT / "reports")
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DB와 리포트를 갱신했습니다.")


if __name__ == "__main__":
    main()
