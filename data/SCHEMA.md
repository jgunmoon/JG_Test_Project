# agreements_db.json 스키마

누적 데이터베이스는 이 프로젝트의 단일 기준(Single Source of Truth)입니다.
리포트는 모두 이 파일에서 생성하며, 리포트 파일을 직접 수정하지 않습니다.
DB는 `scripts/parse_agreements.py`가 Chair notes에서 만들며, 같은 문서를 다시 넣으면 그 회의 항목만 교체됩니다.

```json
{
  "schema_version": 1,
  "updated_at": "2026-10-17T01:52:52+00:00",
  "meetings": {
    "RAN1#126": {
      "ftp_dir": "TSGR1_126",
      "chair_notes_url": "https://www.3gpp.org/ftp/.../Chair%20notes%20RAN1%23126_eom1.docx",
      "agenda_source": "agenda.csv",
      "parser_version": 6,
      "provisional": {"doc": "Draft Chair notes RAN1#126bis_v03.docx", "reason": "회의 종료본(eom) Chair notes가 아직 없음 (…)"},
      "health": {"summary": "확인 필요 1건", "issues": [{"level": "warning", "code": "unrecognized_markers", "message": "…", "samples": ["…"]}],
                 "stats": {"markers": 356, "extracted": 356, "quoted": 0, "empty": 0, "outside": 0}}
    }
  },
  "entries": [
    {
      "id": "RAN1#126:9.1.1:001",
      "meeting": "RAN1#126",
      "agenda_item": "9.1.1",
      "agenda_title": "CSI spatial/frequency compression without temporal aspects (“Case 0”)",
      "agenda_path": [
        {"number": "9", "title": "Release 20 NR"},
        {"number": "9.1", "title": "Artificial Intelligence (AI)/Machine Learning (ML) for NR air interface enhancements"},
        {"number": "9.1.1", "title": "CSI spatial/frequency compression without temporal aspects (“Case 0”)"}
      ],
      "type": "Agreement",
      "text": "합의 원문 (요약하지 않고 그대로, 하위 항목은 '- '로 들여쓰기)",
      "ffs": ["FFS: reportQuantity"],
      "source": {
        "doc": "Chair notes RAN1#126_eom1",
        "kind": "chairman_note",
        "url": "https://www.3gpp.org/ftp/.../Chair%20notes%20RAN1%23126_eom1.docx",
        "tdoc": "R1-2606361",
        "tdoc_url": "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606361.zip",
        "discussion": "126-R20-6GR-Beam management"
      }
    }
  ]
}
```

## 필드 규칙

| 필드 | 규칙 |
|---|---|
| `id` | `회의:Agenda:순번`. 같은 문서를 다시 파싱하면 같은 값이 나옵니다. |
| `type` | `Agreement`, `Working Assumption`, `Conclusion` 중 하나. 벤더 제안(Proposal)이나 Observation은 저장하지 않습니다. |
| `agenda_path` | **필수.** 최상위 Agenda부터 결정이 기록된 Agenda까지의 번호와 제목. 결정은 모든 Agenda에서 기록합니다. |
| `updated_at` | 새 회의 결과가 DB에 마지막으로 반영된 시각(UTC). 대시보드·README 맨 위 '마지막 업데이트'에 한국시간으로 표시합니다. |
| `meetings.*.provisional` | 선택. 회의 종료본이 아닌 최신 Chair notes로 처리한 '잠정' 회의에만 있습니다. 종료본으로 다시 처리하면 사라집니다. |
| `agenda_item` | 결정이 기록된 Agenda 번호. 공식 agenda.csv가 있으면(RAN1#124~) 그 번호, 없으면 Chair notes의 Word 자동 번호로 계산한 값입니다. |
| `text` | 원문 그대로 저장합니다. 요약은 리포트 단계에서만 합니다. |
| `ffs` | 결정 안에 남아 있는 FFS 줄 목록. 별도 결정이 아니라 미결 항목입니다. |
| `source.doc`, `source.url` | **필수.** Chair notes 파일 이름과 FTP 원문 링크 |
| `source.kind` | `chairman_note`, `tdoc`, `tr`, `ts` 중 하나 |
| `source.tdoc`, `source.tdoc_url` | 선택. 결정 바로 앞의 근거 TDoc(주로 FL summary) |
| `source.discussion` | 선택. 결정을 묶는 이메일 토론 태그 (6GR 구간에서 주로 사용) |
