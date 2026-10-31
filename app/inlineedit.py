"""렌더링 화면에서 글을 눌러 그 자리에서 그 부분의 마크다운 원문만 고치는 작은 입력칸(렌더링 칸 위에 겹쳐 띄운다).
항목(한 줄)은 Enter 로 저장, 여러 줄 블록은 Ctrl+Enter 로 저장, Esc 는 취소, 칸 밖을 누르면 저장한다."""
import tkinter as tk
import tkinter.font as tkfont


class InlineEdit:
    def __init__(self, view, start, end, text, multiline, font, colors, on_commit, on_cancel=None, keys=None, cursor=None):
        """view: 렌더링 칸(tk.Text). start/end: 고칠 부분이 화면에서 차지하는 글 위치(index). text: 입력칸에 넣을 원문.
        keys: {'enter','tab','btab','back','up','down': 함수(편집기)} — 아웃라이너 항목 편집용. 함수가 True 를 돌려주면 그 키를 처리한 것.
        cursor: 처음 커서 위치(글자 수, 없으면 맨 끝)"""
        self.view, self.multiline = view, multiline
        self.on_commit, self.on_cancel = on_commit, on_cancel
        self.done = False
        bb = view.bbox(start)
        if not bb:                                   # 화면 밖이면 열 수 없다
            raise ValueError("화면에 안 보이는 글")
        try:
            eb = view.bbox(f"{end}-1c") or bb
        except tk.TclError:
            eb = bb
        x, y = bb[0], bb[1]
        bottom = eb[1] + eb[3]
        width = max(120, view.winfo_width() - x - 16)
        self.lh = max(14, tkfont.Font(font=font).metrics("linespace"))
        self.seamless = bool(keys)                   # 아웃라이너 항목: 테두리·여백 없이 렌더링된 글 바로 그 자리에서 고치는 것처럼 보이게
        self.txt = tk.Text(view, wrap="word", font=font, relief="flat", bd=0,
                           highlightthickness=0 if self.seamless else 1, highlightbackground=colors["accent"],
                           highlightcolor=colors["accent"], bg=colors["bg"], fg=colors["text"], insertbackground=colors["accent"],
                           selectbackground=colors.get("sel", colors["accent"]), selectforeground=colors["text"],
                           padx=0 if self.seamless else 6, pady=0 if self.seamless else 3, undo=True, height=1,
                           spacing2=3 if self.seamless else 0)
        self.txt.insert("1.0", text)
        self.txt.edit_reset()
        if self.seamless:
            self._x, self._y, self._w = x, y, max(60, view.winfo_width() - x - 24)
            self.txt.place(x=self._x, y=self._y, width=self._w, height=max(self.lh, bottom - y))
        else:
            self._x, self._y, self._w = max(0, x - 8), max(0, y - 4), width + 8
            self.txt.place(x=self._x, y=self._y, width=self._w, height=max(self.lh + 8, bottom - y + 8))
        self.txt.focus_set()
        self.txt.mark_set("insert", "end-1c" if cursor is None else f"1.0+{max(0, min(cursor, len(text)))}c")
        self.keys = keys or {}
        self.txt.bind("<Escape>", lambda e: self._cancel())
        if self.keys:
            self.txt.bind("<Tab>", lambda e: self._key("tab"))
            self.txt.bind("<ISO_Left_Tab>", lambda e: self._key("btab"))
            self.txt.bind("<Shift-Tab>", lambda e: self._key("btab"))
            self.txt.bind("<BackSpace>", lambda e: self._key("back") if (not self.value() and self.keys.get("back")) else None)
            self.txt.bind("<Up>", lambda e: self._key("up") if self._on_line(first=True) else None)
            self.txt.bind("<Down>", lambda e: self._key("down") if self._on_line(first=False) else None)
        if multiline:
            self.txt.bind("<Control-Return>", lambda e: self._commit())
        else:
            self.txt.bind("<Return>", lambda e: self._key("enter") or self._commit())
            self.txt.bind("<KP_Enter>", lambda e: self._key("enter") or self._commit())
        self.txt.bind("<KeyRelease>", lambda e: self._fit(), add="+")
        self.txt.bind("<FocusOut>", lambda e: self.txt.after(120, self._lost))
        self._fit()

    def _key(self, name):
        fn = self.keys.get(name)
        if fn and not self.done:
            fn(self)
        return "break"

    def _on_line(self, first):
        """커서가 (줄바꿈으로 보이는) 첫 줄 / 마지막 줄에 있는가"""
        a = self.txt.bbox("insert")
        if not a:
            return True
        edge = self.txt.bbox("1.0" if first else "end-1c")
        return bool(edge) and abs(a[1] - edge[1]) < max(4, self.lh // 2)

    def cursor(self):
        """커서의 글자 위치"""
        return len(self.txt.get("1.0", "insert"))

    def detach(self):
        """입력칸을 닫고 (글, 커서 위치) 를 돌려준다. on_commit 은 부르지 않는다(호출한 쪽이 직접 반영)"""
        text, cur = self.value(), self.cursor()
        self.done = True
        try:
            self.txt.destroy()
        except tk.TclError:
            pass
        return (text if self.multiline else " ".join(text.split("\n"))), min(cur, len(text))

    def _fit(self):
        """글이 줄바꿈되며 길어지면 입력칸 높이도 따라 늘린다"""
        if self.done:
            return
        try:
            n = self.txt.count("1.0", "end-1c", "displaylines")
            n = (n[0] if n else 1) or 1
            self.txt.place_configure(height=n * (self.lh + 3) if self.seamless else n * self.lh + 10)
        except tk.TclError:
            pass

    def _lost(self):
        if self.done:
            return
        try:
            if self.txt.focus_displayof() is self.txt:
                return
        except (tk.TclError, KeyError):
            pass
        self._commit()

    def value(self):
        return self.txt.get("1.0", "end-1c")

    def _commit(self):
        self.finish(True)
        return "break"

    def _cancel(self):
        self.finish(False)
        return "break"

    def finish(self, commit):
        if self.done:
            return
        self.done = True
        text = self.value()
        try:
            self.txt.destroy()
        except tk.TclError:
            pass
        if commit:
            self.on_commit(text if self.multiline else " ".join(text.split("\n")))
        elif self.on_cancel:
            self.on_cancel()
