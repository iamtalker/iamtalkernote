"""가져온 폴더(노트 폴더 밖의 pdf·txt·mp3 …)를 훑고 색인하는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음): 가져온 폴더 추가·빼기, 뒤에서 자동 읽기, 색인 진행 표시."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class DocFoldersMixin:
    # ------------------------------------------------------------ 가져온 폴더 (노트 폴더 밖의 pdf·txt·mp3 …)
    def after_docs_changed(self):
        """색인이 바뀐 뒤: 노트북 칸의 개수를 새로 쓰고, 가져온 폴더를 보고 있으면 목록도 새로"""
        self.update_content_check()
        self.reload_notebooks()
        if self.nb.startswith("@doc") or self.scope_all():
            self.reload_notes(keep_scroll=True)

    def scan_docs(self, only=None, quiet=False):
        """가져온 폴더를 훑어 새로 생기거나 바뀐 파일만 읽는다(진행 창, 취소 가능). 파일이 많으면 처음 한 번은 오래 걸린다"""
        if not self.docs.folders():
            return
        self.doc_scan_last = None

        def work(prog, cancel):
            def update(d, total, phase=None):
                self.doc_scan_progress = {"done": d, "total": total, "phase": phase}
                prog(d, total, phase)
            try:
                return self.docs.scan(update, cancel, only)
            finally:
                self.doc_scan_progress = None

        def done(res):
            read, gone, total = res
            self.doc_scan_last = {"read": read, "removed": gone, "total": total}
            self.after_docs_changed()
            self.status.config(text=tr('가져온 폴더: 파일 {0:,}개 (새로 읽은 것 {1:,}, 사라진 것 {2:,})').format(total, read, gone))
        self.doc_scan_progress = {"done": 0, "total": 0, "phase": None}
        self.run_task(tr("가져온 폴더 읽는 중"), work, done,
                      text=tr("가져온 폴더의 문서를 읽는 중… (처음 한 번은 오래 걸립니다)"))

    def auto_scan_docs(self):
        """조용히(창 없이 뒤에서) 가져온 폴더에서 바뀐 파일만 다시 읽는다. 시작하고 20초 뒤에 한 번, 그 뒤로는 앱을 열어 두는 동안 5분마다 되풀이"""
        self.root.after(DOC_RESCAN_SECONDS * 1000, self.auto_scan_docs)
        self.rescan_docs_bg()

    def rescan_docs_bg(self):
        """조용히(창 없이 뒤에서) 가져온 폴더에서 바뀐 파일만 다시 읽는다(주기적 자동 읽기와 새로 고침이 함께 쓴다)"""
        if self.doc_scanning or not self.docs.folders():
            return
        self.doc_scanning = True
        self.doc_scan_last = None
        q = queue.Queue()
        prog = {"v": None}   # (읽은 수, 읽을 수, 지금 읽는 파일) — 뒤에서 읽는 동안 아래 상태 줄에 보인다
        self.doc_scan_progress = {"done": 0, "total": 0, "phase": None}

        def job():
            try:
                def update(d, total, phase=None):
                    prog.update(v=(d, total, phase))
                    self.doc_scan_progress = {"done": d, "total": total, "phase": phase}
                q.put(("ok", self.docs.scan(update)))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=job, daemon=True).start()

        def poll():
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                v = prog["v"]
                if v and v[1]:
                    self.status.config(text=tr('가져온 폴더 문서 읽는 중… {0:,} / {1:,}   {2}').format(v[0], v[1], (v[2] or "").replace("읽는 중 — ", "").strip()))
                return self.root.after(1000, poll)
            self.doc_scanning = False
            self.doc_scan_progress = None
            if kind == "ok":
                read, gone, total = val
                self.doc_scan_last = {"read": read, "removed": gone, "total": total}
            if prog["v"]:   # 진행 글을 지우고 원래 상태 줄로 되돌린다(열린 노트가 없으면 update_status 가 아무것도 안 하니 먼저 비운다)
                self.status.config(text="")
                try:
                    self.update_status()
                except Exception:  # noqa: BLE001
                    pass
            if kind == "ok" and (val[0] or val[1]):
                self.after_docs_changed()
        poll()

    def remove_doc_folder(self, fid):
        f = next((f for f in self.docs.folders() if f["id"] == fid), None)
        if not f or not messagebox.askyesno(APP, tr('「{0}」을(를) 가져온 폴더 목록에서 뺄까요?\n(원본 파일과 태그·메모는 유지합니다. 색인은 3일 뒤 삭제하며, 그 안에 다시 넣으면 재사용합니다)').format(f['path']), parent=self.root):
            return
        self.docs.remove_folder(fid)
        if self.nb.startswith("@doc:") and self.doc_key_parts(self.nb)[0] == fid:
            self.close_note()
            self.nb = "@docs"
        self.after_docs_changed()
