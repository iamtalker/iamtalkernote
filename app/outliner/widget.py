"""아웃라이너 편집기: 한 장의 tk.Text 에 항목을 한 줄씩(점 ● + 글) 그리고, 그 자리에서 바로 고친다(WorkFlowy 처럼).
글자 입력·줄 안 커서 이동은 Text 가 그대로 하고, 줄을 바꾸는 키(Enter·Tab·Backspace·Delete·붙여넣기·여러 줄 지우기 등)만 모델(model.py)로
처리한 뒤 다시 그린다. 바뀔 때마다 on_change(마크다운 원문)를 부른다.

키: Enter 새 항목(커서 뒤 글은 새 항목으로) · Tab / Shift+Tab 들여쓰기·내어쓰기 · 줄 맨 앞 Backspace 앞 항목에 붙이기(빈 항목은 지우기) ·
Delete(줄 끝) 다음 항목 붙이기 · Ctrl+↑/↓ 접기·펼치기 · Ctrl+Shift+↑/↓ 항목 옮기기 · Ctrl+Enter 완료 · Alt+→ 줌인 · Alt+← 줌아웃 ·
점(●)을 누르면 줌인 · Ctrl+Z / Ctrl+Y 되돌리기·다시"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import model as M

MAX_DEPTH = 12
OFF = 2                              # 줄 맨 앞의 점 글자("● ")가 차지하는 글자 수: 항목 글은 한 줄의 OFF 번째 글자부터


class OutlineEditor(tk.Frame):
    def __init__(self, master, colors, font, on_change, get_title=lambda: "노트"):
        super().__init__(master, bg=colors["bg"])
        self.C, self.font, self.on_change, self.get_title = colors, font, on_change, get_title
        self.family = tkfont.Font(root=master, font=font).actual("family")
        self.items = [M.Item(0, "")]
        self.zoom = None                    # 줌인한 항목 번호(없으면 노트 전체)
        self.vis = []                       # 화면 줄 → 항목 번호
        self.undo, self.redo = [], []
        self._typing = False
        self._typing_job = self._change_job = None
        self.crumb = tk.Frame(self, bg=colors["bg"])
        self.crumb.pack(side="top", fill="x", padx=18)
        wrap = tk.Frame(self, bg=colors["bg"])
        wrap.pack(fill="both", expand=True)
        self.txt = t = tk.Text(wrap, wrap="word", font=font, bg=colors["bg"], fg=colors["text"], relief="flat", bd=0, highlightthickness=0,
                               padx=14, pady=8, undo=False, spacing1=3, spacing3=3, insertbackground=colors["accent"],
                               selectbackground=colors["sel"], selectforeground=colors["text"], cursor="xterm")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        for d in range(MAX_DEPTH + 1):
            t.tag_configure(f"d{d}", lmargin1=6 + 26 * d, lmargin2=6 + 26 * d + 22)
        t.tag_configure("bul", foreground=colors["muted"], font=(self.family, 8))
        t.tag_configure("bulc", foreground=colors["accent"], font=(self.family, 8))
        t.tag_bind("bul", "<Button-1>", self._bullet_click)
        t.tag_bind("bulc", "<Button-1>", self._bullet_click)
        for tg in ("bul", "bulc"):
            t.tag_bind(tg, "<Enter>", lambda e: t.config(cursor="hand2"))
            t.tag_bind(tg, "<Leave>", lambda e: t.config(cursor="xterm"))
        t.tag_configure("done", foreground=colors["muted"], overstrike=True)
        t.tag_configure("link", foreground=colors["accent"], underline=True)
        for seq, fn in (("<Return>", self._enter), ("<KP_Enter>", self._enter), ("<Tab>", self._tab), ("<ISO_Left_Tab>", self._btab),
                        ("<Shift-Tab>", self._btab), ("<BackSpace>", self._backspace), ("<Delete>", self._delete),
                        ("<Control-Return>", self._done), ("<Control-Up>", lambda e: self._fold(True)), ("<Control-Down>", lambda e: self._fold(False)),
                        ("<Control-Shift-Up>", lambda e: self._move(True)), ("<Control-Shift-Down>", lambda e: self._move(False)),
                        ("<Alt-Right>", self._zoom_in), ("<Alt-Left>", self._zoom_out), ("<Control-z>", lambda e: self._undo()),
                        ("<Control-y>", lambda e: self._undo(redo=True)), ("<Control-Shift-Z>", lambda e: self._undo(redo=True)),
                        ("<Home>", self._home), ("<Left>", self._left), ("<Right>", self._right), ("<<Cut>>", self._cut),
                        ("<<Copy>>", self._copy), ("<<Paste>>", self._paste), ("<Key>", self._key)):
            t.bind(seq, fn)
        t.bind("<KeyRelease>", self._released)
        t.bind("<ButtonRelease-1>", lambda e: self.after_idle(self._fix_cursor))
        t.bind("<FocusOut>", lambda e: self.flush())
        self._crumbs()

    # ---------------------------------------------------------------- 불러오기·내보내기
    def load(self, body):
        self.items = M.parse(body) or [M.Item(0, "")]
        self.zoom = None
        self.undo.clear()
        self.redo.clear()
        self.redraw(0, 0)

    def body(self):
        return M.dump(self.items)

    def reload_if_changed(self, body):
        """밖(다른 편집·되돌리기)에서 원문이 바뀌었으면 다시 읽는다. 내가 바꾼 것이면 그대로 둔다"""
        self.pull()
        if M.dump(M.parse(body)) != M.dump(self.items) and not (not body.strip() and len(self.items) == 1 and not self.items[0].text):
            z = self.zoom
            self.items = M.parse(body) or [M.Item(0, "")]
            self.zoom = z if z is not None and z < len(self.items) else None
            self.redraw(self.vis[0] if self.vis else 0, 0)

    def flush(self):
        if self._change_job:
            self.after_cancel(self._change_job)
            self._change_job = None
        self.pull()
        self.on_change(self.body())

    # ---------------------------------------------------------------- 그리기
    def _floor(self):
        return 0 if self.zoom is None else self.items[self.zoom].depth + 1

    def redraw(self, focus=None, col=0):
        t = self.txt
        top = t.yview()[0]
        self.vis = M.visible(self.items, self.zoom)
        if not self.vis and self.zoom is not None:           # 줌인한 항목에 하위가 없으면 첫 하위를 하나 만들어 준다
            self.items.insert(self.zoom + 1, M.Item(self.items[self.zoom].depth + 1, ""))
            self.vis = M.visible(self.items, self.zoom)
        if focus is None and self.vis:
            focus = self.vis[0]
        base = self._floor()
        t.delete("1.0", "end")
        parts, spans = [], []                                # 글 전체를 한 번에 넣고 태그만 따로 입힌다(줄마다 insert 하면 느리다)
        for k, i in enumerate(self.vis):
            it = self.items[i]
            hidden = it.collapsed and M.has_children(self.items, i)
            parts.append(("◉ " if hidden else "● ") + it.text)
            spans.append((k + 1, "bulc" if hidden else "bul", f"d{min(MAX_DEPTH, max(0, it.depth - base))}", M.is_done(it)))
        t.insert("1.0", "\n".join(parts))
        for ln, bul, dtag, done in spans:
            t.tag_add(bul, f"{ln}.0", f"{ln}.1")
            t.tag_add(dtag, f"{ln}.0", f"{ln}.end")
            if done:
                t.tag_add("done", f"{ln}.{OFF}", f"{ln}.end")
        if focus is not None and focus in self.vis:
            ln = self.vis.index(focus) + 1
            t.mark_set("insert", f"{ln}.{OFF + min(col, len(self.items[focus].text))}")
        t.yview_moveto(top)
        t.see("insert")
        self._crumbs()

    def _crumbs(self):
        for w in self.crumb.winfo_children():
            w.destroy()
        if self.zoom is None:
            return
        chain = [(self.get_title() or "노트", None)] + [(self.items[a].text[:30] or "…", a) for a in M.ancestors(self.items, self.zoom)]
        for text, idx in chain:
            lb = tk.Label(self.crumb, text=text, bg=self.C["bg"], fg=self.C["accent"], cursor="hand2", font=(self.family, 9))
            lb.pack(side="left")
            lb.bind("<Button-1>", lambda e, idx=idx: self.set_zoom(idx))
            tk.Label(self.crumb, text=" › ", bg=self.C["bg"], fg=self.C["muted"], font=(self.family, 9)).pack(side="left")
        tk.Label(self.crumb, text=self.items[self.zoom].text or "(빈 항목)", bg=self.C["bg"], fg=self.C["text"],
                 font=(self.family, 11, "bold")).pack(side="left")

    # ---------------------------------------------------------------- 화면 ↔ 모델
    def _pos(self):
        ln, col = map(int, self.txt.index("insert").split("."))
        return ln - 1, max(0, col - OFF)

    def _cur(self):
        k, col = self._pos()
        k = max(0, min(k, len(self.vis) - 1))
        return self.vis[k], col, k

    def pull(self):
        """화면의 글을 항목에 옮겨 담는다(줄 수가 안 맞으면 건드리지 않는다)"""
        t = self.txt
        if int(t.index("end-1c").split(".")[0]) != len(self.vis):
            return
        for k, i in enumerate(self.vis):
            self.items[i].text = t.get(f"{k + 1}.{OFF}", f"{k + 1}.end")

    def _bullet_click(self, e):
        k = int(self.txt.index(f"@{e.x},{e.y}").split(".")[0]) - 1
        if 0 <= k < len(self.vis):
            self.set_zoom(self.vis[k])
        return "break"

    def _clamp_sel(self):
        """고른 곳이 줄 앞의 점 글자를 포함하면 점은 빼 준다(점이 지워지면 구조가 어긋난다)"""
        r = self.txt.tag_ranges("sel")
        if r:
            ln, c = map(int, str(r[0]).split("."))
            if c < OFF:
                self.txt.tag_remove("sel", "1.0", "end")
                self.txt.tag_add("sel", f"{ln}.{OFF}", r[1])

    def _fix_cursor(self):
        ln, col = map(int, self.txt.index("insert").split("."))
        if col < OFF and not self.txt.tag_ranges("sel"):
            self.txt.mark_set("insert", f"{ln}.{OFF}")

    def _snapshot(self):
        return [(it.depth, it.text, it.collapsed) for it in self.items], self.zoom

    def _push_undo(self):
        self.pull()
        self.undo.append(self._snapshot())
        del self.undo[:-200]
        self.redo.clear()

    def _commit(self, focus, col=0):
        """모델을 바꾼 뒤: 다시 그리고 원문을 알린다"""
        if focus is not None and 0 <= focus < len(self.items):
            self.redraw(focus, col)
        else:
            self.redraw()
        self.flush()

    def _released(self, e):
        if e.keysym in ("Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next"):
            self._fix_cursor()
            return
        if e.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        if self._change_job:
            self.after_cancel(self._change_job)
        self._change_job = self.after(350, self.flush)

    def _key(self, e):
        """글자를 칠 때: 첫 글자에서 되돌리기 지점을 만들고, 여러 줄을 고른 채 치면 고른 것을 먼저 지운다"""
        if not e.char or ord(e.char[0]) < 32 or e.keysym in ("Escape",):
            return None
        self._clamp_sel()
        if self._multi_sel():
            self._delete_selection()
        if not self._typing:
            self._push_undo()
        self._typing = True
        if self._typing_job:
            self.after_cancel(self._typing_job)
        self._typing_job = self.after(1200, lambda: setattr(self, "_typing", False))
        return None

    def _multi_sel(self):
        r = self.txt.tag_ranges("sel")
        return bool(r) and str(r[0]).split(".")[0] != str(r[1]).split(".")[0]

    def _delete_selection(self):
        """여러 줄에 걸친 선택을 지운다: 처음 줄 앞부분 + 끝 줄 뒷부분이 한 항목이 된다"""
        t = self.txt
        self._push_undo()
        la, ca = map(int, str(t.index("sel.first")).split("."))
        lb, cb = map(int, str(t.index("sel.last")).split("."))
        ia, ib = self.vis[la - 1], self.vis[lb - 1]
        ca, cb = max(0, ca - OFF), max(0, cb - OFF)
        text = self.items[ia].text[:ca] + self.items[ib].text[cb:]
        del self.items[ia + 1:ib + 1]
        self.items[ia].text = text
        if not self.items:
            self.items = [M.Item(0, "")]
        M.normalize(self.items)
        t.tag_remove("sel", "1.0", "end")
        self._commit(ia, ca)

    # ---------------------------------------------------------------- 키
    def _enter(self, e=None):
        t = self.txt
        if self._multi_sel():
            self._delete_selection()
        elif t.tag_ranges("sel"):
            t.delete("sel.first", "sel.last")
        self.pull()
        i, col, _k = self._cur()
        it = self.items[i]
        self._push_undo()
        if not it.text.strip() and it.depth > self._floor() and not M.has_children(self.items, i):
            M.outdent(self.items, i, self._floor())          # 빈 항목에서 Enter: 한 단계 밖으로
            return self._commit(i, 0) or "break"
        j, c = M.split(self.items, i, col)
        self._commit(j, c)
        return "break"

    def _tab(self, e=None):
        self.pull()
        i, col, _k = self._cur()
        self._push_undo()
        if M.indent(self.items, i, self._floor()):
            self._commit(i, col)
        else:
            self.undo.pop()
        return "break"

    def _btab(self, e=None):
        self.pull()
        i, col, _k = self._cur()
        self._push_undo()
        if M.outdent(self.items, i, self._floor()):
            self._commit(i, col)
        else:
            self.undo.pop()
        return "break"

    def _backspace(self, e=None):
        t = self.txt
        self._clamp_sel()
        if self._multi_sel():
            self._delete_selection()
            return "break"
        if t.tag_ranges("sel"):
            return None
        k, col = self._pos()
        if col > 0:
            return None
        self.pull()
        i = self.vis[k]
        it = self.items[i]
        if k == 0:
            if not it.text and len(self.vis) > 1 and not M.has_children(self.items, i):   # 맨 위의 빈 항목은 지운다
                self._push_undo()
                del self.items[i]
                self._commit(self.vis[1] - 1 if len(self.vis) > 1 else 0, 0)
            return "break"
        self._push_undo()
        prev = self.vis[k - 1]
        if not it.text and not M.has_children(self.items, i):
            c = len(self.items[prev].text)
            del self.items[i]
        else:
            prev, c = M.merge_prev(self.items, i, prev)
        self._commit(prev, c)
        return "break"

    def _delete(self, e=None):
        t = self.txt
        self._clamp_sel()
        if self._multi_sel():
            self._delete_selection()
            return "break"
        if t.tag_ranges("sel"):
            return None
        k, col = self._pos()
        ln = k + 1
        if col < len(t.get(f"{ln}.{OFF}", f"{ln}.end")):
            return None                                       # 줄 안에서는 글자 하나를 지운다
        if k >= len(self.vis) - 1:
            return "break"
        self.pull()
        self._push_undo()
        i, c = M.merge_next(self.items, self.vis[k], self.vis[k + 1])
        self._commit(i, c)
        return "break"

    def _done(self, e=None):
        self.pull()
        i, col, _k = self._cur()
        self._push_undo()
        M.toggle_done(self.items[i])
        self._commit(i, col + 4 if M.is_done(self.items[i]) else col)
        return "break"

    def _fold(self, collapse):
        self.pull()
        i, col, _k = self._cur()
        if M.has_children(self.items, i) and self.items[i].collapsed != collapse:
            self.items[i].collapsed = collapse
            self.redraw(i, col)
        return "break"

    def _move(self, up):
        self.pull()
        i, col, _k = self._cur()
        lo, hi = (0, len(self.items)) if self.zoom is None else (self.zoom + 1, M.end_of(self.items, self.zoom))
        self._push_undo()
        j = M.move(self.items, i, up, lo, hi)
        if j is None:
            self.undo.pop()
        else:
            self._commit(j, col)
        return "break"

    def set_zoom(self, i):
        self.pull()
        self.zoom = i
        self.redraw(None, 0)
        self.txt.focus_set()

    def _zoom_in(self, e=None):
        i, _c, _k = self._cur()
        self.set_zoom(i)
        return "break"

    def _zoom_out(self, e=None):
        if self.zoom is not None:
            chain = M.ancestors(self.items, self.zoom)
            old = self.zoom
            self.set_zoom(chain[-1] if chain else None)
            if old in self.vis:
                self.redraw(old, 0)
        return "break"

    def _undo(self, redo=False):
        src, dst = (self.redo, self.undo) if redo else (self.undo, self.redo)
        if not src:
            return "break"
        self.pull()
        dst.append(self._snapshot())
        rows, zoom = src.pop()
        self.items = [M.Item(d, t, c) for d, t, c in rows]
        self.zoom = zoom if zoom is not None and zoom < len(self.items) else None
        self.redraw()
        self.flush()
        return "break"

    def _home(self, e=None):
        k, _c = self._pos()
        self.txt.mark_set("insert", f"{k + 1}.{OFF}")
        return "break"

    def _left(self, e=None):
        k, col = self._pos()
        if col == 0 and not self.txt.tag_ranges("sel"):
            if k > 0:
                self.txt.mark_set("insert", f"{k}.end")
            return "break"
        return None

    def _right(self, e=None):
        k, col = self._pos()
        ln = k + 1
        if col >= len(self.txt.get(f"{ln}.{OFF}", f"{ln}.end")) and k < len(self.vis) - 1 and not self.txt.tag_ranges("sel"):
            self.txt.mark_set("insert", f"{ln + 1}.{OFF}")
            return "break"
        return None

    # ---------------------------------------------------------------- 복사·잘라내기·붙여넣기
    def _selection_items(self):
        """고른 줄들을 마크다운 목록 글로"""
        t = self.txt
        la, ca = map(int, str(t.index("sel.first")).split("."))
        lb, cb = map(int, str(t.index("sel.last")).split("."))
        self.pull()
        rows = []
        for ln in range(la, lb + 1):
            it = self.items[self.vis[ln - 1]]
            s = it.text[max(0, ca - OFF):] if ln == la else it.text
            if ln == lb:
                s = s[:max(0, cb - OFF) - (max(0, ca - OFF) if ln == la else 0)]
            rows.append(M.Item(it.depth, s))
        base = min(r.depth for r in rows)
        for r in rows:
            r.depth -= base
        return rows

    def _copy(self, e=None):
        if not self.txt.tag_ranges("sel") or not self._multi_sel():
            return None
        self.clipboard_clear()
        self.clipboard_append(M.dump(self._selection_items()))
        return "break"

    def _cut(self, e=None):
        if not self.txt.tag_ranges("sel"):
            return "break"
        if not self._multi_sel():
            return None
        self._copy()
        self._delete_selection()
        return "break"

    def _paste(self, e=None):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return "break"
        t = self.txt
        if self._multi_sel():
            self._delete_selection()
        elif t.tag_ranges("sel"):
            t.delete("sel.first", "sel.last")
        new = M.parse(clip) if "\n" in clip.strip("\n") else None
        if not new or len(new) < 2:
            t.insert("insert", " ".join(clip.split()))     # 한 줄은 그냥 끼워 넣는다
            self._released(type("E", (), {"keysym": "v"})())
            return "break"
        self.pull()
        i, col, _k = self._cur()
        self._push_undo()
        cur = self.items[i]
        before, after = cur.text[:col], cur.text[col:]
        cur.text = before + new[0].text
        rows = [M.Item(cur.depth + n.depth, n.text) for n in new[1:]]
        rows[-1].text += after
        self.items[i + 1:i + 1] = rows
        M.normalize(self.items)
        self._commit(i + len(rows), len(new[-1].text))
        return "break"
