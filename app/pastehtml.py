"""붙여넣기: 웹 페이지에서 복사한 표(HTML)를 마크다운 표로 바꿔 넣는다.

브라우저에서 표를 복사하면 클립보드에 표 구조가 있는 HTML 과 글자만 있는 형식이 함께 담긴다. Tk Text 의 기본 붙여넣기는 글자만
가져와서 표가 칸마다 탭으로 이어진 평문이 되므로, **표가 든 HTML 일 때만** 마크다운으로 바꾼다(그 밖의 붙여넣기는 그대로 둔다:
코드·서식 글을 복사했을 때 의도치 않게 바뀌지 않게). Ctrl+Shift+V 는 언제나 글자만 붙인다."""
import re

import winclip


def table_markdown(html):
    """표가 든 HTML 이면 마크다운(앞뒤 빈 줄 없음), 아니면 None"""
    if not html or not re.search(r"<table\b", html, re.I):
        return None
    from clipserver import html_to_md
    md = html_to_md(html).strip("\n")
    return md if "|" in md and re.search(r"(?m)^\|\s*:?-{3}", md) else None


def markdown_from_clipboard():
    try:
        return table_markdown(winclip.get_html())
    except Exception:  # noqa: BLE001  (클립보드를 못 읽으면 기본 붙여넣기로)
        return None


def around(before_on_line, after_on_line, md):
    """표 앞뒤에 줄바꿈을 보태 표가 자기 줄에서 시작·끝나게 한다. before/after = 붙여넣는 자리 앞·뒤에 같은 줄에 있는 글"""
    return ("\n\n" if before_on_line.strip() else "") + md + ("\n\n" if after_on_line.strip() else "\n")
