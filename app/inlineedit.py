"""렌더링 화면에서 글을 눌러 그 자리에서 그 부분의 마크다운 원문만 고치는 작은 입력칸(렌더링 칸 위에 겹쳐 띄운다).
항목(한 줄)은 Enter 로 저장, 여러 줄 블록은 Ctrl+Enter 로 저장, Esc 는 취소, 칸 밖을 누르면 저장한다."""
import tkinter as tk
import tkinter.font as tkfont


class InlineEdit:
    def __init__(self, view, start, end, text, multiline, font, colors, on_commit, on_cancel=None):
        """view: 렌더링 칸(tk.Text). start/end: 고칠 부분이 화면에서 차지하는 글 위치(index). text: 입력칸에 넣을 원문."""
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
        self.txt = tk.Text(view, wrap="word", font=font, relief="flat", bd=0, highlightthickness=1, highlightbackground=colors["accent"],
                           highlightcolor=colors["accent"], bg=colors["bg"], fg=colors["text"], insertbackground=colors["accent"],
                           padx=6, pady=3, undo=True, height=1)
        self.txt.insert("1.0", text)
        self.txt.edit_reset()
        self._x, self._y, self._w = max(0, x - 8), max(0, y - 4), width + 8
        self.txt.place(x=self._x, y=self._y, width=self._w, height=max(self.lh + 8, bottom - y + 8))
        self.txt.focus_set()
        self.txt.mark_set("insert", "end-1c")
        self.txt.bind("<Escape>", lambda e: self._cancel())
        if multiline:
            self.txt.bind("<Control-Return>", lambda e: self._commit())
        else:
            self.txt.bind("<Return>", lambda e: self._commit())
            self.txt.bind("<KP_Enter>", lambda e: self._commit())
        self.txt.bind("<KeyRelease>", lambda e: self._fit(), add="+")
        self.txt.bind("<FocusOut>", lambda e: self.txt.after(120, self._lost))
        self._fit()

    def _fit(self):
        """글이 줄바꿈되며 길어지면 입력칸 높이도 따라 늘린다"""
        if self.done:
            return
        try:
            n = self.txt.count("1.0", "end-1c", "displaylines")
            n = (n[0] if n else 1) or 1
            self.txt.place_configure(height=n * self.lh + 10)
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
