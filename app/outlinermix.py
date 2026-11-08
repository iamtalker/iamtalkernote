"""아웃라이너 보기(점 계층 목록)와 렌더링 화면에서 글을 바로 고치는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class OutlinerMixin:
    # ---- 렌더링 화면에서 글을 눌러 그 부분의 원문만 고친다(항목 한 줄 / 블록 하나)
    def on_view_resize(self, e=None):
        """렌더링 칸 너비가 바뀌면(창 크기·칸 켜기 끄기) 그림이 든 글만 잠시 뒤에 다시 그려 그림 크기를 맞춘다"""
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(300, self.refit_images)

    def refit_images(self):
        self.resize_job = None
        if self.cur and self.mode != "edit" and self.has_imgs and self.img_avail() != self.img_w_used:
            self.render()

    def draw_view(self, segs):
        v = self.view
        self._render_img_avail = self.img_avail()
        self._drawing_view = True
        self.view_sb_frozen = True
        try:
            self.draw_view_body(segs)
        finally:
            self._drawing_view = False
            self.view_sb_frozen = False
            self.view_scroll(*v.yview())

    def draw_view_body(self, segs):
        v = self.view
        self.stop_gifs()
        self.img_w_used = self.img_avail()
        self.has_imgs = any(extra and extra[0] == "img" for _, _, extra in segs)
        top = v.yview()[0]
        top_source = None
        if getattr(self, "view_ok", False):
            top_source = self.w2s(self.wcount(v, v.index("@0,0")))
        v.config(state="normal")
        v.delete("1.0", "end")
        self.links.clear()
        self.photos.clear()
        self.img_files.clear()
        vmap, w_off, s_off = [], 0, 0        # 화면 위치(w) ↔ 렌더링 글 위치(s): 렌더링만으로는 원문 위치를 몰라서 블록 맞추기에 쓴다
        wiki, widx = self.wiki_on(), None
        if wiki and st.read_config().get("wikiAuto", False) and self.cur and not self.doc_open:
            segs = self.auto_link_segs(segs)
        for t, tags, extra in segs:
            tg = list(tags)
            self.tab_tags(tg)
            if "b" in tg and "i" in tg:
                tg.append("bi")
            if extra and extra[0] == "link" and extra[1] == "page":
                if not wiki:   # 위키를 끄면 [[ ]] 는 그냥 글자
                    tg = [x for x in tg if x != "link"]
                    extra = None
                else:
                    if self.wiki_find(wikilinks.split_target(extra[2])[0]) is None:
                        tg.append("linkmiss")
            if extra and extra[0] == "link":
                key = "L%d" % len(self.links)
                self.links[key] = extra[1:]
                tg.append(key)
            if extra and extra[0] == "img" and self.show_image(extra[1], extra[3] if len(extra) > 3 else 0):
                vmap.append((w_off, 1, s_off, len(t), None))        # 화면에는 그림 한 칸, 렌더링 글로는 '[그림: …]'
                w_off += 1
                s_off += len(t)
                if len(extra) > 5:   # 링크로 감싼 그림(썸네일 등): 그림을 누르면 그 링크가 열린다
                    key = "L%d" % len(self.links)
                    self.links[key] = extra[4:6]
                    v.tag_add(key, "end-2c", "end-1c")
                    v.tag_add("link", "end-2c", "end-1c")
                continue
            if extra and extra[0] == "img" and len(extra) > 5:   # 링크로 감싼 그림을 아직/못 불러왔으면 글자 칩이 링크 노릇을 한다
                key = "L%d" % len(self.links)
                self.links[key] = extra[4:6]
                tg += [key, "link"]
            v.insert("end", t, tuple(tg))
            wl = utf16_len(t)
            vmap.append((w_off, wl, s_off, len(t), t))
            w_off += wl
            s_off += len(t)
        v.config(state="disabled")
        try:
            total = v.count("1.0", "end-1c", "indices")
            self.view_ok = bool(total) and int(total[0]) == w_off or (not total and w_off == 0)
        except (tk.TclError, TypeError, ValueError):
            self.view_ok = False
        self.view_map = vmap
        self.view_w0 = [m[0] for m in vmap]
        self.view_s0 = [m[2] for m in vmap]
        self.view_total_s = s_off
        v.tk.call(v._w, "sync")
        top_view = self.s2w(top_source) if top_source is not None else None
        if top_view is not None:
            v.yview(f"1.0+{top_view}c")
        else:
            v.yview_moveto(top)
        self.find_later()   # 다시 그렸으면 찾은 곳의 강조도 다시 한다
        self.pair_later(self._pair_side)   # 다시 그렸으면 왼쪽↔오른쪽 짝 강조도 다시 한다

    def data_image(self, src, target=None):
        """data:image/...;base64,… 주소 → 화면에 쓸 PhotoImage와 선택적 애니메이션."""
        m = re.match(r"(?is)^data:image/([a-z0-9.+-]+)[^,]*;base64,(.*)$", src.strip())
        if not m:
            return None
        kind, payload = m.group(1).lower(), re.sub(r"\s+", "", m.group(2))
        try:
            raw = base64.b64decode(payload)
            if kind == "gif":
                import io
                loaded = self.animated_gif(io.BytesIO(raw), target)
                return loaded or (tk.PhotoImage(data=payload), None)
            if kind == "png":
                return tk.PhotoImage(data=payload), None
            path = os.path.join(ed.image_cache_dir(), hashlib.sha1(raw).hexdigest()[:20] + "." + ("jpg" if kind in ("jpeg", "jpg") else kind))
            if not os.path.isfile(path):
                with open(path, "wb") as f:
                    f.write(raw)
            return tk.PhotoImage(file=ed.local_image_png(path, max_w=target or self.img_avail())), None
        except (tk.TclError, OSError, ValueError):
            return None

    def animated_gif(self, source, target):
        """GIF 첫 장면과 재생 정보를 연다. 실패하면 정지 이미지 경로로 돌아간다."""
        image = None
        try:
            from PIL import Image, ImageTk
            image = Image.open(source)
            image.seek(0)
            frame = image.convert("RGBA")
            if target and frame.width > target:
                height = max(1, round(frame.height * target / frame.width))
                resized = frame.resize((target, height), Image.Resampling.LANCZOS)
                frame.close()
                frame = resized
            photo = ImageTk.PhotoImage(frame, master=self.view)
            frame.close()
            count = int(getattr(image, "n_frames", 1))
            if count < 2:
                image.close()
                return photo, None
            return photo, {
                "image": image,
                "photo": photo,
                "frames": count,
                "index": 0,
                "target": target,
                "delay": int(image.info.get("duration", 100)),
                "remaining": image.info.get("loop", 1),
            }
        except (ImportError, OSError, ValueError, EOFError, tk.TclError):
            if image is not None:
                image.close()
            return None

    def find_local_image(self, src):
        """노트 속 그림 주소 → 실제 파일 경로(없으면 None). 상대 경로, %인코딩, file:///, 조플린 ':/아이디' 를 다 받는다."""
        if src.lower().startswith("file:///"):
            src = src[8:]
        m = re.match(r"^:/([0-9a-fA-F]{32})", src)
        if m:   # 조플린 내부 주소 → 리소스 폴더의 <아이디>.* 파일
            media = self.store.media_dir
            hits = [f for f in os.listdir(media) if f.lower().startswith(m.group(1).lower())] if os.path.isdir(media) else []
            return os.path.join(media, hits[0]) if hits else None
        src = unquote(src.split("#")[0])
        if src.startswith("?"):
            return None
        base = os.path.dirname(self.cur["path"]) if self.cur else self.store.root
        cands = [os.path.normpath(os.path.join(base, src.replace("/", os.sep)))]
        cands.append(os.path.normpath(os.path.join(base, src.split("?")[0].replace("/", os.sep))))
        cands.append(os.path.join(self.store.media_dir, os.path.basename(src.split("?")[0])))   # 노트가 옮겨져 링크가 어긋났을 때
        return next((c for c in cands if os.path.isfile(c)), None)

    def view_copy(self, e=None):
        """렌더링 화면에서 복사: 글자(표는 칸을 탭으로 이은 줄)와 HTML 을 함께 클립보드에 넣는다. 안 되면 기본 복사로"""
        v = self.view
        if not v.tag_ranges("sel"):
            return None
        try:
            def link_of(tag):
                lk = self.links.get(tag)
                return lk[1] if lk and lk[0] == "url" else None
            plain, html = copyhtml.selection(v, v.index("sel.first"), v.index("sel.last"), link_of)
            if not plain.strip() or not winclip.set_text_html(plain, html):
                return None
        except Exception:  # noqa: BLE001
            return None
        return "break"

    def text_paste(self, e=None):
        """편집 칸 붙여넣기: 클립보드에 표가 든 HTML 이 있으면(웹에서 복사한 표) 마크다운 표로 바꿔 넣는다. 그 밖에는 기본 붙여넣기"""
        if getattr(self, "_plain_paste", False):
            self._plain_paste = False
            return None
        md = pastehtml.markdown_from_clipboard()
        if not md:
            return None
        t = self.text
        a, b = (t.index("sel.first"), t.index("sel.last")) if t.tag_ranges("sel") else (t.index("insert"), t.index("insert"))
        new = pastehtml.around(t.get(f"{a} linestart", a), t.get(b, f"{b} lineend"), md)
        self.replace(a, b, new, len(new), len(new))
        return "break"

    def plain_paste(self, e=None):
        """글자만 붙여넣기(Ctrl+Shift+V)"""
        self._plain_paste = True
        try:
            self.text.event_generate("<<Paste>>")
        finally:
            self._plain_paste = False
        return "break"

    def table_kw(self):
        """표를 렌더링 칸 폭에 맞추는 데 필요한 값(preview.layout 의 avail·measure). 칸 폭은 20 픽셀 단위로 내려서 조금 변해도 같은 값
        (렌더링과 블록 맞추기가 같은 값을 써야 하므로 둘 다 이 함수를 쓴다). 아직 화면에 안 나왔으면 {}"""
        box = self.view.master
        box.update_idletasks()
        w = box.winfo_width()
        if w < 80:      # 아직 화면에 안 나왔다
            return {}
        return {"avail": max(120, (w - 2 * 18 - 4 - 20 - 16) // 20 * 20), "measure": self.fonts["table"].measure}

    def tab_tags(self, names):
        """preview 가 낸 표 탭 태그('T:14l;150r;…')를 Text 태그의 tabs 로 만든다(처음 보는 이름만)"""
        seen = self.__dict__.setdefault("_tab_tags", set())
        for nm in names:
            if nm.startswith("T:") and nm not in seen:
                seen.add(nm)
                stops = []
                for part in nm[2:].split(";"):
                    stops += [int(part[:-1]), {"l": "left", "r": "right", "c": "center"}[part[-1]]]
                self.view.tag_configure(nm, tabs=tuple(stops))

    def img_avail(self):
        """렌더링 화면에서 그림이 쓸 수 있는 너비(픽셀): 렌더링 칸 너비 - 여백(스크롤바 포함). 50 단위로 내려서 변환 캐시가 늘지 않게.
        스크롤바가 생겼다 사라져도 값이 같도록 스크롤바가 들어가는 바깥 칸의 너비로 잰다."""
        if getattr(self, "_drawing_view", False):
            return self._render_img_avail
        box = self.view.master
        box.update_idletasks()
        w = box.winfo_width()
        if w < 200:   # 아직 화면에 안 나왔다
            return ed.IMG_MAX_W
        return max(300, min((w - 2 * 18 - 4 - 20) // 50 * 50, ed.IMG_FETCH_W))

    def photo_from_file(self, path, target=None):
        """그림 파일 → PhotoImage (너비가 target 보다 크면 target 으로 줄여서). 형식은 확장자가 아니라 내용으로 알아본다.
        PNG·GIF 는 작으면 바로, 그 밖(JPEG·BMP·WebP 등)이나 큰 것은 PNG 로 바꿔서"""
        kind = ed.sniff_image(path)
        target = target or self.img_avail()
        try:
            if kind in ("png", "gif"):
                try:
                    img = tk.PhotoImage(file=path)
                    if img.width() <= target:
                        return img
                except tk.TclError:   # Tk 가 못 읽는 PNG(16비트 등)
                    pass
            return tk.PhotoImage(file=ed.local_image_png(path, max_w=target))
        except (tk.TclError, OSError):
            return None

    def local_image_photo(self, path, target):
        """파일 그림을 작은 PNG 캐시로 뒤에서 바꾼 뒤 화면에 올린다."""
        try:
            stat = os.stat(path)
        except OSError:
            return None
        key = f"local:{os.path.normcase(os.path.abspath(path))}:{stat.st_mtime_ns}:{stat.st_size}:{target}"
        state = self.imgs.get(key)
        if state is None:
            self.imgs[key] = ("pending",)
            with self.local_img_lock:
                self.local_img_q.put((key, path, target))
                if not self.local_img_worker:
                    self.local_img_worker = True
                    threading.Thread(target=self.convert_local_images, daemon=True).start()
            self.root.after(150, self.poll_images)
            return None
        if state[0] != "ok":
            return None
        return self.photo_from_file(state[1], target)

    def convert_local_images(self):
        while True:
            try:
                key, path, target = self.local_img_q.get(timeout=0.1)
            except queue.Empty:
                with self.local_img_lock:
                    if self.local_img_q.empty():
                        self.local_img_worker = False
                        return
                continue
            try:
                result = ed.local_image_png(path, max_w=target)
                self.img_q.put((key, "ok", result))
            except Exception as ex:  # noqa: BLE001
                self.img_q.put((key, "fail", str(ex)))
            finally:
                self.local_img_q.task_done()

    def stop_gifs(self):
        self.gif_generation += 1
        for job in self.gif_jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.gif_jobs.clear()
        for image in self.gif_sources:
            image.close()
        self.gif_sources.clear()

    def start_gif(self, animation):
        from PIL import Image
        image, photo = animation["image"], animation["photo"]
        self.gif_sources.append(image)
        generation = self.gif_generation
        job = None

        def advance():
            nonlocal job
            self.gif_jobs.discard(job)
            if generation != self.gif_generation:
                return
            next_index = animation["index"] + 1
            if next_index >= animation["frames"]:
                remaining = animation["remaining"]
                if remaining != 0:
                    if remaining <= 1:
                        return
                    animation["remaining"] = remaining - 1
                next_index = 0
            animation["index"] = next_index
            try:
                image.seek(next_index)
                frame = image.convert("RGBA")
                target = animation["target"]
                if target and frame.width > target:
                    height = max(1, round(frame.height * target / frame.width))
                    resized = frame.resize((target, height), Image.Resampling.LANCZOS)
                    frame.close()
                    frame = resized
                photo.paste(frame)
                frame.close()
            except (OSError, ValueError, EOFError, tk.TclError):
                return
            delay = max(20, min(int(image.info.get("duration", 100)), 10000))
            job = self.root.after(delay, advance)
            self.gif_jobs.add(job)

        try:
            job = self.root.after(max(20, animation["delay"]), advance)
            self.gif_jobs.add(job)
        except tk.TclError:
            image.close()

    def show_image(self, src, width=0):
        """그림으로 보여 준다: 같은 폴더·리소스 폴더의 파일, http(s) 주소, 본문에 박힌 data: 그림. 안 되면 글자 칩으로 남는다."""
        src = src.strip()
        avail = self.img_avail()
        target = min(width, avail) if width else avail
        animation = None
        if src[:5].lower() == "data:":   # 노트 본문에 base64 로 박힌 그림
            loaded = self.data_image(src, target)
            if loaded is None:
                return False
            img, animation = loaded
            return self.put_image(img, width, animation=animation)
        if re.match(r"(?i)^https?://", src):
            path = self.remote_image(src)
            if not path:
                return False
        else:
            if re.match(r"(?i)^[a-z][a-z0-9+.-]+:", src) and not re.match(r"(?i)^(file:///|:/)", src):
                return False   # mailto: 같은 그림이 아닌 주소
            path = self.find_local_image(src)
            if not path:
                return False
        if ed.sniff_image(path) == "gif":
            loaded = self.animated_gif(path, target)
            if loaded:
                img, animation = loaded
            else:
                img = self.photo_from_file(path, target)
        else:
            img = self.local_image_photo(path, target)
        return self.put_image(img, width, path, animation) if img is not None else False

    def put_image(self, img, width=0, path=None, animation=None):
        """그림을 렌더링 화면에 넣는다. 파일 그림은 photo_from_file 에서 이미 알맞게 줄였고, 본문에 박힌 PNG·GIF 처럼 못 줄인 것만
        여기서 정수 배로 줄인다(HTML 의 width 가 있으면 그 너비에 가깝게, 없으면 칸 너비보다 클 때만)"""
        if width and img.width() > width:
            img = img.subsample(max(1, round(img.width() / width)))
        elif img.width() > self.img_avail():
            img = img.subsample(math.ceil(img.width() / self.img_avail()))
        self.photos.append(img)
        name = self.view.image_create("end", image=img)
        if path:
            self.img_files[str(name)] = path
        if animation:
            self.start_gif(animation)
        return True

    def image_at(self, e):
        """렌더링 화면의 (x, y) 에 있는 그림의 (이름 or None) — 그림이 아니면 None"""
        idx = self.view.index(f"@{e.x},{e.y}")
        hit = self.view.dump(idx, idx + "+1c", image=True)
        return str(hit[0][1]) if hit else None

    NO_OPEN_EXT = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".lnk", ".scr", ".jar", ".hta", ".reg", ".dll", ".cpl"}

    def local_file(self, target):
        """노트 속 링크 주소가 이 컴퓨터의 파일(리소스 폴더의 pdf 등)이면 그 경로, 아니면 None. 실행 파일 종류는 열지 않는다."""
        if not target or re.match(r"(?i)^(https?|ftp|mailto|javascript|data):", target):
            return None
        path = self.find_local_image(target)
        return path if path and os.path.splitext(path)[1].lower() not in self.NO_OPEN_EXT else None

    def open_local_file(self, target):
        """링크한 파일(pdf·문서·영상 …)을 윈도 기본 프로그램으로 연다(pdf 는 pdf 리더). 파일이 없으면 알린다"""
        path = self.local_file(target)
        if not path:
            raw = self.find_local_image(target)
            msg = tr("보안을 위해 실행 파일은 열지 않습니다. 파일 위치 열기로 직접 여세요.") if raw else tr("연결된 파일을 찾을 수 없습니다.")
            return messagebox.showinfo(APP, msg, parent=self.root)
        try:
            os.startfile(path) if sys.platform == "win32" else webbrowser.open("file://" + path)
        except OSError as ex:
            messagebox.showerror(APP, tr('파일을 열 수 없습니다: {0}').format(ex), parent=self.root)

    def link_at(self, e):
        """렌더링 화면 (x, y) 에 있는 링크의 (종류, 주소) — 링크가 아니면 None"""
        idx = self.view.index(f"@{e.x},{e.y}")
        for t in self.view.tag_names(idx):
            if t in self.links:
                return self.links[t]
        return None

    def reveal_file(self, path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            webbrowser.open(os.path.dirname(path))

    def on_view_menu(self, e):
        v = self.view
        m = tk.Menu(self.root, tearoff=0)
        name = self.image_at(e)
        if name is not None:
            path = self.img_files.get(name)
            m.add_command(label=tr("파일 위치 열기"), command=lambda: self.reveal_file(path), state="normal" if path else "disabled")
            m.add_separator()
        else:
            lk = self.link_at(e)
            fpath = self.local_file(lk[1]) if lk and lk[0] == "url" else None
            raw = self.find_local_image(lk[1]) if lk and lk[0] == "url" and not fpath and not re.match(r"(?i)^(https?|ftp|mailto|javascript|data):", lk[1] or "") else None
            if fpath:
                m.add_command(label=tr("열기"), command=lambda: self.open_local_file(lk[1]))
            if fpath or raw:   # 실행 파일 종류는 열지 않지만, 탐색기에서 그 위치를 보는 것은 된다
                m.add_command(label=tr("파일 위치 열기"), command=lambda: self.reveal_file(fpath or raw))
                m.add_separator()
        m.add_command(label=tr("복사"), command=lambda: v.event_generate("<<Copy>>"), state="normal" if v.tag_ranges("sel") else "disabled")
        m.add_command(label=tr("모두 선택"), command=lambda: v.tag_add("sel", "1.0", "end-1c"))
        m.add_separator()
        if name is not None:
            m.add_command(label=tr("그림 삭제"), command=lambda: self.delete_view_image(e))
        m.add_command(label=tr("삭제"), command=self.delete_view_selection, state="normal" if v.tag_ranges("sel") else "disabled")
        m.tk_popup(e.x_root, e.y_root)
