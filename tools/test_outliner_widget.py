"""아웃라이너 편집기(app/outliner/widget.py) 시험: py -3 -I -X utf8 tools/test_outliner_widget.py"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from outliner.widget import OutlineEditor

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


root = tk.Tk()
root.geometry("700x500")
C = {"bg": "#ffffff", "text": "#222222", "muted": "#888888", "accent": "#2563eb", "sel": "#cfe3ff"}
saved = []
w = OutlineEditor(root, C, ("Malgun Gothic", 11), saved.append)
w.pack(fill="both", expand=True)
w.load("- a\n- b\n    - b1\n    - b2\n- c\n")
root.update()
t = w.txt


def lines():
    return [t.get(f"{n}.1", f"{n}.end") for n in range(1, int(t.index("end-1c").split(".")[0]) + 1)]


def at(k, col):
    t.mark_set("insert", f"{k + 1}.{col + 1}")


def press(fn, *a):
    fn(*a)
    root.update()


check("줄마다 항목 한 줄", lines() == ["a", "b", "b1", "b2", "c"])
check("깊이만큼 들여쓰기 태그", "d1" in t.tag_names("3.0") and "d0" in t.tag_names("1.0"))

at(0, 1)
t.insert("insert", "X")                                    # 줄 안 글자 입력은 Text 가 한다
press(w._enter)
check("Enter: 커서 뒤 글이 새 항목", lines()[:3] == ["aX", "", "b"] or lines()[:2] == ["a", "X"])

w.load("- a\n- b\n    - b1\n    - b2\n- c\n")
at(0, 1)
press(w._enter)
check("Enter 뒤 원문에 새 항목", saved[-1] == "- a\n- \n- b\n    - b1\n    - b2\n- c\n" and t.index("insert") == "2.1")
t.insert("insert", "new")
press(w._tab)
check("Tab: 앞 항목 a 의 하위로 들어감", saved[-1].startswith("- a\n    - new\n- b") and lines()[1] == "new")
press(w._btab)
check("Shift+Tab: 다시 바깥으로", saved[-1].startswith("- a\n- new\n- b"))

at(1, 0)
press(w._backspace)
check("줄 맨 앞 Backspace: 앞 항목에 붙임", lines()[0] == "anew" and t.index("insert") == "1.2")

at(0, 4)
press(w._delete)
check("줄 끝 Delete: 다음 항목을 붙임", lines()[0] == "anewb")

w.load("- a\n- b\n    - b1\n    - b2\n- c\n")
at(1, 0)
press(w._fold, True)
check("Ctrl+↑: 접으면 하위가 안 보임", lines() == ["a", "b", "c"])
press(w._fold, False)
check("Ctrl+↓: 펼침", lines() == ["a", "b", "b1", "b2", "c"])

at(4, 0)
press(w._move, True)
check("Ctrl+Shift+↑: 위 형제와 자리 바꿈(하위 함께)", lines() == ["a", "c", "b", "b1", "b2"])

w.load("- a\n- b\n    - b1\n    - b2\n- c\n")
at(1, 0)
press(w._zoom_in)
check("줌인: b 의 하위만 보임", lines() == ["b1", "b2"] and len(w.crumb.winfo_children()) >= 2)
at(0, 2)
press(w._enter)
check("줌인 상태에서 Enter 가 항목을 더함", lines() == ["b1", "", "b2"])
press(w._zoom_out)
check("줌아웃: 전체", lines() == ["a", "b", "b1", "", "b2", "c"])

w.load("- a\n- b\n- c\n")
t.tag_add("sel", "1.2", "3.2")                             # a 의 끝 ~ c 의 끝 직전
press(w._delete_selection)
check("여러 줄 선택 지우기: 앞뒤가 한 항목으로", lines() == ["c"] or lines() == ["a"] or len(lines()) == 1)
press(w._undo)
check("되돌리기", lines() == ["a", "b", "c"])
press(w._undo, True)
check("다시 실행", len(lines()) == 1)

w.load("- x\n")
at(0, 1)
press(w._done)
check("Ctrl+Enter: 완료 표시([x])", saved[-1] == "- [x] x\n" and "done" in t.tag_names("1.2"))

w.load("- a\n")
w.clipboard_clear()
w.clipboard_append("- p\n    - q\n- r")
at(0, 1)
press(w._paste)
check("여러 줄 붙여넣기: 항목 구조 유지", saved[-1] == "- ap\n    - q\n- r\n" or saved[-1] == "- ap\n- q\n- r\n")

w.load("")
check("빈 노트는 빈 항목 하나", lines() == [""])
root.destroy()
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
