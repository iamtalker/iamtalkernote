"""글 정리(app/tidytext.py, formattools.tidy)와 찾아 바꾸기(findbar.py) 시험: py -3 -X utf8 tools/test_tidytext.py
앞부분은 화면 없는 함수, 뒷부분은 숨긴 Tk 편집 칸에서 실제로 고치고 되돌리기까지 본다."""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import tidytext as tt  # noqa: E402
from findbar import FindBarMixin  # noqa: E402
from formattools import FormatToolsMixin  # noqa: E402

fails = 0
NL = chr(10)
WIDE = chr(0x3000)   # 전각 공백
TAB = chr(9)


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def T(*lines):
    return NL.join(lines)


# ---- 화면 없는 함수
check("줄 앞 공백·탭·전각 공백 지움", tt.apply(T("  가", TAB + "나", WIDE + "다", "라"), "lead") == T("가", "나", "다", "라"))
check("줄 안·줄 끝 공백은 그대로", tt.apply("  가 나  ", "lead") == "가 나  ")
check("공백만 있는 줄은 그대로", tt.apply(T("가", "   ", "나"), "lead") == T("가", "   ", "나"))
check("코드 블록 안은 그대로", tt.apply(T("  가", "```", "    x = 1", "```", "  나"), "lead") == T("가", "```", "    x = 1", "```", "나"))
check("~~~ 울타리도 코드 블록", tt.apply(T("~~~", "  x", "~~~", "  나"), "lead") == T("~~~", "  x", "~~~", "나"))
check("하위 목록은 그대로", tt.apply(T("- 가", "  - 나", "    1. 다", "  글"), "lead") == T("- 가", "  - 나", "    1. 다", "글"))
check("그대로 둔 줄 수를 센다", tt.leading_ops(["  - 나", "```", "  x", "```", "  글"])[1] == 2)
check("범위 밖의 줄 앞 공백은 안 건드림", tt.leading_ops([" 가", " 나", " 다"], 1, 1)[0] == [(1, 0, 1, 1, "")])
check("줄 끝 공백 지움", tt.apply(T("가  ", "나" + TAB, " 다" + WIDE, "   "), "trail") == T("가", "나", " 다", ""))
check("줄 끝 공백: 코드 블록은 그대로", tt.apply(T("```", "x  ", "```", "가 "), "trail") == T("```", "x  ", "```", "가"))
check("빈 줄 2·3줄을 1줄로", tt.apply(T("가", "", "", "나", "", "", "", "다"), "blank") == T("가", "", "나", "", "다"))
check("빈 줄 1줄은 그대로", tt.apply(T("가", "", "나", "다"), "blank") == T("가", "", "나", "다"))
check("공백만 있는 줄도 빈 줄", tt.apply(T("가", "  ", TAB, "나"), "blank") == T("가", "", "나"))
check("코드 블록 안의 빈 줄은 그대로", tt.apply(T("```", "a", "", "", "b", "```", "", "", "끝"), "blank") == T("```", "a", "", "", "b", "```", "", "끝"))
check("범위를 주면 그 줄들만", tt.blank_ops(["가", "", "", "나", "", "", "다"], 3, 6) == [(4, 0, 5, 0, "")])
check("빈 줄 모두 지우기", tt.apply(T("", "가", "", "", "나", " ", "다", "", ""), "noblank") == T("가", "나", "다"))
check("빈 줄 모두 지우기: 코드 블록은 그대로", tt.apply(T("가", "", "```", "", "```", "", "나"), "noblank") == T("가", "```", "", "```", "나"))
check("빈 줄뿐인 글", tt.apply(T("", " ", ""), "noblank") == "")
check("여러 공백을 하나로", tt.apply(T("가   나" + TAB + TAB + "다", "  라  마  "), "spaces") == T("가 나 다", "  라 마  "))
check("여러 공백: 한 칸은 그대로·코드 블록은 그대로", tt.apply(T("가 나", "```", "a   b", "```"), "spaces") == T("가 나", "```", "a   b", "```"))
check("중복 줄 지우기", tt.apply(T("가", "나", "가", "", "나 ", "다", "가"), "dupes") == T("가", "나", "", "다"))
check("중복 줄: 이어진 중복·맨 끝", tt.apply(T("가", "가", "가"), "dupes") == "가")
check("중복 줄: 울타리 줄은 그대로", tt.apply(T("```", "a", "```", "```", "a", "```"), "dupes") == T("```", "a", "```", "```", "a", "```"))
check("문단 안 줄 바꿈 지우기", T(*tt.unwrap(["가나", "다라 ", " 마바", "", "사", "아"])) == T("가나 다라 마바", "", "사 아"))
check("문단: 제목·표·가로줄은 그대로", tt.unwrap(["# 제목", "글", "글2", "| a | b |", "| 1 | 2 |", "---", "끝"]) == ["# 제목", "글 글2", "| a | b |", "| 1 | 2 |", "---", "끝"])
check("문단: 목록은 줄마다, 이어 쓴 줄은 붙임", tt.unwrap(["- 가", "  이어서", "- 나", "> 인용", "글"]) == ["- 가 이어서", "- 나", "> 인용 글"])
check("문단: 코드 블록·일부러 넣은 줄 바꿈은 그대로", tt.unwrap(["가  ", "나", "```", "a", "b", "```", "다" + chr(92), "라"]) == ["가  ", "나", "```", "a", "b", "```", "다" + chr(92), "라"])
check("문단: 범위만", tt.unwrap(["가", "나", "다", "라"], 1, 2) == ["나 다"])
check("줄 합치기", tt.join_lines(["  가 ", "", "나", TAB + "다"]) == "가 나 다")
check("줄 정렬", tt.sort_lines(["다", "", "b", "가", "A"]) == ["A", "b", "가", "다"] and tt.sort_lines(["가", "다", "나"], True) == ["다", "나", "가"])


# ---- 편집 칸에서
class Status:
    text = ""

    def config(self, text=""):
        self.text = text


class Label:
    def config(self, **kw):
        self.kw = kw


class Bar:
    on = False

    def winfo_ismapped(self):
        return self.on

    def pack(self, **kw):
        self.on = True

    def pack_forget(self):
        self.on = False


class Fake(FormatToolsMixin, FindBarMixin):
    def __init__(self, root):
        self.root = root
        self.text = tk.Text(root, undo=True)
        self.view = tk.Text(root)
        self.cur, self.doc_open, self.mode, self.status = {"nb": ""}, False, "edit", Status()
        self.findbar, self.replbar, self.find_count = Bar(), Bar(), Label()
        self.find_var, self.repl_var = tk.StringVar(root), tk.StringVar(root)
        self.find_entry, self.repl_entry = tk.Entry(root), tk.Entry(root)
        self.find_hits, self.find_i, self.find_job, self.pv_active = [], -1, None, False

    def is_outline_note(self):
        return False

    def set_mode(self, m):
        self.mode = m

    def put(self, s):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", s)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.tag_remove("sel", "1.0", "end")
        self.text.mark_set("insert", "1.0")

    def body(self):
        return self.text.get("1.0", "end-1c")

    def undo_ok(self, src):
        self.text.edit_undo()
        return self.body() == src


root = tk.Tk()
root.withdraw()
f = Fake(root)

src = T("  가", "", "", "   나", "```", "  x", "", "", "```", "", "", "", "  - 목록", WIDE + "다  끝 ", "  가")
for kind in ("lead", "trail", "blank", "noblank", "spaces", "dupes"):
    f.put(src)
    f.tidy(kind)
    check(f"편집 칸 {kind}: 화면 없는 함수와 같은 결과", f.body() == tt.apply(src, kind) != src)
    check(f"편집 칸 {kind}: 되돌리기 한 번으로 원래대로", f.undo_ok(src))
f.put(src)
f.tidy("lead")
check("편집 칸: 상태 글에 고친 곳·그대로 둔 줄 수", "4" in f.status.text and "2" in f.status.text)

f.put(src)
f.text.mark_set("insert", "14.1")
f.tidy("blank")
check("편집 칸: 커서가 같은 줄에 남는다", f.text.get("insert linestart", "insert lineend") == WIDE + "다  끝 ")

f.put(T(" 가", "", "", " 나", "", "", " 다"))
f.text.tag_add("sel", "4.0", "7.end")
f.tidy("blank")
check("편집 칸: 고른 줄들만 빈 줄 정리", f.body() == T(" 가", "", "", " 나", "", " 다"))
f.put(T(" 가", " 나", " 다"))
f.text.tag_add("sel", "2.0", "3.0")   # 줄 맨 앞에서 끝난 선택은 그 줄을 뺀다
f.tidy("lead")
check("편집 칸: 고른 줄만 앞 공백", f.body() == T(" 가", "나", " 다"))

f.put(T("가", "", "나"))
f.tidy("blank")
check("편집 칸: 고칠 곳이 없으면 그대로", f.body() == T("가", "", "나") and not f.text.edit_modified())

para = T("첫 줄", "둘째 줄", "", "셋째", "넷째")
f.put(para)
f.tidy("unwrap")
check("편집 칸: 문단 안 줄 바꿈 지우기(노트 전체)", f.body() == T("첫 줄 둘째 줄", "", "셋째 넷째"))
check("편집 칸: 문단 되돌리기", f.undo_ok(para))
f.put(para)
f.tidy("join")
check("편집 칸: 줄 합치기는 고른 글이 있어야", f.body() == para)
f.text.tag_add("sel", "1.0", "2.end")
f.tidy("join")
check("편집 칸: 고른 줄을 한 줄로", f.body() == T("첫 줄 둘째 줄", "", "셋째", "넷째"))
check("편집 칸: 합친 줄이 골라져 있다", f.text.get("sel.first", "sel.last") == "첫 줄 둘째 줄")
f.put(T("머리", "다", "가", "나", "꼬리"))
f.text.tag_add("sel", "2.0", "4.end")
f.tidy("sort")
check("편집 칸: 고른 줄 정렬", f.body() == T("머리", "가", "나", "다", "꼬리"))
f.tidy("rsort")
check("편집 칸: 내림차순", f.body() == T("머리", "다", "나", "가", "꼬리"))
f.put("Hello World")
f.text.tag_add("sel", "1.0", "1.5")
f.tidy("upper")
check("편집 칸: 대문자로(고른 글자만)", f.body() == "HELLO World")
f.tidy("lower")
check("편집 칸: 소문자로", f.body() == "hello World")

# ---- 찾아 바꾸기
doc = T("사과와 배", "Apple apple", "사과 사과")
f.put(doc)
f.find_var.set("사과")
f.repl_var.set("사과나무")   # 바꿀 글 안에 찾는 글이 들어 있어도 한 번씩만
f.show_replace()
check("찾아 바꾸기: 막대 두 줄이 뜨고 3곳을 찾는다", f.findbar.on and f.replbar.on and len(f.find_hits) == 3)
f.replace_one()
check("바꾸기: 첫 곳만 바꾸고 다음 곳으로", f.body() == T("사과나무와 배", "Apple apple", "사과 사과") and f.text.index("insert") == "3.0")
f.replace_all()
check("모두 바꾸기: 바꾼 글이 다시 걸리지 않는다", f.body() == T("사과나무나무와 배", "Apple apple", "사과나무 사과나무"))
check("모두 바꾸기: 되돌리기 한 번", f.undo_ok(T("사과나무와 배", "Apple apple", "사과 사과")))
f.put(doc)
f.find_var.set("apple")
f.repl_var.set("")
f.replace_all()
check("모두 바꾸기: 대소문자 구분 없이, 빈 글로(지우기)", f.body() == T("사과와 배", " ", "사과 사과"))
f.put(T("a", "a", "a", "a"))
f.find_var.set("a")
f.repl_var.set("b")
f.text.tag_add("sel", "2.0", "3.end")
f.replace_all()
check("모두 바꾸기: 여러 줄을 골랐으면 그 안에서만", f.body() == T("a", "b", "b", "a"))
f.put("가")
f.find_var.set("없는글")
f.replace_all()
check("바꿀 곳이 없으면 그대로", f.body() == "가" and not f.text.edit_modified())
f.hide_find(focus=False)
check("닫으면 두 줄 다 사라진다", not f.findbar.on and not f.replbar.on)

f.doc_open = True
f.put("  가")
f.tidy("lead")
f.show_replace()
check("가져온 문서에서는 안 한다", f.body() == "  가" and not f.replbar.on)
root.destroy()
sys.exit(1 if fails else 0)
