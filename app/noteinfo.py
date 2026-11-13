"""노트 속성(조플린의 ⓘ 정보 창)을 다루는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class NoteInfoMixin:
    # ------------------------------------------------------------ 노트 속성 (조플린의 ⓘ)
    def apply_body(self, body):
        """본문을 통째로 바꾸고(복원 등) 저장한다. 이전 내용은 호출하는 쪽에서 버전으로 남긴 뒤다."""
        n = self.cur
        self.set_text(body)
        self.store.save(n["path"], body, versioned=False)
        self.dirty = False
        n["body"], n["mtime"], n["tags"] = body, time.time(), note_tags(body)
        n.pop("_hay", None)
        self.reload_tags()
        self.refresh(keep_page=True)
        self.render()
        self.update_status(tr("복원됨 ") + time.strftime("%H:%M:%S"))

    def rebuild_ui(self):
        """색을 바꾼 뒤 화면을 다시 만든다. 열어 둔 노트·검색어·보기 설정은 그대로 둔다."""
        self.flush()
        cur_path = self.cur["path"] if self.cur else None
        q, d1, d2 = self.q.get(), self.d_from.get(), self.d_to.get()
        widths = dict(self.widths)
        for job in (self.render_job, self.search_job):
            if job:
                self.root.after_cancel(job)
        self.render_job = self.search_job = None
        self.cur = None
        self.root.configure(bg=C["bg"])
        self.pane.destroy()
        self.style_ttk()
        self.make_fonts()
        self.build()
        self.widths.update(widths)
        self.bind_keys()
        self.q.set(q)
        self.d_from.set(d1)
        self.d_to.set(d2)
        self.reload_notes()
        self.set_mode(self.mode)
        self.relayout()
        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
        if n:
            self.open_note(n, record=False)

    def set_language(self, code):
        """Language 메뉴: 언어를 바꾸고 화면(메뉴줄 포함)을 다시 그린다"""
        if code == i18n.lang():
            return
        i18n.set_lang(code)
        st.write_config(lang=code)
        self.build_menu()
        self.rebuild_ui()

    def set_theme(self, name, custom="keep"):
        """name 을 쓴다. 내 테마의 색(custom = {bg, accent})을 같이 바꿀 수 있다(주지 않으면 저장돼 있던 색)"""
        old = migrate_theme(st.read_config().get("theme", {}))
        cus = old["custom"] if custom == "keep" else custom
        st.write_config(theme={"name": name, "custom": cus})
        apply_theme(name, cus)
        self.rebuild_ui()
        self.show_options("theme")
