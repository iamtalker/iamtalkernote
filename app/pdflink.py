"""본문이 pdf 파일 링크 하나뿐인 노트 알아보기 — 그런 노트는 윈도 기본 pdf 뷰어로 바로 보여 준다.
머리말(---), 맨 위 제목 줄(# …), 맨 아래 `태그: #a #b` 줄과 빈 줄은 글로 치지 않는다."""
import os
import re
from urllib.parse import unquote

FRONT = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>]+?)>?(?:\s+\"[^\"]*\")?\s*\)")
TAG_LINE = re.compile(r"^\s*(?:태그|tags?)\s*:.*$|^\s*(?:#[^\s#]+\s*)+$", re.I)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S.*$")


def pdf_target(text, note_path):
    """노트 글 → 가리키는 pdf 파일의 전체 경로(본문이 그 링크 하나뿐이고 파일이 있을 때), 아니면 None"""
    body = FRONT.sub("", text, count=1)
    links = []
    rest = []
    for line in body.splitlines():
        if not line.strip() or TAG_LINE.match(line) or (HEADING.match(line) and not links):
            continue
        found = LINK.findall(line)
        left = LINK.sub("", line).strip()
        if found and not left:
            links.extend(found)
            continue
        rest.append(line)
    if rest or len(links) != 1:
        return None
    target = links[0].strip()
    if re.match(r"(?i)^https?:", target):
        return None
    target = unquote(target.split("#")[0].split("?")[0])
    if target.lower().startswith("file:///"):
        target = target[8:]
    if not target.lower().endswith(".pdf"):
        return None
    path = os.path.normpath(target if os.path.isabs(target) else os.path.join(os.path.dirname(note_path), target))
    return path if os.path.isfile(path) else None
