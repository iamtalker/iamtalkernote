"""도구 > 본문에 글자로 박힌 그림을 리소스 파일로 일괄 분리.
노트를 열 때 한 개씩 묻던 '그림을 리소스 폴더의 파일로 분리할까요?'(noteio.offer_split)를 전체 노트에 한 번에 적용한다.
각 노트는 저장 전 내용이 이전 버전(.history)에 남고, 수정 시각(updated)은 바꾸지 않는다."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import store as st  # noqa: E402


def scan_embedded(notes, progress=None, cancelled=lambda: False):
    """노트 목록 → [(노트, 그림 개수, 글자 수)] 글자 수가 큰 것부터. base64 그림이 없는 노트는 뺀다."""
    found = []
    total = len(notes)
    for i, n in enumerate(notes):
        if cancelled():
            return []
        if progress and i % 200 == 0:
            progress(i, total)
        try:
            with open(n["path"], "rb") as fh:
                text = st.decode(fh.read())
        except OSError:
            continue
        if "base64," not in text:
            continue
        count, size = st.embedded_images(text)
        if count:
            found.append((n, count, size))
    found.sort(key=lambda x: -x[2])
    return found


def convert_embedded(store, found, progress=None, cancelled=lambda: False):
    """scan_embedded 결과를 실제로 분리한다 → (바뀐 노트 수, 옮긴 그림 수, 실패 [(경로, 이유)])."""
    changed = moved_total = 0
    failed = []
    for i, (n, _count, _size) in enumerate(found):
        if cancelled():
            break
        if progress:
            progress(i, len(found))
        try:
            with open(n["path"], "rb") as fh:
                text = st.decode(fh.read())
            new, moved = store.extract_images(text, n["nb"])
            if moved and new != text:
                store.save(n["path"], new, versioned=True, force=True, touch=False, ev="image")
                changed += 1
                moved_total += moved
        except Exception as e:  # 한 노트가 실패해도 나머지는 계속한다
            failed.append((n["path"], str(e)))
    return changed, moved_total, failed


class EmbeddedMixin:
    # ------------------------------------------------------------ 도구: 글자로 박힌 그림 일괄 분리
    def show_embedded_images(self):
        """도구 > 본문의 긴 글자 그림을 리소스 파일로 일괄 분리: 먼저 찾고, 개수를 보여 준 뒤 확인을 받고 바꾼다"""
        self.scan_notes(tr("글자로 박힌 그림 찾기"), lambda notes, prog, cancel: scan_embedded(notes, prog, cancel), self.embedded_dialog)

    def embedded_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, tr("본문에 글자로 박힌 그림이 있는 노트가 없습니다."), parent=self.root)
        total_chars = sum(s for _, _, s in found)
        total_imgs = sum(c for _, c, _ in found)
        msg = tr("그림 {0}개가 글자로 박힌 노트가 {1}개 있습니다 (글자 {2:.1f}MB).\n\n그림을 리소스 폴더의 파일로 옮기고 노트를 고칩니다.\n바뀌기 전 내용은 노트 버전(.history)에 남고, 수정 시각은 그대로 둡니다.\n\n지금 바꿀까요?").format(
            total_imgs, len(found), total_chars / 1048576)
        if not messagebox.askyesno(APP, msg, parent=self.root):
            return
        self.flush()
        self.run_task(tr("그림 분리 중"), lambda prog, cancel: convert_embedded(self.store, found, prog, cancel), self.embedded_done)

    def embedded_done(self, result):
        changed, moved, failed = result
        text = tr("노트 {0}개의 그림 {1}개를 리소스 폴더로 옮겼습니다.").format(changed, moved)
        if failed:
            text += "\n\n" + tr("실패 {0}개:").format(len(failed)) + "\n" + "\n".join(f"{p}: {e}" for p, e in failed[:10])
        messagebox.showinfo(APP, text, parent=self.root)
        self.reload_notes(keep_scroll=True)

    # ------------------------------------------------------------ 도구: 중복 이미지 찾기 (쓰는 노트를 옆에 보여 준다)
    def show_duplicate_media(self):
        """도구 > 중복 이미지 찾기: 내용이 같은 그림 파일을 묶고, 각 그림을 가리키는 노트를 함께 보여 준다"""
        def work(notes, prog, cancel):
            groups = cleanup.duplicate_media(self.store, prog, cancel)
            if not groups:
                return [], {}
            wanted = {os.path.basename(p): None for g in groups for p in g}
            refs = {k: [] for k in wanted}
            for n in notes:
                if cancel():
                    return [], {}
                try:
                    with open(n["path"], "rb") as fh:
                        text = st.decode(fh.read())
                except OSError:
                    continue
                names = set(re.findall(r"\.resources/([^)\s\"'<>]+)", text))
                for name in names & set(refs):
                    refs[name].append(n)
            return groups, refs
        self.scan_notes(tr("중복 이미지 찾기"), work, self.duplicate_media_dialog)

    def duplicate_media_dialog(self, result):
        groups, refs = result
        if not groups:
            return messagebox.showinfo(APP, tr("내용이 같은 그림 파일이 없습니다."), parent=self.root)
        def mb(n):
            return f"{n / 1048576:,.1f}MB" if n >= 1048576 else f"{n / 1024:,.0f}KB"
        extra = sum(len(g) - 1 for g in groups)
        wasted = sum(os.path.getsize(g[0]) * (len(g) - 1) for g in groups)
        top = self.tool_window(tr("중복 이미지 — {0:,}묶음").format(len(groups)), "900x560", native=True)
        tk.Label(top, text=tr("내용이 같은 그림 {0:,}묶음 (남는 파일 {1:,}개, 약 {2}). 각 그림 아래에 그 그림을 쓰는 노트를 보여 줍니다. 노트 이름을 클릭하면 그 노트로 갑니다.").format(len(groups), extra, mb(wasted)),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10).pack(fill="x")
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", font=(self.ui, 10), exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        note_at = {}
        for g in groups:
            lb.insert("end", tr("── {0}개 · 각 {1}").format(len(g), mb(os.path.getsize(g[0]))))
            for p in g:
                name = os.path.basename(p)
                lb.insert("end", "  " + os.path.relpath(p, self.store.media_dir))
                users = refs.get(name, [])
                if not users:
                    lb.insert("end", "      " + tr("(쓰는 노트 없음)"))
                for n in users:
                    lb.insert("end", "      ↳ " + n["title"])
                    note_at[lb.size() - 1] = n["path"]
        def open_sel(e=None):
            sel = lb.curselection()
            if sel and sel[0] in note_at:
                self.goto_note(note_at[sel[0]])   # 노트 목록에서 그 노트를 선택해 보여 준다
        lb.bind("<ButtonRelease-1>", open_sel)   # 노트 줄을 클릭하면 그 노트로 간다
