"""하단 태그 입력(조플린의 '태그 추가 및 제거' 같은 방식): 태그를 치고 Enter 하면 칩(태그 + ×)으로 쌓이고 입력칸은 다음 태그를 받는다.
[확인] 을 눌러야 한꺼번에 노트에 들어가고 [취소] 는 아무것도 바꾸지 않는다. 치는 동안 기존 태그를 후보 목록으로 보여 주고(↓↑ Tab Enter 클릭),
오른쪽 ▾ 를 누르면 모든 태그를 펼친다. 후보 계산(suggest 등)은 화면을 모르는 순수 함수라 따로 시험한다."""
import re
import tkinter as tk


def current_token(text):
    """입력 글에서 지금 치고 있는 낱말(공백·쉼표 뒤) → (시작 위치, 낱말('#' 포함))"""
    m = re.search(r"[^\s,]*$", text)
    return m.start(), m.group(0)


def suggest(counts, token, have=(), limit=8):
    """counts {태그: 개수}, token 치는 중인 낱말, have 이미 넣은 태그 → 후보 태그 목록.
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


def clean(tok):
    """입력한 낱말을 태그 이름으로 정리한다(앞의 # 떼기). 쓸 수 없으면 ''"""
    t = tok.strip().lstrip("#").strip()
    if not t or len(t) > 30 or re.search(r"[\[\]()/<>]", t):
        return ""
    return t


def complete(text, start, tag):
    """text 의 start 부터 끝까지(치던 낱말)를 '#태그 ' 로 바꾼다"""
    return text[:start] + "#" + tag + " "


class TagComplete:
    """tk.Entry 위에 띄우는 태그 후보 목록. on_pick(tag) 를 주면 고른 태그를 입력칸 글이 아니라 그 함수로 넘긴다(칩 추가용)."""

    def __init__(self, entry, get_counts, colors, font, get_extra=lambda: "", get_have=lambda: (), on_pick=None, cancel_ime=lambda: None):
        self.ent, self.get_counts, self.C, self.font, self.get_extra = entry, get_counts, colors, font, get_extra
        self.get_have, self.on_pick, self.cancel_ime = get_have, on_pick, cancel_ime
        self.lb = None          # 후보 목록: 별도 창이 아니라 앱 창 안에 띄운다(별도 창은 뜨고 닫힐 때마다 입력칸의 키보드 포커스를 가져가 글자가 늦게 들어갔다)
        self._shown = False
        self.items = []
        self.clicking = False
        entry.bind("<KeyRelease>", self._typed, add="+")
        entry.bind("<Down>", lambda e: self._move(1), add="+")
        entry.bind("<Up>", lambda e: self._move(-1), add="+")
        entry.bind("<Tab>", lambda e: self._tab(), add="+")

    # ---- 보이기
    def visible(self):
        return self._shown

    def _typed(self, e=None):
        if e is not None and e.keysym in ("Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self.refresh()

    def refresh(self, everything=False):
        text = self.ent.get() + self.get_extra()
        start, tok = current_token(text)
        self.items = suggest(self.get_counts(), tok, list(tags_in(text[:start])) + list(self.get_have()), limit=40 if everything else 8)
        if not self.items:
            return self.close()
        if self.lb is None:
            self.lb = tk.Listbox(self.ent.winfo_toplevel(), relief="flat", bd=0, highlightthickness=1, highlightbackground=self.C["line"], bg=self.C["panel"],
                                 fg=self.C["text"], selectbackground=self.C["soft"], selectforeground=self.C["text"], activestyle="none", exportselection=False,
                                 font=self.font, takefocus=0)
            # 누르기는 우리가 처리한다(기본 동작은 목록이 포커스를 가져간다). 떼는 순간 그 줄을 고른다
            self.lb.bind("<ButtonPress-1>", lambda e: (setattr(self, "clicking", True), "break")[1])
            self.lb.bind("<ButtonRelease-1>", self._clicked)
        self.lb.delete(0, "end")
        counts = self.get_counts()
        for t in self.items:
            self.lb.insert("end", f"#{t}   ({counts.get(t, 0):,})")
        self.lb.configure(height=min(len(self.items), 12))
        self.lb.selection_clear(0, "end")
        self.lb.update_idletasks()
        top = self.ent.winfo_toplevel()
        w = max(self.ent.winfo_width(), self.lb.winfo_reqwidth(), 220)
        h = self.lb.winfo_reqheight()
        x = self.ent.winfo_rootx() - top.winfo_rootx()
        y = self.ent.winfo_rooty() - top.winfo_rooty() - h - 2          # 입력칸 바로 위(맨 아래 줄이라 아래는 화면 밖)
        self.lb.place(x=x, y=max(0, y), width=w, height=h)
        self.lb.lift()
        self._shown = True

    def toggle_all(self):
        """▾ 버튼: 모든 태그 목록을 펼치거나 접는다"""
        if self.visible():
            self.close()
        else:
            self.ent.focus_set()
            self.refresh(everything=True)

    def close(self):
        if self._shown and self.lb is not None:
            self.lb.place_forget()
        self._shown = False
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
        """고른(또는 첫) 후보를 넣는다. 넣었으면 True"""
        tag = tag or self._selected()
        if tag is None:
            return False
        text = self.ent.get()
        start, _tok = current_token(text)
        if self.on_pick:                     # 칩으로 추가: 치던 낱말은 지우고 태그만 넘긴다
            self.ent.delete(start, "end")
            if self.get_extra():             # 한글 조합 중이던 글자가 입력칸에 되살아나지 않게 버린다
                self.cancel_ime()
            self.on_pick(tag)
        else:
            self.ent.delete(0, "end")
            self.ent.insert(0, complete(text, start, tag))
            self.ent.icursor("end")
        self.ent.focus_set()
        self.refresh()
        return True

    def destroy_list(self):
        if self.lb is not None:
            self.lb.destroy()
            self.lb = None
        self._shown = False

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
        """Enter: 목록에서 고른 것이 있으면 그것을 넣고 True, 없으면 False"""
        if self.visible() and self._selected() is not None:
            return self.accept()
        return False


class TagBox(tk.Frame):
    """하단에 붙는 작은 박스: '태그 추가 및 제거:' [칩 칩 … 입력칸 ▾]  [확인] [취소].
    initial 태그들이 칩으로 먼저 보이고(× 로 뺄 수 있다), 새 태그는 Enter(또는 공백·쉼표)로 칩이 된다.
    [확인] → on_confirm(태그 목록), [취소]·Esc → on_cancel(). 빈 입력칸에서 Enter 도 확인이다."""

    def __init__(self, parent, initial, get_counts, colors, font, on_confirm, on_cancel, make_button, get_extra=lambda: "", cancel_ime=lambda: None):
        C = self.C = colors
        super().__init__(parent, bg=C["bg"])
        self.font = font
        self.tags = []
        self.on_confirm, self.on_cancel = on_confirm, on_cancel
        self.get_extra, self.cancel_ime = get_extra, cancel_ime
        self._chips = {}
        tk.Frame(self, height=1, bg=C["line"]).pack(fill="x")
        row = tk.Frame(self, bg=C["bg"])
        row.pack(fill="x", padx=14, pady=(8, 2))
        tk.Label(row, text="태그 추가 및 제거:", bg=C["bg"], fg=C["muted"], font=font).pack(side="left")
        self.field = tk.Frame(row, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"])
        self.field.pack(side="left", fill="x", expand=True, padx=(8, 0))
        arrow = tk.Label(self.field, text="▾", bg=C["panel"], fg=C["muted"], font=font, cursor="hand2", padx=8)
        arrow.pack(side="right", fill="y")
        self.flow = tk.Frame(self.field, bg=C["panel"], height=28)
        self.flow.pack(side="left", fill="x", expand=True)
        self.flow.pack_propagate(False)
        self.ent = tk.Entry(self.flow, relief="flat", bg=C["panel"], fg=C["text"], insertbackground=C["accent"], highlightthickness=0, font=font, width=14)
        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(fill="x", padx=14, pady=(2, 8))
        make_button(btns, "취소", self.cancel, padx=14, pady=3).pack(side="right")
        make_button(btns, "확인", self.confirm, kind="primary", padx=14, pady=3).pack(side="right", padx=(0, 6))
        tk.Label(btns, text="Enter: 태그 추가 · 빈 칸에서 Enter: 확인 · Esc: 취소", bg=C["bg"], fg=C["muted"], font=(font[0], max(font[1] - 1, 7))).pack(side="left")
        self.ac = TagComplete(self.ent, get_counts, colors, font, get_extra, get_have=lambda: self.tags, on_pick=self.add, cancel_ime=cancel_ime)
        arrow.bind("<Button-1>", lambda e: self.ac.toggle_all())
        self.ent.bind("<Return>", lambda e: self._enter())
        self.ent.bind("<KP_Enter>", lambda e: self._enter())
        self.ent.bind("<Escape>", lambda e: self._escape())
        self.ent.bind("<BackSpace>", lambda e: self._backspace())
        self.ent.bind("<KeyRelease>", lambda e: self._split(), add="+")
        self.flow.bind("<Configure>", lambda e: self.reflow())
        self.flow.bind("<Button-1>", lambda e: self.ent.focus_set())
        for t in initial:
            self.add(t, refresh=False)
        self.reflow()

    # ---- 칩
    def add(self, tag, refresh=True):
        t = clean(tag)
        if not t or t in self.tags:
            return False
        self.tags.append(t)
        chip = tk.Frame(self.flow, bg=self.C["soft"], padx=6)
        tk.Label(chip, text=t, bg=self.C["soft"], fg=self.C["text"], font=self.font).pack(side="left", pady=2)
        x = tk.Label(chip, text="×", bg=self.C["soft"], fg=self.C["muted"], font=self.font, cursor="hand2", padx=2)
        x.pack(side="left")
        x.bind("<Button-1>", lambda e, t=t: self.remove(t))
        x.bind("<Enter>", lambda e: x.config(fg="#d33"))
        x.bind("<Leave>", lambda e: x.config(fg=self.C["muted"]))
        self._chips[t] = chip
        if refresh:
            self.reflow()
        return True

    def remove(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            self._chips.pop(tag).destroy()
            self.reflow()
            self.ent.focus_set()

    def reflow(self):
        """칩과 입력칸을 한 줄씩 채워 가며 놓는다(넘치면 다음 줄)"""
        width = max(self.flow.winfo_width(), 200)
        x = y = 0
        row_h = 26
        for t in self.tags:
            c = self._chips[t]
            w = c.winfo_reqwidth()
            if x and x + w > width:
                x, y = 0, y + row_h
            c.place(x=x, y=y)
            x += w + 4
        ew = 120
        if x and x + ew > width:
            x, y = 0, y + row_h
        self.ent.place(x=x + 2, y=y, width=max(ew, width - x - 4), height=24)
        self.flow.configure(height=y + row_h + 2)

    # ---- 입력
    def _split(self):
        """공백·쉼표로 끝나면 그 낱말을 칩으로 만든다"""
        text = self.ent.get()
        if text and text[-1] in " ,":
            for tok in re.split(r"[,\s]+", text):
                self.add(tok)
            self.ent.delete(0, "end")

    def _enter(self):
        if self.ac.on_return():
            return "break"
        extra = self.get_extra()                    # 한글을 치는 중이면 마지막 글자는 아직 입력칸 값에 없다(예: '만화' 의 '화')
        text = (self.ent.get() + extra).strip()
        if text:
            for tok in re.split(r"[,\s]+", text):
                self.add(tok)
            self.ent.delete(0, "end")
            if extra:
                self.cancel_ime()                   # 조합 중이던 글자가 비운 입력칸에 다시 붙지 않게
            self.ac.close()
            self.focus_entry()
            self.after_idle(self.focus_entry)       # 칩이 놓이며 화면이 다시 그려진 뒤에도 한 번 더
        else:
            self.confirm()
        return "break"

    def _backspace(self):
        if not self.ent.get() and self.tags:       # 빈 칸에서 지우면 마지막 칩을 뺀다
            self.remove(self.tags[-1])
            return "break"
        return None

    def _escape(self):
        if self.ac.visible():
            self.ac.close()
        else:
            self.cancel()
        return "break"

    # ---- 끝내기
    def confirm(self):
        text = (self.ent.get() + self.get_extra()).strip()   # 치다 만 낱말(조합 중인 글자 포함)도 버리지 않고 함께 넣는다
        for tok in re.split(r"[,\s]+", text):
            self.add(tok, refresh=False)
        self.on_confirm(list(self.tags))

    def cancel(self):
        self.on_cancel()

    def close(self):
        self.ac.close()
        self.ac.destroy_list()

    def focus_entry(self):
        """칩을 더하거나 뺀 직후에도 입력칸이 키보드 포커스와 깜빡이는 커서를 갖게 한다"""
        self.ent.focus_set()
        self.ent.icursor("end")
