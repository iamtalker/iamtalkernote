"""렌더링 화면과 원문을 블록 단위로 맞추는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class RenderSyncMixin:
    # ---- 렌더링 화면 ↔ 원문 맞추기(블록 단위): 우클릭 삭제와 좌우 분할 짝 강조가 함께 쓴다
    def render_flat(self, src):
        """원문을 그려 본 렌더링 글(화면에 그릴 글자들을 이어 붙인 것)"""
        return "".join(t for t, _, _ in preview.layout(wikiconv.parse(self.expand_embeds(src), bulk.SYNTAX[FMT], self.title_var.get()), **self.table_kw()))

    def view_source(self):
        """렌더링에 실제로 쓰인 원문('원본: 주소' 줄을 뺀 것)과 그 줄의 길이"""
        text = self.text.get("1.0", "end-1c")
        m = SOURCE_LINE.match(text)
        return (text[m.end():], m.end()) if m else (text, 0)

    def block_map(self):
        """[(원문 블록 시작, 끝, 렌더링 글 시작, 끝)] — 블록마다 따로 그려 본 길이로 원문과 렌더링 글을 맞춘다. 맞출 수 없으면 None.
        같은 원문이면 다시 계산하지 않는다(커서를 옮길 때마다 부르므로)"""
        src, _off = self.view_source()
        key = (self.cur.get("path") if self.cur else None, len(src), hash(src), self.title_var.get())
        if getattr(self, "_bm_key", None) == key:
            return self._bm
        res = None
        if len(src) < 300_000:
            try:
                blocks = viewdelete.split_blocks(src)
                texts = [self.render_flat(b + "\n") for b, _ in blocks]
                if "".join(texts) == self.render_flat(src):
                    res, ps, pr = [], 0, 0
                    for (b, sep), t in zip(blocks, texts):
                        res.append((ps, ps + len(b), pr, pr + len(t.rstrip("\n"))))
                        ps += len(b) + len(sep)
                        pr += len(t)
            except Exception:  # noqa: BLE001
                res = None
        self._bm_key, self._bm = key, res
        return res

    def wcount(self, widget, index):
        """글 칸의 맨 앞에서 index 까지의 Tk 글 위치(UTF-16 단위)"""
        r = widget.count("1.0", index, "indices")
        return int(r[0]) if r else 0

    def w2s(self, w, end=False):
        """화면 위치 → 렌더링 글 위치. 맞출 수 없으면 None"""
        m = getattr(self, "view_map", None)
        if not m or not getattr(self, "view_ok", False):
            return None
        i = bisect.bisect_right(self.view_w0, w) - 1
        if i < 0:
            return 0
        w0, wl, s0, sl, t = m[i]
        if w >= w0 + wl:
            return s0 + sl
        if t is None:                               # 그림: 앞이면 그림 앞, 뒤면 그림 뒤
            return s0 + sl if (end or w > w0) else s0
        return s0 + u16_to_idx(t, w - w0)

    def s2w(self, s, end=False):
        """렌더링 글 위치 → 화면 위치"""
        m = getattr(self, "view_map", None)
        if not m or not getattr(self, "view_ok", False):
            return None
        i = (bisect.bisect_left(self.view_s0, s) - 1) if end else (bisect.bisect_right(self.view_s0, s) - 1)
        i = min(max(i, 0), len(m) - 1)
        w0, wl, s0, sl, t = m[i]
        if s >= s0 + sl:
            return w0 + wl
        if t is None:
            return w0 + wl if end else w0
        return w0 + idx_to_u16(t, s - s0)

    def pair_later(self, side=None):
        """좌우 분할: 커서가 있는 쪽의 블록을 반대쪽에서 강조한다. 키·클릭이 이어질 때 한 번만 하려고 잠깐 미룬다"""
        if side:
            self._pair_side = side
        if self.mode != "split" or not self.cur or self.doc_open:
            return
        if getattr(self, "_pair_job", None):
            self.root.after_cancel(self._pair_job)
        self._pair_job = self.root.after(90, self.pair_run)

    def pair_clear(self):
        for w in (self.text, self.view):
            w.tag_remove("pair", "1.0", "end")

    def keep_pair_visible(self, widget, start, end):
        top = widget.index("@0,0")
        bottom = widget.index(f"@0,{max(0, widget.winfo_height() - 1)}")
        if widget.compare(end, "<=", top) or widget.compare(start, ">", bottom):
            widget.see(start)

    def pair_run(self):
        self._pair_job = None
        if self.mode != "split" or not self.cur or self.doc_open:
            return self.pair_clear()
        bm = self.block_map()
        self.pair_clear()
        if not bm:
            return
        src, off = self.view_source()
        text = self.text.get("1.0", "end-1c")
        try:
            if self._pair_side == "view":
                w = self.wcount(self.view, "insert")
                sv = self.w2s(w)
                hit = next((b for b in bm if sv is not None and b[2] <= sv <= b[3] and b[3] > b[2]), None)
                if not hit:
                    return
                a, z = off + hit[0], off + hit[1]
                ua, uz = idx_to_u16(text, a), idx_to_u16(text, z)
                self.text.tag_add("pair", f"1.0+{ua}c", f"1.0+{uz}c")
                self.keep_pair_visible(self.text, f"1.0+{ua}c", f"1.0+{uz}c")
            else:
                u = self.wcount(self.text, "insert")
                p = u16_to_idx(text, u) - off
                hit = next((b for b in bm if b[0] <= p <= b[1] and b[3] > b[2]), None)
                if not hit:
                    return
                w0, w1 = self.s2w(hit[2]), self.s2w(hit[3], end=True)
                if w0 is None or w1 is None or w1 <= w0:
                    return
                self.view.tag_add("pair", f"1.0+{w0}c", f"1.0+{w1}c")
                self.keep_pair_visible(self.view, f"1.0+{w0}c", f"1.0+{w1}c")
        except tk.TclError:
            pass

    def view_sel_range(self):
        """렌더링 화면에서 고른 범위 → 렌더링 글 위치 (시작, 끝). 맞출 수 없으면 None"""
        v = self.view
        if not v.tag_ranges("sel"):
            return None
        a, z = self.w2s(self.wcount(v, "sel.first")), self.w2s(self.wcount(v, "sel.last"), end=True)
        return (a, z) if a is not None and z is not None and z > a else None

    def delete_view_image(self, e):
        """그림 위에서 우클릭 → '그림 삭제': 그 그림을 고른 것으로 두고 삭제한다"""
        v = self.view
        idx = v.index(f"@{e.x},{e.y}")
        v.tag_remove("sel", "1.0", "end")
        v.tag_add("sel", idx, idx + "+1c")
        self.delete_view_selection()

    def apply_text_change(self, old, new):
        """글 칸을 old 에서 new 로 바꾼다(바뀐 구간만 지우고 넣어 되돌리기·커서가 덜 흔들린다)"""
        p, s_ = viewdelete.minimal_change(old, new)
        T = self.text
        up, ue = idx_to_u16(old, p), idx_to_u16(old, len(old) - s_)
        T.edit_separator()
        auto = T.cget("autoseparators")
        T.configure(autoseparators=False)      # 지우고 넣는 사이에 구분점이 자동으로 끼면 되돌리기가 두 번 걸린다
        try:
            T.delete(f"1.0+{up}c", f"1.0+{ue}c")
            mid = new[p:len(new) - s_]
            if mid:
                T.insert(f"1.0+{up}c", mid)
        finally:
            T.configure(autoseparators=auto)
        T.edit_separator()

    def delete_view_selection(self):
        """렌더링 화면에서 고른 글·그림·표·목록을 마크다운 원문에서 바로 지운다(불필요한 부분을 손으로 정리할 때). Ctrl+Z 로 되돌린다"""
        v = self.view
        if not v.tag_ranges("sel") or not self.cur:
            return
        rng = self.view_sel_range()
        if rng:      # 블록 단위로 원문과 맞춰 지운다(그림·표·목록·서식이 든 글도 된다)
            src, off = self.view_source()
            new_src = viewdelete.delete_range(src, rng[0], rng[1], self.render_flat)
            if new_src is not None:
                old = self.text.get("1.0", "end-1c")
                self.apply_text_change(old, old[:off] + new_src)
                v.tag_remove("sel", "1.0", "end")
                self.status.config(text=tr("선택한 부분을 지웠습니다 (Ctrl+Z 로 되돌립니다)"))
                return self.render()
        sel = v.get("sel.first", "sel.last")
        before = v.get("1.0", "sel.first")
        old = self.text.get("1.0", "end-1c")
        new = viewdelete.delete(old, sel, before)
        if new is None:
            return self.status.config(text=tr("고른 글을 원문에서 정확히 찾지 못해 지우지 않았습니다. ‘마크다운만’ 보기에서 지워 주세요."))
        p, s = viewdelete.minimal_change(old, new)
        self.text.edit_separator()
        self.text.delete(f"1.0+{p}c", f"1.0+{len(old) - s}c")
        mid = new[p:len(new) - s]
        if mid:
            self.text.insert(f"1.0+{p}c", mid)
        self.text.edit_separator()
        v.tag_remove("sel", "1.0", "end")
        self.status.config(text=tr("선택한 글을 지웠습니다 (Ctrl+Z 로 되돌립니다)"))
        self.render()

    def on_text_menu(self, e):
        t = self.text
        t.focus_set()
        has_sel = bool(t.tag_ranges("sel"))
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=tr("실행 취소"), command=lambda: t.event_generate("<<Undo>>"))
        m.add_command(label=tr("다시 실행"), command=lambda: t.event_generate("<<Redo>>"))
        m.add_separator()
        m.add_command(label=tr("잘라내기"), command=lambda: t.event_generate("<<Cut>>"), state="normal" if has_sel else "disabled")
        m.add_command(label=tr("복사"), command=lambda: t.event_generate("<<Copy>>"), state="normal" if has_sel else "disabled")
        m.add_command(label=tr("붙여넣기"), command=lambda: t.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label=tr("모두 선택"), command=lambda: t.tag_add("sel", "1.0", "end-1c"))
        m.tk_popup(e.x_root, e.y_root)

    def remote_image(self, url):
        s = self.imgs.get(url)
        if s is None:
            self.imgs[url] = ("pending",)

            def job():
                try:
                    self.img_q.put((url, "ok", ed.fetch_image(url, max_w=ed.IMG_FETCH_W)))   # 크게 보관하고 보여 줄 때 칸 너비에 맞춰 줄인다
                except Exception as ex:  # noqa: BLE001
                    self.img_q.put((url, "fail", str(getattr(ex, "reason", None) or ex)))
            threading.Thread(target=job, daemon=True).start()
            self.root.after(150, self.poll_images)
            return None
        return s[1] if s[0] == "ok" else None

    def poll_images(self):
        changed = remote_changed = False
        try:
            while True:
                url, kind, val = self.img_q.get_nowait()
                self.imgs[url] = (kind, val)
                changed = True
                remote_changed |= not url.startswith("local:")
        except queue.Empty:
            pass
        local_pending = any(key.startswith("local:") and value[0] == "pending" for key, value in self.imgs.items())
        if changed and (remote_changed or not local_pending):
            self.render()
        if any(v[0] == "pending" for v in self.imgs.values()):
            self.root.after(200, self.poll_images)

    def on_view_click(self, e):
        self.view.focus_set()   # 클릭하면 키보드(PageUp/PageDown, 방향키)가 이 화면에 먹히게
        idx = self.view.index(f"@{e.x},{e.y}")
        for t in self.view.tag_names(idx):
            if t in self.links:
                kind, target = self.links[t]
                return self.follow(kind, target)

    def open_url(self, url):
        """주소를 연다. 유튜브 영상은 설정에 따라 작은 재생 창(Brave 앱 창, 없으면 Edge, 주소창 없음)으로, 아니면 기본 브라우저로."""
        # 유튜브와 영상 파일(.mp4 …)은 주소창 없는 앱 창으로 연다: 재생 단추·소리·전체 화면이 있는 깨끗한 재생 창이 된다.
        # Brave 를 먼저 찾는다(Edge 는 광고를 못 막음). 둘 다 크롬 계열이라 --app 옵션이 같다
        if sys.platform == "win32" and st.read_config().get("video_open", "app") == "app" and (wikiconv.tree.youtube_id(url) or wikiconv.tree.is_video_file(url)):
            for exe in (os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                        os.path.expandvars(r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                        os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
                if os.path.isfile(exe):
                    subprocess.Popen([exe, f"--app={url}", "--window-size=980,640"])
                    return
        webbrowser.open(url)

    def auto_link_segs(self, segs):
        """옵션 '단어만 있어도 연결'(톰보이 방식): 평범한 글 속에서 다른 노트의 제목과 같은 낱말을 위키 링크로 만든다"""
        scoped = self.wiki_scoped()
        key = (id(self.all_notes), len(self.all_notes), self.cur["nb"] if scoped and self.cur else None)
        if getattr(self, "_auto_key", None) != key:
            self._auto_key, self._auto_tab = key, wikilinks.title_table(wikilinks.in_space(self.all_notes, self.cur["nb"] if self.cur else "", scoped))
        table, lengths = self._auto_tab
        own = self.cur["title"] if self.cur else ""
        skip = {"code", *TABLE_TAGS, "codeblock", "raw", "math", "link", "chip", "h1", "h2", "h3", "h4", "h5", "h6"}
        out = []
        for t, tags, extra in segs:
            if extra is not None or len(t) < 2 or skip.intersection(tags):
                out.append((t, tags, extra))
                continue
            for piece, title in wikilinks.auto_links(t, table, lengths, own):
                out.append((piece, tags + ("link",) if title else tags, ("link", "page", title) if title else None))
        return out

    def follow_path(self, path):
        found = next((x for x in self.all_notes if x["path"] == path), None)
        if not found:
            return
        if found not in self.notes:
            self.nb = ALL
            self.reload_notes()
        n = next((x for x in self.notes if x["path"] == path), None)
        if n:
            self.open_note(n)

    def follow(self, kind, target):
        if kind == "url":
            if re.match(r"(?i)^(https?|ftp|mailto):", target):
                self.open_url(target)
            else:
                self.open_local_file(target)
            return
        # 위키 링크 [[문서]] → 같은 노트북의 같은 이름 노트
        if not self.wiki_on():
            return
        want = wikilinks.split_target(target)[0]
        found = self.wiki_find(want)   # 같은 제목이 여럿이면 가장 최근 노트(범위 제한이 켜져 있으면 같은 위키 공간 안에서만)
        if found:
            path = found["path"]
            if found not in self.notes:
                self.nb = ALL
                self.reload_notes()
            return self.open_note(next(n for n in self.notes if n["path"] == path))
        if messagebox.askyesno(APP, tr('"{0}" 노트가 없습니다. 새로 만들까요?').format(target), parent=self.root):
            nb = self.cur["nb"] if self.cur else ""
            made = self.store.create_note(nb, want or "제목 없음")
            self.reload_notes()
            n = next((x for x in self.notes if x["path"] == made["path"]), None)
            if n:
                self.open_note(n)
