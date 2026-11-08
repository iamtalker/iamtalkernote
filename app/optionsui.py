"""설정 > 옵션 창(왼쪽 탭·오른쪽 내용)을 여는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class OptionsMixin:
    # ------------------------------------------------------------ 옵션 (설정 > 옵션: 왼쪽 탭 + 오른쪽 내용)
    def bind_keys(self):
        r = self.root
        r.bind_all("<Control-n>", lambda e: self.new_note())
        r.bind_all("<Control-d>", lambda e: (self.toggle_favorite(), "break")[1])   # 즐겨찾기 켜고 끄기
        r.bind_all("<Control-N>", lambda e: self.add_notebook())
        r.bind_all("<Control-l>", lambda e: self.cur and self.cycle_mode())
        r.bind_all("<Control-e>", lambda e: self.cur and self.cycle_mode())
        r.bind_all("<Control-L>", lambda e: (self.v["list"].set(not self.show["list"]), self.on_view_toggle()))
        r.bind_all("<Control-slash>", lambda e: self.toggle_syntax())
        r.bind_all("<Control-f>", lambda e: self.on_ctrl_f())
        r.bind_all("<Control-F>", lambda e: self.focus_search())
        # 윈도 미리보기가 키보드를 쥐고 있어도, 앱 안을 클릭하면 입력이 앱으로 돌아오게 한다
        r.bind_all("<Button-1>", lambda e: winpreview.reclaim_keyboard(r.winfo_id()), add="+")
        self.ow.txt.bind("<Control-d>", lambda e: (self.toggle_favorite(), "break")[1])
        self.ow.txt.bind("<Control-f>", lambda e: "break")
        for w in (self.text, self.view):   # 글자 칸의 기본 Ctrl+F(커서를 한 글자 오른쪽으로)는 막는다
            w.bind("<Control-f>", lambda e: (self.on_ctrl_f(), "break")[1])
            w.bind("<Control-d>", lambda e: (self.toggle_favorite(), "break")[1])   # 글자 칸의 기본 Ctrl+D(오른쪽 글자 지우기)는 즐겨찾기로 바꾼다
        r.bind_all("<F3>", lambda e: self.find_step(1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Shift-F3>", lambda e: self.find_step(-1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Control-comma>", lambda e: self.show_options("general"))
        r.bind_all("<F1>", lambda e: self.open_manual())
        r.bind_all("<F5>", lambda e: self.refresh_all())
        r.bind_all("<Control-minus>", lambda e: self.go(-1))
        r.bind_all("<Control-plus>", lambda e: self.go(1))
        r.bind_all("<Control-equal>", lambda e: self.go(1))
        r.bind_all("<Control-T>", lambda e: self.insert_datetime())
        r.bind_all("<F10>", lambda e: (self.v["notebooks"].set(not self.show["notebooks"]), self.on_view_toggle()))
        r.bind_all("<Prior>", lambda e: self.page_key(e, -1))
        r.bind_all("<Next>", lambda e: self.page_key(e, 1))
        for w in (self.lst, self.view, self.text):   # 포커스가 있는 칸보다 마우스 아래 칸을 우선
            w.bind("<Prior>", lambda e: self.page_redirect(e, -1), add="+")
            w.bind("<Next>", lambda e: self.page_redirect(e, 1), add="+")
        # 렌더링 화면은 읽기 전용이라 글자 위젯의 '커서를 한 쪽 옮기기' 대신 화면을 직접 밀어 준다. 기본 동작은 그림처럼 화면보다 큰 줄을
        # 누른 뒤에는 커서가 그 줄을 못 벗어나서 PageDown 이 거의 안 되고, 방향키는 그림 한 줄을 통째로 건너뛴다.
        for seq, args in (("<Prior>", ("scroll", -1, "pages")), ("<Next>", ("scroll", 1, "pages")),
                          ("<Up>", ("scroll", -48, "pixels")), ("<Down>", ("scroll", 48, "pixels")),
                          ("<Home>", ("moveto", 0.0)), ("<End>", ("moveto", 1.0))):
            self.view.bind(seq, lambda e, a=args: (self.view.yview(*a), "break")[1], add="+")
        for key, action in (("b", ("wrap", "b")), ("i", ("wrap", "i")), ("k", ("wrap", "link"))):
            self.text.bind(f"<Control-{key}>", lambda e, a=action: (self.run_action(a), "break")[1])

    def pane_under_pointer(self):
        """마우스가 올라가 있는 스크롤 칸(목록·렌더링·편집·트리). 없으면 None"""
        w = self.root.winfo_containing(*self.root.winfo_pointerxy())
        panes = (self.lst, self.view, self.text, self.tree, self.nbtree, self.tagtree)
        while w is not None:
            if any(w is p for p in panes):
                return w
            w = getattr(w, "master", None)
        return None

    def page_redirect(self, e, direction):
        """목록·렌더링·편집 칸에 포커스가 있어도, 마우스가 다른 칸 위에 있으면 그 칸을 한 쪽 스크롤한다
        (목록에서 노트를 클릭한 직후 마우스를 오른쪽 노트 위에 두고 PageDown 으로 읽을 수 있게). 같은 칸이면 그 칸이 알아서 한다."""
        pane = self.pane_under_pointer()
        if pane is not None and pane is not e.widget:
            pane.yview_scroll(direction, "pages")
            return "break"

    def page_key(self, e, direction):
        """PageUp/PageDown 의 나머지 경우: 입력칸·버튼 등에 포커스가 있거나 포커스가 없을 때.
        마우스가 올라가 있는 칸을 스크롤하고, 칸 위가 아니면 지금 읽는 노트를 스크롤한다."""
        if isinstance(e.widget, (tk.Text, tk.Listbox, ttk.Treeview)):
            return   # 그 칸이 알아서(위의 page_redirect 가 먼저 다른 칸 위의 마우스를 처리한다)
        target = self.pane_under_pointer()
        if target is None and self.cur:
            target = self.text if self.mode == "edit" else self.view
        if target is not None:
            target.yview_scroll(direction, "pages")
            return "break"

    def restore_window(self, win):
        """지난번 창 크기·위치·최대화 상태로 연다(화면 밖이면 위치는 버린다)"""
        m = re.fullmatch(r"(\d+)x(\d+)(?:([+-]+\d+)([+-]+\d+))?", str(win.get("geometry", "")))
        if m:
            def num(s):   # Tk 는 화면 왼쪽·위쪽 밖의 좌표를 '+-1900' 으로 적는다
                return int(s.replace("+-", "-").lstrip("+"))
            vx, vy, vw, vh = 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            if sys.platform == "win32":   # 모니터가 여러 개면 전체 가상 화면 기준(주 모니터 왼쪽·위쪽 모니터는 좌표가 음수)
                try:
                    import ctypes
                    gm = ctypes.windll.user32.GetSystemMetrics
                    vx, vy, vw, vh = gm(76), gm(77), gm(78) or vw, gm(79) or vh
                except Exception:  # noqa: BLE001
                    pass
            w, h = max(900, min(int(m[1]), vw)), max(520, min(int(m[2]), vh))
            pos = ""
            if m[3] and m[4]:
                x, y = num(m[3]), num(m[4])
                if vx - w + 100 < x < vx + vw - 100 and vy <= y < vy + vh - 100:
                    pos = f"+{x}+{y}"
            self.root.geometry(f"{w}x{h}{pos}")
        if win.get("zoomed"):
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass

    def save_window(self):
        """창 크기·칸 너비·정렬·노트북을 기억해 다음 실행 때 되살린다"""
        try:
            zoomed = self.root.state() == "zoomed"
            if zoomed:
                self.root.state("normal")
                self.root.update_idletasks()
            geo = self.root.geometry()
            self.capture_nb_height()
            managed = [str(p) for p in self.pane.panes()]
            for key, w in (("left", self.leftf), ("list", self.listf), ("syntax", self.sidebar)):
                if str(w) in managed and w.winfo_width() > 1:
                    self.widths[key] = max(w.winfo_width(), 150)
            st.write_config(window={"geometry": geo, "zoomed": zoomed, "widths": self.widths, "sort": self.sort, "asc": self.asc, "nb": self.nb, "nb_h": self.nb_h})
        except (tk.TclError, OSError):
            pass

    def close_action(self):
        """창의 닫기(X) 버튼을 누르면: 'tray' = 트레이로 들어가 계속 실행(웹 클리퍼·가져온 폴더 색인도 계속), 'quit' = 바로 종료"""
        v = st.read_config().get("closeAction", "tray")
        return v if v in ("tray", "quit") else "tray"

    def on_close(self):
        if self.close_action() == "quit":
            return self.quit()
        self.hide_to_tray()

    def hide_to_tray(self):
        """창을 숨기고 트레이 아이콘만 남긴다(아이콘을 못 만들면 그냥 작업표시줄로 최소화)"""
        self.flush()
        self.save_window()
        if self.pv_active:                       # 숨겨진 동안 mp3 가 계속 재생되지 않게 미리보기는 닫아 둔다(다시 열 때 되살림)
            self.pv.unload()
            self.pv_active = False
            self.pv_was_active = True
        if not self.tray.start():
            return self.root.iconify()
        self.tray_was_zoomed = self.root.state() == "zoomed"
        self.root.withdraw()
        self.tray_hidden = True
        self.root.after(200, self.poll_tray)

    def poll_single(self):
        """두 번째 실행이 보낸 '창을 열어 달라'는 신호를 0.4초마다 확인한다"""
        self.root.after(400, self.poll_single)
        if single.signaled():
            self.bring_to_front()

    def bring_to_front(self):
        """트레이에 들어가 있거나 최소화된 창을 다시 열어 앞으로 가져온다"""
        if self.tray_hidden:
            return self.show_from_tray()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)                      # 윈도가 포커스를 안 줘도 일단 맨 앞에 보이게
        self.root.after(250, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def poll_tray(self):
        if not self.tray_hidden:
            return
        try:
            ev = self.tray.events.get_nowait()
        except queue.Empty:
            return self.root.after(200, self.poll_tray)
        if ev == "quit":
            return self.quit()
        self.show_from_tray()

    def show_from_tray(self):
        self.tray_hidden = False
        self.tray.stop()
        self.root.deiconify()
        if self.tray_was_zoomed:
            self.root.state("zoomed")
        self.root.lift()
        self.root.focus_force()
        if getattr(self, "pv_was_active", False):
            self.pv_was_active = False
            if self.doc_open and self.cur:
                self.show_doc(self.cur, native=True)
            elif self.pdf_note and self.cur:
                self.show_pdf_note(self.pdf_note)

    def quit(self):
        self.tray_hidden = False
        self.tray.stop()
        self.pv.unload()
        self.save_window()
        self.flush()
        self.stop_clipper()
        self.sync.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
