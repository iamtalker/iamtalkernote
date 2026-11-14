"""목록 Tab 들여쓰기(formattools.list_tab)와 체크 칸 누르기(rendersync.toggle_task) 시험: py -3 -I -X utf8 tools/test_list_tab_task.py"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import bulk
import wikiconv
from formattools import FormatToolsMixin
from rendersync import RenderSyncMixin

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


class Fake(RenderSyncMixin, FormatToolsMixin):
    def __init__(self, root, src, view_text, boxes):
        self.text = tk.Text(root)
        self.text.insert("1.0", src)
        self.view = tk.Text(root)
        self.view.insert("1.0", view_text)
        self.links = {}
        for key, (start, end) in boxes.items():   # 화면의 체크 칸을 흉내 낸다: 칸마다 키 태그와 task 링크
            self.links[key] = ("task", "")
            self.view.tag_add(key, start, end)


root = tk.Tk()
root.withdraw()

# --- Tab / Shift+Tab 들여쓰기
f = Fake(root, "1. 예시", "", {})
f.text.mark_set("insert", "1.end")
check("번호 목록 줄에서 Tab → 두 칸 들여쓰기", f.list_tab(None) == "break" and f.text.get("1.0", "end-1c") == "  1. 예시")
check("들여쓴 줄에서 Shift+Tab → 원래대로", f.list_tab(None, True) == "break" and f.text.get("1.0", "end-1c") == "1. 예시")
f = Fake(root, "- 가\n- 나\n", "", {})
f.text.mark_set("insert", "2.0")
check("글머리 줄에서 Tab → 들여쓰기", f.list_tab(None) == "break" and f.text.get("2.0", "2.end") == "  - 나")
f = Fake(root, "- [ ] 할 일", "", {})
f.text.mark_set("insert", "1.3")
check("체크 목록 줄도 들여쓰기", f.list_tab(None) == "break" and f.text.get("1.0", "1.end") == "  - [ ] 할 일")
f = Fake(root, "그냥 글", "", {})
f.text.mark_set("insert", "1.0")
check("목록이 아닌 줄의 Tab 은 평범한 Tab 으로(None)", f.list_tab(None) is None and f.text.get("1.0", "end-1c") == "그냥 글")
f = Fake(root, "  - 깊은 줄", "", {})
f.text.mark_set("insert", "1.0")
check("내어쓰기는 앞 공백 두 칸만 지운다", f.list_tab(None, True) == "break" and f.text.get("1.0", "end-1c") == "- 깊은 줄")

# --- 들여쓴 목록이 실제로 하위 목록이 되는지(파서)
doc = wikiconv.parse("- 가\n  - 나\n", bulk.SYNTAX["markdown"], "t")
item = doc.blocks[0][2][0] if doc.blocks and doc.blocks[0][0] == "list" else None
check("두 칸 들여쓴 줄은 하위 목록", item is not None and any(s[0] == "list" for s in item))

# --- 체크 칸 누르기
src = "- [ ] 할 일\n```\n- [ ] 코드\n```\n- [x] 끝\n"
view = "☐  할 일\n☑  끝\n"
f = Fake(root, src, view, {"L0": ("1.0", "1.3"), "L1": ("2.0", "2.3")})
f.toggle_task(f.view.index("1.1"))
check("첫 칸 누르면 원문 첫 할 일이 [x]", f.text.get("1.0", "1.end") == "- [x] 할 일")
check("코드 블록 안의 체크 글은 안 건드림", f.text.get("3.0", "3.end") == "- [ ] 코드")
f.toggle_task(f.view.index("2.1"))
check("둘째 칸 누르면 원문의 [x] 끝이 [ ] 로", f.text.get("5.0", "5.end") == "- [ ] 끝")
f.toggle_task(f.view.index("2.1"))
check("다시 누르면 [x] 로 되돌아감", f.text.get("5.0", "5.end") == "- [x] 끝")

print("\n실패 %d건" % fails)
root.destroy()
sys.exit(1 if fails else 0)
