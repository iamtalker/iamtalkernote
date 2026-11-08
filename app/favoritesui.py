"""즐겨찾기의 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class FavoritesMixin:
    # ---- 즐겨찾기(설정 폴더의 작은 파일에 적어 폰과 맞춘다)
    def fav_move(self, old_path, new_path):
        """이름을 바꾸거나 옮긴 노트의 즐겨찾기를 새 경로로 옮긴다"""
        try:
            self.fav.move(favorites.rel_of(self.store.root, old_path), favorites.rel_of(self.store.root, new_path))
        except Exception:  # noqa: BLE001
            pass

    def fav_rel(self, n):
        return n.get("key") or favorites.rel_of(self.store.root, n["path"])   # 노트의 key 는 노트 폴더 기준 슬래시 경로(rel_of 와 같다)

    def is_fav(self, n):
        return bool(n) and not isinstance(n, docidx.Doc) and self.fav.is_fav(self.fav_rel(n))

    def update_star(self):
        return

    def toggle_favorite(self, n=None):
        """노트의 즐겨찾기를 켜고 끈다(가져온 문서는 제외)"""
        n = n or self.cur
        if not n or isinstance(n, docidx.Doc):
            return
        on = self.fav.toggle(self.fav_rel(n))
        self.status.config(text=(tr("즐겨찾기에 넣었습니다: ") if on else tr("즐겨찾기에서 뺐습니다: ")) + n["title"])
        if self.nb == FAVS:   # 즐겨찾기 목록을 보는 중이면 빠진 노트는 목록에서도 빠진다
            self.notes = [x for x in self.all_notes if self.is_fav(x)]
        self.reload_notebooks()
        if self.nb == FAVS:
            self.refresh(keep_page=True)
        else:
            self.draw_list(keep_scroll=True)
        return "break"

    def trash_menu(self, e, n):
        m = tk.Menu(self.root, tearoff=0)

        def restore():
            try:
                self.store.restore_trash(n["trash"])
            except OSError as ex:
                return messagebox.showerror(APP, tr('복원하지 못했습니다.\n{0}').format(ex), parent=self.root)
            self.close_note()
            self.reload_notes()

        def remove():
            if messagebox.askyesno(APP, tr('「{0}」을(를) 완전히 지울까요? 되돌릴 수 없습니다.').format(n['title']), parent=self.root):
                self.store.delete_trash(n["trash"])
                self.close_note()
                self.reload_notes()

        def empty():
            if messagebox.askyesno(APP, tr('휴지통의 {0:,}개를 모두 완전히 지울까요? 되돌릴 수 없습니다.').format(len(self.notes)), parent=self.root):
                self.store.empty_trash()
                self.close_note()
                self.reload_notes()
        m.add_command(label=tr("복원"), command=restore)
        m.add_command(label=tr("완전히 삭제"), command=remove)
        m.add_separator()
        m.add_command(label=tr("휴지통 비우기"), command=empty)
        m.tk_popup(e.x_root, e.y_root)

    def on_list_menu(self, e):
        """노트 우클릭 메뉴 (조플린: 삭제 · 노트북으로 이동 · 링크 복사 …)"""
        n = self.card_at(e)
        if not n:
            return
        if isinstance(n, docidx.Doc):
            return self.doc_menu(e, n)
        if n.get("trash"):
            self.open_note(n)
            return self.trash_menu(e, n)
        if self.multi and n["path"] in self.multi:   # 여러 개를 고른 채 그 안에서 우클릭
            return self.multi_menu(e)
        self.clear_multi()
        self.open_note(n)
        self.ctx_note = n
        lm, mm = self.listmenu, self.movemenu
        lm.delete(0, "end")
        mm.delete(0, "end")
        for key in [""] + self.visible_notebooks():
            label = ("    " * key.count("/") + (self.nb_short(key) if key else self.store.root_name))
            mm.add_command(label=label, command=lambda k=key: self.move_note(n, k), state="disabled" if key == n["nb"] else "normal")
        if st.conflict_of(os.path.basename(n["path"])):
            lm.add_command(label=tr("동기화 충돌 해결…"), command=lambda: self.conflict_dialog(n))
            lm.add_separator()
        lm.add_cascade(label=tr("노트북으로 이동"), menu=mm)
        lm.add_command(label=tr("즐겨찾기 해제") if self.is_fav(n) else tr("즐겨찾기 추가"), accelerator="Ctrl+D", command=lambda: self.toggle_favorite(n))
        lm.add_command(label=tr("연결된 노트 보기…"), command=lambda: self.show_links(n))
        lm.add_command(label=tr("태그 추가…"), command=lambda: self.tag_new([n]))
        lm.add_command(label=tr("노트 링크 복사"), command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(f"[[{n['title']}]]")))
        lm.add_command(label=tr("노트 속성…"), command=self.show_properties)
        lm.add_command(label=tr("노트 버전…"), command=self.show_versions)
        lm.add_command(label=tr("파일 위치 열기"), command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_separator()
        lm.add_command(label=tr("삭제"), command=self.delete_note)
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    def multi_menu(self, e):
        lm, mm = self.listmenu, self.movemenu
        lm.delete(0, "end")
        mm.delete(0, "end")
        for key in [""] + self.visible_notebooks():
            label = ("    " * key.count("/") + (self.nb_short(key) if key else self.store.root_name))
            mm.add_command(label=label, command=lambda k=key: self.move_multi(k))
        lm.add_cascade(label=tr("노트 {n}개를 노트북으로 이동").format(n=len(self.multi)), menu=mm)
        lm.add_command(label=tr("노트 {n}개에 태그 추가…").format(n=len(self.multi)), command=lambda: self.tag_new(list(self.multi.values())))
        lm.add_command(label=tr("노트 {n}개 휴지통으로").format(n=len(self.multi)), command=self.trash_multi)
        lm.add_separator()
        lm.add_command(label=tr("선택 해제"), command=self.clear_multi)
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    def move_note(self, n, nb):
        self.flush()
        try:
            new = self.store.move(n["path"], nb)
            self.fav_move(n["path"], new)
        except OSError as ex:
            return messagebox.showerror(APP, tr('노트를 옮기지 못했습니다.\n{0}').format(ex))
        if self.cur and self.cur["path"] == n["path"]:
            self.cur = None
        self.reload_notes()
        moved = next((x for x in self.all_notes if x["path"] == new), None)
        if moved and moved in self.notes:
            self.open_note(moved)

    def sort_by(self, mode):
        if self.sort == mode:
            self.asc = not self.asc
        else:
            self.sort, self.asc = mode, False
        self.refresh()
        st.write_config(window={**st.read_config().get("window", {}), "sort": self.sort, "asc": self.asc})

    def toggle_date(self):
        if self.date_row.winfo_ismapped():
            self.date_row.pack_forget()
        else:
            self.date_row.pack(fill="x", before=self.count, pady=(6, 0))
        self.b_date.set_on(self.date_row.winfo_ismapped())
