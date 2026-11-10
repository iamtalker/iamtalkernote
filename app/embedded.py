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
            # 아무 노트도 쓰지 않는 파일(휴지통 노트만 쓰던 파일 포함)은 중복 대상이 아니다 → 안 쓰는 미디어 정리 대상
            groups = [[p for p in g if refs.get(os.path.basename(p))] for g in groups]
            groups = [g for g in groups if len(g) > 1]
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
        top = self.tool_window(tr("중복 이미지 — {0:,}묶음").format(len(groups)), "900x580", native=True)
        head = tk.Frame(top, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(head, text=tr("내용이 같은 그림 {0:,}묶음 · 줄이면 남는 파일 {1:,}개 (약 {2})").format(len(groups), extra, mb(wasted)),
                 bg=C["bg"], fg=C["text"], font=(self.ui, 10), anchor="w").pack(side="left")
        Btn(head, tr("그림만 있는 노트 정리…"), self.image_only_cleanup, pady=4).pack(side="right")
        tk.Label(top, text=tr("▸를 누르면 그 그림을 쓰는 노트가 펼쳐집니다. 노트 이름을 누르면 그 노트로 갑니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16).pack(fill="x", pady=(0, 6))
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        tree = ttk.Treeview(wrap, show="tree", selectmode="none")
        tree.column("#0", width=840, stretch=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        note_at = {}
        for gi, g in enumerate(groups):
            head_iid = f"g{gi}"
            tree.insert("", "end", iid=head_iid, text=tr("[같은 그림 {0}개] {1} (각 {2})").format(len(g), os.path.basename(g[0]), mb(os.path.getsize(g[0]))))
            for pi, p in enumerate(g):
                name = os.path.basename(p)
                users = refs.get(name, [])
                file_iid = f"f{gi}_{pi}"
                tree.insert(head_iid, "end", iid=file_iid, text=f"{os.path.relpath(p, self.store.media_dir)}   ({tr('쓰는 노트 {0}개').format(len(users))})")
                if not users:
                    tree.insert(file_iid, "end", text="    " + tr("(쓰는 노트 없음)"))
                for ui, n in enumerate(users):
                    iid = f"u{gi}_{pi}_{ui}"
                    tree.insert(file_iid, "end", iid=iid, text=f"    ↳ {n['title']}")
                    note_at[iid] = n["path"]
        def on_click(e):
            if tree.identify_element(e.x, e.y) == "Treeitem.indicator":
                return
            row = tree.identify_row(e.y)
            if row in note_at:
                self.goto_note(note_at[row])
                top.lift()
        tree.bind("<ButtonRelease-1>", on_click)

        Btn(top, tr("그림만 있는 노트 정리…"), self.image_only_cleanup, pady=5).pack(side="bottom", anchor="e", padx=16, pady=(0, 12))

    # ------------------------------------------------------------ 중복 이미지 창: 그림만 있는 노트 정리
    def image_only_cleanup(self):
        def work(notes, prog, cancel):
            return cleanup.image_only_groups(self.store, notes, prog, cancel)
        self.scan_notes(tr("그림만 있는 노트 찾기"), work, self.image_only_dialog)

    def image_only_dialog(self, groups):
        if not groups:
            return messagebox.showinfo(APP, tr("그림만 있고 그림이 같은 노트가 없습니다."), parent=self.root)
        top = self.tool_window(tr("그림만 있는 노트 정리 — {0:,}묶음").format(len(groups)), "880x620", native=True)
        tk.Label(top, text=tr("같은 그림을 쓰는 노트 묶음입니다. ☐를 눌러 처리할 묶음을 ☑로 고르세요. ▸/▾를 누르면 펼치고 접습니다. 묶음마다 가장 먼저 만든 노트([남김])는 남고, [휴지통] 노트는 휴지통으로 갑니다. 노트 이름을 누르면 그 노트로 갑니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10, wraplength=840).pack(fill="x")
        chosen = set()          # 처음에는 모두 해제
        expanded = set(range(len(groups)))   # 처음에는 모두 펼침
        status = tk.Label(top, text="", bg=C["bg"], fg=C["text"], font=(self.ui, 10), anchor="w", padx=16)
        status.pack(fill="x")
        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tree = ttk.Treeview(wrap, columns=("check", "title"), show="headings", selectmode="none")
        tree.heading("check", text=tr("선택"), anchor="center")
        tree.heading("title", text=tr("묶음 / 노트"), anchor="w")
        tree.column("check", width=70, anchor="center", stretch=False)
        tree.column("title", width=660, stretch=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        note_at = {}

        def render():
            tree.delete(*tree.get_children())
            note_at.clear()
            for gi, g in enumerate(groups):
                mark = "▾" if gi in expanded else "▸"
                tree.insert("", "end", iid=f"g{gi}", values=("☑" if gi in chosen else "☐",
                            f"{mark} [{tr('남김')}] {g[0]['title']}   ({tr('묶음 {0:,}개 중 1개').format(len(g))})"))
                note_at[f"g{gi}"] = None
                if gi in expanded:
                    for ni, n in enumerate(g[1:], 1):
                        iid = f"n{gi}_{ni}"
                        tree.insert("", "end", iid=iid, values=("", f"        [{tr('휴지통')}] {n['title']}"))
                        note_at[iid] = n["path"]
            drop_n = sum(len(groups[i]) - 1 for i in chosen)
            status.config(text=tr("선택한 묶음 {0:,}개 · 휴지통으로 갈 노트 {1:,}개").format(len(chosen), drop_n))

        def on_click(e):
            row = tree.identify_row(e.y)
            if not row:
                return
            col = tree.identify_column(e.x)
            if row.startswith("g"):
                gi = int(row[1:])
                if col == "#1":          # 체크 칸: 묶음 선택
                    chosen.symmetric_difference_update({gi})
                    render()
                elif col == "#2":        # 제목 칸: 펼치기·접기
                    expanded.symmetric_difference_update({gi})
                    render()
                return
            if row in note_at and note_at[row]:   # 노트 줄: 그 노트로 가고 이 창은 앞에 둔다
                self.goto_note(note_at[row])
                top.lift()
        tree.bind("<ButtonRelease-1>", on_click)
        render()

        def go():
            drop = [n["path"] for gi in sorted(chosen) for n in groups[gi][1:]]
            if not drop:
                return messagebox.showinfo(APP, tr("선택한 묶음이 없습니다."), parent=top)
            if not messagebox.askyesno(APP, tr("선택한 묶음에서 휴지통으로 {0:,}개 노트를 보냅니다. 진행할까요?").format(len(drop)), parent=top):
                return
            top.destroy()
            self.trash_notes(drop)
        Btn(bar, tr("선택한 묶음 휴지통으로"), go, pady=5).pack(side="right")
        Btn(bar, tr("취소"), top.destroy, pady=5).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------ 도구: 본문이 빈 옛 스크랩 다시 스크랩하기
    def show_empty_scraps(self):
        """도구 > 빈 옛 스크랩 찾기: 출처 주소는 있는데 본문이 없는 노트를 보여 주고, 주소를 브라우저에서 다시 스크랩할 수 있게 한다"""
        self.scan_notes(tr("빈 스크랩 다시 받기"), lambda notes, prog, cancel: cleanup.empty_scraps(notes, prog, cancel), self.empty_scraps_dialog)

    def empty_scraps_dialog(self, result):
        empties, repaired = result
        if not empties:
            return messagebox.showinfo(APP, tr("본문이 빈 옛 스크랩이 없습니다."), parent=self.root)
        top = self.tool_window(tr("빈 스크랩 다시 받기 — {0:,}개").format(len(empties)), "860x560", native=True)
        tk.Label(top, text=tr("출처 주소는 있는데 본문이 없는 노트 {0:,}개입니다. '다음 10개 열기'로 브라우저에서 열어 조플린 클리퍼로 다시 스크랩하세요. 같은 주소로 내용이 채워진 노트가 생기면 '다시 채워진 빈 노트 정리'로 옛 빈 노트를 휴지통에 보냅니다.").format(len(empties)),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10, wraplength=800).pack(fill="x")
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", font=(self.ui, 10), exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        for n, url in empties:
            lb.insert("end", f"{n['title'][:50]}   {url[:70]}")
        state = {"next": 0}
        def open_next():
            import webbrowser
            batch = empties[state["next"]:state["next"] + 10]
            for _n, url in batch:
                webbrowser.open(url, new=2)
            state["next"] += len(batch)
            if not batch:
                messagebox.showinfo(APP, tr("모든 주소를 열었습니다."), parent=top)
        def clean_repaired():
            if not repaired:
                return messagebox.showinfo(APP, tr("다시 채워진 빈 노트가 없습니다."), parent=top)
            if not messagebox.askyesno(APP, tr("같은 주소로 내용이 채워진 옛 빈 노트 {0:,}개를 휴지통으로 보냅니다.\n(휴지통에서 복원할 수 있습니다.) 진행할까요?").format(len(repaired)), parent=top):
                return
            self.trash_notes([n["path"] for n in repaired])
        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=12)
        Btn(bar, tr("다음 10개 열기"), open_next, pady=5).pack(side="left")
        Btn(bar, tr("다시 채워진 빈 노트 정리…"), clean_repaired, pady=5).pack(side="right")

