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
                return [], {}, []
            media_re = re.escape(os.path.basename(self.store.media_dir)) + r"/([^)\s\"'<>]+)"   # 리소스 폴더 이름(.resources · _resources) 뒤의 파일 이름
            wanted = {os.path.basename(p): None for g in groups for p in g}
            refs = {k: [] for k in wanted}
            for n in notes:
                if cancel():
                    return [], {}, []
                try:
                    with open(n["path"], "rb") as fh:
                        text = st.decode(fh.read())
                except OSError:
                    continue
                names = set(re.findall(media_re, text))
                for name in names & set(refs):
                    refs[name].append(n)
            # 아무 노트도 쓰지 않는 파일(휴지통 노트만 쓰던 파일 포함)은 중복 대상이 아니다 → 안 쓰는 미디어 정리 대상
            groups = [[p for p in g if refs.get(os.path.basename(p))] for g in groups]
            groups = [g for g in groups if len(g) > 1]
            return groups, refs, notes
        self.scan_notes(tr("중복 이미지 찾기"), work, self.duplicate_media_dialog)

    def duplicate_media_dialog(self, result):
        groups, refs, notes = result
        if not groups:
            return messagebox.showinfo(APP, tr("내용이 같은 그림 파일이 없습니다."), parent=self.root)
        def mb(n):
            return f"{n / 1048576:,.1f}MB" if n >= 1048576 else f"{n / 1024:,.0f}KB"
        extra = sum(len(g) - 1 for g in groups)
        wasted = sum(os.path.getsize(g[0]) * (len(g) - 1) for g in groups)
        top = self.tool_window(tr("중복 이미지 — {0:,}묶음").format(len(groups)), "1000x620", native=True)
        head = tk.Frame(top, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(head, text=tr("내용이 같은 그림 {0:,}묶음 · 줄이면 남는 파일 {1:,}개 (약 {2}) · 줄일 용량이 큰 묶음부터").format(len(groups), extra, mb(wasted)),
                 bg=C["bg"], fg=C["text"], font=(self.ui, 10), anchor="w").pack(side="left")
        tk.Label(top, text=tr("그림을 누르면 오른쪽에 미리 봅니다. ▸를 누르면 그 그림을 쓰는 노트가 펼쳐지고, 노트 이름을 누르면 그 노트로 갑니다. 합치면 묶음마다 파일 하나만 남기고 노트의 링크를 그 파일로 고친 뒤, 안 쓰게 된 나머지 파일은 휴지통으로 보냅니다(쓰는 노트가 가장 많은 파일을 남깁니다)."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=960, padx=16).pack(fill="x", pady=(0, 6))
        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        side = tk.Frame(wrap, bg=C["panel"], width=320)   # 미리보기
        side.pack(side="right", fill="y", padx=(10, 0))
        side.pack_propagate(False)
        preview = tk.Label(side, bg=C["panel"], fg=C["muted"], font=(self.ui, 9), wraplength=300, justify="center")
        preview.pack(fill="both", expand=True, padx=8, pady=8)
        tree = ttk.Treeview(wrap, show="tree", selectmode="browse")
        tree.column("#0", width=600, stretch=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        note_at, file_at, shown = {}, {}, {}
        for gi, g in enumerate(groups):
            head_iid = f"g{gi}"
            tree.insert("", "end", iid=head_iid, text=tr("[같은 그림 {0}개] {1} (각 {2} · 줄이면 {3})").format(
                len(g), os.path.basename(g[0]), mb(os.path.getsize(g[0])), mb(os.path.getsize(g[0]) * (len(g) - 1))))
            for pi, p in enumerate(g):
                name = os.path.basename(p)
                users = refs.get(name, [])
                file_iid = f"f{gi}_{pi}"
                file_at[file_iid] = p
                tree.insert(head_iid, "end", iid=file_iid, text=f"{os.path.relpath(p, self.store.media_dir)}   ({tr('쓰는 노트 {0}개').format(len(users))})")
                if not users:
                    tree.insert(file_iid, "end", text="    " + tr("(쓰는 노트 없음)"))
                for ui, n in enumerate(users):
                    iid = f"u{gi}_{pi}_{ui}"
                    tree.insert(file_iid, "end", iid=iid, text=f"    ↳ {n['title']}")
                    note_at[iid] = n["path"]

        def show_preview(path):
            """고른 그림을 오른쪽에 보인다(그림이 아니거나 못 읽으면 이름만)"""
            shown.pop("img", None)
            try:
                from PIL import Image, ImageTk
                with Image.open(path) as im:
                    size = im.size
                    im.seek(0)
                    frame = im.convert("RGBA")
                frame.thumbnail((300, 360))
                shown["img"] = ImageTk.PhotoImage(frame, master=top)
                preview.config(image=shown["img"], text=f"{os.path.basename(path)}\n{size[0]}×{size[1]} · {mb(os.path.getsize(path))}", compound="top")
            except Exception:  # noqa: BLE001  (동영상·깨진 파일 등)
                preview.config(image="", text=f"{os.path.basename(path)}\n{tr('미리 볼 수 없는 파일입니다')}")

        def group_of(iid):
            while iid and not iid.startswith("g"):
                iid = tree.parent(iid)
            return int(iid[1:]) if iid else None

        def on_select(_e=None):
            sel = tree.selection()
            if not sel:
                return
            iid = sel[0]
            if iid.startswith("g"):
                show_preview(groups[int(iid[1:])][0])
            elif iid in file_at:
                show_preview(file_at[iid])
        tree.bind("<<TreeviewSelect>>", on_select)

        def on_click(e):
            if tree.identify_element(e.x, e.y) == "Treeitem.indicator":
                return
            row = tree.identify_row(e.y)
            if row in note_at:
                self.goto_note(note_at[row])
                top.lift()
        tree.bind("<ButtonRelease-1>", on_click)

        def merge(which, label):
            todo = [groups[i] for i in which]
            fix = 0
            for g in todo:
                names = [os.path.basename(q) for q in g]
                keep = cleanup.keep_name(names, refs)
                fix += sum(len(refs.get(n, [])) for n in names if n != keep)
            if not messagebox.askyesno(APP, tr("{0}: 그림 {1:,}묶음을 한 파일로 합치고, 노트 {2:,}곳의 링크를 고친 뒤 안 쓰게 된 나머지 파일을 휴지통으로 보냅니다.\n바뀌기 전 노트 내용은 노트 버전에 남고 수정 시각은 그대로입니다. 보낸 파일은 {3}일 동안 휴지통에서 복원할 수 있습니다.\n\n진행할까요?").format(label, len(todo), fix, self.store.trash_days), parent=top):
                return
            top.destroy()
            self.flush()
            self.run_task(tr("그림 합치는 중"), lambda prog, cancel: cleanup.merge_and_remove(self.store, todo, refs, notes, prog, cancel),
                          self.merge_media_done, text=tr("노트의 그림 링크를 고치는 중…"))

        def merge_selected():
            sel = tree.selection()
            gi = group_of(sel[0]) if sel else None
            if gi is None:
                return messagebox.showinfo(APP, tr("합칠 묶음을 먼저 고르세요."), parent=top)
            merge([gi], tr("이 묶음"))
        Btn(bar, tr("모두 합치기"), lambda: merge(range(len(groups)), tr("모든 묶음")), pady=5).pack(side="right")
        Btn(bar, tr("고른 묶음 합치기"), merge_selected, pady=5).pack(side="right", padx=(0, 8))
        Btn(bar, tr("그림만 있는 노트 정리…"), self.image_only_cleanup, pady=5).pack(side="left")
        first = tree.get_children()
        if first:
            tree.selection_set(first[0])

    def merge_media_done(self, result):
        changed, links, merged, failed, trashed, left = result
        text = tr("노트 {0:,}개의 링크 {1:,}곳을 고치고, 중복 파일 {2:,}개를 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)").format(changed, links, trashed)
        if left:
            text += "\n\n" + tr("{0:,}개 파일은 아직 다른 곳에서 쓰고 있어 그대로 두었습니다. (휴지통 노트의 링크나 인코딩된 링크 등)").format(left)
        if failed:
            text += "\n\n" + tr("실패 {0}개:").format(len(failed)) + "\n" + "\n".join(f"{p}: {e}" for p, e in failed[:10])
        self.reload_notes(keep_scroll=True)
        messagebox.showinfo(APP, text, parent=self.root)

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
        tk.Label(top, text=tr("출처 주소는 있는데 본문이 없는 노트 {0:,}개입니다. 다시 받을 필요가 없으면 '빈 노트 모두 휴지통으로'로 한 번에 정리하세요. 골라서 받으려면 먼저 '주소 확인 · 죽은 글 정리'로 없어진 웹페이지의 빈 노트를 휴지통으로 보내고, '다음 10개 열기'로 살아 있는 글만 브라우저에서 열어 조플린 클리퍼로 다시 스크랩하세요. 같은 주소로 내용이 채워진 노트가 생기면 '다시 채워진 빈 노트 정리'로 옛 빈 노트를 휴지통에 보냅니다.").format(len(empties)),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10, wraplength=800).pack(fill="x")
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", font=(self.ui, 10), exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        state = {"empties": empties, "repaired": repaired, "opened": set(), "status": {}}   # opened: 브라우저로 연 빈 노트의 경로
        info = tk.Label(top, text="", bg=C["bg"], fg=C["text"], font=(self.ui, 10), anchor="w", padx=16)

        def render():
            done = {n["path"] for n, _twin in state["repaired"]}
            lb.delete(0, "end")
            for n, url in state["empties"]:
                mark = (tr("[채워짐] ") if n["path"] in done else tr("[열었음] ") if n["path"] in state["opened"]
                        else {"alive": tr("[살아 있음] "), "dead": tr("[없어짐] "), "blocked": tr("[로그인 필요] "), "unknown": tr("[확인 못 함] ")}.get(state["status"].get(n["path"]), ""))
                lb.insert("end", f"{mark}{n['title'][:50]}   {url[:70]}")
            left = sum(1 for n, _u in state["empties"] if n["path"] not in state["opened"] and n["path"] not in done)
            top.title(tr("빈 스크랩 다시 받기 — {0:,}개").format(len(state["empties"])))
            info.config(text=tr("빈 노트 {0:,}개 · 다시 채워진 것 {1:,}개 · 아직 안 연 것 {2:,}개").format(len(state["empties"]), len(done), left))

        def rescan(after=None):
            """노트를 다시 훑어 목록을 지금 상태로 맞춘다(창을 연 뒤에 받은 스크랩도 짝으로 잡힌다)"""
            def got(result):
                if not top.winfo_exists():
                    return
                state["empties"], state["repaired"] = result
                render()
                top.lift()
                if after:
                    after()
            self.scan_notes(tr("빈 스크랩 다시 받기"), lambda notes, prog, cancel: cleanup.empty_scraps(notes, prog, cancel), got)

        def open_next():
            import webbrowser
            done = {n["path"] for n, _twin in state["repaired"]}
            order = {"alive": 0, None: 1, "unknown": 1, "blocked": 2}   # 살아 있는 글부터. 없어진 글은 열지 않는다
            batch = sorted(((n, url) for n, url in state["empties"] if n["path"] not in state["opened"] and n["path"] not in done
                            and state["status"].get(n["path"]) != "dead"), key=lambda x: order.get(state["status"].get(x[0]["path"]), 1))[:10]
            if not batch:
                return messagebox.showinfo(APP, tr("모든 주소를 열었습니다."), parent=top)
            for n, url in batch:
                webbrowser.open(url, new=2)
                state["opened"].add(n["path"])
            render()

        def clean_now():
            pairs = state["repaired"]
            if not pairs:
                return messagebox.showinfo(APP, tr("다시 채워진 빈 노트가 없습니다.\n(다시 받은 글의 주소가 옛 주소와 사이트·글 번호까지 달라졌으면 짝을 찾지 못합니다.)"), parent=top)
            shown = "\n".join(f"· {old['title'][:34]}  ←  {new['title'][:34]}" for old, new in pairs[:12])
            if len(pairs) > 12:
                shown += "\n" + tr("… 외 {0:,}개").format(len(pairs) - 12)
            if not messagebox.askyesno(APP, tr("다시 받아 내용이 채워진 옛 빈 노트 {0:,}개를 휴지통으로 보냅니다.\n(왼쪽이 휴지통으로 갈 빈 노트, 오른쪽이 남는 새 노트. 휴지통에서 복원할 수 있습니다.)\n\n{1}\n\n진행할까요?").format(len(pairs), shown), parent=top):
                return
            self.trash_notes([old["path"] for old, _new in pairs])
            rescan()

        def check_dead():
            """빈 노트의 출처 주소가 살아 있는지 확인하고, 없어진 글의 빈 노트는 휴지통으로 보낸다(다시 받을 수 없으므로)"""
            todo = [(n, url) for n, url in state["empties"] if n["path"] not in {m["path"] for m, _t in state["repaired"]}]
            if not todo:
                return messagebox.showinfo(APP, tr("확인할 빈 노트가 없습니다."), parent=top)
            if not messagebox.askyesno(APP, tr("빈 노트 {0:,}개의 출처 주소에 접속해 웹페이지가 아직 있는지 확인합니다.\n각 사이트에 요청이 가며 시간이 걸릴 수 있습니다(같은 사이트에는 동시에 2개까지).\n\n진행할까요?").format(len(todo)), parent=top):
                return

            def done_check(res):
                if not top.winfo_exists():
                    return
                if res is None:
                    return messagebox.showerror(APP, tr("인터넷에 연결되어 있지 않은 것 같습니다. 연결을 확인한 뒤 다시 해 보세요."), parent=top)
                for n, url in todo:
                    state["status"][n["path"]] = res.get(url, "unknown")
                render()
                top.lift()
                dead = [n for n, url in todo if res.get(url) == "dead"]
                count = {k: sum(1 for v in res.values() if v == k) for k in ("alive", "dead", "blocked", "unknown")}
                summary = tr("살아 있음 {0:,} · 없어짐 {1:,} · 로그인 필요 {2:,} · 확인 못 함 {3:,}").format(count["alive"], count["dead"], count["blocked"], count["unknown"])
                if not dead:
                    return messagebox.showinfo(APP, tr("없어진 웹페이지가 없습니다.") + "\n" + summary, parent=top)
                shown = "\n".join(f"· {n['title'][:40]}" for n in dead[:10])
                if len(dead) > 10:
                    shown += "\n" + tr("… 외 {0:,}개").format(len(dead) - 10)
                if not messagebox.askyesno(APP, tr("{0}\n\n웹페이지가 없어져 다시 받을 수 없는 빈 노트 {1:,}개를 휴지통으로 보냅니다(휴지통에서 복원할 수 있습니다).\n살아 있는 글·로그인이 필요한 글·확인 못 한 글은 그대로 둡니다.\n\n{2}\n\n진행할까요?").format(summary, len(dead), shown), parent=top):
                    return
                self.trash_notes([n["path"] for n in dead])
                rescan()
            self.run_task(tr("주소 확인"), lambda prog, cancel: cleanup.check_urls([url for _n, url in todo], prog, cancel), done_check, text=tr("출처 주소를 확인하는 중…"))

        def trash_all():
            """다시 받지 않고 빈 노트를 전부 휴지통으로 보낸다(다시 받는 수고에 비해 잃을 것이 적을 때)"""
            items = list(state["empties"])
            if not items:
                return messagebox.showinfo(APP, tr("정리할 빈 노트가 없습니다."), parent=top)
            shown = "\n".join(f"· {n['title'][:40]}" for n, _u in items[:10])
            if len(items) > 10:
                shown += "\n" + tr("… 외 {0:,}개").format(len(items) - 10)
            if not messagebox.askyesno(APP, tr("출처 주소만 남은 빈 노트 {0:,}개를 모두 휴지통으로 보냅니다.\n{1}일 동안 휴지통에서 복원할 수 있습니다.\n\n{2}\n\n진행할까요?").format(len(items), self.store.trash_days, shown), parent=top):
                return
            self.trash_notes([n["path"] for n, _u in items])
            rescan()

        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=12)
        info.pack(side="bottom", fill="x")
        Btn(bar, tr("다음 10개 열기"), open_next, pady=5).pack(side="left")
        Btn(bar, tr("목록 새로 고침"), rescan, pady=5).pack(side="left", padx=(8, 0))
        Btn(bar, tr("주소 확인 · 죽은 글 정리"), check_dead, pady=5).pack(side="left", padx=(8, 0))
        Btn(bar, tr("빈 노트 모두 휴지통으로"), trash_all, kind="danger", pady=5).pack(side="right", padx=(0, 8))
        Btn(bar, tr("다시 채워진 빈 노트 정리…"), lambda: rescan(clean_now), pady=5).pack(side="right")
        render()

