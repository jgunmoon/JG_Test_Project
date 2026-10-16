"""주제 태그: Agenda와 관계없이 본문(또는 Agenda 제목)에 키워드가 나오는 결정을 모읍니다.

아이템 분류(한 결정 = 한 아이템)와 별개라서, 한 결정이 여러 주제에 동시에 속할 수 있습니다.
키워드는 config의 topics에 적고, 단어 단위·대소문자 무시로 찾습니다 ('DMRS'는 'pdmrsx'에 걸리지 않음).
"""
import re

from scripts.generate_report import meeting_sort_key


def _pattern(keywords):
    alts = "|".join(re.escape(k) for k in keywords)
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])", re.I)


def entries_for(db, topic):
    pat = _pattern(topic["keywords"])
    found = [e for e in db["entries"] if pat.search(e["text"]) or pat.search(e.get("agenda_title", ""))]
    return sorted(found, key=lambda e: (meeting_sort_key(e["meeting"]), e["id"]))
