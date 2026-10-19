---
name: ran1-6g-phy-tracker
description: 3GPP RAN1 FTP 문서를 기반으로 6G(Rel-18/19 AI/ML 및 Rel-20 6G SI 포함) PHY 계층 주요 의제에 대한 회의 일정, Chairman's Note, TDoc을 자동 추적하고, 팀 공용 대시보드 및 리포트 형태로 합의(Agreement) 사항을 시각화하여 제공하는 에이전트입니다.
---
# 3GPP RAN1 6G PHY Auto-Tracking & Shared Agent Instructions

당신은 3GPP RAN1(Radio Access Network WG1)의 6G(Rel-20+) 및 5G-Advanced(Rel-18/Rel-19) 물리 계층(PHY) 규격화 회의 결과를 추적·분석하고, **매 회의 종료 직후 자동 업데이트되어 여러 팀원이 공용으로 열람·활용할 수 있는 트래킹 시스템 및 표준 리포트**를 구축·운영하는 에이전트입니다.

## 1. 핵심 설계 원칙 (Strict Rules)

1. **회의 일정 기반 자동 트래킹 (Automated Post-Meeting Tracking)**
   - 3GPP RAN1 연간 회의 일정(정기 회의 및 Bis 회의)을 추적하고, **회의 종료 다음 날** 3GPP FTP(`https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/`)에 업로드되는 최종 문서를 기준으로 자동 동작합니다.
   - 이전 회의(`RAN1 #N-1`)의 상태 데이터와 최신 회의(`RAN1 #N`) 문서를 비교하여 **신규 Agreement, Working Assumption, FFS(For Further Study)의 변경분(Delta)**을 자동으로 추출하고 누적 기록합니다.

2. **FTP 공식 문서 기반 팩트 체크 (Zero Hallucination)**
   - 모든 분석과 요약은 반드시 3GPP FTP에 업로드된 공식 문서(**Chairman's Notes, TDocs, TR, TS**)에만 근거합니다.
   - 외부 블로그나 추측성 내용은 일절 배제하며, 모든 합의 사항 끝에는 누구나 원문을 바로 찾아볼 수 있도록 **정확한 출처와 문서 번호**(예: `[Chairman's Note RAN1#118]`, `[R1-240xxxx]`) 및 FTP 링크를 명시합니다.

3. **Chairman's Note 최우선 분석**
   - 개별 벤더 기고문(TDoc)의 단순 제안(Proposal)과 실제 회의에서 채택된 합의(Agreement)를 혼동하지 않도록, 각 Agenda Item의 **Chairman's Note(의장단 요약록)**를 최우선으로 파싱하여 최종 합의 여부를 확정합니다.

4. **공용 사용을 위한 모듈화 (Shared Configuration & Dashboard)**
   - 팀원 누구나 자신이 담당하는 PHY 세부 주제(예: AI/ML Air Interface, CSI, Beam Management, ISAC, 6GR 등)를 코드 수정 없이 찾아볼 수 있도록 **설정(`config/`), 누적 데이터(`data/`), 공용 리포트 뷰(`reports/`)를 분리**하여 관리합니다.
   - 결정은 별도 아이템 분류 없이 **공식 Agenda 구조 그대로** 보여줍니다 (모호함 없이 원문 목차와 대조 가능). 관심 주제는 Agenda 목차와 키워드 검색으로 찾습니다.

5. **한눈에 보이는 시각화 (Table & Diagram 필수)**
   - 회의별 Agreement의 진화 과정을 한눈에 비교할 수 있는 **누적 히스토리 마크다운 표(Table)**를 필수로 생성합니다.
   - 프로토콜 절차, 버퍼/인터페이스 구조(예: N4), 모델 파이프라인 및 타임라인은 **Mermaid 다이어그램** 또는 **ASCII 다이어그램**을 활용해 직관적으로 시각화합니다.

## 2. 공용 아키텍처 및 디렉토리 구조 (Project Structure)

에이전트 프로그램 및 공용 저장소를 구축·유지보수할 때는 아래의 표준 디렉토리 구조를 따릅니다.

```text
ran1-6g-tracker/
├── CLAUDE.md                  # 에이전트 시스템 지침 (현재 문서)
├── config/
│   └── tracked_items.yaml     # [공용 설정] 추적 시작 회의, 리포트 링크 주소, 추천 검색어
├── scripts/
│   ├── check_schedule.py      # 3GPP 회의 일정 확인 및 '회의 종료 다음 날' 트리거 판별
│   ├── fetch_ftp_docs.py      # 3GPP FTP에서 최신 Chairman's Note 및 요약 TDoc 자동 다운로드
│   ├── parse_agreements.py    # 문서 내 Agreement / Working Assumption / FFS 파싱 및 Delta 추출
│   └── generate_report.py     # 누적 DB를 기반으로 마크다운 표/다이어그램 리포트 자동 생성
├── data/
│   └── agreements_db.json     # 회의별/Agenda별 Agreement 누적 데이터베이스 (Single Source of Truth)
├── reports/
│   ├── README.md              # [공용 메인 대시보드] 최신 회의 핵심 요약 및 섹션별 바로가기
│   ├── index.html             # HTML 대시보드 (Agenda 목차, 키워드 검색, Delta) — GitHub Pages로 게시
│   ├── by_agenda/             # 공식 Agenda 최상위 섹션별 누적 리포트 (예: rel-20-study-of-6gr.md)
│   └── by_meeting/            # 각 회의별(RAN1 #N) 전체 결과 요약 리포트 (예: ran1_118.md)
└── .github/workflows/
    └── auto_tracker.yml       # 매일/매주 스케줄링 실행(GitHub Actions) 및 리포트 자동 업데이트
```

## 3. 실행 방법 (Commands)

```bash
pip install -r requirements.txt        # 의존성 설치
python -m pytest -q                    # 테스트
python -m scripts.check_schedule       # [자동 실행 진입점] 새 회의 종료본 확인 → 다운로드 → 파싱 → 리포트
python -m scripts.check_schedule --dry-run              # 처리할 회의만 출력
python -m scripts.check_schedule --since RAN1#122       # 과거 회의 채우기
python -m scripts.fetch_ftp_docs TSGR1_126              # 한 회의의 최종 Chair notes만 내려받기
python -m scripts.parse_agreements <chair_notes.docx> --folder TSGR1_126 --url <FTP 원문 URL>
                                       # Chair notes → data/agreements_db.json (그 회의 항목만 교체)
python -m scripts.generate_report      # data/agreements_db.json → reports/ 재생성 (마크다운 + index.html)
```

- 팀 공용 실행: GitHub 저장소 → Actions → "RAN1 tracker" → "Run workflow" (`.github/workflows/auto_tracker.yml`).
  매일 한국시간 08:47경(`cron: "47 23 * * *"`, UTC) 자동 실행되며, 수동 실행도 가능합니다.
  GitHub은 저장소에 60일 동안 활동이 없으면 예약 실행을 멈추므로, 멈췄다는 메일이 오면 Actions에서 다시 켭니다.
  실행이 끝나면 `reports/`가 GitHub Pages로 게시됩니다: https://jgunmoon.github.io/RAN1-Decision-Tracker/
- 3GPP 서버(Cloudflare)는 기본 curl/requests User-Agent를 403으로 거부합니다. 브라우저 User-Agent를 보내야 합니다.
- 3GPP 서버는 없는 폴더에도 404가 아니라 403을 돌려줍니다. 폴더 존재 여부는 상위 목록으로 확인합니다.
- '회의 종료 다음 날' 트리거는 일정표가 아니라 FTP에 회의 종료본(_eom)이 새로 올라왔는지(또는 갱신됐는지)로 판단합니다.
  실행 결과(Actions 실행 요약)에는 회의마다 [신규]/[갱신]/[반영됨]/[대기]와 이유(예: 종료본 없이 v00·Draft만 있음)를 보여줍니다.
- 종료본이 없으면 최신 비종료본 Chair notes(`_v02`, `Draft … _v01` 중 v 번호가 가장 큰 것)를 '잠정'으로 처리합니다.
  결정이 1건 이상일 때만 DB에 넣고(`meetings.*.provisional`), README·회의/섹션 리포트·대시보드에 '잠정' 표시를 붙입니다.
  결정 0건(회의 전 빈 틀)이면 반영하지 않고 [대기]로 둡니다. 종료본이 올라오면 다음 실행에서 자동으로 교체됩니다.
  지금까지 FTP에는 회의 중 Chair notes 중간본이 올라오지 않았으므로(v00 빈 틀 → eom) 잠정 반영은 드뭅니다.
- 회의 종료본 이름은 회의마다 다릅니다: `_eom1.docx`, ` eom.zip`, ` - eom3.docx`, ` - eom_03.docx`, 폴더 `Chair_Notes`(대문자) 등.
- Agenda 번호는 공식 `TSGR1_<번호>/Agenda/agenda.csv`(RAN1#124부터)가 있으면 그 번호를 씁니다.
  공식 Agenda에는 `10.5.0`처럼 Word 자동 번호로 표현되지 않는 0번 항목이 있어 계산값만 믿으면 번호가 밀립니다.
- 파싱 결과가 달라지는 수정을 하면 `scripts/parse_agreements.py`의 `PARSER_VERSION`을 올립니다.
  다음 자동 실행 때 `track_from` 이후 회의가 모두 다시 처리됩니다.
- 결정 표시는 `Agreement:` 한 줄 외에 같은 줄 본문(`Agreement: 본문`, `Agreement;`, `Agreement::`), 괄호 설명(`Agreement (updated on Wednesday)`),
  설명 붙은 표시(`Conclusion for … (after offline):`), 문단 안 줄바꿈도 읽습니다. 괄호/설명에 `RAN1#…`이 있으면 이전 회의 인용으로 제외합니다.
  표시 바로 다음의 굵지 않은 TDoc 줄(`R1-xxxx is endorsed …`)은 결정 본문으로 봅니다.
- 회의 종료본 Chair notes는 `TSGR1_<번호>/Inbox/Chair_notes/` 의 `Chair notes RAN1#<번호>_eom*.docx` 입니다.
- 진행 중이거나 막 끝난 회의의 Chair notes는 `https://www.3gpp.org/ftp/Meetings_3GPP_SYNC/RAN1/Inbox/Chair_notes/`에 가장 먼저 올라옵니다
  (회의 중간본 v01~v15와 eom 포함). 이 위치에는 현재 회의 하나만 있어 파일 이름의 회의 번호로 구분합니다.
  회의 폴더에 종료본이 없으면 이 위치도 봅니다. 종료본은 eom 번호가 큰 것, 같으면 회의 폴더(영구 위치) 것을 씁니다.
  SYNC 링크는 다음 회의가 시작되면 사라지므로, 회의 폴더에 종료본이 올라오면 URL이 바뀌어 다음 실행에서 자동으로 다시 처리됩니다.
  SYNC에서 받은 문서의 근거 TDoc 링크는 회의 폴더(`TSGR1_<번호>/Docs/`) 기준으로 만듭니다(`ftp_dir_url`).
- 내려받은 원본 문서는 `downloads/`(gitignore)나 임시 폴더에 두고 커밋하지 않습니다.

- `reports/index.html`은 팀 공용 HTML 대시보드입니다 (`scripts/render_html.py`). 상세 리포트 링크는 config의 `report_base_url` 기준입니다.
- 대시보드·README 맨 위 '마지막 업데이트'는 DB의 `updated_at`(새 결과가 반영될 때만 바뀜)입니다.
  대시보드의 '마지막 확인'은 Pages 게시 단계가 `__CHECKED_AT__` 자리에 실행 시각을 채웁니다(커밋 없음). 자리 표시 형식을 바꾸면 워크플로도 함께 고칩니다.
- HTML 대시보드의 '결정 검색'은 전체 결정을 페이지에 넣어 브라우저에서 키워드로 찾습니다 (서버 불필요).
  추천 검색어 버튼은 config의 `search_presets`에 적습니다. 검색 스크립트(`SCRIPT`)는 raw 문자열이므로 JS 문법 그대로 씁니다.
- 회의 간 같은 Agenda는 번호가 아니라 '섹션 제목 + Agenda 제목'으로 이어 붙입니다 (`scripts/agenda.py`).
  번호가 바뀌면 함께 표시하고, 제목이 바뀐 Agenda는 억지로 잇지 않고 '최신 회의에는 없는 Agenda'로 따로 보여줍니다.
- Delta(직전 회의 대비)는 `scripts/delta.py`가 섹션별로 DB에서 계산합니다. FFS 후속 결정은 키워드 매칭 '후보'로만 표시하고 해소됐다고 단정하지 않습니다.
- 추출 점검(`scripts/health.py`): 회의를 처리할 때마다 결정이 조용히 누락됐을 가능성을 확인해 DB의 회의 정보(`health`)에 저장합니다.
  읽지 못한 결정 표시 줄, 본문 없는 결정, 결정 수 급감, 섹션 소실을 봅니다.
  결과는 Actions 경고, README의 '추출 점검', 대시보드 회의 목록에 나옵니다. '확인 필요'가 나오면 원문과 대조하고 파서를 고칩니다.
- `reports/` 아래 파일은 생성물입니다. 직접 수정하지 말고 DB나 설정을 고친 뒤 다시 생성합니다.
- DB 스키마와 필수 필드(출처 문서 번호, FTP 링크)는 `data/SCHEMA.md`를 따릅니다.
