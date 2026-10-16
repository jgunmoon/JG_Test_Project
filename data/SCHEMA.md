# agreements_db.json 스키마

누적 데이터베이스는 이 프로젝트의 단일 기준(Single Source of Truth)입니다.
리포트는 모두 이 파일에서 생성하며, 리포트 파일을 직접 수정하지 않습니다.

```json
{
  "schema_version": 1,
  "meetings": {
    "RAN1#118": {
      "start": "YYYY-MM-DD",
      "end": "YYYY-MM-DD",
      "ftp_dir": "TSGR1_118",
      "processed_at": "YYYY-MM-DDTHH:MM:SSZ"
    }
  },
  "entries": [
    {
      "id": "RAN1#118:csi_prediction:001",
      "meeting": "RAN1#118",
      "item": "csi_prediction",
      "agenda_item": "9.1.x",
      "type": "Agreement",
      "text": "합의 원문 (요약하지 않고 그대로 저장)",
      "source": {
        "doc": "R1-24xxxxx",
        "kind": "chairman_note",
        "url": "https://www.3gpp.org/ftp/..."
      }
    }
  ]
}
```

## 필드 규칙

| 필드 | 규칙 |
|---|---|
| `type` | `Agreement`, `Working Assumption`, `FFS`, `Conclusion` 중 하나 |
| `text` | 원문 그대로 저장합니다. 요약은 리포트 단계에서만 합니다. |
| `source.doc` | **필수.** 출처 문서 번호가 없는 항목은 저장하지 않습니다. |
| `source.url` | **필수.** FTP의 원문 링크 |
| `source.kind` | `chairman_note`, `tdoc`, `tr`, `ts` 중 하나 |
