"""제목을 안 쓴 새 노트의 제목: 본문 첫 줄(머리말·빈 줄·마크다운 기호를 뺀 첫 글)을 제목으로 쓴다. 화면 없는 순수 함수.
폰 앱(NoteText.titleFromBody)과 같은 규칙이다."""
import re

MAX = 50
_FM = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.S)


def title_from_body(body):
    """본문 → 제목(없으면 ''). 첫 글 줄에서 앞의 #·>·-·*·번호·체크 칸을 떼고, 강조 기호와 파일 이름에 못 쓰는 글자를 지우고, 50자로 자른다"""
    m = _FM.match(body or "")
    for raw in (body[m.end():] if m else (body or "")).split("\n"):
        line = raw.strip()
        if not line or set(line) <= set("-*_=` "):          # 빈 줄·가로줄·코드 울타리
            continue
        line = re.sub(r"^(?:[>#]+\s*|[-*+]\s+|\d+[.)]\s+)+", "", line)   # 인용·제목·목록 기호
        line = re.sub(r"^\[[ xX]\]\s*", "", line)                          # 체크 칸
        line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)             # [글](주소) → 글
        line = re.sub(r"[*_`~]+", "", line)
        line = re.sub(r"[\\/:*?\"<>|]", " ", line)
        line = re.sub(r"\s+", " ", line).strip(" .")
        if line:
            return line[:MAX].rstrip(" .")
    return ""
