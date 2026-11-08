"""노트를 열고 저장하는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import autotitle  # noqa: E402   (제목 없이 쓴 새 노트: 본문 첫 줄을 제목으로)
import pdflink  # noqa: E402   (본문이 pdf 링크 하나뿐인 노트는 pdf 뷰어로)


class NoteIOMixin:
    # ------------------------------------------------------------ 노트 열기·저장
    def set_text(self, text):
        self.loading = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.loading = False

    def open_doc(self, n, record=True):
        """가져온 문서(pdf·txt·mp3 …)를 읽기 전용으로 연다: 색인해 둔 글을 편집 칸에 보여 준다(Ctrl+F 로 문서 안에서 찾을 수 있다)"""
        self.flush()
        # '모든 파일' 목록에서는 노트에서 가져온 파일로 바로 이동할 수 있다.
        # 노트북을 바꿀 때처럼 기존 보기·미리보기를 정리하고 화면을 다시 붙여,
        # Markdown 렌더링 칸이 가져온 파일 미리보기 아래에 남지 않게 한다.
        self.close_note()
        self.root.update_idletasks()
        self.cur = n
        self.doc_open = True
        self.snap_done = False
        if record and not (self.hist and self.hpos >= 0 and self.hist[self.hpos] == n["path"]):
            del self.hist[self.hpos + 1:]
            self.hist.append(n["path"])
            self.hpos = len(self.hist) - 1
        self.show_empty(False)
        self.title_var.set(n["title"])
        self.update_star()
        self.title_entry.config(state="readonly")
        for b in self.mode_btns.values():   # 가져온 문서에는 원문·분할 보기가 없다
            b.enabled = False
            b.set_on(False)
        self.dirty = False
        self.show_doc(n, native=True)
        self.mark_selected()

    def doc_can_preview(self, n):
        return n["ext"] in PREVIEW_EXT and winpreview.available(n["ext"])

    def schedule_preview_fit(self):
        """일부 미리보기 처리기는 DoPreview 뒤늦게 창을 만들므로 본문 크기를 다시 맞춘다."""
        def fit():
            if self.pv_active:
                self.pv.resize(self.body.winfo_width(), self.body.winfo_height())
        for delay in (0, 100, 350):
            self.root.after(delay, fit)

    def show_doc(self, n, native):
        """가져온 문서를 보여 준다. native=True 이고 윈도에 그 형식의 미리보기 처리기가 있으면 그 프로그램(pdf → Edge, mp3 → Media Player …)이
        노트 화면 안에 직접 그리고, 아니면(또는 실패하면) 색인해 둔 글을 읽기 전용으로 보여 준다(Ctrl+F 로 찾을 수 있다)."""
        self.pv.unload()
        self.pv_active = False
        can = self.doc_can_preview(n)
        if native and can:
            # 원본 미리보기는 별도 창으로 그려진다. 이전에 보던 문서의
            # 편집·렌더링 글이 밑에 남으면 새 미리보기와 겹쳐 보일 수 있다.
            self.text.config(state="normal")
            self.set_text("")
            self.text.config(state="disabled")
            self.view.config(state="normal")
            self.view.delete("1.0", "end")
            self.view.config(state="disabled")
            self.apply_layout("pv")
            self.root.update_idletasks()
            self.pv_active = self.pv.show(self.pv_frame.winfo_id(), n["path"], self.body.winfo_width(), self.body.winfo_height())
            if self.pv_active:
                # IPreviewHandler creates a native child window during show(); re-raise
                # its host afterwards so sibling Tk panes cannot show around the edges.
                self.pv_frame.lift()
                self.root.after_idle(self.pv_frame.lift)
                # Match the resize sequence that occurs when the syntax sidebar is toggled.
                self.relayout()
                self.root.update_idletasks()
                self.schedule_preview_fit()
        if self.pv_active:
            self.hide_find(focus=False)
            self.status.config(text=tr('원본 미리보기 (윈도 기본 프로그램)   ·   {0}   ·   글로 바꾸면 Ctrl+F 로 찾을 수 있습니다').format(n['path']))
        else:
            self.apply_layout("edit")
            body = n.read()
            if not body.strip() and n["ext"] in docidx.TEXT_EXT:   # 문서 안 글 검색을 꺼 두면 색인에는 글이 없다: 글 파일은 파일에서 바로 읽어 보인다
                try:
                    body = docidx.extract(n["path"], n["ext"], os.path.getsize(n["path"]))[:1_000_000]
                except OSError:
                    body = ""
            if not body.strip():
                body = (tr("(이 파일에서 뽑은 글이 없습니다.)\n\n") if n["ext"] not in docidx.AUDIO_EXT else "") + tr("위치: ") + n["path"]
            if n.get("memo"):
                body = tr("[메모]\n") + n["memo"] + "\n\n" + "─" * 24 + "\n\n" + body
            n["body"] = body
            self.text.config(state="normal", wrap="word")
            self.set_text(body)
            self.text.config(state="disabled")
            self.text.yview_moveto(0)
            self.status.config(text=tr('가져온 파일 (읽기 전용)   ·   {0}   ·   더블클릭이나 우클릭 → 기본 프로그램으로 열기').format(n['path']))
            if self.findbar.winfo_ismapped():
                self.find_run()
        if can:
            if not self.doc_toggle.winfo_ismapped():
                self.doc_toggle.pack(side="right", padx=(8, 0), before=self.mode_seg if self.mode_seg.winfo_manager() else self.mode_anchor)
            self.doc_toggle.config(text=tr("뽑은 글로 보기") if self.pv_active else tr("원본으로 보기"))
        else:
            self.doc_toggle.pack_forget()
        if not self.memo_btn.winfo_ismapped():
            self.memo_btn.pack(side="right", padx=(8, 0), before=self.doc_toggle if self.doc_toggle.winfo_ismapped() else (self.mode_seg if self.mode_seg.winfo_manager() else self.mode_anchor))
        self.memo_btn.config(text=tr("메모 ●") if n.get("memo") else tr("메모"))
        self.update_status()

    def toggle_doc_view(self):
        if self.doc_open and self.cur:
            self.show_doc(self.cur, native=not self.pv_active)
        elif self.pdf_note and self.cur:   # pdf 링크 노트: pdf 뷰어 ↔ 노트 글
            if self.pv_active:
                self.pv.unload()
                self.pv_active = False
                self.apply_layout(self.mode)
                self.render()
                self.doc_toggle.config(text=tr("PDF 로 보기"))
                self.update_status()
            else:
                self.show_pdf_note(self.pdf_note)

    def try_pdf_note(self, n):
        """본문이 pdf 파일 링크 하나뿐인 노트면 pdf 뷰어(윈도 미리보기 처리기)로 보여 준다. 노트 글은 머리줄 단추로 오간다."""
        if n.get("trash") or not winpreview.available("pdf"):
            return
        path = pdflink.pdf_target(n["body"], n["path"])
        if path and self.cur is n:
            self.show_pdf_note(path)

    def show_pdf_note(self, path):
        self.apply_layout("pv")
        self.root.update_idletasks()
        self.pdf_note = path
        self.pv_active = self.pv.show(self.pv_frame.winfo_id(), path, self.body.winfo_width(), self.body.winfo_height())
        if not self.pv_active:
            self.pdf_note = None
            self.apply_layout(self.mode)
            return
        self.pv_frame.lift()
        self.root.after_idle(self.pv_frame.lift)
        self.relayout()
        self.root.update_idletasks()
        self.schedule_preview_fit()
        self.hide_find(focus=False)
        if not self.doc_toggle.winfo_ismapped():
            self.doc_toggle.pack(side="right", padx=(8, 0), before=self.mode_seg if self.mode_seg.winfo_manager() else self.mode_anchor)
        self.doc_toggle.config(text=tr("노트 글로 보기"))
        self.status.config(text=tr('PDF 미리보기 (윈도 기본 프로그램)   ·   {0}').format(path))

    def leave_pdf_note(self):
        if not self.pdf_note:
            return
        self.pdf_note = None
        self.pv.unload()
        self.pv_active = False
        self.doc_toggle.pack_forget()
        self.apply_layout(self.mode)

    def leave_doc(self):
        """가져온 문서를 보던 상태를 풀고 노트 편집 상태로 돌아간다"""
        if not self.doc_open:
            return
        self.doc_open = False
        self.pv.unload()
        self.pv_active = False
        self.doc_toggle.pack_forget()
        self.memo_btn.pack_forget()
        for k, b in self.mode_btns.items():
            b.enabled = True
            b.set_on(k == self.mode)
        self.text.config(state="normal")
        self.title_entry.config(state="normal")
        self.apply_layout(self.mode)
        self.hide_find(focus=False)

    def open_note(self, n, record=True):
        if isinstance(n, docidx.Doc):
            return self.open_doc(n, record)
        self.flush()
        self.leave_doc()
        self.leave_pdf_note()
        if self.cur is not None and self.cur is not n:
            self.hide_find(focus=False)   # 다른 노트로 가면 찾기 막대는 닫는다
        if self.cur is not None and self.cur is not n and not self.dirty:
            self.cur.pop("body", None)   # 연 적 있는 노트의 본문이 계속 쌓이지 않게
        self.cur = n
        if record and not (self.hist and self.hpos >= 0 and self.hist[self.hpos] == n["path"]):
            del self.hist[self.hpos + 1:]
            self.hist.append(n["path"])
            self.hpos = len(self.hist) - 1
        self.snap_done = False
        self.show_empty(False)
        # Reapply the selected layout before revealing the note area. If the
        # previous view left a stale pane arrangement, this keeps the source
        # editor from flashing while a rendered note (especially one with
        # images) is being opened.
        if self.is_outline_note() or self._outl_on:
            self._outl_path = None
        self.apply_layout(self.mode)
        if self.mode == "view":
            # Keep the source widget unmapped while replacing its contents;
            # Tk may process idle redraws during image sizing in render().
            self.edit_frame.grid_forget()
        self.title_var.set(n["title"])
        # 한 줄이 아주 긴 글(base64 그림 등)은 줄바꿈 계산이 수십 초 걸려서 줄바꿈을 끈다
        longest = max((len(x) for x in n["body"].split("\n")), default=0)
        self.text.config(wrap="none" if longest > 20000 else "word")
        self.text.config(state="normal")
        self.title_entry.config(state="normal")
        preview_first = self.mode == "view" and not self.is_outline_note()
        if preview_first:
            # Build the new preview before putting its source into the editor.
            # Image sizing can process Tk idle redraws during render(), so this
            # prevents the new Markdown from appearing even if the editor pane
            # is briefly exposed by the window system.
            self.render(source=n["body"])
        self.set_text(n["body"])
        self.text.yview_moveto(0)
        self.dirty = False
        self.update_status()
        if n.get("trash"):               # 휴지통의 노트: 읽기 전용(우클릭 → 복원 · 완전히 삭제)
            self.text.config(state="disabled")
            self.title_entry.config(state="readonly")
            self.status.config(text=tr("휴지통의 노트 — 읽기 전용입니다. 목록에서 우클릭 → 복원 · 완전히 삭제"))
        if not preview_first:
            self.render()
        self.mark_selected()
        self.try_pdf_note(n)
        count, size = st.embedded_images(n["body"])
        if count and size > 200_000 and n["path"] not in self.declined:
            self.root.after(150, lambda: self.offer_split(n, count, size))

    def offer_split(self, n, count, size):
        """본문에 통째로 박힌 그림을 _resources 파일로 분리할지 묻는다(분리해도 그림은 그대로)"""
        if self.cur is not n:
            return
        self.declined.add(n["path"])
        msg = (tr('이 노트에는 그림 {0}개({1:.1f}MB)가 글자로 본문에 박혀 있어 열 때 느립니다.\n\n그림을 리소스 폴더의 파일로 분리할까요?\n(그림은 그대로 보이고 노트는 작아집니다)').format(count, size / 1_000_000))
        if not messagebox.askyesno(APP, msg, parent=self.root):
            return
        body, moved = self.store.extract_images(self.text.get("1.0", "end-1c"), n["nb"])
        self.text.config(wrap="word")
        self.set_text(body)
        self.dirty = True
        self.flush()
        self.render()
        self.status.config(text=tr('그림 {0}개를 리소스 폴더로 옮겼습니다').format(moved))

    def go(self, step):
        """이동 > 뒤로 / 앞으로 (본 노트 기록)"""
        pos = self.hpos + step
        while 0 <= pos < len(self.hist):
            path = self.hist[pos]
            n = next((x for x in self.all_notes if x["path"] == path), None)
            if n:
                if n not in self.notes:
                    self.nb = ALL
                    self.reload_notes()
                    n = next((x for x in self.notes if x["path"] == path), None)
                self.hpos = pos
                return self.open_note(n, record=False)
            pos += step

    def close_note(self):
        self.leave_doc()
        self.leave_pdf_note()
        self.cur = None
        self.update_star()
        self.dirty = False
        self.show_empty(True)

    def on_modified(self, e=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self._typed_at = time.time()   # 한글 입력기가 확정해 넣은 글자도 '입력 중'(막대 고정)으로 친다
        if self.loading or not self.cur:
            return
        self.dirty = True
        self.find_later()   # 찾기 막대가 열려 있으면 바뀐 글에서 다시 찾는다
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(600, self.autosave)
        if self.mode != "edit":
            if self.render_job:
                self.root.after_cancel(self.render_job)
            self.render_job = self.root.after(200 if len(self.text.get("1.0", "end")) < 40000 else 700, self.render)

    def autosave(self):
        """타이머 저장: 쓰는 중에 제목이 바뀌지 않게 flush 와 달리 본문 첫 줄 제목을 만들지 않는다"""
        self._autosaving = True
        try:
            self.flush()
        finally:
            self._autosaving = False

    def auto_title(self, body):
        """제목을 안 쓴 새 노트를 떠날 때: 본문 첫 줄을 제목으로 쓴다(없으면 그대로)"""
        if not (self.cur and getattr(self, "fresh", None) == self.cur["path"]) or self.title_var.get().strip():
            return
        t = autotitle.title_from_body(body)
        if t:
            self.title_var.set(t)
            self.commit_title()

    def flush(self):
        if not getattr(self, "_autosaving", False):
            self.commit_title()
        self._flush_save()
        if not getattr(self, "_autosaving", False) and self.cur and not self.doc_open and getattr(self, "fresh", None) == self.cur["path"]:
            self.auto_title(self.text.get("1.0", "end-1c"))   # 노트를 떠날 때(타이머 저장이 아닐 때): 제목을 안 썼으면 본문 첫 줄을 제목으로

    def schedule_title_commit(self, *_):
        """제목 입력이 2초간 멈추면 저장한다. IME 조합 중에는 글자가 확정될 때까지 기다린다."""
        if self.title_save_job:
            self.root.after_cancel(self.title_save_job)
            self.title_save_job = None
        if not self.cur or self.doc_open or self.title_var.get().strip() == self.cur["title"]:
            return
        self.title_save_job = self.root.after(2000, self.commit_title_when_idle)

    def commit_title_when_idle(self):
        self.title_save_job = None
        if self.title_entry.focus_get() is self.title_entry and ime.composing():
            if not ime.complete():
                self.title_save_job = self.root.after(250, self.commit_title_when_idle)
                return
            self.title_save_job = self.root.after(50, self.commit_title_when_idle)
            return
        self.commit_title()

    def _flush_save(self):
        if self.cur and self.cur.get("trash"):
            self.dirty = False
            return
        if self._outl_on and self.cur and self.is_outline_note():
            self.ow.flush()                       # 아웃라이너에서 막 고친 글(0.35초 뒤에 넘기려던 것)을 노트에 먼저 넣는다
        if self.save_job:
            self.root.after_cancel(self.save_job)
            self.save_job = None
        if not (self.cur and self.dirty):
            return
        body = self.text.get("1.0", "end-1c")
        try:
            # 노트를 연 뒤 첫 저장은 간격과 상관없이 이전 내용을 버전으로 남긴다
            written = self.store.save(self.cur["path"], body, force=not self.snap_done)
        except OSError as ex:
            return self.status.config(text=tr("저장 실패: ") + str(ex))
        self.snap_done = True
        self.dirty = False
        old_tags = self.cur.get("tags", set())
        self.cur["body"] = written
        self.cur["mtime"] = time.time()
        self.cur["tags"] = note_tags(body)
        self.cur.pop("_hay", None)
        if self.cur["tags"] != old_tags:
            self.reload_tags()
        self.refresh(keep_page=True)
        self.update_status(tr("저장됨 ") + time.strftime("%H:%M:%S"))

    def update_status(self, extra=""):
        if self.cur and self.doc_open:   # 가져온 파일: 아랫줄 상태 글은 그대로 두고 태그만 갱신
            if not self.tag_edit:
                tags = sorted(self.cur.get("tags", ()))
                shown = "   ".join("# " + t for t in tags[:6]) + (f"   … +{len(tags) - 6}" if len(tags) > 6 else "")
                self.tag_labels.config(text=shown)
            return
        if self.cur:
            self.status.config(text=tr('{0}/{1}   ·   {2:,}자').format(self.nb_label(self.cur['nb']), os.path.basename(self.cur['path']), len(self.cur['body'])) + (f"   ·   {extra}" if extra else "") + "   ·")
            if not self.tag_edit:
                tags = sorted(self.cur.get("tags", ()))
                shown = "   ".join("# " + t for t in tags[:6]) + (f"   … +{len(tags) - 6}" if len(tags) > 6 else "")
                self.tag_labels.config(text=shown)

    def commit_title(self):
        if (self.cur and not self.doc_open and self.title_entry.focus_get() is self.title_entry
                and ime.composing()):
            if self.title_save_job:
                self.root.after_cancel(self.title_save_job)
            self.title_save_job = self.root.after(250, self.commit_title_when_idle)
            return
        if self.title_save_job:
            self.root.after_cancel(self.title_save_job)
            self.title_save_job = None
        if not self.cur or self.doc_open:
            return
        new = self.title_var.get().strip()
        if new == self.cur["title"]:
            return
        if not new and getattr(self, "fresh", None) == self.cur["path"]:
            return                                  # 새 노트는 제목을 비워 둘 수 있다(나갈 때 본문 첫 줄이 제목이 된다)
        if self.wiki_on() and new and wikilinks.taken(new, self.store.titles(wikilinks.space(self.cur["nb"]) if st.wiki_scoped() else None), own=self.store.key_of(self.cur["path"])):
            self.title_var.set(self.cur["title"])
            return messagebox.showinfo(APP, tr('"{0}" 제목의 노트가 이미 있습니다.\n위키 링크([[제목]])를 쓰는 동안은 같은 제목을 만들 수 없어서 제목을 바꾸지 않았습니다.\n(옵션 → 일반에서 위키 링크를 끄면 같은 제목도 쓸 수 있습니다)').format(new), parent=self.root)
        self._flush_save()
        try:
            title, path = self.store.rename(self.cur["path"], new)
            self.fav_move(self.cur["path"], path)   # 즐겨찾기가 풀리지 않게 새 경로로 옮긴다
        except OSError as ex:
            self.title_var.set(self.cur["title"])
            return messagebox.showerror(APP, tr('제목을 바꾸지 못했습니다.\n{0}').format(ex))
        if self.title_var.get() != title:
            self.title_var.set(title)
        if getattr(self, "fresh", None) == self.cur["path"]:
            self.fresh = None                       # 제목이 정해졌다
        old = self.cur["path"]
        self.cur["title"], self.cur["path"] = title, path
        self.cur.pop("_hay", None)
        self.hist = [path if p == old else p for p in self.hist]
        self.reload_notes()
        self.update_status()

    def new_note(self):
        self.flush()
        self.q.set("")
        self.d_from.set("")
        self.d_to.set("")
        self.tag, self.tag_none, self.adv_conditions = None, False, []
        nb = self.md_nb()
        try:
            made = self.store.create_note(nb)
        except OSError as ex:
            return messagebox.showerror(APP, tr('노트를 만들지 못했습니다.\n{0}').format(ex))
        self.close_note()
        self.reload_notes()
        n = next((x for x in self.notes if x["path"] == made["path"]), None)
        if n:
            self.open_note(n)
            if not body_after_fm(n["body"]).strip():
                self.set_text("")  # 새 노트의 날짜 머리말은 파일에 보관하고 입력은 빈 본문에서 시작한다.
                self.render()
            self.fresh = made["path"]            # 제목을 아직 안 쓴 새 노트(파일 이름만 임시로 '제목 없음')
            self.title_var.set("")
            self.text.focus_set()                # 바로 본문부터 쓴다(제목은 위 칸에서 나중에도 쓸 수 있다)

    def delete_note(self):
        if self.doc_open:
            return messagebox.showinfo(APP, tr("가져온 파일은 여기서 지우지 않습니다(원본 파일은 그대로 둡니다).\n목록에서 빼려면 노트북 칸의 가져온 폴더를 우클릭하세요."), parent=self.root)
        if not self.cur or not messagebox.askyesno(APP, tr('이 노트를 휴지통으로 보낼까요?\n({0}일 동안 보관하며 파일 → 휴지통에서 복원할 수 있습니다)').format(self.store.trash_days), parent=self.root):
            return
        if self.save_job:
            self.root.after_cancel(self.save_job)
            self.save_job = None
        path = self.cur["path"]
        self.dirty = False
        try:
            self.store.delete_note(path)
        except OSError as ex:
            return messagebox.showerror(APP, str(ex))
        self.hist = [p for p in self.hist if p != path]
        self.hpos = min(self.hpos, len(self.hist) - 1)
        self.close_note()
        self.reload_notes(keep_scroll=True)

    def set_mode(self, m):
        self.mode = m
        self.v_mode.set(m)
        for k, b in self.mode_btns.items():
            b.set_on(k == m)
        if not self.doc_open:
            self.apply_layout(m)
        self.save_view()
        self.render()
        if self.findbar.winfo_ismapped():
            self.root.after(60, self.find_run)

    def is_outline_note(self):
        return self.feat["outl"] and bool(self.cur) and not self.doc_open and (self.cur["nb"] == OUTL or self.cur["nb"].startswith(OUTL + "/"))

    def show_outline_layout(self, on):
        """아웃라이너 폴더의 노트는 편집 칸·렌더링 칸 대신 아웃라이너 편집기 한 칸을 쓴다"""
        if on:
            self.mode_seg.pack_forget()                      # 아웃라이너 노트에는 원문·분할·렌더링 보기가 없다
            self.pv.unload()
            self.pv_active = False
            self.pv_frame.lower()
            self.edit_frame.grid_forget()
            self.view_frame.grid(row=0, column=0, sticky="nsew")
            self.body.grid_columnconfigure(0, weight=1, uniform="")
            self.body.grid_columnconfigure(1, weight=0, uniform="")
            if not self._outl_on:
                self.box2.pack_forget()
                self.ow.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        elif self._outl_on:
            self.ow.pack_forget()
            self.mode_seg.pack(side="right", padx=(8, 0), after=self.mode_anchor)
            self.box2.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._outl_on = on

    def split_front(self, text):
        """맨 위 머리말(--- … ---)과 나머지"""
        m = FRONT.match(text)
        return (text[:m.end()], text[m.end():]) if m else ("", text)

    def render_outline(self):
        front, body = self.split_front(self.text.get("1.0", "end-1c"))
        if self._outl_path != self.cur["path"]:
            self._outl_path = self.cur["path"]
            self.ow.load(body)
        else:
            self.ow.reload_if_changed(body)

    def outline_changed(self, body):
        """아웃라이너 편집기가 바꾼 원문을 노트에 넣는다(되돌리기·저장은 평소 노트와 같은 길)"""
        if not self.cur or not self.is_outline_note():
            return
        old = self.text.get("1.0", "end-1c")
        front, rest = self.split_front(old)
        if not rest.strip() and body.strip() in ("", "-"):
            return                                           # 빈 노트에 빈 항목 하나는 글이 아니다
        new = front + body
        if new != old:
            self.apply_text_change(old, new)
            self.dirty = True                                # <<Modified>> 는 한 박자 늦게 오므로 바로 표시한다(그 사이 노트를 옮겨도 저장됨)
            if not self.save_job:
                self.save_job = self.root.after(600, self.flush)

    def apply_layout(self, m):
        on = self.is_outline_note()
        if m != "pv" and (on or self._outl_on):
            self.show_outline_layout(on)
            if on:
                return
        if m != "pv":
            self.pv.unload()
            self.pv_active = False
            self.pv_frame.lower()
        for w in (self.edit_frame, self.view_frame):
            w.grid_forget()
        if m == "pv":   # 윈도 미리보기 처리기가 한 칸 전체를 쓴다
            self.pv_frame.lift()
            self.body.grid_columnconfigure(0, weight=1, uniform="")
            self.body.grid_columnconfigure(1, weight=0, uniform="")
            return
        if m in ("edit", "split"):
            self.edit_frame.grid(row=0, column=0, sticky="nsew")
        if m in ("view", "split"):
            self.view_frame.grid(row=0, column=1 if m == "split" else 0, sticky="nsew")
        two = m == "split"
        self.body.grid_columnconfigure(0, weight=1, uniform="pane" if two else "")
        self.body.grid_columnconfigure(1, weight=1 if two else 0, uniform="pane" if two else "")

    def cycle_mode(self):
        if self.doc_open:   # 가져온 문서에는 원문·분할 보기가 없다
            return
        self.set_mode({"edit": "split", "split": "view", "view": "edit"}[self.mode])

    def render(self, source=None):
        self.render_job = None
        if self.cur and self.is_outline_note():
            return self.render_outline()
        if not self.cur or self.mode == "edit" or self.doc_open:
            return
        title = self.title_var.get()
        try:
            # 클리퍼가 맨 위에 적는 '원본: <주소>' 줄은 렌더링 화면에서만 숨긴다(문서 정보의 URL 은 이 줄에서 읽는다)
            raw = self.text.get("1.0", "end-1c") if source is None else source
            src = SOURCE_LINE.sub("", raw, count=1)
            doc = wikiconv.parse(self.expand_embeds(src), bulk.SYNTAX[FMT], title)
            segs = preview.layout(doc, **self.table_kw())
        except Exception as ex:  # noqa: BLE001  (읽기 도구가 못 읽은 글도 편집은 계속할 수 있게)
            return self.status.config(text=tr("렌더링 오류: ") + str(ex))
        # 그림 변환이 아직 끝나지 않았으면 그리지 않고 기다린다. 글자 칩으로 한 번 그린 뒤 그림으로 또 바꾸면
        # 화면이 두 번 뒤바뀌어 번쩍이기 때문이다. 너무 오래 기다리면(1.5초) 그냥 그린다.
        pending = any(e and e[0] == "img" and self.img_pending(e) for _, _, e in segs)
        now = time.monotonic()
        if pending:
            since = getattr(self, "_img_hold_since", None)
            if since is None:
                self._img_hold_since = since = now
            if now - since < 1.5:
                return
        self._img_hold_since = None
        self.draw_view(segs)

    def img_pending(self, extra):
        """이 그림이 아직 변환 중인지(변환을 시작하지 않았으면 지금 시작한다)."""
        src = extra[1].strip()
        if src[:5].lower() == "data:" or re.match(r"(?i)^https?://", src):
            return False
        path = self.find_local_image(src)
        if not path or ed.sniff_image(path) == "gif":
            return False
        width = extra[3] if len(extra) > 3 else 0
        avail = self.img_avail()
        target = min(width, avail) if width else avail
        try:
            st = os.stat(path)
        except OSError:
            return False
        key = f"local:{os.path.normcase(os.path.abspath(path))}:{st.st_mtime_ns}:{st.st_size}:{target}"
        state = self.imgs.get(key)
        if state is None:
            self.local_image_photo(path, target)   # 변환을 시작한다(끝나면 poll_images 가 다시 그린다)
            return True
        return state[0] == "pending"
