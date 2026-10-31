"""복사: 렌더링 화면에서 고른 부분을 HTML 로도 클립보드에 넣는다(표를 웹 에디터·워드 등에 표로 붙일 수 있게).

Tk Text 의 기본 복사는 글자만 넣는데, 표는 칸 정렬용 탭이 끼어 있어 웹에서 표가 되지 않는다. 렌더링 화면의 태그(표 칸 tb00·tb01·tb10·tb11·th0·th1,
굵게·기울임·링크·제목 …)를 읽어 표는 <table>, 나머지는 서식 글 HTML 로 만들고, 글자 형식은 칸을 탭 하나로 이은 평문(엑셀에 붙여도 표)으로 넣는다."""
import html as _html

TABLE_CELL = ("tb00", "tb01", "tb10", "tb11", "th0", "th1")
INLINE = {"b": "b", "i": "i", "bi": None, "u": "u", "s": "s", "code": "code"}


def _esc(s):
    return _html.escape(s, quote=False)


def lines_of(items, active0=()):
    """위젯 dump 항목 [(종류, 값)] ('text'·'tagon'·'tagoff') → 줄 목록, 줄 = [(글, 태그 집합)]"""
    active, lines, cur = set(active0), [], []
    for kind, val in items:
        if kind == "tagon":
            active.add(val)
        elif kind == "tagoff":
            active.discard(val)
        elif kind == "text":
            parts = val.split("\n")
            for k, part in enumerate(parts):
                if k:
                    lines.append(cur)
                    cur = []
                if part:
                    cur.append((part, frozenset(active)))
    lines.append(cur)
    return lines


def _row_kind(tags):
    """표 줄의 행 종류: 머리행 'h', 본문은 행 홀짝 'b0'/'b1'(줄바꿈된 줄은 같은 값이라 한 행으로 묶인다)"""
    for t in tags:
        if t in ("th0", "th1"):
            return "h"
        if t in ("tb00", "tb01", "tb10", "tb11"):
            return "b" + t[2]
    return None


def _aligns(tags):
    """T:14l;150r;… 태그에서 열 정렬을 읽는다(열마다 [글 위치, 다음 열 시작] 정지점 쌍)"""
    for t in tags:
        if t.startswith("T:"):
            stops = [p[-1] for p in t[2:].split(";")]
            return [{"r": "right", "c": "center"}.get(s, "") for s in stops[0::2]]
    return []


def table_of(tlines):
    """표 줄들 [[(글, 태그)]] → (행들 [(머리행?, [칸 글])], 열 정렬들)"""
    rows, aligns, prev = [], [], None
    for line in tlines:
        cells, kind = [], None
        for text, tags in line:
            k = _row_kind(tags)
            if k is None:
                continue
            kind = kind or k
            if not aligns:
                aligns = _aligns(tags)
            cells.append(text.replace("\t", " ").strip())
        if kind is None:
            continue
        if kind == prev and rows:                 # 줄바꿈된 칸: 같은 행에 이어 붙인다
            old = rows[-1][1]
            for j, c in enumerate(cells):
                if j < len(old):
                    old[j] = (old[j] + " " + c).strip()
                else:
                    old.append(c)
        else:
            rows.append((kind == "h", cells))
        prev = kind
    return rows, aligns


def table_html(rows, aligns):
    out = ['<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse">']
    for head, cells in rows:
        tag = "th" if head else "td"
        out.append("<tr>" + "".join('<%s%s>%s</%s>' % (tag, (' align="%s"' % aligns[j]) if j < len(aligns) and aligns[j] and not head else "", _esc(c), tag)
                                    for j, c in enumerate(cells)) + "</tr>")
    out.append("</table>")
    return "".join(out)


def table_plain(rows):
    return "\n".join("\t".join(cells) for _, cells in rows)


def inline_html(segs, link_of):
    """한 줄의 [(글, 태그 집합)] → 서식(굵게·기울임·밑줄·취소선·코드·링크)이 든 HTML"""
    out = []
    for text, tags in segs:
        h = _esc(text)
        for t in tags:
            if t.startswith("L") and t[1:].isdigit():
                href = link_of(t)
                if href:
                    h = '<a href="%s">%s</a>' % (_html.escape(href, quote=True), h)
        if "b" in tags or "bi" in tags:
            h = "<b>%s</b>" % h
        if "i" in tags or "bi" in tags:
            h = "<i>%s</i>" % h
        for t, el in (("u", "u"), ("s", "s"), ("code", "code")):
            if t in tags:
                h = "<%s>%s</%s>" % (el, h, el)
        out.append(h)
    return "".join(out)


def build(lines, link_of=lambda tag: None):
    """줄 목록 → (글자 평문, HTML 조각). 표는 <table>·탭으로 이은 줄, 제목은 <hN>, 코드 블록은 <pre>, 나머지는 <p>"""
    plain, html, i = [], [], 0
    para = []

    def flush():
        if para:
            html.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
    while i < len(lines):
        line = lines[i]
        if any(_row_kind(t) for _, t in line):
            flush()
            j = i
            while j < len(lines) and any(_row_kind(t) for _, t in lines[j]):
                j += 1
            rows, aligns = table_of(lines[i:j])
            if rows:
                html.append(table_html(rows, aligns))
                plain.append(table_plain(rows))
            i = j
            continue
        text = "".join(t for t, _ in line)
        tags = set().union(*[tg for _, tg in line]) if line else set()
        head = next((t for t in tags if len(t) == 2 and t[0] == "h" and t[1] in "123456"), None)
        if "codeblock" in tags:
            flush()
            j = i
            block = []
            while j < len(lines) and any("codeblock" in tg for _, tg in lines[j]):
                block.append("".join(t for t, _ in lines[j]))
                j += 1
            html.append("<pre>%s</pre>" % _esc("\n".join(block)))
            plain.append("\n".join(block))
            i = j
            continue
        plain.append(text)
        if head:
            flush()
            html.append("<%s>%s</%s>" % (head, inline_html(line, link_of), head))
        elif text.strip():
            para.append(inline_html(line, link_of))
        else:
            flush()
        i += 1
    flush()
    return "\n".join(plain).strip("\n"), "".join(html)


def selection(widget, first, last, link_of=lambda tag: None):
    """Text 위젯의 first~last 범위 → (평문, HTML 조각)"""
    items = [(k, v) for k, v, _ in widget.dump(first, last, text=True, tag=True)]
    return build(lines_of(items, widget.tag_names(first)), link_of)


def has_table(lines):
    return any(any(_row_kind(t) for _, t in line) for line in lines)
