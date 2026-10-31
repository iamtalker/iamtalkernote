"""하단 태그 입력칸 자동완성: 치고 있는 낱말에 맞는 기존 태그를 입력칸 위 작은 목록으로 보여 주고, ↓↑ 로 고르고 Tab/Enter/클릭으로 넣는다.
후보 계산(suggest 등)은 화면을 모르는 순수 함수라 따로 시험한다."""
import re
import tkinter as tk


def current_token(text):
    """입력 글에서 지금 치고 있는 낱말(공백·쉼표 뒤) → (시작 위치, 낱말('#' 포함))"""
    m = re.search(r"[^\s,]*$", text)
    return m.start(), m.group(0)


def suggest(counts, token, have=(), limit=8):
    """counts {태그: 개수}, token 치는 중인 낱말, have 이미 입력칸에 있는 태그 → 후보 태그 목록.
    앞부분이 같은 것이 먼저, 그다음 글자가 들어 있는 것. 각각 많이 쓴 순. 낱말이 비었으면 많이 쓴 태그를 보여 준다"""
    key = token.lstrip("#").lower()
    have_l = {h.lower() for h in have}
    pool = [(t, c) for t, c in counts.items() if t.lower() not in have_l and t.lower() != key]
    pool.sort(key=lambda tc: (-tc[1], tc[0].lower()))
    if not key:
        return [t for t, _ in pool[:limit]]
    first = [t for t, _ in pool if t.lower().startswith(key)]
    rest = [t for t, _ in pool if key in t.lower() and not t.lower().startswith(key)]
    return (first + rest)[:limit]


def tags_in(text):
    """입력 글에 이미 적힌 태그들(# 뗀 것)"""
    return [t.lstrip("#") for t in re.split(r"[,\s]+", text) if t.lstrip("#")]


def complete(text, start, tag):
    """text 의 start 부터 끝까지(치던 낱말)를 '#태그 ' 로 바꾼다"""
    return text[:start] + "#" + tag + " "


class TagComplete:
    """tk.Entry 위에 띄우는 태그 후보 목록. get_counts() → {태그: 개수}, get_extra() → 한글 조합 중인 글자(없으면 빈 글)"""

    def __init__(self, entry, get_counts, colors, font, get_extra=lambda: ""):
        self.ent, self.get_counts, self.C, self.font, self.get_extra = entry, get_counts, colors, font, get_extra
        self.pop = None
        self.lb = None
        self.items = []
        self.clicking = False
        entry.bind("<KeyRelease>", self._typed, add="+")
        entry.bind("<Down>", lambda e: self._move(1), add="+")
        entry.bind("<Up>", lambda e: self._move(-1), add="+")
        entry.bind("<Tab>", lambda e: self._tab(), add="+")

    # ---- 보이기
    def visible(self):
        return self.pop is not None

    def _typed(self, e=None):
        if e is not None and e.keysym in ("Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self.refresh()

    def refresh(self):
        text = self.ent.get() + self.get_extra()
        start, tok = current_token(text)
        self.items = suggest(self.get_counts(), tok, tags_in(text[:start]))
        if not self.items:
            return self.close()
        if self.pop is None:
            self.pop = tk.Toplevel(self.ent)
            self.pop.overrideredirect(True)
            self.pop.attributes("-topmost", True)
            self.lb = tk.Listbox(self.pop, relief="flat", bd=0, highlightthickness=1, highlightbackground=self.C["line"], bg=self.C["panel"], fg=self.C["text"],
                                 selectbackground=self.C["soft"], selectforeground=self.C["text"], activestyle="none", exportselection=False,
                                 font=self.font, takefocus=0)
            self.lb.pack()
            self.lb.bind("<ButtonPress-1>", lambda e: setattr(self, "clicking", True))
            self.lb.bind("<ButtonRelease-1>", self._clicked)
        self.lb.delete(0, "end")
        counts = self.get_counts()
        for t in self.items:
            self.lb.insert("end", f"#{t}   ({counts.get(t, 0):,})")
        self.lb.configure(height=len(self.items))
        self.lb.selection_clear(0, "end")
        self.pop.update_idletasks()
        w = max(self.ent.winfo_width(), self.lb.winfo_reqwidth())
        h = self.lb.winfo_reqheight()
        self.pop.geometry(f"{w}x{h}+{self.ent.winfo_rootx()}+{self.ent.winfo_rooty() - h - 2}")   # 입력칸 바로 위(맨 아래 줄이라 아래는 화면 밖)

    def close(self):
        if self.pop is not None:
            try:
                self.pop.destroy()
            except tk.TclError:
                pass
        self.pop = self.lb = None
        self.items = []

    # ---- 고르기
    def _selected(self):
        if self.lb is None:
            return None
        s = self.lb.curselection()
        return self.items[s[0]] if s else None

    def _move(self, d):
        if not self.visible():
            return None
        n = len(self.items)
        s = self.lb.curselection()
        i = (s[0] + d) % n if s else (0 if d > 0 else n - 1)
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return "break"

    def accept(self, tag=None):
        """고른(또는 첫) 후보를 입력칸에 넣는다. 넣었으면 True"""
        tag = tag or self._selected()
        if tag is None:
            return False
        text = self.ent.get()
        start, _tok = current_token(text)
        self.ent.delete(0, "end")
        self.ent.insert(0, complete(text, start, tag))
        self.ent.icursor("end")
        self.ent.focus_set()
        self.refresh()          # 이어서 다음 태그를 칠 수 있게 후보를 다시 계산
        return True

    def _tab(self):
        if self.visible() and self.accept(self._selected() or self.items[0]):
            return "break"
        return None

    def _clicked(self, e):
        i = self.lb.nearest(e.y)
        self.clicking = False
        if 0 <= i < len(self.items):
            self.accept(self.items[i])
        else:
            self.ent.focus_set()
        return "break"

    def on_return(self):
        """Enter: 목록에서 고른 것이 있으면 그것을 넣고 True(저장하지 않는다), 없으면 False(저장)"""
        if self.visible() and self._selected() is not None:
            return self.accept()
        return False
