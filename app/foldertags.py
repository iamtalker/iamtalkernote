"""폴더 정보 화면: 노트 칸에 노트북이나 가져온 폴더를 고르면 파일처럼 폴더 이름·경로·태그·메모를 보여 준다.
태그는 가져온 파일처럼 '태그 추가' 단추를 눌러야 입력 박스(tagac.TagBox)가 열린다(처음부터 입력 상태로 두지 않는다).
폴더 자체에만 붙고 안의 노트·파일에는 붙지 않는다(저장은 색인 DB 의 ftag·fmemo 표)."""
import tkinter as tk

import tagac
from i18n import tr


class FolderTagPage(tk.Frame):
    def __init__(self, parent, colors, ui, title_of, get_tags, set_tags, on_change, get_counts, make_button, composing, cancel_ime,
                 path_of=lambda k: "", get_memo=lambda k: "", set_memo=lambda k, m: None):
        super().__init__(parent, bg=colors["bg"])
        self.C, self.ui = colors, ui
        self.path_of, self.get_memo, self.set_memo = path_of, get_memo, set_memo
        self.title_of, self.get_tags, self.set_tags, self.on_change = title_of, get_tags, set_tags, on_change
        self.get_counts, self.make_button, self.composing, self.cancel_ime = get_counts, make_button, composing, cancel_ime
        self.key, self.box, self.tags = None, None, []
        self.title_lab = tk.Label(self, bg=colors["bg"], fg=colors["text"], font=(ui, 14, "bold"), anchor="w")
        self.title_lab.pack(fill="x", padx=24, pady=(24, 2))
        self.path_lab = tk.Label(self, bg=colors["bg"], fg=colors["muted"], font=(ui, 9), anchor="w", justify="left", wraplength=640)
        self.path_lab.pack(fill="x", padx=24, pady=(0, 8))
        self.tag_row = tk.Frame(self, bg=colors["bg"])
        self.tag_row.pack(fill="x", padx=24, pady=(0, 4))
        self.tag_btn = make_button(self.tag_row, tr("태그 추가"), self.edit_tags, kind="primary", padx=10, pady=3)
        self.tag_labels = tk.Label(self.tag_row, bg=colors["bg"], fg=colors["accent"], font=(ui, 10), anchor="w")
        self.hint = tk.Label(self, text=tr("폴더 태그·메모는 폴더 자체에만 붙고, 안의 노트·파일에는 붙지 않습니다"), bg=colors["bg"], fg=colors["muted"],
                             font=(ui, 9), anchor="w")
        self.hint.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(self, text=tr("폴더 메모"), bg=colors["bg"], fg=colors["muted"], font=(ui, 9), anchor="w").pack(fill="x", padx=24)
        self.memo_box = tk.Text(self, height=8, wrap="word", relief="flat", bd=0, padx=10, pady=8, bg=colors["panel"], fg=colors["text"],
                                insertbackground=colors["text"], highlightthickness=1, highlightbackground=colors["line"], font=(ui, 10))
        self.memo_box.pack(fill="x", padx=24, pady=(2, 0))
        self.memo_box.bind("<FocusOut>", lambda e: self.save_memo())

    def show(self, key):
        self.save_memo()                 # 다른 폴더로 옮기기 전에 이전 폴더의 메모를 저장한다
        self.close_box()
        self.key = key
        self.title_lab.config(text="📁  " + self.title_of(key))
        self.path_lab.config(text=self.path_of(key))
        self.tags = sorted(self.get_tags(key))
        self.draw_tags()
        self.memo_box.delete("1.0", "end")
        self.memo_box.insert("1.0", self.get_memo(key))

    def draw_tags(self):
        self.tag_labels.config(text="  ".join("#" + t for t in self.tags))
        self.tag_btn.pack(side="left", padx=(0, 8))
        if self.tags:
            self.tag_labels.pack(side="left")
        else:
            self.tag_labels.pack_forget()

    def edit_tags(self, e=None):
        """'태그 추가'를 누르면 입력 박스가 열린다. [확인]은 저장, [취소]·Esc 는 아무것도 바꾸지 않는다"""
        if self.box is not None or self.key is None:
            return
        self.tag_row.pack_forget()
        self.box = tagac.TagBox(self, self.tags, self.get_counts, self.C, (self.ui, 9), self.confirm, self.close_box,
                                self.make_button, self.composing, self.cancel_ime)
        self.box.pack(side="top", fill="x", before=self.hint)
        self.box.ent.focus_set()

    def close_box(self):
        if self.box is not None:
            self.box.close()
            self.box.destroy()
            self.box = None
            self.tag_row.pack(fill="x", padx=24, pady=(0, 4), before=self.hint)

    def confirm(self, tags):
        self.set_tags(self.key, list(dict.fromkeys(tags)))
        self.tags = sorted(self.get_tags(self.key))
        self.close_box()
        self.draw_tags()
        self.on_change()

    def save_memo(self):
        if self.key is not None:
            self.set_memo(self.key, self.memo_box.get("1.0", "end-1c"))
