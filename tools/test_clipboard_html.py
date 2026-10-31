"""표 복사(렌더링 화면 → HTML 클립보드 형식)와 표 붙여넣기(웹의 HTML 표 → 마크다운) 시험.
진짜 Tk Text 위젯에 preview.layout 결과를 그대로 넣어 선택 범위를 복사한다. 실제 클립보드는 IAT_TEST_CLIPBOARD=1 일 때만 건드린다(내용은 복원).
  py -3 -I -X utf8 tools/test_clipboard_html.py"""
import os
import re
import sys
import tkinter as tk
import tkinter.font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import copyhtml  # noqa: E402
import pastehtml  # noqa: E402
import preview  # noqa: E402
import wikiconv  # noqa: E402
import winclip  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


print("HTML Format 바이트")
frag = "<table><tr><td>가나다</td></tr></table>"
data = winclip.cf_html(frag)
check("머리의 위치가 바이트 기준으로 맞음", (lambda m: data[int(m[0]):int(m[1])] == frag.encode("utf-8"))([re.search(rb"StartFragment:(\d+)", data).group(1), re.search(rb"EndFragment:(\d+)", data).group(1)]))
check("fragment_of 로 되돌림", winclip.fragment_of(data) == frag)
check("StartHTML·EndHTML 이 전체 범위", int(re.search(rb"StartHTML:(\d+)", data).group(1)) < int(re.search(rb"EndHTML:(\d+)", data).group(1)) == len(data))
chrome = ("Version:0.9\r\nStartHTML:0000000105\r\nEndHTML:0000000400\r\nStartFragment:0000000140\r\nEndFragment:0000000300\r\n"
          "<html><body><!--StartFragment--><b>x</b><!--EndFragment--></body></html>").encode("utf-8") + b"\x00"
check("크롬식(주석 표시)·널 끝 처리", winclip.fragment_of(chrome) == "<b>x</b>")
body = b"<p>hello</p>"
hdr = b"Version:0.9\r\nStartFragment:%010d\r\nEndFragment:%010d\r\n"
n = len(hdr % (0, 0))
offs = hdr % (n, n + len(body)) + body
check("주석이 없으면 StartFragment·EndFragment 위치로 자름", winclip.fragment_of(offs) == "<p>hello</p>")

print("붙여넣기: HTML 표 → 마크다운")
html = ('<table style="x"><tbody><tr><th>이름</th><th>나이</th></tr><tr><td><div>홍길동</div></td><td>30<br>살</td></tr>'
        '<tr><td>a|b</td><td><a href="https://x.com">링크</a></td></tr></tbody></table>')
md = pastehtml.table_markdown(html)
check("머리줄·구분줄·행", md.splitlines()[0] == "| 이름 | 나이 |" and md.splitlines()[1].startswith("| ---") and "| 홍길동 | 30 살 |" in md)
check("칸 안의 | 는 이스케이프, 링크는 마크다운 링크", "a\\|b" in md and "[링크](https://x.com)" in md)
check("표 없는 HTML 은 None(기본 붙여넣기)", pastehtml.table_markdown("<p>그냥 <b>글</b></p>") is None and pastehtml.table_markdown("") is None and pastehtml.table_markdown(None) is None)
check("앞뒤 줄바꿈: 글 뒤에서 시작하면 빈 줄", pastehtml.around("앞글 ", "", "| a |") == "\n\n| a |\n")
check("앞뒤 줄바꿈: 뒤에 글이 있으면 빈 줄", pastehtml.around("", "뒤글", "| a |") == "| a |\n\n")
check("앞뒤 줄바꿈: 빈 줄이면 그대로", pastehtml.around("", "", "| a |") == "| a |\n")
# 변환한 마크다운이 이 앱에서 다시 표로 읽히는가
check("변환 결과가 이 앱에서 표로 읽힘", [b[0] for b in wikiconv.parse(md, "markdown", "t").blocks] == ["table"])

print("복사: 렌더링 화면(Text 위젯) → HTML")
root = tk.Tk()
root.withdraw()
font = tkfont.Font(family="맑은 고딕" if "맑은 고딕" in set(tkfont.families()) else "TkDefaultFont", size=10)
T = tk.Text(root, font=font, wrap="word", width=80, height=30)
T.pack()
T.tag_configure("b", font=(font.actual("family"), 10, "bold"))
src = ("# 제목\n\n앞 글 **굵게** [링크](https://example.com/x) 끝.\n\n"
       "| 항목 | 수량 | 가격 |\n|:--|--:|:-:|\n| 사과 | 3 | 1,200 |\n| 아주 긴 이름의 과일 | 12 | 15,000 |\n\n뒤 글.\n")
segs = preview.layout(wikiconv.parse(src, "markdown", "t"), avail=240, measure=font.measure)   # 좁게: 칸 안 줄바꿈이 생기게
links = {}
for text, tags, extra in segs:
    tg = list(tags)
    if extra and extra[0] == "link":
        k = "L%d" % len(links)
        links[k] = extra[1:]
        tg.append(k)
    T.insert("end", text, tuple(tg))
T.update()
plain, html = copyhtml.selection(T, "1.0", "end-1c", lambda t: (links.get(t) or [None, None])[1] if (links.get(t) or [""])[0] == "url" else None)
rows = re.findall(r"<tr>.*?</tr>", html)
check("표가 <table> 로 나옴", html.count("<table") == 1 and len(rows) == 3)
check("머리행은 <th>, 본문은 <td>", rows[0].count("<th>") == 3 and rows[1].count("<td") == 3)
check("줄바꿈된 칸이 한 칸으로 이어 붙음", "아주 긴 이름의 과일" in rows[2] and rows[2].count("<td") == 3)
check("열 정렬(오른쪽·가운데)이 속성으로", 'align="right"' in rows[1] and 'align="center"' in rows[1])
check("제목 <h1>, 굵게 <b>, 링크 <a>", "<h1>제목</h1>" in html and "<b>굵게</b>" in html and '<a href="https://example.com/x">링크</a>' in html)
check("평문: 칸은 탭 하나, 행은 줄", "항목\t수량\t가격" in plain and "사과\t3\t1,200" in plain and "\t\t" not in plain)
check("표 앞뒤 글도 평문에", "앞 글 굵게 링크 끝." in plain and "뒤 글." in plain)
# 선택이 표 한가운데에서 시작해도(태그가 이미 켜져 있는 상태) 표 행으로 읽힌다
i = T.search("사과", "1.0")
p2, h2 = copyhtml.selection(T, i, "end-1c")
check("표 중간부터 선택해도 <td> 행", "<td>사과</td>" in h2 and "<table" in h2)
check("표 밖만 선택하면 표 없음", "<table" not in copyhtml.selection(T, "1.0", T.index(T.search("항목", "1.0") + " linestart"))[1])
check("XSS 안전: 글자 이스케이프", "&lt;script&gt;" in copyhtml.build([[("<script>", frozenset())]])[1])
root.destroy()

if os.environ.get("IAT_TEST_CLIPBOARD") == "1" and sys.platform == "win32":
    print("실제 클립보드 왕복(내용은 복원)")
    r = tk.Tk()
    r.withdraw()
    try:
        saved = r.clipboard_get()
    except tk.TclError:
        saved = ""
    check("쓰기 성공", winclip.set_text_html("a\tb\n1\t2", "<table><tr><td>a</td></tr></table>"))
    check("HTML 읽기 왕복", winclip.get_html() == "<table><tr><td>a</td></tr></table>")
    check("평문도 같이", r.clipboard_get() == "a\tb\n1\t2")
    r.clipboard_clear()
    r.clipboard_append(saved)
    r.update()
    r.destroy()

print("\n%s" % ("모두 통과" if not fails else "실패 %d" % fails))
sys.exit(1 if fails else 0)
