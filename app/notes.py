"""iamtalkernote — 위키나루 기반 마크다운 노트 앱 (표준 라이브러리 tkinter).

    pythonw iamtalkernote.pyw          (콘솔 창 없이)      또는   python notes.py

조플린처럼: 메뉴줄(파일·편집·보기·이동·도구·도움말) · 노트북/태그 사이드바 · 노트 목록 · 서식 도구줄이 있는 에디터.
위키나루의 마크다운 렌더링·문법 해설, 폴더검색의 검색, 조플린 클리퍼 플러스(웹 클리퍼) 연동.
노트는 .md 파일로 저장된다.
"""
from notes_shared import *  # noqa: E402,F401,F403   (가져오기·상수·색·Btn·보조 함수: notes_shared.py)
import notes_shared as _shared  # noqa: E402
import autotitle  # noqa: E402   (제목 없이 쓴 새 노트: 본문 첫 줄을 제목으로)
from dialogs import DialogsMixin  # noqa: E402   (큰 대화창들: dialogs.py)
from langbtn import LangButton  # noqa: E402   (오른쪽 위 언어 단추: langbtn.py)
from searchbox import SearchBoxMixin  # noqa: E402   (검색창 자동완성·입력기 글꼴: searchbox.py)
from findbar import FindBarMixin  # noqa: E402   (문서에서 찾기 막대(Ctrl+F): findbar.py)
from wikiui import WikiUIMixin  # noqa: E402   (위키 링크(켜짐 확인·[[ 자동완성·연결된 노트 보기): wikiui.py)
from tagedit import TagEditMixin  # noqa: E402   (태그 편집(맨 아래 태그 박스·메모·이름 바꾸기·삭제·합치기): tagedit.py)


class App(DialogsMixin, SearchBoxMixin, TagEditMixin, WikiUIMixin, FindBarMixin):
    def __init__(self):
        global UI
        i18n.init(st.read_config().get("lang"))
        theme = migrate_theme(st.read_config().get("theme", {}))
        apply_theme(theme["name"], theme["custom"])
        self.root = tk.Tk()
        self.root.title(APP)
        win = st.read_config().get("window", {})
        self.root.geometry("1440x860")
        self.root.minsize(900, 520)
        self.restore_window(win)
        self.root.configure(bg=C["bg"])
        try:
            self.root.iconbitmap(default=os.path.join(HERE, "assets", "icon.ico"))   # 옵션·대화상자 등 이후에 열리는 모든 창도 같은 아이콘
        except tk.TclError:
            pass
        fams = set(tkfont.families())
        UI = self.ui = next((f for f in ("맑은 고딕", "Malgun Gothic", "Segoe UI") if f in fams), "TkDefaultFont")
        _shared.UI = UI   # notes_shared 의 납작한 버튼 등도 같은 글꼴을 쓰게
        self.mono = next((f for f in ("D2Coding", "Consolas", "Courier New") if f in fams), "TkFixedFont")
        self.size = 11
        self.style_ttk()

        view = st.read_config().get("view", {})
        self.show = {k: bool(view.get(k, d)) for k, d in (("notebooks", True), ("list", True), ("tags", False), ("syntax", True))}
        self.mode = view.get("mode") if view.get("mode") in ("edit", "split", "view") else "split"
        self.store = st.Store()
        self.fav = favorites.Favorites(syncsettings.control_dir())   # 즐겨찾기(설정 폴더의 작은 파일, 폰과 맞춤)
        self.store.tagger = note_tags   # 색인에 태그도 함께 기억
        self.docs = docidx.DocIndex()  # 가져온 폴더의 문서 색인
        self.doc_open = False          # 가져온 문서(읽기 전용)를 열어 둔 중인가
        self.doc_scanning = False      # 가져온 폴더를 뒤에서 다시 읽는 중인가(겹쳐 돌지 않게)
        self.pv = winpreview.Preview() # 윈도 미리보기 처리기(pdf → Edge, mp3 → Media Player …)
        self.pv_active = False         # 지금 노트 화면에 윈도 미리보기를 띄워 두었는가
        self.snap = sn.Snapshots(self.store)   # 복원 지점
        self.store.on_change = self.snap.preserve   # 노트를 바꾸기 직전에 그 내용을 복원 지점용으로 보관
        try:
            self.store.purge_trash()   # 휴지통에 보관 기간(기본 30일)이 지난 항목은 완전히 지운다
        except OSError:
            pass
        cfg = st.read_config()
        self.planner = pm.Planner(self.store.root)
        self.planner_view = self.trash_view = None
        self.feat = {k: bool(cfg.get("use_" + k, d)) for k, d in (("favs", True), ("outl", True), ("cal", True))}   # 설정 → 일반 → 기능 체크
        self.feat["gongsu"] = bool(cfg.get("cal_gongsu", False))   # 공수달력은 기본으로 꺼져 있고 체크해서 켠다
        self.nb = win.get("nb") if isinstance(win.get("nb"), str) and not win["nb"].startswith("@smart") else ALL   # '*' 모든 노트 · '' 기본 · 그 밖은 노트북 폴더 이름(없어졌으면 읽은 뒤 '*' 로)
        self.tag = None                # 태그로 거르는 중이면 그 태그
        self.nb_keys, self.tag_keys = [], []
        self.all_notes, self.notes, self.results, self.words = [], [], [], []
        self.cards = []                # 목록에 그려진 카드 → note
        self.rendered, self.card_starts, self.next_line = 0, [], 1   # 목록에 그려 놓은 노트 수 / 카드 시작 줄 / 다음 카드 줄
        self.sort, self.asc = win.get("sort") if win.get("sort") in ("relevance", "time", "ctime", "title") else "relevance", bool(win.get("asc", False))
        self.cur = None               # 열어 둔 노트(dict)
        self.hist, self.hpos = [], -1  # 이동 > 뒤로/앞으로
        self.declined = set()          # 그림 분리 제안을 거절한 노트
        self.snap_done = False         # 노트를 연 뒤 이전 내용을 버전으로 남겼는가
        self.load_gen = 0              # 배경 읽기 구분용
        self.load_prog = (0, 0)        # 처음 색인을 만들 때의 진행(읽은 수, 총 수)
        self.dirty = self.loading = self.quiet = False
        self.save_job = self.render_job = self.search_job = None
        self.resize_job = None        # 렌더링 칸 너비가 바뀐 뒤 그림 크기를 다시 맞추는 예약
        self.img_w_used, self.has_imgs = None, False   # 마지막으로 그릴 때 쓴 그림 너비 / 그 글에 그림이 있는지
        self.imgs, self.img_q, self.photos = {}, queue.Queue(), []
        self.multi = {}       # 목록에서 Shift/Ctrl+클릭으로 고른 노트들 {경로: 노트} (한 개만 고르면 비어 있다)
        self.anchor = None    # Shift+클릭 범위의 시작 노트 경로
        self.img_files = {}   # 렌더링 화면 속 그림 이름 → 원본 파일 경로(우클릭 "파일 위치 열기"용)
        self.links = {}
        self.clip_q = queue.Queue()
        self.srv = self.port = None
        self.nb_menu_target = self.ctx_note = None

        self.make_fonts()
        self.build_menu()
        self.build()
        self.start_clipper()
        self.sync = syncengine.Engine()
        self.sync_error = ""
        syncui.resume(self)
        self.tray = tray.Tray(os.path.join(HERE, "assets", "icon.ico"), f"{APP} {VERSION}")   # 닫기(X)를 누르면 들어가는 트레이 아이콘(마우스를 올리면 버전이 보인다: 트레이에 구버전이 남아 있는지 알아보려고)
        self.tray_hidden = self.tray_was_zoomed = False
        for cls in ("Entry", "Text"):    # 어느 칸에서 한글을 쳐도 조합 중인 글자가 그 칸 글꼴로 보이게
            self.root.bind_class(cls, "<FocusIn>", self.match_ime_font, add="+")
            self.root.bind_class(cls, "<KeyPress>", self.ime_keep_font, add="+")
            self.root.bind_class(cls, "<KeyRelease>", self.ime_keep_font, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_keys()
        self.set_mode(self.mode)
        self.relayout()
        self.reload_notes(background=True)
        self.root.after(3000, self.check_due)
        self.root.after(6000, self.sync_holidays)
        self.root.after(300, self.fit_panes)
        self.root.after(400, self.poll_single)
        self.root.after(20000, self.auto_scan_docs)   # 가져온 폴더에서 바뀐 파일만 뒤에서 다시 읽기
        self.root.after(15000, self.auto_snapshot)   # 시작하고 한참 뒤(목록을 다 읽은 다음) 하루 한 번 복원 지점
        self.root.after(600, self.poll_clip)

    # ------------------------------------------------------------ 글꼴·ttk 모양
    def font_cfg(self):
        """글꼴 설정(기본: 목록 10pt 보통, 노트 11pt 보통)"""
        c = st.read_config().get("fonts", {})

        def num(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(float(c.get(key, default)))))
            except (TypeError, ValueError):
                return default
        return {"list_size": num("list_size", 10, 8, 20), "list_bold": bool(c.get("list_bold", False)),
                "note_size": num("note_size", 11, 8, 28), "note_bold": bool(c.get("note_bold", False))}

    def set_fonts(self, ls, lb, ns, nb):
        def num(v, d, lo, hi):
            try:
                return max(lo, min(hi, int(float(v))))
            except (TypeError, ValueError):
                return d
        st.write_config(fonts={"list_size": num(ls, 10, 8, 20), "list_bold": bool(lb),
                               "note_size": num(ns, 11, 8, 28), "note_bold": bool(nb)})
        self.rebuild_ui()
        self.show_options("fonts")

    def make_fonts(self):
        fc = self.font_cfg()
        self.size = sz = fc["note_size"]
        self.note_bold = fc["note_bold"]
        fam = self.ui
        F = lambda **kw: tkfont.Font(family=kw.pop("family", fam), size=kw.pop("size", sz), **kw)  # noqa: E731
        self.fonts = {"base": F(weight="bold" if fc["note_bold"] else "normal"), "b": F(weight="bold"), "i": F(slant="italic"), "bi": F(weight="bold", slant="italic"),
                      "mono": F(family=self.mono, size=max(sz - 1, 8)), "small": F(size=max(sz - 3, 7)),
                      "title": F(size=sz + 6, weight="bold"), "meta": F(size=max(fc["list_size"] - 2, 7)),
                      "card": F(size=fc["list_size"], weight="bold" if fc["list_bold"] else "normal"), "tb_b": F(size=sz - 1, weight="bold"),
                      "tb_i": F(size=sz - 1, slant="italic"), "tb_s": F(size=sz - 1, overstrike=True)}
        self.hfonts = {n: F(weight="bold", size=sz + max(8 - 2 * n, 0) + (3 if n == 1 else 0)) for n in range(1, 7)}

    def style_ttk(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Flat.Treeview", background=C["bg"], fieldbackground=C["bg"], foreground=C["text"],
                    rowheight=30, borderwidth=0, relief="flat", font=(self.ui, 10), indent=16)
        s.layout("Flat.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.map("Flat.Treeview", background=[("selected", C["soft"])], foreground=[("selected", C["accent"])])
        s.configure("Syntax.Treeview", background=C["bg"], fieldbackground=C["bg"], foreground=C["text"], rowheight=28,
                    borderwidth=0, font=(self.ui, 10))
        s.layout("Syntax.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.map("Syntax.Treeview", background=[("selected", C["bg"])], foreground=[("selected", C["text"])])
        for orient in ("Vertical", "Horizontal"):
            name = f"{orient}.TScrollbar"
            s.layout(name, [(f"{orient}.Scrollbar.trough", {"sticky": "nswe", "children": [
                (f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            s.configure(name, troughcolor=C["bg"], background=C["thumb"], bordercolor=C["bg"], lightcolor=C["thumb"],
                        darkcolor=C["thumb"], gripcount=0, width=5, arrowsize=9, relief="flat")
            s.map(name, background=[("active", C["thumb_h"])])
        s.configure("TCombobox", fieldbackground=C["bg"], background=C["bg"], bordercolor=C["line"], arrowsize=12,
                    lightcolor=C["bg"], darkcolor=C["bg"], padding=3, foreground=C["text"])
        s.map("TCombobox", fieldbackground=[("readonly", C["bg"])], foreground=[("readonly", C["text"])])
        for opt, val in (("background", C["bg"]), ("foreground", C["text"]), ("selectBackground", C["soft"]), ("selectForeground", C["accent"])):
            self.root.option_add(f"*TCombobox*Listbox.{opt}", val)

    # ------------------------------------------------------------ 메뉴줄 (조플린: 파일 편집 보기 이동 도구 도움말)
    def build_menu(self):
        mb = tk.Menu(self.root)
        self.v = {k: tk.BooleanVar(value=self.show[k]) for k in self.show}
        self.v_mode = tk.StringVar(value=self.mode)
        act = lambda a: (lambda: self.run_action(a))  # noqa: E731

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("새 노트"), accelerator="Ctrl+N", command=self.new_note)
        m.add_command(label=tr("새 노트북"), accelerator="Ctrl+Shift+N", command=self.add_notebook)
        m.add_command(label=tr("새 하위 노트북"), command=self.add_subnotebook)
        m.add_separator()
        m.add_command(label=tr("폴더 가져오기…"), command=lambda: self.show_options("imports"))
        m.add_separator()
        m.add_command(label=tr("휴지통"), command=lambda: self.go_nb(TRASH))
        m.add_separator()
        m.add_command(label=tr("종료"), accelerator="Alt+F4", command=self.quit)
        mb.add_cascade(label=tr("파일"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("실행 취소"), accelerator="Ctrl+Z", command=lambda: self.text_do("edit_undo"))
        m.add_command(label=tr("다시 실행"), accelerator="Ctrl+Y", command=lambda: self.text_do("edit_redo"))
        m.add_separator()
        m.add_command(label=tr("잘라내기"), accelerator="Ctrl+X", command=lambda: self.text.event_generate("<<Cut>>"))
        m.add_command(label=tr("복사"), accelerator="Ctrl+C", command=lambda: self.text.event_generate("<<Copy>>"))
        m.add_command(label=tr("붙여넣기"), accelerator="Ctrl+V", command=lambda: self.text.event_generate("<<Paste>>"))
        m.add_command(label=tr("모두 선택"), accelerator="Ctrl+A", command=lambda: (self.text.tag_add("sel", "1.0", "end-1c"), self.text.focus_set()))
        m.add_separator()
        m.add_command(label=tr("굵게"), accelerator="Ctrl+B", command=act(("wrap", "b")))
        m.add_command(label=tr("기울임꼴"), accelerator="Ctrl+I", command=act(("wrap", "i")))
        m.add_command(label=tr("취소선"), command=act(("wrap", "s")))
        m.add_command(label=tr("링크 만들기"), accelerator="Ctrl+K", command=act(("wrap", "link")))
        m.add_command(label=tr("코드"), command=act(("wrap", "code")))
        m.add_separator()
        m.add_command(label=tr("번호 매기기 목록"), command=act(("line", "ol")))
        m.add_command(label=tr("글머리 기호 목록"), command=act(("line", "ul")))
        m.add_command(label=tr("인용"), command=act(("line", "quote")))
        h = tk.Menu(m, tearoff=0)
        for lv in (1, 2, 3, 4):
            h.add_command(label=tr("제목 {n}").format(n=lv), command=act(("heading", lv)))
        h.add_command(label=tr("본문"), command=act(("heading", 0)))
        m.add_cascade(label=tr("제목"), menu=h)
        m.add_command(label=tr("가로줄"), command=act(("block", "hr")))
        m.add_command(label=tr("표"), command=act(("block", "table")))
        m.add_command(label=tr("코드 블록"), command=act(("block", "codeblock")))
        m.add_command(label=tr("날짜 및 시간 삽입"), accelerator="Ctrl+Shift+T", command=self.insert_datetime)
        m.add_separator()
        m.add_command(label=tr("문서에서 찾기"), accelerator="Ctrl+F", command=lambda: self.cur and self.show_find())
        m.add_command(label=tr("모든 파일에서 검색"), accelerator="Ctrl+Shift+F", command=self.focus_search)
        m.add_separator()
        m.add_command(label=tr("노트 속성…"), command=self.show_properties)
        m.add_command(label=tr("노트 버전…"), command=self.show_versions)
        m.add_command(label=tr("비슷한 노트 찾기…"), command=self.show_similar)
        mb.add_cascade(label=tr("편집"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_checkbutton(label=tr("노트북 보기"), variable=self.v["notebooks"], command=self.on_view_toggle)
        m.add_checkbutton(label=tr("태그 보기"), variable=self.v["tags"], command=self.on_view_toggle)
        m.add_checkbutton(label=tr("노트 목록 보기"), accelerator="Ctrl+Shift+L", variable=self.v["list"], command=self.on_view_toggle)
        m.add_checkbutton(label=tr("문법 해설 보기"), accelerator="Ctrl+/", variable=self.v["syntax"], command=self.on_view_toggle)
        m.add_separator()
        for key, label in (("edit", tr("마크다운만")), ("split", tr("마크다운 + 렌더링")), ("view", tr("렌더링만"))):
            m.add_radiobutton(label=label, value=key, variable=self.v_mode, command=lambda k=key: self.set_mode(k))
        m.add_command(label=tr("편집기 레이아웃 전환"), accelerator="Ctrl+L", command=lambda: self.cur and self.cycle_mode())
        mb.add_cascade(label=tr("보기"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("뒤로"), accelerator="Ctrl+-", command=lambda: self.go(-1))
        m.add_command(label=tr("앞으로"), accelerator="Ctrl++", command=lambda: self.go(1))
        mb.add_cascade(label=tr("이동"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("복원 지점…"), command=self.show_snapshots)
        m.add_command(label=tr("전체 변경 이력…"), command=self.show_journal)
        m.add_separator()
        m.add_command(label=tr("중복 노트 찾기…"), command=self.show_duplicates)
        m.add_command(label=tr("스크랩 군더더기 정리…"), command=self.show_cleanup)
        m.add_command(label=tr("안 쓰는 미디어 파일 정리…"), command=self.show_unused_media)
        mb.add_cascade(label=tr("도구"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("옵션…"), accelerator="Ctrl+,", command=lambda: self.show_options("general"))
        m.add_separator()
        m.add_command(label=tr("폴더 설정… (노트·리소스 폴더)"), command=lambda: self.show_options("folders"))
        m.add_separator()
        m.add_command(label=tr("글꼴·크기…"), command=lambda: self.show_options("fonts"))
        m.add_command(label=tr("테마·색상…"), command=lambda: self.show_options("theme"))
        m.add_command(label=tr("노트 버전 설정…"), command=lambda: self.show_options("versions"))
        m.add_command(label=tr("동기화 설정…"), command=lambda: self.show_options("sync"))
        m.add_command(label=tr("웹 클리퍼 설정…"), command=lambda: self.show_options("clipper"))
        mb.add_cascade(label=tr("설정"), menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label=tr("사용 설명서 (GitHub)…"), accelerator="F1", command=self.open_manual)
        m.add_command(label=tr("검색 문법"), command=self.help_search)
        m.add_command(label=tr("안드로이드 앱 내려받기 (APK)…"), command=lambda: webbrowser.open(self.ANDROID_URL))
        m.add_command(label=tr("오픈소스 라이선스…"), command=self.show_licenses)
        m.add_separator()
        m.add_command(label=tr("업데이트 확인…"), command=self.check_update)
        m.add_command(label=tr("{app} 정보 (버전 {v})").format(app=APP, v=VERSION), command=lambda: messagebox.showinfo(
            APP, f"{APP} {VERSION}\n\n" + tr("위키나루 기반 마크다운 노트 앱\n노트는 .md 파일로 저장됩니다.\n\n저장 폴더: ") + self.store.root
            + "\n\nhttps://github.com/" + updater.REPO, parent=self.root))
        mb.add_cascade(label=tr("도움말"), menu=m)

        self.root.config(menu=mb)

    # ------------------------------------------------------------ 도구: 중복 노트 · 스크랩 군더더기
    def tool_window(self, title, size="900x580", native=False):
        """native=True 면 메인 창에 딸린 창(transient)이 아니라 독립 창으로 만든다 → 제목줄 오른쪽 위에 최소화·최대화·닫기 아이콘이 생긴다"""
        top = tk.Toplevel(self.root)
        top.title(title)
        top.configure(bg=C["bg"])
        if not native:
            top.transient(self.root)
        top.geometry(f"{size}+{self.root.winfo_x() + 80}+{self.root.winfo_y() + 50}")
        top.minsize(640, 400)
        return top

    def open_path_note(self, path):
        """경로로 노트를 찾아 메인 창에서 연다"""
        n = next((x for x in self.all_notes if x["path"] == path), None)
        if n:
            self.open_note(n)
        return n

    def run_task(self, title, work, done, text=tr("노트를 읽는 중…"), cancellable=True):
        """오래 걸리는 일을 뒤에서 돌리고 진행 창을 보여 준다(work(progress, cancelled) → 결과). 끝나면 done(결과). 취소하면 done 은 부르지 않는다."""
        self.flush()
        top = self.tool_window(title, "420x150")
        msg = tk.Label(top, text=text, bg=C["bg"], fg=C["text"], font=(self.ui, 10), pady=24)
        msg.pack()
        state = {"cancel": False, "prog": (0, 0, None)}
        q = queue.Queue()

        def stop():
            state["cancel"] = True
            top.destroy()
        if cancellable:
            top.protocol("WM_DELETE_WINDOW", stop)
            Btn(top, tr("취소"), stop, padx=14, pady=3).pack()
        else:   # 중간에 멈추면 안 되는 작업(파일 옮기기·링크 고치기)
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            top.grab_set()

        def job():
            try:
                q.put(("ok", work(lambda d, t, phase=None: state.update(prog=(d, t, phase)), lambda: state["cancel"])))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=job, daemon=True).start()

        def poll():
            if state["cancel"]:
                return
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                d, t, phase = state["prog"]
                msg.config(text=f"{phase or text} {d:,} / {t:,}" if t else text)
                return top.after(100, poll)
            top.destroy()
            if kind == "err":
                return messagebox.showerror(APP, val, parent=self.root)
            done(val)
        poll()

    def scan_notes(self, title, work, done):
        """모든 노트를 뒤에서 훑는다(work(notes, progress, cancelled) → 결과). 끝나면 done(결과). 취소 가능."""
        self.flush()
        notes = list(self.all_notes)
        self.run_task(title, lambda prog, cancel: work(notes, prog, cancel), done)

    # ------------------------------------------------------------ 복원 지점
    def snap_cfg(self):
        c = st.read_config()
        return {"auto": bool(c.get("snap_auto", True)), "count": max(1, int(c.get("snap_count", sn.KEEP_COUNT))),
                "days": max(0, int(c.get("snap_days", sn.KEEP_DAYS)))}

    def checkpoint(self, label, then):
        """큰 작업 직전에 복원 지점을 만들고(바뀐 게 없으면 바로) then() 을 부른다. 취소하면 then 은 부르지 않는다."""
        self.run_task(tr("복원 지점 만드는 중"), lambda prog, cancel: self.snap.create(label, prog, cancel), lambda pid: then(),
                      text=tr('"{0}" 복원 지점을 만드는 중… (처음 한 번은 오래 걸립니다)').format(label))

    def auto_snapshot(self):
        """시작한 뒤 한참 있다가: 마지막 복원 지점이 하루 넘었으면 조용히 하나 만들고 오래된 것을 정리한다"""
        cfg = self.snap_cfg()
        if not cfg["auto"]:
            return
        pts = self.snap.points()
        if pts and time.time() - pts[0]["created"] < 20 * 3600:
            return
        q = queue.Queue()

        def job():
            try:
                self.snap.create(tr("자동"))
                self.snap.prune(cfg["count"], cfg["days"])
                q.put("ok")
            except Exception as ex:  # noqa: BLE001
                q.put("err")
        threading.Thread(target=job, daemon=True).start()

        def poll():
            try:
                r = q.get_nowait()
            except queue.Empty:
                return self.root.after(1000, poll)
            if r == "ok":
                self.status.config(text=tr("복원 지점을 만들었습니다."))
        poll()

    def trash_notes(self, paths):
        """휴지통으로 보내고 목록을 새로 읽는다 → 보낸 개수"""
        cur_path = self.cur["path"] if self.cur else None
        if cur_path in paths:
            if self.save_job:
                self.root.after_cancel(self.save_job)
                self.save_job = None
            self.dirty = False
            self.close_note()
        else:
            self.flush()
        done = 0
        for p in paths:
            try:
                self.store.delete_note(p)
                done += 1
            except OSError:
                pass
        self.multi.clear()
        self.reload_notes(keep_scroll=True)   # 지운 뒤에도 보던 자리를 유지
        return done

    def go_nb(self, key):
        """노트북 목록의 항목(휴지통 등)으로 옮겨 간다"""
        self.flush()
        self.nb = key
        self.close_note()
        self.reload_notes()

    def show_duplicates(self):
        """도구 > 중복 노트 찾기: 같은 원본 주소 · 같은 본문 · 같은 제목에 비슷한 본문을 묶어 보여 주고, 골라서 휴지통으로"""
        self.scan_notes(tr("중복 노트 찾기"), lambda notes, prog, cancel: cleanup.find_duplicates(notes, prog, cancel), self.duplicates_dialog)

    def show_similar(self):
        """편집 > 비슷한 노트 찾기: 열어 둔 노트와 쓰인 낱말이 비슷한 노트를 색인된 본문에서 찾아 보여 준다(See Also)"""
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, tr("먼저 노트를 여세요.") if not self.cur else tr("가져온 파일은 아직 지원하지 않습니다(노트만)."), parent=self.root)
        self.flush()
        n = self.cur
        key, body = self.store.key_of(n["path"]), n["body"]

        def done(res):
            top = self.tool_window(tr("비슷한 노트 — ") + n["title"], "700x520")
            if not res:
                tk.Label(top, text=tr("비슷한 노트를 찾지 못했습니다(글이 너무 짧거나 흔한 낱말뿐일 수 있습니다)."), bg=C["bg"], fg=C["muted"],
                         font=(self.ui, 10), padx=16, pady=20).pack(fill="x")
                return
            tk.Label(top, text=tr("열어 둔 노트에서 자주 나오면서 흔하지 않은 낱말을 다른 노트 본문에서 찾은 결과입니다. 더블클릭하면 그 노트를 엽니다."),
                     bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
            wrap = tk.Frame(top, bg=C["bg"])
            wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))
            tv = ttk.Treeview(wrap, columns=("title", "nb", "hit"), show="headings", selectmode="browse")
            for col, text, w, stretch in (("title", tr("노트"), 380, True), ("nb", tr("노트북"), 170, False), ("hit", tr("겹친 낱말"), 90, False)):
                tv.heading(col, text=text)
                tv.column(col, width=w, stretch=stretch, anchor="e" if col == "hit" else "w")
            sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
            tv.config(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            tv.pack(side="left", fill="both", expand=True)
            by_key = {x["key"]: x for x in self.all_notes}
            for k, hit, tot in res:
                m = by_key.get(k)
                if m:
                    tv.insert("", "end", iid=k, values=(m["title"], self.nb_label(m["nb"]), f"{hit}/{tot}"))

            def open_sel(e=None):
                sel = tv.selection()
                if sel and sel[0] in by_key:
                    self.open_note(by_key[sel[0]])
            tv.bind("<Double-1>", open_sel)
            tv.bind("<Return>", open_sel)
        self.run_task(tr("비슷한 노트 찾기"), lambda prog, cancel: similar.find(self.store, key, body, 40, prog, cancel), done, text=tr("비슷한 노트를 찾는 중…"))

    def show_unused_media(self):
        """도구 > 안 쓰는 미디어 파일 정리: 어떤 노트도 가리키지 않는 그림·첨부를 찾아 한꺼번에 휴지통으로"""
        self.scan_notes(tr("안 쓰는 미디어 파일 찾기"), lambda notes, prog, cancel: cleanup.unused_media(self.store, notes, prog, cancel), self.unused_media_dialog)

    def unused_media_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, tr("안 쓰는 미디어 파일이 없습니다."), parent=self.root)
        total = sum(s for _, s in found)
        top = self.tool_window(tr('안 쓰는 미디어 파일 — {0:,}개').format(len(found)), "760x520", native=True)

        def mb(n):
            return f"{n / 1048576:,.1f}MB" if n >= 1048576 else f"{n / 1024:,.0f}KB"
        tk.Label(top, text=tr('어떤 노트도 가리키지 않는 파일 {0:,}개 ({1}). 휴지통으로 보내면 {2}일 동안 복원할 수 있습니다.\n(노트의 이전 버전 기록이 가리키는 그림은 확인하지 않으므로, 오래된 버전으로 되돌릴 때 그림이 빠질 수 있습니다.)').format(len(found), mb(total), self.store.trash_days),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=lb.xview)
        lb.config(yscrollcommand=autohide(sb, lb), xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        lb.pack(side="left", fill="both", expand=True)
        for p, s in found:
            lb.insert("end", f"{os.path.relpath(p, self.store.media_dir)}   {mb(s)}")

        def open_sel(e=None):
            sel = lb.curselection()
            if sel:
                self.reveal_file(found[sel[0]][0])

        def trash(items):
            if not items:
                return messagebox.showinfo(APP, tr("먼저 파일을 고르세요."), parent=top)
            if not messagebox.askyesno(APP, tr('{0:,}개 파일을 휴지통으로 보낼까요?').format(len(items)), parent=top):
                return
            try:
                n = self.store.trash_files([p for p, _ in items], self.store.media_dir)
            except OSError as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            top.destroy()
            messagebox.showinfo(APP, tr('{0:,}개 파일을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)').format(n), parent=self.root)
        def open_one(e=None):   # 파일 하나를 누르면 그 파일을 연다(그림·영상 등 보는 파일만. 나머지는 폴더에서 위치만 보여 준다)
            sel = lb.curselection()
            if len(sel) != 1:
                return
            p = found[sel[0]][0]
            if sys.platform == "win32" and os.path.splitext(p)[1].lower() in VIEWABLE:
                os.startfile(p)
            else:
                self.reveal_file(p)
        lb.bind("<<ListboxSelect>>", open_one)
        Btn(btns, tr("모두 휴지통으로"), lambda: trash(list(found)), kind="danger", padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고, 열기·위치 열기·휴지통 메뉴를 띄운다
            i = lb.nearest(e.y)
            if 0 <= i < lb.size() and i not in lb.curselection():
                lb.selection_clear(0, "end")
                lb.selection_set(i)
            sel = list(lb.curselection())
            one = len(sel) == 1
            menu.delete(0, "end")
            menu.add_command(label=tr("파일 열기"), command=open_one, state="normal" if one else "disabled")
            menu.add_command(label=tr("파일 위치 열기"), command=open_sel, state="normal" if sel else "disabled")
            menu.add_command(label=tr('휴지통으로 보내기 ({0}개)').format(len(sel)) if len(sel) > 1 else tr("휴지통으로 보내기"),
                             command=lambda: trash([found[k] for k in lb.curselection()]), state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        lb.bind("<Button-3>", on_menu)

    def show_cleanup(self):
        """도구 > 스크랩 군더더기 정리: 노트마다 지울 줄을 미리 보여 주고, 골라서 적용(적용 전 내용은 노트 버전으로 남는다)"""
        self.cleanup_options()

    def cleanup_cfg(self):
        c = st.read_config().get("cleanup", {})
        try:
            ratio = min(100, max(5, int(c.get("ratio", round(cleanup.DEFAULT_RATIO * 100)))))
            docs = min(200, max(2, int(c.get("min_docs", cleanup.DEFAULT_MIN_DOCS))))
        except (TypeError, ValueError):
            ratio, docs = round(cleanup.DEFAULT_RATIO * 100), cleanup.DEFAULT_MIN_DOCS
        return {"ratio": ratio, "min_docs": docs, "keep": [k for k in c.get("keep", []) if isinstance(k, str)]}

    def cleanup_options(self):
        """군더더기 찾기 전에 기준을 고른다: 사이트 공통 줄로 볼 비율·최소 노트 수, 지우지 않기로 한 줄 목록"""
        cfg = self.cleanup_cfg()
        top = self.tool_window(tr("스크랩 군더더기 정리 — 기준"), "560x470", native=True)
        tk.Label(top, text=tr("같은 사이트에서 스크랩한 노트 여럿에 똑같이 나오는 줄(메뉴·머리글·바닥글)을 군더더기로 봅니다. 기준을 높이면 덜 지우고, 낮추면 더 지웁니다.\n"
                           "찾은 뒤 미리 보기에서 지우기 싫은 줄을 오른쪽 클릭해 \"이 줄은 지우지 않기\" 를 고르면 아래 목록에 쌓입니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=520, padx=16, pady=10).pack(fill="x")
        f = tk.Frame(top, bg=C["bg"])
        f.pack(fill="x", padx=16)
        ratio = tk.IntVar(value=cfg["ratio"])
        docs = tk.IntVar(value=cfg["min_docs"])
        tk.Label(f, text=tr("사이트 노트의"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=0, column=0, sticky="w")
        tk.Spinbox(f, from_=5, to=100, increment=5, width=4, textvariable=ratio, font=(self.ui, 10)).grid(row=0, column=1, padx=4)
        tk.Label(f, text=tr("% 이상에 나오는 줄 (기본 30)"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=0, column=2, sticky="w")
        tk.Label(f, text=tr("그리고 최소"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=1, column=0, sticky="w", pady=6)
        tk.Spinbox(f, from_=2, to=200, width=4, textvariable=docs, font=(self.ui, 10)).grid(row=1, column=1, padx=4)
        tk.Label(f, text=tr("개 노트에 나와야 함 (기본 4)"), bg=C["bg"], fg=C["text"], font=(self.ui, 10)).grid(row=1, column=2, sticky="w")
        tk.Label(top, text=tr("지우지 않기로 한 줄"), bg=C["bg"], fg=C["text"], font=(self.ui, 10, "bold"), anchor="w", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=16)
        lb = tk.Listbox(wrap, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lb.pack(fill="both", expand=True, padx=6, pady=6)
        keep = list(cfg["keep"])
        for k in keep:
            lb.insert("end", k)

        def drop():
            for i in reversed(lb.curselection()):
                lb.delete(i)
                del keep[i]

        def save():
            try:
                r, d = int(ratio.get()), int(docs.get())
            except (tk.TclError, ValueError):
                r, d = cfg["ratio"], cfg["min_docs"]
            c = {"ratio": min(100, max(5, r)), "min_docs": min(200, max(2, d)), "keep": keep}
            st.write_config(cleanup=c)
            return c

        def go():
            c = save()
            top.destroy()
            self.cleanup_scan(c)
        Btn(btns, tr("군더더기 찾기"), go, kind="primary", bold=True, padx=16).pack(side="right")
        Btn(btns, tr("닫기"), lambda: (save(), top.destroy()), padx=14).pack(side="right", padx=6)
        Btn(btns, tr("고른 줄 목록에서 빼기"), drop, padx=12).pack(side="left")

    def cleanup_scan(self, c):
        opts = {"ratio": c["ratio"] / 100, "min_docs": c["min_docs"], "keep": c["keep"]}
        self.scan_notes(tr("스크랩 군더더기 찾기"), lambda notes, prog, cancel: cleanup.scan_junk(notes, prog, cancel, opts), self.cleanup_dialog)

    def check_update(self):
        """GitHub 의 최신 릴리스를 확인하고, 새 버전이면 내려받아 exe 를 바꾸고 다시 시작한다(소스로 실행 중이면 릴리스 페이지만 안내)"""
        self.run_task(tr("업데이트 확인"), lambda prog, cancel: updater.latest(), self.update_found, text=tr("최신 버전을 확인하는 중…"))

    def update_found(self, rel):
        if not updater.is_newer(rel["tag"], VERSION):
            return messagebox.showinfo(APP, tr('최신 버전입니다.\n현재 {0}, 최신 릴리스 {1}').format(VERSION, rel['tag']), parent=self.root)
        news = updater.whats_new(rel["body"])
        head = tr('새 버전 {0} 이 나왔습니다. (현재 {1})\n\n{2}\n\n').format(rel['tag'], VERSION, news)
        if not (ed.FROZEN and rel["asset_url"] and rel["sha"]):   # 소스로 실행 중이거나 자동으로 바꿀 파일이 없으면 페이지만
            why = tr("소스로 실행 중이라 자동으로 바꾸지 않습니다. ") if not ed.FROZEN else ""
            if messagebox.askyesno(APP, head + why + tr("릴리스 페이지를 열까요?"), parent=self.root):
                webbrowser.open(rel["url"])
            return
        ans = messagebox.askyesnocancel(
            APP, head + tr("예: 지금 업데이트(내려받아 바꾸고 자동으로 다시 시작)\n아니오: 릴리스 페이지 열기\n취소: 나중에"), parent=self.root)
        if ans is None:
            return
        if not ans:
            return webbrowser.open(rel["url"])
        self.run_task(tr("업데이트 내려받기"), lambda prog, cancel: updater.download(rel, prog, cancel), self.update_downloaded,
                      text=tr('{0} 을 내려받는 중… (KB)').format(rel['tag']))

    def update_downloaded(self, path):
        if not path:
            return
        self.flush()
        try:
            updater.apply(path)
        except OSError as ex:
            return messagebox.showerror(APP, tr('업데이트를 시작하지 못했습니다.\n{0}').format(ex), parent=self.root)
        self.quit()   # 앱이 끝나야 실행 파일이 풀려서 바뀐다. 바뀐 뒤 새 버전이 자동으로 다시 시작된다.

    MANUAL_URL = "https://github.com/iamtalker/iamtalkernote/blob/main/docs/manual.md"

    ANDROID_URL = "https://github.com/iamtalker/iamtalkernote-android/releases/latest"   # 폰 앱(APK) 최신 릴리스

    def open_manual(self):
        """도움말 → 사용 설명서(F1): GitHub 의 설명서 문서를 기본 브라우저로 연다"""
        webbrowser.open(self.MANUAL_URL)

    def help_search(self):
        messagebox.showinfo(tr("검색 문법"), tr("공백 = AND\n회의록 AND (예산 OR 일정) NOT 취소\n\"정확한 구절\"\n"
                            "& | ! 기호도 AND OR NOT 으로 쓸 수 있습니다(대문자만 연산자로 인식).\n\n"
                            "기간: date:20101011-20240104 만화&아이유  → 그 기간에 고친(생성순이면 만든) 글 중 만화와 아이유가 함께 든 글\n"
                            "   date:20240101(그 날) · date:202401(그 달) · date:2024(그 해) · date:20240101-(그날부터) · date:-20240104(그날까지)\n"
                            "   날짜:·기간: 으로 써도 됩니다. 아래 '기간' 칸과 함께 쓰면 겹치는 부분만 찾습니다.\n\n"
                            "태그는 본문의 #태그, 또는 '태그: a, b' 줄에서 모읍니다."), parent=self.root)

    def text_do(self, name):
        try:
            getattr(self.text, name)()
        except tk.TclError:
            pass

    def focus_search(self):
        if not self.show["list"]:
            self.v["list"].set(True)
            self.on_view_toggle()
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def insert_datetime(self):
        if self.cur:
            self.text.insert("insert", time.strftime("%Y-%m-%d %H:%M"))
            self.text.focus_set()

    # ------------------------------------------------------------ 화면 만들기
    def build(self):
        self.pane = tk.PanedWindow(self.root, orient="horizontal", sashwidth=4, sashrelief="flat", bg=C["line"], bd=0)
        self.pane.pack(fill="both", expand=True)
        self.widths = {"left": 230, "list": 360, "syntax": 300}
        nbh = st.read_config().get("window", {}).get("nb_h")
        if not getattr(self, "nb_h", 0):   # 노트북·태그 사이 경계 높이(테마를 바꿔 다시 만들 때는 지금 값을 유지)
            self.nb_h = nbh if isinstance(nbh, int) and 90 <= nbh <= 3000 else 0
        for k, v in st.read_config().get("window", {}).get("widths", {}).items():
            if k in self.widths and isinstance(v, int) and 100 <= v <= 8000:
                self.widths[k] = v
        self.build_left()
        self.build_list()
        self.build_editor()
        self.build_sidebar()
        if getattr(self, "lang_btn", None):
            self.lang_btn.destroy()
        self.lang_btn = LangButton(self.root, self.set_language, C, (self.ui, 8))   # 오른쪽 위 모서리의 언어 단추(깃발 + EN/KO)

    def on_view_toggle(self):
        for k, var in self.v.items():
            self.show[k] = bool(var.get())
        self.save_view()
        self.relayout()
        if self.show["tags"]:
            self.reload_tags()

    def save_view(self):
        cfg = dict(self.show)
        cfg["mode"] = self.mode
        st.write_config(view=cfg)

    def relayout(self):
        """보기 설정에 맞게 칸을 다시 놓는다(폭은 사용자가 끈 그대로 둔다)."""
        managed = [str(p) for p in self.pane.panes()]
        for key, w in (("left", self.leftf), ("list", self.listf), ("syntax", self.sidebar)):
            if str(w) in managed and w.winfo_width() > 1:
                self.widths[key] = max(w.winfo_width(), 150)
        for w in (self.leftf, self.listf, self.editf, self.sidebar):
            if str(w) in managed:
                self.pane.forget(w)
        if self.show["notebooks"] or self.show["tags"]:
            self.pane.add(self.leftf, minsize=150, width=self.widths["left"], stretch="never")
        if self.show["list"]:
            self.pane.add(self.listf, minsize=240, width=self.widths["list"], stretch="never")
        self.pane.add(self.editf, minsize=360, stretch="always")
        if self.show["syntax"]:
            self.pane.add(self.sidebar, minsize=220, width=self.widths["syntax"], stretch="never")
        self.capture_nb_height()
        inner = [str(p) for p in self.left_pane.panes()]
        for w in (self.nb_sec, self.tag_sec):
            if str(w) in inner:
                self.left_pane.forget(w)
        if self.show["notebooks"]:
            self.left_pane.add(self.nb_sec, minsize=90, stretch="always")
        if self.show["tags"]:
            self.left_pane.add(self.tag_sec, minsize=90, stretch="always")
        if self.show["notebooks"] and self.show["tags"] and self.nb_h:   # 노트북·태그 사이 경계를 끌어 둔 자리를 다시 켜도 유지
            self.left_pane.paneconfigure(self.nb_sec, height=self.nb_h)
            self.root.after_idle(self.place_nb_sash)

    def fit_panes(self):
        """저장해 둔 칸 너비의 합이 지금 창보다 크면(창을 줄였거나 작은 화면) 노트 칸이 최소 너비를 지키도록 목록 → 노트북 → 문법 해설 순으로 줄인다"""
        try:
            total = self.pane.winfo_width()
            if total < 300:
                return
            managed = [str(p) for p in self.pane.panes()]
            cols = [(k, w, mn) for k, w, mn in (("left", self.leftf, 150), ("list", self.listf, 240), ("syntax", self.sidebar, 220)) if str(w) in managed]
            width = {k: max(w.winfo_width(), mn) for k, w, mn in cols}
            excess = sum(width.values()) + 360 + 4 * len(cols) - total
            for k, w, mn in sorted(cols, key=lambda c: ("list", "left", "syntax").index(c[0])):
                cut = min(max(excess, 0), width[k] - mn)
                if cut > 0:
                    self.pane.paneconfigure(w, width=width[k] - cut)
                    self.widths[k] = width[k] - cut
                    excess -= cut
        except tk.TclError:
            pass

    def capture_nb_height(self):
        """노트북·태그가 같이 보이는 동안의 노트북 칸 높이를 기억"""
        try:
            inner = [str(p) for p in self.left_pane.panes()]
            if str(self.nb_sec) in inner and str(self.tag_sec) in inner and self.nb_sec.winfo_height() > 1:
                self.nb_h = self.nb_sec.winfo_height()
        except tk.TclError:
            pass

    def place_nb_sash(self, tries=0):
        """노트북·태그 사이 경계를 저장해 둔 높이에 놓는다. 창이 아직 화면에 그려지기 전(칸 높이가 작을 때)에 놓으면 값이 엉뚱하게 잘리므로, 그려질 때까지 기다린다"""
        try:
            if len(self.left_pane.panes()) == 2 and self.nb_h:
                if self.left_pane.winfo_height() < 250 and tries < 20:
                    return self.root.after(100, lambda: self.place_nb_sash(tries + 1))
                self.root.update_idletasks()
                self.left_pane.sash_place(0, 0, min(self.nb_h, max(90, self.left_pane.winfo_height() - 90)))
        except tk.TclError:
            pass

    # -- 1단: 노트북 + 태그
    def section_head(self, parent, title, action=None, clear=None):
        h = tk.Frame(parent, bg=C["bg"])
        h.pack(fill="x", padx=14, pady=(14, 4))
        lb = tk.Label(h, text=title, bg=C["bg"], fg=C["muted"], font=(self.ui, 9, "bold"))
        lb.pack(side="left")
        if clear:   # 머리글을 누르면 고른 것이 풀린다
            lb.config(cursor="hand2")
            lb.bind("<Button-1>", lambda e: clear())
            self.tip(lb, tr("누르면 고른 태그가 풀립니다"))
        if action:
            Btn(h, "＋", action, kind="ghost", bg=C["bg"], padx=6, pady=0).pack(side="right")

    def fit_count(self, tree, texts):
        """숫자 칸의 폭을 가장 긴 숫자에 맞춘다(고정 폭이면 13,902 같은 큰 수가 잘린다)"""
        f = tkfont.Font(family=self.ui, size=10)
        w = max([f.measure(t) for t in texts] + [24]) + 28
        tree.column("n", width=w, minwidth=w, stretch=False)
        tree.config(displaycolumns=())   # 숫자는 칸을 따로 두지 않고 이름 바로 뒤에 붙여 보인다(창을 늘려도 멀어지지 않게)

    def make_tree(self, parent):
        wrap = tk.Frame(parent, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        tree = ttk.Treeview(wrap, style="Flat.Treeview", columns=("n",), show="tree", selectmode="browse")
        tree.column("#0", stretch=True, width=140)
        tree.column("n", width=40, anchor="e", stretch=False)
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.config(yscrollcommand=autohide(sb, tree))
        return tree

    def build_left(self):
        f = self.leftf = tk.Frame(self.pane, bg=C["bg"])
        self.left_pane = tk.PanedWindow(f, orient="vertical", sashwidth=4, sashrelief="flat", bg=C["line"], bd=0)
        self.left_pane.pack(fill="both", expand=True)
        self.nb_sec = tk.Frame(self.left_pane, bg=C["bg"])
        self.section_head(self.nb_sec, tr("노트북"))
        self.nbtree = self.make_tree(self.nb_sec)
        self.nbtree.bind("<<TreeviewSelect>>", self.on_nb_select)
        self.nbtree.bind("<Delete>", lambda e: self.delete_notebook())
        self.nbtree.bind("<Button-3>", self.on_nb_menu)
        self.nbmenu = tk.Menu(self.root, tearoff=0)
        self.tag_sec = tk.Frame(self.left_pane, bg=C["bg"])
        self.section_head(self.tag_sec, tr("태그"), clear=self.clear_tag)
        self.tagtree = self.make_tree(self.tag_sec)
        self.tagtree.config(selectmode="extended")   # Ctrl/Shift+클릭으로 태그 여러 개를 골라 한꺼번에 이름 변경·삭제
        self.tagtree.bind("<ButtonRelease-1>", self.on_tag_click)
        self.tagtree.bind("<Button-3>", self.on_tag_menu)
        self.root_label = tk.Label(f, text="", bg=C["bg"], fg=C["muted"], font=(self.ui, 8), anchor="w", padx=14, pady=6)
        self.root_label.pack(side="bottom", fill="x", before=self.left_pane)

    # -- 2단: 검색 + 목록
    def build_list(self):
        f = self.listf = tk.Frame(self.pane, bg=C["bg"])
        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill="x", padx=14, pady=(14, 8))
        Btn(top, tr("＋ 새 노트"), self.new_note, kind="primary", bold=True, pady=6).pack(side="right", padx=(8, 0))
        Btn(top, tr("검색"), self.search_now, pady=6).pack(side="right", padx=(8, 0))   # 치는 즉시 검색하지만, 눌러서 바로 다시 검색할 수도 있다
        box = tk.Frame(top, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"])
        box.pack(side="left", fill="x", expand=True)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: (self.schedule_search(), self.update_placeholder()))
        self.search_entry = tk.Entry(box, textvariable=self.q, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                                     insertbackground=C["text"], insertwidth=2, insertborderwidth=0, insertontime=600, insertofftime=400,
                                     font=(self.ui, 10))   # 세로 막대 커서가 깜빡인다
        self.search_entry.pack(fill="x", padx=(10, 28), pady=7)
        self.clear_btn = tk.Label(box, text="×", bg=C["panel"], fg=C["muted"], font=(self.ui, 13), cursor="hand2")   # 오른쪽 끝 × : 검색 초기화
        self.clear_btn.bind("<Button-1>", lambda e: self.clear_search())
        self.clear_btn.bind("<Enter>", lambda e: self.clear_btn.config(fg=C["text"]))
        self.clear_btn.bind("<Leave>", lambda e: self.clear_btn.config(fg=C["muted"]))
        self.search_entry.bind("<Return>", self.search_now)
        self.ph =tk.Label(box, text=tr("검색"), bg=C["panel"], fg=C["muted"], font=(self.ui, 10))
        self.ph.bind("<Button-1>", lambda e: self.search_entry.focus_set())
        self.search_entry.bind("<FocusIn>", lambda e: self.update_placeholder())    # 안내 문구가 커서를 가리지 않게
        self.search_entry.bind("<FocusOut>", lambda e: self.update_placeholder())
        self.ac_init()
        bar = tk.Frame(f, bg=C["bg"])
        bar.pack(fill="x", padx=10, pady=(0, 2))
        self.sort_names = {"relevance": tr("관련도순"), "time": tr("수정순"), "ctime": tr("생성순"), "title": tr("제목순")}
        self.sort_btns = {k: Btn(bar, v, lambda k=k: self.sort_by(k), padx=6, pady=3) for k, v in self.sort_names.items()}
        self.b_date = Btn(bar, tr("기간"), self.toggle_date, padx=6, pady=3)
        for b in (*self.sort_btns.values(), self.b_date):
            b.pack(side="left", padx=1)
        # 가져온 파일의 '문서 안 글'까지 찾을지(끄면 이름·경로·태그·메모만 찾아서 빠르고 결과가 짧다). 가져온 폴더가 있을 때만 보인다
        self.v_content = tk.BooleanVar(value=self.docs.content_search)
        self.opt_row = tk.Frame(f, bg=C["bg"])      # 정렬 줄이 이미 꽉 차서 체크박스는 아래 줄에 둔다
        self.cb_content = tk.Checkbutton(self.opt_row, text=tr("문서 안 글 포함"), variable=self.v_content, command=self.on_content_toggle, relief="flat",
                                         bd=0, takefocus=False, bg=C["bg"], fg=C["sub"], activebackground=C["soft"], selectcolor=C["bg"],
                                         cursor="hand2", font=(self.ui, 9))
        self.cb_content.pack(side="left")
        self.tip(self.cb_content, tr("켜면 가져온 pdf·txt 등의 본문까지 찾고, 끄면 파일 이름·경로·태그·메모만 찾습니다"))
        b_save = Btn(bar, tr("저장"), self.save_search, padx=6, pady=3)   # 지금의 검색식·기간·태그·정렬을 '저장된 검색'으로
        b_save.pack(side="right", padx=1)
        self.tip(b_save, tr("지금의 검색을 왼쪽 '저장된 검색'에 이름을 붙여 저장합니다(스마트 폴더)"))
        self.tip(self.sort_btns["time"], tr("마지막으로 고친 시각 순 (조플린 내보내기 노트는 머리말의 updated)"))
        self.tip(self.sort_btns["ctime"], tr("만든 시각 순 (조플린 내보내기 노트는 머리말의 created)"))
        self.date_row = tk.Frame(f, bg=C["bg"])
        self.d_from, self.d_to = tk.StringVar(), tk.StringVar()
        for v in (self.d_from, self.d_to):
            v.trace_add("write", lambda *a: self.schedule_search())
        for var in (self.d_from, self.d_to):
            tk.Entry(self.date_row, textvariable=var, width=11, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                     highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"],
                     font=(self.ui, 9)).pack(side="left", padx=(14 if var is self.d_from else 4, 0), ipady=3)
            if var is self.d_from:
                tk.Label(self.date_row, text="~", bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(4, 0))
        Btn(self.date_row, tr("지우기"), lambda: (self.d_from.set(""), self.d_to.set("")), padx=8, pady=2).pack(side="left", padx=6)
        tk.Label(self.date_row, text=tr("예) 2021.01.01"), bg=C["bg"], fg=C["muted"], font=(self.ui, 8)).pack(side="left")
        self.count = tk.Label(f, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=16)
        self.count.pack(fill="x", pady=(6, 4))
        self.update_content_check()
        self.list_sep = tk.Frame(f, height=1, bg=C["line"])
        self.list_sep.pack(fill="x")
        self.folder_box = tk.Frame(f, bg=C["bg"])   # 노트북을 고르면 그 안의 하위 노트북(폴더)이 노트 목록 맨 위에 뜬다(누르면 그 노트북으로)
        self.nb_direct = {}
        body = self.list_body = tk.Frame(f, bg=C["bg"])
        body.pack(fill="both", expand=True)
        self.lst = tk.Text(body, wrap="word", cursor="arrow", relief="flat", bd=0, highlightthickness=0, bg=C["bg"],
                           fg=C["text"], font=self.fonts["base"], padx=0, pady=0, state="disabled", exportselection=False)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.lst.yview)
        hide = autohide(sb, self.lst)

        self.sb_frozen = False

        def on_scroll(lo, hi):
            if self.sb_frozen:
                return
            hide(lo, hi)
            if self.rendered < len(self.results) and (1 - float(hi)) < MORE_SCREENS * (float(hi) - float(lo)):
                self.root.after_idle(self.more_cards)
        self.lst.config(yscrollcommand=on_scroll)
        self.lst_scroll = on_scroll
        self.lst.pack(side="left", fill="both", expand=True)
        L = self.lst
        L.tag_configure("title", font=self.fonts["card"], lmargin1=18, lmargin2=18, spacing1=10, rmargin=14)
        L.tag_configure("meta", font=self.fonts["meta"], foreground=C["muted"], lmargin1=18, lmargin2=18, rmargin=14, spacing1=1)
        L.tag_configure("snip", font=self.fonts["meta"], foreground=C["sub"], lmargin1=18, lmargin2=18, rmargin=14, spacing1=3, spacing3=10)
        L.tag_configure("pad", spacing3=10)
        L.tag_configure("sep", font=("TkDefaultFont", 1), background=C["line"])
        L.tag_configure("selcard", background=C["soft"])
        L.tag_configure("hl", background=C["mark"])
        L.tag_lower("selcard")
        L.tag_raise("hl")
        L.bind("<Button-1>", self.on_list_click)
        # 목록에서는 글자 선택이 없다(여러 노트 고르기는 Shift/Ctrl+클릭). 어떤 경로(Ctrl+A·Ctrl+/·Shift+PageDown 등 Text 기본 단축키)로
        # 선택이 생겨도 바로 지우고, 혹시 보이더라도 진한 파랑이 아니라 안 보이게 한다.
        L.config(selectbackground=C["bg"], selectforeground=C["text"], inactiveselectbackground=C["bg"])
        L.bind("<<Selection>>", lambda e: L.tag_remove("sel", "1.0", "end"))
        # 끌기·더블/트리플 클릭으로 글자가 여러 카드에 걸쳐 선택되는 Text 기본 동작을 막는다(여러 개 선택은 Shift/Ctrl+클릭만)
        for seq in ("<B1-Motion>", "<Triple-Button-1>", "<Shift-B1-Motion>", "<Control-B1-Motion>"):
            L.bind(seq, lambda e: "break")
        L.bind("<Double-Button-1>", self.on_list_double)
        L.bind("<Escape>", lambda e: self.clear_multi())
        L.bind("<Delete>", lambda e: self.trash_multi() if self.multi else None)
        L.bind("<Button-3>", self.on_list_menu)
        self.listmenu = tk.Menu(self.root, tearoff=0)
        self.movemenu = tk.Menu(self.listmenu, tearoff=0)
        self.update_placeholder()

    def update_content_check(self):
        """'문서 안 글 포함' 체크박스는 가져온 폴더가 있을 때만 보인다"""
        if self.docs.folders():
            if not self.opt_row.winfo_ismapped():
                self.opt_row.pack(fill="x", padx=14, before=self.count)
        else:
            self.opt_row.pack_forget()

    def on_content_toggle(self):
        self.docs.content_search = bool(self.v_content.get())
        st.write_config(docContentSearch=self.docs.content_search)
        self.refresh()

    # -- 3단: 에디터 (제목줄 + 서식 도구줄, 조플린식)
    def tip(self, widget, text):
        """툴바 아이콘에 올리면 뜨는 말풍선(위키나루와 같은 방식)"""
        target = getattr(widget, "label", widget)
        tt = {"win": None, "job": None}

        def show():
            w = tk.Toplevel(target)
            w.wm_overrideredirect(True)
            w.wm_geometry(f"+{target.winfo_rootx() + 4}+{target.winfo_rooty() + target.winfo_height() + 4}")
            tk.Label(w, text=text, background=C["text"], foreground="white", padx=8, pady=3, font=(self.ui, 9)).pack()
            tt["win"] = w

        def enter(_):
            tt["job"] = target.after(450, show)

        def leave(_):
            if tt["job"]:
                target.after_cancel(tt["job"])
                tt["job"] = None
            if tt["win"]:
                tt["win"].destroy()
                tt["win"] = None
        target.bind("<Enter>", enter, add="+")
        target.bind("<Leave>", leave, add="+")
        target.bind("<ButtonPress>", leave, add="+")

    def pane_head(self, parent, name, badge):
        h = tk.Frame(parent, bg=C["panel"])
        h.pack(fill="x", padx=10, pady=(8, 5))
        tk.Label(h, text=name, bg=C["panel"], fg=C["text"], font=(self.ui, 10, "bold")).pack(side="left")
        tk.Label(h, text=badge, bg=C["panel"], fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=8)

    # -- 3단: 에디터 (위키나루 방식: 제목 + 보기 탭, 납작한 아이콘 툴바, 머리글이 있는 두 패널)
    def build_editor(self):
        f = self.editf = tk.Frame(self.pane, bg=C["bg"])
        self.empty = tk.Label(f, text=tr("노트를 선택하거나 새로 만드세요\nCtrl+N"), bg=C["bg"], fg=C["muted"], font=(self.ui, 11), justify="center")
        self.main = tk.Frame(f, bg=C["bg"])
        head = tk.Frame(self.main, bg=C["bg"])
        head.pack(fill="x", padx=18, pady=(14, 6))
        self.title_var = tk.StringVar()
        # 문법 체크박스(위키나루처럼): 제목줄 맨 오른쪽, 노트 속성(ⓘ) 아이콘의 오른쪽
        sb = tk.Checkbutton(head, text=tr("문법"), variable=self.v["syntax"], command=self.on_view_toggle, relief="flat", bd=0,
                            takefocus=False, bg=C["bg"], fg=C["text"], activebackground=C["soft"], selectcolor=C["bg"],
                            cursor="hand2", font=(self.ui, 10))
        sb.pack(side="right", padx=(2, 2))
        sb.bind("<Enter>", lambda e: sb.config(bg=C["soft"]), add="+")
        sb.bind("<Leave>", lambda e: sb.config(bg=C["bg"]), add="+")
        self.tip(sb, tr("문법 해설 사이드바 보이기/숨기기 (Ctrl+/)"))
        info = Btn(head, "ⓘ", self.show_properties, kind="icon", padx=8, pady=2, font=(self.ui, 13))
        info.pack(side="right", padx=(6, 0))
        self.tip(info, tr("노트 속성"))
        # 보기 탭 (좌우 분할 / 렌더링만 / 원문만)
        seg = tk.Frame(head, bg=C["line"], padx=1, pady=1)
        seg.pack(side="right", padx=(8, 0))
        self.mode_anchor = tk.Frame(head, width=0, height=0, bg=C["bg"])   # 아웃라이너 노트에서 보기 탭을 숨겼다가 같은 자리에 되돌리는 기준점
        self.mode_anchor.pack(side="right", before=seg)
        self.mode_btns = {}
        for m, label, hint in (("split", tr("좌우 분할"), tr("마크다운과 렌더링을 나란히")), ("view", tr("렌더링만"), tr("렌더링 결과만 크게")),
                               ("edit", tr("원문만"), tr("마크다운 원문만 크게(집중 편집)"))):
            b = Btn(seg, label, lambda m=m: self.set_mode(m), kind="tab", padx=9, pady=3)
            b.pack(side="left")
            self.tip(b, hint)
            self.mode_btns[m] = b
        self.mode_seg = seg
        self.doc_toggle = Btn(head, "", self.toggle_doc_view, kind="tab", padx=9, pady=3)   # 가져온 문서: 원본 미리보기 ↔ 뽑은 글(찾기). 평소엔 숨김
        self.memo_btn = Btn(head, tr("메모"), self.edit_memo, kind="tab", padx=9, pady=3)       # 가져온 문서: 메모 붙이기. 평소엔 숨김
        self.title_entry =tk.Entry(head, textvariable=self.title_var, relief="flat", bd=0, font=self.fonts["title"],
                                    bg=C["bg"], fg=C["text"], insertbackground=C["accent"], width=8)
        self.title_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.title_entry.bind("<Return>", lambda e: (self.commit_title(), self.text.focus_set()))
        self.title_entry.bind("<FocusOut>", lambda e: self.commit_title())

        tk.Frame(self.main, height=1, bg=C["line"]).pack(fill="x")
        self.statusbar = tk.Frame(self.main, bg=C["bg"])
        self.statusbar.pack(side="bottom", fill="x")
        self.status = tk.Label(self.statusbar, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=18, pady=4)
        self.status.pack(side="left")
        # 맨 아래 줄의 태그 부분: 누르면 그 자리에서 바로 태그를 고친다
        self.tagbtn = tk.Label(self.statusbar, text="", anchor="w", bg=C["bg"], fg=C["accent"], font=(self.ui, 9), cursor="hand2", pady=4)
        self.tagbtn.pack(side="left")
        self.tagbtn.bind("<Button-1>", self.edit_tags)
        self.tagbtn.bind("<Enter>", lambda e: self.tagbtn.config(font=(self.ui, 9, "underline")))
        self.tagbtn.bind("<Leave>", lambda e: self.tagbtn.config(font=(self.ui, 9)))
        self.tag_edit = None   # 태그를 고치는 중이면 그 하단 박스(tagac.TagBox)
        self.status_sep = tk.Frame(self.main, height=1, bg=C["line"])
        self.status_sep.pack(side="bottom", fill="x")
        self.body = tk.Frame(self.main, bg=C["panel"])
        self.body.pack(fill="both", expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        # 문서 안에서 찾기 막대(Ctrl+F 로 보이고 Esc 로 닫는다). 평소엔 숨겨 둔다.
        self.findbar = tk.Frame(self.main, bg=C["soft"])
        self.find_var = tk.StringVar()
        self.find_hits, self.find_i, self.find_job = [], -1, None
        tk.Label(self.findbar, text=tr("문서에서 찾기"), bg=C["soft"], fg=C["sub"], font=(self.ui, 9), padx=14).pack(side="left")
        self.find_entry = tk.Entry(self.findbar, textvariable=self.find_var, width=30, relief="flat", bg=C["bg"], fg=C["text"],
                                   insertbackground=C["accent"], highlightthickness=1, highlightbackground=C["line"],
                                   highlightcolor=C["accent"], font=(self.ui, 10))
        self.find_entry.pack(side="left", pady=5, ipady=2)
        self.find_count = tk.Label(self.findbar, text="", bg=C["soft"], fg=C["muted"], font=(self.ui, 9), padx=10, width=9, anchor="w")
        self.find_count.pack(side="left")
        for label, cmd in (("▲", lambda: self.find_step(-1)), ("▼", lambda: self.find_step(1)), ("✕", self.hide_find)):
            Btn(self.findbar, label, cmd, padx=8, pady=1).pack(side="left", padx=1)
        tk.Label(self.findbar, text=tr("Enter 다음 · Shift+Enter 이전 · Esc 닫기"), bg=C["soft"], fg=C["muted"], font=(self.ui, 8), padx=12).pack(side="left")
        self.find_var.trace_add("write", lambda *a: self.find_run())
        self.find_entry.bind("<Return>", lambda e: self.find_step(1))
        self.find_entry.bind("<Shift-Return>", lambda e: self.find_step(-1))
        self.find_entry.bind("<Escape>", lambda e: self.hide_find())
        ring = dict(highlightthickness=2, highlightbackground=C["line"], highlightcolor=C["accent"], relief="flat", bd=0)

        self.edit_frame = tk.Frame(self.body, bg=C["panel"])
        self.pane_head(self.edit_frame, tr("마크다운"), tr("편집"))
        box = tk.Frame(self.edit_frame, bg=C["panel"])
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(box, wrap="word", undo=True, maxundo=-1, font=(self.mono, self.size) + (("bold",) if self.note_bold else ()), padx=14, pady=10,
                            tabs=("1c",), bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                            selectbackground=C["sel"], selectforeground=C["text"], spacing2=3, **ring)
        sb1 = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        ed_hide = autohide(sb1, self.text)
        self._typed_at, self._ed_job = 0.0, None

        def ed_flush():
            """입력을 멈춘 뒤에 막대를 한 번만 맞춘다"""
            self._ed_job = None
            if time.time() - self._typed_at < 0.45:
                self._ed_job = self.root.after(450, ed_flush)
            else:
                ed_hide(*self.text.yview())

        def ed_scroll(lo, hi):
            """글을 치는 동안은 막대를 가만히 둔다: Tk 가 줄 높이를 늦게 계산해 글자마다 막대 크기가 출렁이기 때문"""
            if time.time() - self._typed_at < 0.45:
                if not self._ed_job:
                    self._ed_job = self.root.after(450, ed_flush)
            else:
                ed_hide(lo, hi)
        self.text.config(yscrollcommand=ed_scroll)
        self.text.bind("<Key>", lambda e: setattr(self, "_typed_at", time.time()), add="+")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<<Modified>>", self.on_modified)

        # 윈도 미리보기 처리기가 그림을 그리는 자리. 한 번 미리보기를 품은 틀은 숨겼다 다시 붙이면 화면에 안 올라오므로(Tk 의 map/unmap)
        # 숨기지 않고 항상 이 자리에 둔 채 위로 올리고(미리보기) 아래로 내린다(평소). 평소에는 편집·렌더링 칸이 그 위를 완전히 덮는다.
        self.pv_frame = tk.Frame(self.body, bg=C["bg"])
        self.pv_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.pv_frame.lower()
        self.pv_frame.bind("<Configure>", lambda e: self.pv_active and self.pv.resize(e.width, e.height))

        self.view_frame = tk.Frame(self.body, bg=C["panel"])
        self.pane_head(self.view_frame, tr("렌더링"), tr("읽기 전용"))
        box2 = self.box2 = tk.Frame(self.view_frame, bg=C["panel"])
        box2.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.ow = OutlineEditor(self.view_frame, C, self.fonts["base"], self.outline_changed, lambda: self.title_var.get())   # 아웃라이너 폴더 노트용
        self._outl_on, self._outl_path = False, None
        self.view = tk.Text(box2, wrap="word", state="disabled", font=self.fonts["base"], padx=18, pady=12, cursor="arrow",
                            bg=C["bg"], fg=C["text"], selectbackground=C["sel"], selectforeground=C["text"], spacing2=3, **ring)
        sb2 = ttk.Scrollbar(box2, orient="vertical", command=self.view.yview)
        hide2 = autohide(sb2, self.view)
        self.view_sb_frozen = False
        self.view_scroll = lambda lo, hi: None if self.view_sb_frozen else hide2(lo, hi)
        self.view.config(yscrollcommand=self.view_scroll)
        self.view.pack(side="left", fill="both", expand=True)
        self.configure_tags()
        self.view.bind("<Button-1>", self.on_view_click)
        box2.bind("<Configure>", self.on_view_resize)
        self.view.bind("<Button-3>", self.on_view_menu)
        self._pair_side = "edit"
        for w in (self.text, self.view):
            w.tag_configure("pair", background=C["soft"])          # 좌우 분할에서 반대쪽 칸의 같은 블록 강조
            w.tag_lower("pair")
        self.text.bind("<KeyRelease>", lambda e: self.pair_later("edit"), add="+")
        self.text.bind("<ButtonRelease-1>", lambda e: self.pair_later("edit"), add="+")
        self.view.bind("<ButtonRelease-1>", lambda e: self.pair_later("view"), add="+")
        self.view.bind("<Control-z>", lambda e: (self.text_do("edit_undo"), self.render(), "break")[2])   # 렌더링만 볼 때도 되돌리기(우클릭 → 삭제를 되돌림)
        self.text.bind("<Button-3>", self.on_text_menu)
        self.wiki_pop = None   # [[ 를 치는 동안 뜨는 노트 제목 후보 목록
        self.text.bind("<KeyRelease>", self.wiki_typed, add="+")
        for key, step in (("Down", 1), ("Up", -1)):
            self.text.bind(f"<{key}>", lambda e, d=step: self.wiki_move(d), add="+")
        for key in ("Return", "Tab"):
            self.text.bind(f"<{key}>", lambda e: self.wiki_pick(), add="+")
        self.text.bind("<Escape>", lambda e: self.wiki_close(True), add="+")
        self.text.bind("<FocusOut>", lambda e: self.wiki_close(), add="+")
        self.show_empty(True)

    def show_empty(self, on):
        if on:
            self.main.pack_forget()
            if self.trash_view is not None:
                self.trash_view.destroy()
                self.trash_view = None
            if self.nb == CAL and self.feat["cal"]:        # 달력·할일을 골랐으면 노트 자리에 달력과 할일
                self.empty.pack_forget()
                if self.planner_view is None:
                    self.planner_view = PlannerView(self.editf, C, self.ui, self.planner, self.planner_cfg,
                                                   lambda k, v: st.write_config(**{"cal_" + k: v}), self.planner_changed)
                self.planner_view.refresh()
                self.planner_view.pack(fill="both", expand=True)
            else:
                if self.planner_view is not None:
                    self.planner_view.pack_forget()
                self.empty.pack(fill="both", expand=True)
        else:
            self.empty.pack_forget()
            if self.planner_view is not None:
                self.planner_view.pack_forget()
            if self.trash_view is not None:
                self.trash_view.destroy()
                self.trash_view = None
            self.main.pack(fill="both", expand=True)

    def planner_changed(self):
        """달력·할일을 고친 뒤: 새로 생기거나 바뀐 달력 파일이 노트 목록에 보이게 잠시 뒤 목록을 다시 읽는다(연달아 고치면 한 번만)"""
        if getattr(self, "_pl_job", None):
            self.root.after_cancel(self._pl_job)
        self._pl_job = self.root.after(1200, lambda: self.nb == CAL and self.reload_notes(keep_scroll=True))

    def planner_cfg(self):
        c = st.read_config()
        num = lambda k: int(float(c.get(k) or 0))  # noqa: E731
        try:
            return {"gongsu": bool(c.get("cal_gongsu", False)), "wage": num("cal_wage"), "meal": num("cal_meal"), "hide_done": bool(c.get("cal_hide_done", False))}
        except (TypeError, ValueError):
            return {"gongsu": bool(c.get("cal_gongsu", False)), "wage": 0, "meal": 0, "hide_done": bool(c.get("cal_hide_done", False))}

    def sync_holidays(self, force=False):
        """구글 달력의 공개 '대한민국의 휴일'(로그인 필요 없음)을 뒤에서 받아 달력에 쓴다. 한 달에 한 번, 못 받으면 내장 표를 쓴다"""
        if not self.feat["cal"] or not st.read_config().get("cal_google", True):
            return
        today = pm.iso(__import__("datetime").date.today())
        if not force and not self.planner.google_stale(today):
            return
        q = queue.Queue()

        def work():
            try:
                q.put(pm.fetch_google())
            except Exception:  # noqa: BLE001  (오프라인 등: 내장 표로 계속)
                q.put(None)
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                days = q.get_nowait()
            except queue.Empty:
                return self.root.after(400, poll)
            if days:
                self.planner.set_google(days, today)
                if self.planner_view is not None:
                    self.planner_view.refresh()
        poll()

    def check_due(self):
        """달력의 할일이 그날(또는 지난 날짜)이 되면 알린다: 앱 안에 잠깐 뜨는 알림(하루에 한 번). 10분마다 확인"""
        self.root.after(600000, self.check_due)
        if not self.feat["cal"]:
            return
        today = pm.iso(__import__("datetime").date.today())
        due = self.planner.due(today)
        if due:
            for t in due:
                self.planner.mark_notified(t["id"], today)
            self.toast(tr("오늘 할일\n") + "\n".join("· " + t["text"] for t in due[:5]) + (tr('\n… 외 {0}개').format(len(due) - 5) if len(due) > 5 else ""))
            if self.planner_view is not None:
                self.planner_view.refresh()

    def toast(self, text, ms=8000):
        """화면 오른쪽 아래에 잠깐 뜨는 알림 창(누르면 닫힘)"""
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        lb = tk.Label(top, text=text, justify="left", bg=C["text"], fg=C["bg"], font=(self.ui, 10), padx=16, pady=12, cursor="hand2")
        lb.pack()
        top.update_idletasks()
        top.geometry(f"+{top.winfo_screenwidth() - top.winfo_reqwidth() - 24}+{top.winfo_screenheight() - top.winfo_reqheight() - 70}")
        lb.bind("<Button-1>", lambda e: top.destroy())
        top.after(ms, lambda: top.winfo_exists() and top.destroy())

    def configure_tags(self):
        v, f = self.view, self.fonts
        v.tag_configure("b", font=f["b"])
        v.tag_configure("i", font=f["i"])
        v.tag_configure("bi", font=f["bi"])
        v.tag_configure("u", underline=True)
        v.tag_configure("s", overstrike=True)
        v.tag_configure("sup", offset=5, font=f["small"])
        v.tag_configure("sub", offset=-3, font=f["small"])
        v.tag_configure("code", font=f["mono"], background=C["code"])
        v.tag_configure("codeblock", font=f["mono"], background=C["code"], lmargin1=8, lmargin2=8)
        v.tag_configure("math", font=f["mono"])
        v.tag_configure("raw", font=f["mono"], foreground=C["muted"], background="#fef3c7")
        v.tag_configure("chip", foreground="#92400e", background="#fef3c7")
        v.tag_configure("muted", foreground=C["muted"])
        v.tag_configure("link", underline=True, foreground=C["accent"])
        v.tag_configure("linkmiss", foreground=C["danger"])   # 위키 링크인데 그 제목의 노트가 없음
        v.tag_configure("fnref")
        v.tag_configure("quote", foreground=C["muted"])
        v.tag_configure("hr", foreground=C["line"])
        for n in range(1, 7):
            v.tag_configure(f"h{n}", font=self.hfonts[n], spacing1=6, spacing3=2)
        for n in range(1, preview.MAX_LEVEL + 1):
            v.tag_configure(f"M{n}", lmargin1=20 * n, lmargin2=20 * n)
            v.tag_configure(f"B{n}", lmargin1=20 * (n - 1) + 6, lmargin2=20 * n)
        v.tag_raise("link")
        v.tag_raise("linkmiss")
        v.tag_raise("code")
        v.tag_bind("link", "<Enter>", lambda e: v.config(cursor="hand2"))
        v.tag_bind("link", "<Leave>", lambda e: v.config(cursor="arrow"))

    # -- 4단: 문법 해설 (위키나루)
    def build_sidebar(self):
        f = self.sidebar = tk.Frame(self.pane, bg=C["bg"])
        hd = tk.Frame(f, bg=C["bg"])
        hd.pack(fill="x", pady=(12, 0))
        close = Btn(hd, "✕", self.toggle_syntax, kind="icon", padx=8, pady=1)
        close.pack(side="right", padx=8)
        self.tip(close, tr("문법 해설 닫기 (Ctrl+/)"))
        tk.Label(hd, text=tr("문법 해설"), anchor="w", font=(self.ui, 11, "bold"), padx=16, bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Label(f, text=tr("마크다운"), anchor="w", font=(self.ui, 9), padx=16, bg=C["bg"], fg=C["muted"]).pack(fill="x", pady=(0, 8))
        tk.Label(f, text=tr("누르면 커서 자리에 넣고, 글을 고르고 누르면 감쌉니다.\nCtrl+B 굵게 · Ctrl+I 기울임 · Ctrl+K 링크"),
                 justify="left", fg=C["muted"], bg=C["bg"], font=(self.ui, 8), padx=16, pady=8, anchor="w").pack(side="bottom", fill="x")
        tk.Frame(f, height=1, bg=C["line"]).pack(side="bottom", fill="x")
        wrap = tk.Frame(f, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=(8, 0))
        self.tree = ttk.Treeview(wrap, columns=("name",), style="Syntax.Treeview", selectmode="none", show="tree")
        self.tree.column("#0", width=170, minwidth=100, stretch=True)
        self.tree.column("name", width=90, minwidth=60, stretch=False, anchor="e")
        tsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.config(yscrollcommand=autohide(tsb, self.tree))
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("group", foreground=C["accent"], font=(self.ui, 9, "bold"))
        self.tree.tag_configure("item", foreground=C["text"])
        self.tree.bind("<ButtonRelease-1>", self.on_sidebar_click)
        self.actions = {}
        group, parent = None, ""
        for g, name, example, action in syntax_entries():
            if g != group:
                group = g
                parent = self.tree.insert("", "end", text=i18n.group(g), open=True, values=("",), tags=("group",))
            shown = tr("제목 {n}").format(n=name[3:]) if name.startswith("제목 ") else tr(name)   # 이름·예시는 보이기만 한다(넣는 글은 action 이 만든다)
            self.actions[self.tree.insert(parent, "end", text=i18n.example(example), values=(shown,), tags=("item",))] = action

    def toggle_syntax(self):
        self.v["syntax"].set(not self.show["syntax"])
        self.on_view_toggle()

    def on_sidebar_click(self, e):
        action = self.actions.get(self.tree.identify_row(e.y))
        if action:
            self.run_action(action)
        self.tree.selection_remove(*self.tree.selection())

    # ------------------------------------------------------------ 노트북·태그
    def nb_label(self, key):
        """노트북 경로 → 보여 줄 이름 (하위 노트북은 '업무 › 프로젝트')"""
        if key == QUICK:
            return tr("바로가기")
        if key == TRASH:
            return tr("휴지통")
        if key == CAL:
            return tr("달력·할일")
        if key == FAVS:
            return tr("즐겨찾기")
        if key == "@docs":
            return tr("가져온 폴더")
        if key.startswith("@smart"):
            s = next((x for x in self.smart_list() if "@smart:" + x["id"] == key), None)
            return s["name"] if s else tr("저장된 검색")
        if key.startswith("@doc:"):
            f = next((f for f in self.docs.folders() if f["id"] == key[5:]), None)
            return f.get("name") or f["path"] if f else tr("가져온 폴더")
        if not key or key == ALL:
            return self.store.root_name if key == "" else tr("모든 파일")
        return " › ".join(wikiconv.markdown.md_title(p + ".md") for p in key.split("/"))

    def nb_short(self, key):
        return wikiconv.markdown.md_title(key.split("/")[-1] + ".md")

    def scope_all(self):
        """'모든 파일'이나 저장된 검색을 보는 중인가(내 노트 + 가져온 파일 전체가 범위)"""
        return self.nb == ALL or self.nb.startswith("@smart:")

    def md_nb(self):
        """새 노트·하위 노트북을 만들 노트북: 노트북이 아닌 항목(모든 파일·가져온 폴더·저장된 검색)을 보고 있으면 저장 폴더 바로 아래"""
        return "" if self.nb == ALL or self.nb.startswith("@") else self.nb

    # ---- 저장된 검색(스마트 폴더): 검색식·기간·태그·정렬을 이름 붙여 저장해 두고, 고르면 그 조건을 그대로 적용한다
    def smart_list(self):
        return [s for s in st.read_config().get("smart", []) if isinstance(s, dict) and s.get("id")]

    def save_search(self, overwrite=None):
        """지금의 검색(검색어·기간·태그·정렬)을 저장한다. overwrite 는 덮어쓸 저장된 검색의 id"""
        q, f, t, tag = self.q.get().strip(), self.d_from.get().strip(), self.d_to.get().strip(), self.tag
        if not (q or f or t or tag):
            return messagebox.showinfo(APP, tr("저장할 검색이 없습니다. 검색어나 기간, 태그를 먼저 정하세요."), parent=self.root)
        lst = self.smart_list()
        cond = {"q": q, "d_from": f, "d_to": t, "tag": tag or "", "sort": self.sort, "asc": self.asc}
        if overwrite:
            for s in lst:
                if s["id"] == overwrite:
                    s.update(cond)
            sid = overwrite
        else:
            name = simpledialog.askstring(tr("검색 저장"), tr("이 검색의 이름:"), initialvalue=q or (f"# {tag}" if tag else tr("검색")), parent=self.root)
            if not name or not name.strip():
                return
            sid = secrets.token_hex(4)
            lst.append({"id": sid, "name": name.strip(), **cond})
        st.write_config(smart=lst)
        self.nb = "@smart:" + sid
        self.reload_notebooks()
        self.status.config(text=tr("검색을 저장했습니다 (왼쪽 '저장된 검색')"))

    def open_smart(self, key):
        s = next((x for x in self.smart_list() if "@smart:" + x["id"] == key), None)
        if not s:
            return
        self.flush()
        self.close_note()
        self.nb = key
        self.tag = s.get("tag") or None
        self.sort, self.asc = (s.get("sort") if s.get("sort") in self.sort_names else "relevance"), bool(s.get("asc"))
        self.d_from.set(s.get("d_from", ""))
        self.d_to.set(s.get("d_to", ""))
        if (s.get("d_from") or s.get("d_to")) and not self.date_row.winfo_ismapped():
            self.toggle_date()
        self.q.set(s.get("q", ""))
        self.apply_loaded(self.all_notes)

    def smart_menu(self, key):
        """저장된 검색 우클릭 메뉴용: (이름 바꾸기 · 지금 검색으로 덮어쓰기 · 삭제)"""
        sid = key[7:]
        s = next((x for x in self.smart_list() if x["id"] == sid), None)
        if not s:
            return

        def rename():
            name = simpledialog.askstring(tr("이름 바꾸기"), tr("저장된 검색의 이름:"), initialvalue=s["name"], parent=self.root)
            if name and name.strip():
                lst = self.smart_list()
                for x in lst:
                    if x["id"] == sid:
                        x["name"] = name.strip()
                st.write_config(smart=lst)
                self.reload_notebooks()

        def delete():
            if not messagebox.askyesno(APP, tr('저장된 검색 「{0}」을(를) 지울까요?\n(노트와 파일은 그대로입니다)').format(s['name']), parent=self.root):
                return
            st.write_config(smart=[x for x in self.smart_list() if x["id"] != sid])
            if self.nb == key:
                self.nb = ALL
                self.apply_loaded(self.all_notes)
            else:
                self.reload_notebooks()
        return [(tr("이름 바꾸기…"), rename), (tr("지금의 검색으로 덮어쓰기"), lambda: self.save_search(overwrite=sid)), (tr("삭제"), delete)]

    def in_nb(self, n):
        """지금 고른 노트북에 속한 노트인가 (하위 노트북의 노트 포함)"""
        if self.nb == ALL:
            return True
        if self.nb in (CAL, TRASH):
            return False
        if self.nb == FAVS:
            return self.is_fav(n)
        if self.nb == "":
            return n["nb"] == ""
        return n["nb"] == self.nb or n["nb"].startswith(self.nb + "/")

    def visible_notebooks(self):
        """노트북 목록에 보일 폴더: 달력 마크다운 폴더(달력/)는 '바로가기 > 달력·할일' 로만 들어가므로 뺀다"""
        return [n for n in self.store.notebooks() if n != pm.MD_DIR and not n.startswith(pm.MD_DIR + "/")]

    def reload_notebooks(self):
        names = self.visible_notebooks()
        if OUTL not in names:
            try:
                self.store.create_notebook(OUTL)
                names = self.visible_notebooks()
            except OSError:
                pass
        dfolders = self.docs.folders()
        doc_keys = (["@docs"] + ["@doc:" + f["id"] for f in dfolders]) if dfolders else []
        smarts = self.smart_list()
        smart_keys = (["@smarts"] + ["@smart:" + s["id"] for s in smarts]) if smarts else []
        if self.nb not in (ALL, "", FAVS, QUICK, CAL, TRASH) and self.nb not in names and self.nb not in doc_keys and self.nb not in smart_keys:
            self.nb = ALL
        outl = [n for n in names if n == OUTL or n.startswith(OUTL + "/")] if self.feat["outl"] else []
        quick = ([FAVS] if self.feat["favs"] else []) + outl + ([CAL] if self.feat["cal"] else [])
        if self.nb == CAL and not self.feat["cal"]:
            self.nb = ALL
        if self.nb == FAVS and not self.feat["favs"]:
            self.nb = ALL
        self.nb_keys = [ALL] + ([QUICK] + quick if quick else []) + [""] + [n for n in names if n not in outl] + doc_keys + smart_keys + [TRASH]
        dcounts = self.docs.counts() if dfolders else {}
        direct = {}
        for n in self.all_notes:
            direct[n["nb"]] = direct.get(n["nb"], 0) + 1
        self.nb_direct = direct
        total = lambda key: sum(c for k, c in direct.items() if k == key or k.startswith(key + "/"))  # noqa: E731
        self.quiet = True
        self.nbtree.delete(*self.nbtree.get_children())
        idx = {key: i for i, key in enumerate(self.nb_keys)}
        for i, key in enumerate(self.nb_keys):
            if key == QUICK:
                label, count, parent = tr("바로가기"), None, ""
            elif key == FAVS:
                label, count, parent = tr("즐겨찾기"), sum(1 for n in self.all_notes if self.is_fav(n)), f"nb{idx[QUICK]}"
            elif key == OUTL:
                label, count, parent = tr("아웃라이너"), total(key), f"nb{idx[QUICK]}"
            elif key == TRASH:
                try:
                    n_trash = len(os.listdir(self.store.trash_dir))
                except OSError:
                    n_trash = 0
                label, count, parent = tr("🗑 휴지통"), n_trash, ""
            elif key == CAL:
                label, count, parent = tr("달력·할일"), sum(1 for t in self.planner.todos if not t["done"]), f"nb{idx[QUICK]}"
            elif key == ALL:
                label, count, parent = tr("모든 파일"), len(self.all_notes) + sum(dcounts.values()), ""   # 노트 + 가져온 문서
            elif key == "":
                label, count, parent = self.store.root_name, None, ""   # 저장 폴더 줄에는 숫자를 달지 않는다(아래 노트북들이 실제 내용)
            elif key == "@docs":
                label, count, parent = tr("가져온 폴더"), sum(dcounts.values()), ""
            elif key.startswith("@doc:"):
                label, count, parent = self.nb_label(key), dcounts.get(key[5:], 0), f"nb{idx['@docs']}"
            elif key == "@smarts":
                label, count, parent = tr("저장된 검색"), None, ""
            elif key.startswith("@smart:"):
                label, count, parent = self.nb_label(key), None, f"nb{idx['@smarts']}"
            else:
                label, count = self.nb_short(key), total(key)
                # 최상위 노트북은 저장 폴더 항목(scrapbook) 아래에 들여써서 보여 준다
                parent = f"nb{idx[key.rsplit('/', 1)[0]]}" if "/" in key else f"nb{idx['']}"
            self.nbtree.insert(parent, "end", iid=f"nb{i}", text="  " + label + ("" if count is None else f"   {count:,}"), values=("" if count is None else f"{count:,}",), open=True)
        self.nbtree.selection_set(f"nb{idx[self.nb]}")
        texts = []

        def collect(parent=""):
            for c in self.nbtree.get_children(parent):
                texts.append(self.nbtree.set(c, "n"))
                collect(c)
        collect()
        self.fit_count(self.nbtree, texts)
        self.quiet = False
        self.root_label.config(text=self.store.root)

    def reload_tags(self):
        if not self.show["tags"]:
            return   # 태그 보기를 켤 때 만든다(태그가 많으면 느리다)
        counts = {}
        for n in self.all_notes:
            for t in n["tags"]:
                counts[t] = counts.get(t, 0) + 1
        for t, c in self.docs.tag_counts().items():   # 가져온 파일에 붙인 태그도 같은 목록에
            counts[t] = counts.get(t, 0) + c
        self.tag_keys = sorted(counts, key=lambda t: (-counts[t], t.lower()))
        self.quiet = True
        self.tagtree.delete(*self.tagtree.get_children())
        for i, t in enumerate(self.tag_keys):
            self.tagtree.insert("", "end", iid=f"tg{i}", text="  # " + t + f"   {counts[t]:,}", values=(f"{counts[t]:,}",))
        if self.tag in self.tag_keys:
            self.tagtree.selection_set(f"tg{self.tag_keys.index(self.tag)}")
        self.fit_count(self.tagtree, [f"{c:,}" for c in list(counts.values())[:200]])
        self.quiet = False

    def clear_tag(self):
        if self.tag:
            self.tag = None
            self.tagtree.selection_remove(*self.tagtree.selection())
            self.refresh()

    def on_tag_click(self, e):
        row = self.tagtree.identify_row(e.y)
        if not row or e.state & 0x5:   # Ctrl/Shift+클릭은 여러 개 고르기라서 노트를 거르지 않는다
            return
        tag = self.tag_keys[int(row[2:])]
        self.tag = None if tag == self.tag else tag   # 선택된 태그를 다시 누르면 해제
        if self.tag is None:
            self.tagtree.selection_remove(*self.tagtree.selection())
        self.refresh()

    def on_nb_select(self, e=None):
        if self.quiet:
            return
        sel = self.nbtree.selection()
        if not sel:
            return
        key = self.nb_keys[int(sel[0][2:])]
        if key == self.nb:
            return
        if key in ("@smarts", QUICK):   # 머리글: 고를 수 없다. 원래 선택으로 되돌린다
            self.quiet = True
            self.nbtree.selection_set(f"nb{self.nb_keys.index(self.nb)}")
            self.quiet = False
            return
        if key.startswith("@smart:"):
            return self.open_smart(key)
        self.flush()
        self.nb = key
        self.close_note()
        self.reload_notes()

    def on_nb_menu(self, e):
        row = self.nbtree.identify_row(e.y)
        if not row:
            return
        key = self.nb_keys[int(row[2:])]
        self.nb_menu_target = key
        m = self.nbmenu
        m.delete(0, "end")
        if key in (FAVS, QUICK, CAL, TRASH):
            return
        if key.startswith("@smart"):   # 저장된 검색
            if key == "@smarts":
                m.add_command(label=tr("지금의 검색 저장…"), command=self.save_search)
            else:
                for label, cmd in self.smart_menu(key) or []:
                    m.add_command(label=label, command=cmd)
            return m.tk_popup(e.x_root, e.y_root)
        if key.startswith("@doc"):   # 가져온 폴더: 원본 파일은 건드리지 않는다
            if key.startswith("@doc:"):
                m.add_command(label=tr("다시 읽기"), command=lambda: self.scan_docs(key[5:]))
                m.add_command(label=tr("목록에서 빼기 (원본 파일은 그대로)"), command=lambda: self.remove_doc_folder(key[5:]))
            else:
                m.add_command(label=tr("모두 다시 읽기"), command=lambda: self.scan_docs())
            m.add_command(label=tr("가져오기 설정…"), command=lambda: self.show_options("imports"))
            return m.tk_popup(e.x_root, e.y_root)
        if key == ALL:   # '모든 노트'는 노트북이 아니므로 최상위에 새 노트북을 만든다
            m.add_command(label=tr("새 노트북 만들기"), command=self.add_notebook)
        else:            # 저장 폴더(최상위)도 노트북처럼 상위가 될 수 있다
            m.add_command(label=tr("하위 노트북 만들기"), command=lambda: self.add_notebook(parent=key, show_parent=True))
        if key != ALL:
            m.add_command(label=tr("저장 폴더 전체 삭제(휴지통)") if key == "" else tr("노트북 삭제(휴지통)"), command=self.delete_notebook)
        m.tk_popup(e.x_root, e.y_root)

    def add_subnotebook(self):
        """고른 노트북(저장 폴더 자체 포함) 안에 하위 노트북을 만든다. '모든 노트'를 골랐으면 최상위에 만든다."""
        parent = self.md_nb()
        self.add_notebook(parent=parent, show_parent=not (self.nb == ALL or self.nb.startswith("@")))

    def add_notebook(self, parent="", show_parent=False):
        where = tr('\n상위: {0}').format(self.nb_label(parent)) if (parent or show_parent) else ""
        name = simpledialog.askstring(tr("새 하위 노트북") if (parent or show_parent) else tr("새 노트북"), tr("노트북 이름") + where, parent=self.root)
        if not name or not name.strip():
            return
        try:
            folder = self.store.create_notebook(name, parent)
        except OSError as ex:
            return messagebox.showerror(APP, tr('노트북을 만들지 못했습니다.\n{0}').format(ex))
        self.flush()
        self.close_note()
        self.nb = folder
        self.reload_notes()

    def delete_notebook(self):
        key = self.nb_menu_target
        if key is None:
            sel = self.nbtree.selection()
            key = self.nb_keys[int(sel[0][2:])] if sel else None
        self.nb_menu_target = None
        if key in (None, ALL) or key.startswith("@"):   # 가져온 폴더·저장된 검색은 노트북이 아니라 휴지통으로 보내지 않는다
            return
        if key == "":
            return self.delete_root()
        if not messagebox.askyesno(APP, tr('노트북 "{0}"을(를) 휴지통으로 보낼까요?\n(하위 노트북과 안의 노트도 함께 가며, {1}일 동안 보관합니다)').format(self.nb_label(key), self.store.trash_days), parent=self.root):
            return
        self.flush()
        try:
            self.store.delete_notebook(key)
        except OSError as ex:
            return messagebox.showerror(APP, str(ex))
        if self.nb == key or self.nb.startswith(key + "/"):
            self.nb = ALL
        self.close_note()
        self.reload_notes()

    def delete_root(self):
        """저장 폴더(scrapbook) 자체를 통째로 휴지통으로 보낸다. 빈 폴더는 다시 만들어 앱이 계속 동작하게 한다."""
        root = self.store.root
        books = self.store.notebooks()
        inside = os.path.normcase(os.path.abspath(self.store.media_dir)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)
        msg = (tr('저장 폴더 "{0}" 전체를 휴지통으로 보낼까요?\n\n{1}\n\n안의 노트 {2}개, 노트북 {3}개').format(self.store.root_name, root, len(self.all_notes), len(books))
               + (tr(", 리소스 폴더(그림)") if inside else "") + tr(", 노트 버전 기록이 모두 함께 갑니다.\n")
               + ("" if inside else tr("(리소스 폴더는 저장 폴더 밖에 있어서 그대로 남습니다.)\n"))
               + tr('\n앱의 휴지통에서 {0}일 동안 보관하며 복원할 수 있습니다.').format(self.store.trash_days))
        if not messagebox.askyesno(APP, msg, icon="warning", parent=self.root):
            return
        self.flush()

        def go():
            try:
                self.store.delete_root()
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=self.root)
            self.hist, self.hpos = [], -1
            self.nb, self.tag = ALL, None
            self.close_note()
            self.reload_notes()
            self.status.config(text=tr("저장 폴더의 내용을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)"))
        self.checkpoint(tr("저장 폴더 삭제 전"), go)

    def choose_root(self):
        d = filedialog.askdirectory(parent=self.root, initialdir=self.store.root, title=tr("노트를 저장할 폴더"))
        if not d:
            return False
        self.flush()
        self.store.set_root(d)
        self.nb, self.tag = ALL, None
        self.hist, self.hpos = [], -1
        self.close_note()
        self.reload_notes()
        return True

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

        def done(res):
            read, gone, total = res
            self.after_docs_changed()
            self.status.config(text=tr('가져온 폴더: 파일 {0:,}개 (새로 읽은 것 {1:,}, 사라진 것 {2:,})').format(total, read, gone))
        self.run_task(tr("가져온 폴더 읽는 중"), lambda prog, cancel: self.docs.scan(prog, cancel, only), done,
                      text=tr("가져온 폴더의 문서를 읽는 중… (처음 한 번은 오래 걸립니다)"))

    def auto_scan_docs(self):
        """조용히(창 없이 뒤에서) 가져온 폴더에서 바뀐 파일만 다시 읽는다. 시작하고 20초 뒤에 한 번, 그 뒤로는 앱을 열어 두는 동안 5분마다 되풀이"""
        self.root.after(DOC_RESCAN_SECONDS * 1000, self.auto_scan_docs)
        if self.doc_scanning or not self.docs.folders():
            return
        self.doc_scanning = True
        q = queue.Queue()

        def job():
            try:
                q.put(("ok", self.docs.scan()))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=job, daemon=True).start()

        def poll():
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                return self.root.after(1000, poll)
            self.doc_scanning = False
            if kind == "ok" and (val[0] or val[1]):
                self.after_docs_changed()
        poll()

    def remove_doc_folder(self, fid):
        f = next((f for f in self.docs.folders() if f["id"] == fid), None)
        if not f or not messagebox.askyesno(APP, tr('「{0}」을(를) 가져온 폴더 목록에서 뺄까요?\n(원본 파일은 그대로 두고, 이 앱의 색인만 지웁니다)').format(f['path']), parent=self.root):
            return
        self.docs.remove_folder(fid)
        if self.nb == "@doc:" + fid:
            self.close_note()
            self.nb = "@docs"
        self.after_docs_changed()

    # ------------------------------------------------------------ 목록: 불러오기·검색·그리기
    def reload_notes(self, background=False, keep_scroll=False):
        """저장 폴더의 노트를 다시 읽는다. background=True 면 창을 먼저 보이고 뒤에서 읽는다(노트가 많을 때 시작이 느려지지 않게)."""
        self.load_gen += 1
        gen = self.load_gen
        if not background:
            return self.apply_loaded(self.read_all_notes(), keep_scroll)
        self.count.config(text=tr("노트를 불러오는 중…"))
        q = queue.Queue()

        def work():
            try:
                q.put(("ok", self.read_all_notes()))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                d, t = self.load_prog
                if t:
                    self.count.config(text=tr('처음 한 번 색인을 만드는 중… {0:,} / {1:,}').format(d, t))
                return self.root.after(80, poll)
            if gen != self.load_gen:
                return    # 그 사이에 다른 읽기가 있었으면 버린다
            if kind == "ok":
                self.apply_loaded(val)
            else:
                self.count.config(text=tr("노트를 불러오지 못했습니다: ") + val)
        self.root.after(80, poll)

    def read_all_notes(self):
        self.load_prog = (0, 0)
        return self.store.list_notes(ALL, tagger=note_tags, progress=lambda d, t: setattr(self, "load_prog", (d, t)))

    def apply_loaded(self, loaded, keep_scroll=False):
        keep = self.cur["path"] if self.cur else None
        self.all_notes = loaded
        if self.nb.startswith("@doc"):   # 가져온 폴더를 골랐으면 목록은 노트가 아니라 가져온 문서
            self.notes = self.docs.list_docs(self.nb[5:] if self.nb.startswith("@doc:") else None)
        elif self.nb == CAL:             # 달력·할일: 노트 목록에는 달력 마크다운 파일들(달마다 한 개, 눌러서 열 수 있다)
            self.notes = [n for n in self.all_notes if n["nb"] == pm.MD_DIR]
        elif self.nb == TRASH:           # 휴지통: 지운 노트를 다른 노트북과 같은 목록으로(삭제까지 남은 날 표시)
            self.notes = self.store.trash_notes()
        elif self.scope_all():           # 모든 파일(저장된 검색 포함) = 내 노트 + 가져온 문서
            self.notes = list(self.all_notes) + self.docs.list_docs()
        else:
            self.notes = [n for n in self.all_notes if self.in_nb(n)]
        self.cur = next((n for n in self.notes if n["path"] == keep), None) if keep else None
        if keep and self.cur is None and self.doc_open:   # 보던 가져온 문서가 목록에서 사라졌으면 미리보기도 닫는다
            self.close_note()
        self.reload_notebooks()
        self.reload_tags()
        self.refresh(keep_page=keep_scroll)

    def search_now(self, e=None):
        """검색 단추·Enter: 기다리지 않고 지금 검색(날짜 칸이 덜 쓰인 채여도 읽히는 만큼으로)"""
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.search_entry.focus_set()

    def schedule_search(self):
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.search_job = self.root.after(180, self.refresh)

    def refresh(self, keep_page=False):
        """검색·정렬을 다시 하고 목록을 그린다. keep_page=True 는 자동 저장 때처럼 보던 자리를 유지"""
        self.search_job = None
        pool = [n for n in self.notes if self.tag in n["tags"]] if self.tag else self.notes
        self.bad_dates = search.bad_dates(self.q.get(), self.d_from.get(), self.d_to.get())
        if self.bad_dates:   # 날짜를 읽을 수 없으면 기간 없이 찾지 말고 비워서 알린다
            self.results, self.words = [], []
        else:
            self.results, self.words = search.run(pool, self.q.get(), self.sort, self.asc, self.d_from.get(), self.d_to.get(),
                                                  index=None if self.nb == TRASH else self.docs if self.nb.startswith("@doc") else
                                                  docidx.Combined(self.store, self.docs) if self.scope_all() else self.store)
        self.draw_list(keep_scroll=keep_page)

    def update_folder_rows(self):
        """고른 노트북 바로 아래의 하위 노트북을 노트 목록 맨 위에 폴더 줄로 보인다(저장 폴더를 고르면 ScrapBook 같은 노트북들)"""
        box = self.folder_box
        kids = []
        if self.nb == "" or (self.nb and not self.nb.startswith("@") and self.nb != ALL):
            depth = self.nb.count("/") + 1 if self.nb else 0
            kids = [k for k in self.nb_keys if k and not k.startswith("@") and k != ALL and k.count("/") == depth
                    and (not self.nb or k.startswith(self.nb + "/")) and not (self.feat["outl"] and (k == OUTL or k.startswith(OUTL + "/")))]
        sig = (self.nb, tuple(kids), tuple(self.nb_direct.get(k, 0) for k in kids))
        if getattr(self, "_folder_sig", None) == sig:
            return
        self._folder_sig = sig
        for w in box.winfo_children():
            w.destroy()
        if not kids:
            box.pack_forget()
            return
        box.pack(fill="x", before=self.list_body, pady=(4, 2))
        for k in kids[:12]:
            n = sum(c for kk, c in self.nb_direct.items() if kk == k or kk.startswith(k + "/"))
            lb = tk.Label(box, text=f"📁  {self.nb_short(k)}", anchor="w", bg=C["bg"], fg=C["accent"], font=(self.ui, 10), padx=18, pady=3, cursor="hand2")
            lb.pack(fill="x", side="top")
            tk.Label(lb, text=f"{n:,}", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right", padx=14)
            lb.bind("<Button-1>", lambda e, k=k: self.go_nb(k))
            lb.bind("<Enter>", lambda e, lb=lb: lb.config(bg=C["soft"]))
            lb.bind("<Leave>", lambda e, lb=lb: lb.config(bg=C["bg"]))
        if len(kids) > 12:
            tk.Label(box, text=tr('… 외 폴더 {0}개 (왼쪽 노트북 목록에서 고르세요)').format(len(kids) - 12), anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=18).pack(fill="x")

    def draw_list(self, keep_scroll=False):
        self.update_folder_rows()
        total = len(self.results)
        searching = self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip() or self.tag
        unit = i18n.unit("파일") if self.scope_all() or self.nb.startswith("@doc") else i18n.unit("노트")
        text = tr('{0:,}개 중 {1:,}개 찾음').format(len(self.notes), total) if searching else tr('{0:,}개의 {1}').format(total, unit)
        if getattr(self, "bad_dates", None):
            text = tr("날짜를 읽을 수 없습니다: ") + ", ".join(self.bad_dates) + tr("  (예: date:20200202-20221231)")
        if self.tag:
            text += f"  ·  # {self.tag}"
        self.count.config(text=text)
        L = self.lst
        if not keep_scroll:
            self.multi.clear()
        top = L.yview()[0] if keep_scroll else 0.0   # 자동 저장·삭제 때만 스크롤을 유지하고, 정렬·검색·노트북을 바꾸면 맨 위부터
        top_line = L.index("@0,0") if keep_scroll else None   # 목록이 줄어도 같은 자리에 머물도록 맨 위 줄로 되돌린다
        want = max(LIST_CHUNK, self.rendered) if keep_scroll else LIST_CHUNK
        self.sb_frozen = True
        L.config(state="normal")
        L.delete("1.0", "end")
        L.config(state="disabled")
        self.cards, self.card_starts, self.rendered, self.next_line = [], [], 0, 1
        self.append_cards(want)
        L.tk.call(L._w, "sync")   # Tk 가 줄 높이를 다 잰 뒤에 막대를 맞춘다(안 그러면 추정값으로 그렸다가 잠시 뒤 크기가 바뀌어 막대가 출렁인다)
        L.yview_moveto(top)
        if top_line:
            L.yview(top_line)
        self.sb_frozen = False
        self.lst_scroll(*L.yview())
        self.mark_selected()
        self.update_star()   # 폰에서 바꾼 즐겨찾기도 편집기의 별에 반영
        for k, b in self.sort_btns.items():
            arrow = ""
            if self.sort == k:   # 제목순은 기본이 가나다(오름차순)라서 화살표 뜻이 반대
                arrow = " ↑" if (self.asc != (k == "title")) else " ↓"
            b.config(text=self.sort_names[k] + arrow)
            b.set_on(self.sort == k)

    def append_cards(self, count=LIST_CHUNK):
        """검색 결과의 다음 count 개를 목록 아래에 이어 붙인다"""
        chunk = self.results[self.rendered:self.rendered + count]
        if not chunk:
            return
        L = self.lst
        first_line = self.next_line
        L.config(state="normal")
        for n in chunk:
            a = self.next_line
            L.insert("end", n["title"] + "\n", "title")
            shown_t = n.get("ctime", n["mtime"]) if self.sort == "ctime" else n["mtime"]   # 생성순이면 생성 시각을 보여 준다
            meta = time.strftime("%Y.%m.%d %H:%M", time.localtime(shown_t))
            if n.get("trash"):
                meta += "   " + (tr("삭제까지 %d일") % n["left"] if n["left"] is not None else tr("자동 삭제 안 함")) + "   ← " + n["orig"]
            elif self.scope_all() or n["nb"] != self.nb:   # 모든 노트이거나 하위 노트북의 노트면 어느 노트북인지 보여 준다
                meta += "   " + self.nb_label(n["nb"])
            if self.words:   # 검색 중일 때만 일치한 부분을 보여 준다
                L.insert("end", meta + "\n", "meta")
                if isinstance(n, docidx.Doc) and not self.docs.content_search:   # 본문을 찾지 않았으니 글 대신 경로를 보여 준다
                    L.insert("end", n["path"] + "\n", "snip")
                else:
                    L.insert("end", search.snippet(n.read(), self.words) + "\n", "snip")
                lines = 3
            else:            # 평소에는 제목과 날짜만
                L.insert("end", meta + "\n", ("meta", "pad"))
                lines = 2
            L.insert("end", "\n", "sep")
            b = a + lines - 1
            self.cards.append((a, b, n))
            self.card_starts.append(a)
            self.next_line = b + 2
        self.rendered += len(chunk)
        for w in self.words:   # 방금 붙인 부분에서만 검색어를 강조
            if not w:
                continue
            pos = f"{first_line}.0"
            while True:
                pos = L.search(w, pos, "end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(w)}c"
                L.tag_add("hl", pos, end)
                pos = end
        L.config(state="disabled")

    def more_cards(self):
        """스크롤이 목록 끝에 가까워지면 다음 노트들을 이어서 그린다"""
        L = self.lst
        grew = False
        for _ in range(20):   # 아래에 남은 글이 MORE_SCREENS 화면보다 적으면 그만큼 채울 때까지 이어 그린다
            lo, hi = L.yview()
            if self.rendered >= len(self.results) or (1 - hi) >= MORE_SCREENS * (hi - lo):
                break
            # 지금까지 그린 만큼을 한 번에 더 붙여서(핸들이 적어도 중간까지 올라오게), 검색 중에는 본문을 읽으니 적게
            self.append_cards(max(LIST_CHUNK * 2, min(self.rendered, MORE_MAX_SEARCH if self.words else MORE_MAX)))
            grew = True
            L.update_idletasks()   # 늘어난 길이로 스크롤 위치(yview)를 다시 계산
        if grew:
            self.mark_selected()

    def mark_selected(self):
        L = self.lst
        L.tag_remove("selcard", "1.0", "end")
        if self.multi:   # 여러 개를 골랐으면 고른 것 모두
            for a, b, n in self.cards:
                if n["path"] in self.multi:
                    L.tag_add("selcard", f"{a}.0", f"{b + 1}.0")
        elif self.cur:
            for a, b, n in self.cards:
                if n["path"] == self.cur["path"]:
                    L.tag_add("selcard", f"{a}.0", f"{b + 1}.0")
                    break

    def clear_multi(self):
        if self.multi:
            self.multi.clear()
            self.mark_selected()
            self.status.config(text="")

    def pick_multi(self, items):
        """items: 고른 노트들. 한 개 이하면 다중 선택을 끝낸다. 가져온 문서는 이동·삭제 대상이 아니라서 뺀다"""
        items = [n for n in items if not isinstance(n, docidx.Doc)]
        self.multi = {n["path"]: n for n in items} if len(items) > 1 else {}
        self.mark_selected()
        self.status.config(text=tr('노트 {0}개 선택됨 (우클릭: 휴지통·이동, Esc: 해제)').format(len(self.multi)) if self.multi else "")

    def select_range(self, n):
        """Shift+클릭: 시작 노트(anchor)부터 클릭한 노트까지 모두 고른다"""
        start = self.anchor or (self.cur["path"] if self.cur else None)
        order = [c[2] for c in self.cards]
        paths = [x["path"] for x in order]
        if start not in paths:
            self.anchor = n["path"]
            return self.pick_multi([n])
        i, j = paths.index(start), paths.index(n["path"])
        self.pick_multi(order[min(i, j):max(i, j) + 1])

    def toggle_multi(self, n):
        """Ctrl+클릭: 이 노트를 고른 목록에 넣거나 뺀다"""
        cur = dict(self.multi) if self.multi else ({self.cur["path"]: self.cur} if self.cur else {})
        if n["path"] in cur:
            del cur[n["path"]]
        else:
            cur[n["path"]] = n
        self.anchor = n["path"]
        self.pick_multi(list(cur.values()))

    def trash_multi(self):
        items = list(self.multi.values())
        if not items or not messagebox.askyesno(APP, tr('고른 노트 {0}개를 휴지통으로 보낼까요?\n({1}일 동안 보관하며 복원할 수 있습니다)').format(len(items), self.store.trash_days), parent=self.root):
            return
        self.multi.clear()
        self.trash_notes([n["path"] for n in items])

    def move_multi(self, nb):
        items = list(self.multi.values())
        self.flush()
        cur_path = self.cur["path"] if self.cur else None
        fail = 0
        for n in items:
            try:
                self.store.move(n["path"], nb)
            except OSError:
                fail += 1
        self.multi.clear()
        if cur_path in {n["path"] for n in items}:
            self.cur = None
        self.reload_notes()
        if fail:
            messagebox.showerror(APP, tr('{0}개 노트를 옮기지 못했습니다.').format(fail), parent=self.root)

    def card_at(self, e):
        line = int(self.lst.index(f"@{e.x},{e.y}").split(".")[0])
        i = bisect.bisect_right(self.card_starts, line) - 1
        if i >= 0 and line <= self.cards[i][1]:
            return self.cards[i][2]
        return None

    def on_list_click(self, e):
        n = self.card_at(e)
        if n and self.nb == CAL and self.feat["cal"] and not self.cur and self.planner_view is not None:
            m = pm.MONTH_RE.match(os.path.basename(n["path"]))
            if m:                                   # 달력·할일에는 마크다운·좌우 분할 보기가 없다: 달력만 그 달로 간다
                self.planner_view.goto_month(int(m.group(1)), int(m.group(2)))
            return "break"
        if isinstance(n, docidx.Doc):   # 가져온 파일은 여러 개 고르기·이동·삭제가 없다: 그냥 연다
            self.anchor = n["path"]
            self.clear_multi()
            self.open_note(n)
        elif n and e.state & 0x1:       # Shift+클릭: 범위 선택(노트는 열지 않는다)
            self.select_range(n)
        elif n and e.state & 0x4:     # Ctrl+클릭: 하나씩 넣고 빼기
            self.toggle_multi(n)
        elif n:
            self.anchor = n["path"]
            self.clear_multi()
            self.open_note(n)
        # 클릭하면 키보드(PageUp/PageDown)가 목록에 먹히게. 노트를 여는 동안 옮겨 간 포커스를 되찾는다.
        self.lst.focus_set()
        self.root.after_idle(self.lst.focus_set)
        return "break"

    def on_list_double(self, e):
        """가져온 파일을 더블클릭하면 그 파일의 기본 프로그램으로 연다(노트는 Text 의 기본 글자 선택을 막기만 한다)"""
        n = self.card_at(e)
        if isinstance(n, docidx.Doc):
            self.open_doc_file(n)
        return "break"

    def open_doc_file(self, n):
        try:
            os.startfile(n["path"])
        except OSError as ex:
            messagebox.showerror(APP, tr('파일을 열지 못했습니다.\n{0}').format(ex), parent=self.root)

    def doc_menu(self, e, n):
        self.open_note(n)
        lm = self.listmenu
        lm.delete(0, "end")
        lm.add_command(label=tr("기본 프로그램으로 열기"), command=lambda: self.open_doc_file(n))
        lm.add_command(label=tr("태그 추가·고치기…"), command=self.edit_tags)
        lm.add_command(label=tr("메모…"), command=self.edit_memo)
        lm.add_separator()
        lm.add_command(label=tr("파일 위치 열기"), command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_command(label=tr("경로 복사"), command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(n["path"])))
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    # ---- 즐겨찾기(설정 폴더의 작은 파일에 적어 폰과 맞춘다)
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
        if self.cur is not None and self.cur is not n:
            self.hide_find(focus=False)
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

    def show_doc(self, n, native):
        """가져온 문서를 보여 준다. native=True 이고 윈도에 그 형식의 미리보기 처리기가 있으면 그 프로그램(pdf → Edge, mp3 → Media Player …)이
        노트 화면 안에 직접 그리고, 아니면(또는 실패하면) 색인해 둔 글을 읽기 전용으로 보여 준다(Ctrl+F 로 찾을 수 있다)."""
        self.pv.unload()
        self.pv_active = False
        can = self.doc_can_preview(n)
        if native and can:
            self.apply_layout("pv")
            self.root.update_idletasks()
            self.pv_active = self.pv.show(self.pv_frame.winfo_id(), n["path"], self.pv_frame.winfo_width(), self.pv_frame.winfo_height())
        if self.pv_active:
            self.hide_find(focus=False)
            self.status.config(text=tr('원본 미리보기 (윈도 기본 프로그램)   ·   {0}   ·   글로 바꾸면 Ctrl+F 로 찾을 수 있습니다').format(n['path']))
        else:
            self.apply_layout("edit")
            body = n.read()
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
        self.title_var.set(n["title"])
        # 한 줄이 아주 긴 글(base64 그림 등)은 줄바꿈 계산이 수십 초 걸려서 줄바꿈을 끈다
        longest = max((len(x) for x in n["body"].split("\n")), default=0)
        self.text.config(wrap="none" if longest > 20000 else "word")
        self.text.config(state="normal")
        self.title_entry.config(state="normal")
        self.set_text(n["body"])
        self.text.yview_moveto(0)
        self.dirty = False
        self.update_status()
        if n.get("trash"):               # 휴지통의 노트: 읽기 전용(우클릭 → 복원 · 완전히 삭제)
            self.text.config(state="disabled")
            self.title_entry.config(state="readonly")
            self.status.config(text=tr("휴지통의 노트 — 읽기 전용입니다. 목록에서 우클릭 → 복원 · 완전히 삭제"))
        if self.is_outline_note() or self._outl_on:
            self._outl_path = None
            self.apply_layout(self.mode)
        self.render()
        self.mark_selected()
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
        self._flush_save()
        if not getattr(self, "_autosaving", False) and self.cur and not self.doc_open and getattr(self, "fresh", None) == self.cur["path"]:
            self.auto_title(self.text.get("1.0", "end-1c"))   # 노트를 떠날 때(타이머 저장이 아닐 때): 제목을 안 썼으면 본문 첫 줄을 제목으로

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
                self.tagbtn.config(text=shown or tr("# 태그 추가"), fg=C["accent"] if tags else C["muted"])
            return
        if self.cur:
            self.status.config(text=tr('{0}/{1}   ·   {2:,}자').format(self.nb_label(self.cur['nb']), os.path.basename(self.cur['path']), len(self.cur['body'])) + (f"   ·   {extra}" if extra else "") + "   ·")
            if not self.tag_edit:
                tags = sorted(self.cur.get("tags", ()))
                shown = "   ".join("# " + t for t in tags[:6]) + (f"   … +{len(tags) - 6}" if len(tags) > 6 else "")
                self.tagbtn.config(text=shown or tr("# 태그 추가"), fg=C["accent"] if tags else C["muted"])

    def commit_title(self):
        if not self.cur or self.doc_open:
            return
        new = self.title_var.get().strip()
        if new == self.cur["title"]:
            return
        if not new and getattr(self, "fresh", None) == self.cur["path"]:
            return                                  # 새 노트는 제목을 비워 둘 수 있다(나갈 때 본문 첫 줄이 제목이 된다)
        if self.wiki_on() and new and wikilinks.taken(new, self.store.titles(), own=self.store.key_of(self.cur["path"])):
            self.title_var.set(self.cur["title"])
            return messagebox.showinfo(APP, tr('"{0}" 제목의 노트가 이미 있습니다.\n위키 링크([[제목]])를 쓰는 동안은 같은 제목을 만들 수 없어서 제목을 바꾸지 않았습니다.\n(옵션 → 일반에서 위키 링크를 끄면 같은 제목도 쓸 수 있습니다)').format(new), parent=self.root)
        self.flush()
        try:
            title, path = self.store.rename(self.cur["path"], new)
        except OSError as ex:
            self.title_var.set(self.cur["title"])
            return messagebox.showerror(APP, tr('제목을 바꾸지 못했습니다.\n{0}').format(ex))
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
        self.tag = None
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

    def render(self):
        self.render_job = None
        if self.cur and self.is_outline_note():
            return self.render_outline()
        if not self.cur or self.mode == "edit" or self.doc_open:
            return
        title = self.title_var.get()
        try:
            # 클리퍼가 맨 위에 적는 '원본: <주소>' 줄은 렌더링 화면에서만 숨긴다(문서 정보의 URL 은 이 줄에서 읽는다)
            src = SOURCE_LINE.sub("", self.text.get("1.0", "end-1c"), count=1)
            doc = wikiconv.parse(src, bulk.SYNTAX[FMT], title)
            segs = preview.layout(doc)
        except Exception as ex:  # noqa: BLE001  (읽기 도구가 못 읽은 글도 편집은 계속할 수 있게)
            return self.status.config(text=tr("렌더링 오류: ") + str(ex))
        self.draw_view(segs)

    # ---- 아웃라이너 보기(렌더링 화면): 목록은 점(●) 계층으로, 그 밖의 글은 '메모' 카드로 따로 보이고, 점을 누르면 줌인
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
        self.view_sb_frozen = True
        try:
            self.draw_view_body(segs)
        finally:
            self.view_sb_frozen = False
            self.view_scroll(*v.yview())

    def draw_view_body(self, segs):
        v = self.view
        self.img_w_used = self.img_avail()
        self.has_imgs = any(extra and extra[0] == "img" for _, _, extra in segs)
        top = v.yview()[0]
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
            if "b" in tg and "i" in tg:
                tg.append("bi")
            if extra and extra[0] == "link" and extra[1] == "page":
                if not wiki:   # 위키를 끄면 [[ ]] 는 그냥 글자
                    tg = [x for x in tg if x != "link"]
                    extra = None
                else:
                    widx = widx or self.wiki_index()
                    if wikilinks.norm(wikilinks.split_target(extra[2])[0]) not in widx:
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
        v.yview_moveto(top)
        self.find_later()   # 다시 그렸으면 찾은 곳의 강조도 다시 한다
        self.pair_later(self._pair_side)   # 다시 그렸으면 왼쪽↔오른쪽 짝 강조도 다시 한다

    def data_image(self, src):
        """data:image/...;base64,… 주소 → 화면에 쓸 PhotoImage(실패하면 None). GIF·PNG 는 바로, 그 밖(JPEG 등)은 PNG 로 바꿔서"""
        m = re.match(r"(?is)^data:image/([a-z0-9.+-]+)[^,]*;base64,(.*)$", src.strip())
        if not m:
            return None
        kind, payload = m.group(1).lower(), re.sub(r"\s+", "", m.group(2))
        try:
            if kind in ("gif", "png"):
                return tk.PhotoImage(data=payload)
            raw = base64.b64decode(payload)
            path = os.path.join(ed.image_cache_dir(), hashlib.sha1(raw).hexdigest()[:20] + "." + ("jpg" if kind in ("jpeg", "jpg") else kind))
            if not os.path.isfile(path):
                with open(path, "wb") as f:
                    f.write(raw)
            return tk.PhotoImage(file=ed.local_image_png(path, max_w=self.img_avail()))
        except (tk.TclError, OSError, ValueError):
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

    def img_avail(self):
        """렌더링 화면에서 그림이 쓸 수 있는 너비(픽셀): 렌더링 칸 너비 - 여백(스크롤바 포함). 50 단위로 내려서 변환 캐시가 늘지 않게.
        스크롤바가 생겼다 사라져도 값이 같도록 스크롤바가 들어가는 바깥 칸의 너비로 잰다."""
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

    def show_image(self, src, width=0):
        """그림으로 보여 준다: 같은 폴더·리소스 폴더의 파일, http(s) 주소, 본문에 박힌 data: 그림. 안 되면 글자 칩으로 남는다."""
        src = src.strip()
        if src[:5].lower() == "data:":   # 노트 본문에 base64 로 박힌 그림
            img = self.data_image(src)
            return self.put_image(img, width) if img is not None else False
        avail = self.img_avail()
        target = min(width, avail) if width else avail   # HTML 의 width 가 있으면 그 너비로(칸보다 넓지는 않게)
        if re.match(r"(?i)^https?://", src):
            path = self.remote_image(src)
            if not path:
                return False
            img = self.photo_from_file(path, target)
        else:
            if re.match(r"(?i)^[a-z][a-z0-9+.-]+:", src) and not re.match(r"(?i)^(file:///|:/)", src):
                return False   # mailto: 같은 그림이 아닌 주소
            path = self.find_local_image(src)
            if not path:
                return False
            img = self.photo_from_file(path, target)
        return self.put_image(img, width, path) if img is not None else False

    def put_image(self, img, width=0, path=None):
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
            if fpath:
                m.add_command(label=tr("열기"), command=lambda: self.open_local_file(lk[1]))
                m.add_command(label=tr("파일 위치 열기"), command=lambda: self.reveal_file(fpath))
                m.add_separator()
        m.add_command(label=tr("복사"), command=lambda: v.event_generate("<<Copy>>"), state="normal" if v.tag_ranges("sel") else "disabled")
        m.add_command(label=tr("모두 선택"), command=lambda: v.tag_add("sel", "1.0", "end-1c"))
        m.add_separator()
        if name is not None:
            m.add_command(label=tr("그림 삭제"), command=lambda: self.delete_view_image(e))
        m.add_command(label=tr("삭제"), command=self.delete_view_selection, state="normal" if v.tag_ranges("sel") else "disabled")
        m.tk_popup(e.x_root, e.y_root)

    # ---- 렌더링 화면 ↔ 원문 맞추기(블록 단위): 우클릭 삭제와 좌우 분할 짝 강조가 함께 쓴다
    def render_flat(self, src):
        """원문을 그려 본 렌더링 글(화면에 그릴 글자들을 이어 붙인 것)"""
        return "".join(t for t, _, _ in preview.layout(wikiconv.parse(src, bulk.SYNTAX[FMT], self.title_var.get())))

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
                self.text.see(f"1.0+{ua}c")
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
                self.view.see(f"1.0+{w0}c")
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
        changed = False
        try:
            while True:
                url, kind, val = self.img_q.get_nowait()
                self.imgs[url] = (kind, val)
                changed = True
        except queue.Empty:
            pass
        if changed:
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
        """주소를 연다. 유튜브 영상은 설정에 따라 작은 재생 창(Edge 앱 창, 주소창 없음)으로, 아니면 기본 브라우저로."""
        # 유튜브와 영상 파일(.mp4 …)은 주소창 없는 Edge 앱 창으로 연다: 재생 단추·소리·전체 화면이 있는 깨끗한 재생 창이 된다
        if sys.platform == "win32" and st.read_config().get("video_open", "app") == "app" and (wikiconv.tree.youtube_id(url) or wikiconv.tree.is_video_file(url)):
            for exe in (os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
                if os.path.isfile(exe):
                    subprocess.Popen([exe, f"--app={url}", "--window-size=980,640"])
                    return
        webbrowser.open(url)

    def auto_link_segs(self, segs):
        """옵션 '단어만 있어도 연결'(톰보이 방식): 평범한 글 속에서 다른 노트의 제목과 같은 낱말을 위키 링크로 만든다"""
        key = (id(self.all_notes), len(self.all_notes))
        if getattr(self, "_auto_key", None) != key:
            self._auto_key, self._auto_tab = key, wikilinks.title_table(self.all_notes)
        table, lengths = self._auto_tab
        own = self.cur["title"] if self.cur else ""
        skip = {"code", "codeblock", "raw", "math", "link", "chip", "h1", "h2", "h3", "h4", "h5", "h6"}
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
        found = self.wiki_index().get(wikilinks.norm(want))   # 같은 제목이 여럿이면 가장 최근 노트
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

    # ------------------------------------------------------------ 서식 도구 (위키나루)
    def sel_range(self, whole_lines=False):
        t = self.text
        if t.tag_ranges("sel"):
            a, b = t.index("sel.first"), t.index("sel.last")
        else:
            a = b = t.index("insert")
        if whole_lines:
            if b != a and t.index(f"{b} linestart") == b:   # 줄 맨 앞에서 끝난 선택은 그 줄을 빼기
                b = t.index(f"{b} - 1c")
            a, b = t.index(f"{a} linestart"), t.index(f"{b} lineend")
        return a, b

    def replace(self, a, b, new, s=None, e=None):
        t = self.text
        t.edit_separator()
        t.config(autoseparators=False)   # 지우기+넣기를 되돌리기 한 번으로
        t.delete(a, b)
        t.insert(a, new)
        t.config(autoseparators=True)
        t.edit_separator()
        if s is not None:
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", f"{a}+{s}c", f"{a}+{e}c")
            t.mark_set("insert", f"{a}+{e}c")
        t.focus_set()

    def run_action(self, action):
        if not self.cur:
            return
        if self.mode == "view":
            self.set_mode("split")
        kind, *rest = action
        arg = rest[0] if rest else None
        if kind == "wrap":
            before, after, default = WRAP_X.get(arg) or (*ed.WRAP[FMT][arg], ed.WRAP_DEFAULT[arg])
            a, b = self.sel_range()
            new, s, e = ed.wrap_text(self.text.get(a, b), before, after, default)
            self.replace(a, b, new, s, e)
        elif kind == "line":
            spec = LINE_X.get(arg) or ed.LINE[FMT][arg]
            holder = PLACEHOLDER_X.get(arg) or ed.PLACEHOLDER[arg]
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if not any(ln.strip() for ln in lines):   # 빈 줄: 표시와 자리 글을 넣고 그 글을 골라 둔다
                head = spec[0].format(n=1)
                new = "\n".join([head + holder] + lines[1:])
                self.replace(a, b, new, len(head), len(head) + len(holder))
            else:
                new = "\n".join(ed.toggle_prefix(lines, *spec))
                self.replace(a, b, new, 0, len(new))
        elif kind == "heading":
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if arg > 0 and not any(ln.strip() for ln in lines):
                new = ed.set_heading("제목", arg, FMT)
                s = new.index("제목")
                self.replace(a, b, new, s, s + 2)
            else:
                new = "\n".join(ed.set_heading(ln, arg, FMT) if ln.strip() else ln for ln in lines)
                self.replace(a, b, new, 0, len(new))
        elif kind == "indent":
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if arg > 0:
                new = "\n".join(("  " + ln) if ln.strip() else ln for ln in lines)
            else:
                new = "\n".join(re.sub(r"^(  |\t)", "", ln, count=1) for ln in lines)
            self.replace(a, b, new, 0, len(new))
        elif kind == "tpl":
            tpl, default = TPL[arg]
            a, b = self.sel_range()
            sel = self.text.get(a, b)
            line_empty = not self.text.get(f"{a} linestart", f"{a} lineend").strip()
            body = sel or default
            out = tpl.replace("{}", body, 1)
            at_a, at_b, pre = (a, b, "") if (sel or line_empty) else (self.text.index(f"{a} lineend"),) * 2 + ("\n\n",)
            if "{}" in tpl and body:
                s0 = len(pre) + out.index(body)
                self.replace(at_a, at_b, pre + out + ("" if sel else "\n"), s0, s0 + len(body))
            else:
                self.replace(at_a, at_b, pre + out + ("" if sel else "\n"))
        elif kind == "datetime":
            self.insert_datetime()
        elif kind == "footnote":
            t = self.text
            nums = [int(x) for x in re.findall(r"\[\^(\d+)\]", t.get("1.0", "end-1c"))]
            n = (max(nums) + 1) if nums else 1
            t.edit_separator()
            t.insert("insert", f"[^{n}]")
            whole = t.get("1.0", "end-1c")
            tail = "" if whole.endswith("\n\n") else ("\n" if whole.endswith("\n") else "\n\n")
            t.insert("end-1c", f"{tail}[^{n}]: 각주 내용")
            end = t.index("end-1c")
            t.edit_separator()
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", f"{end} - 5c", end)
            t.mark_set("insert", end)
            t.see(end)
            t.focus_set()
        elif kind == "block":
            if arg == "codeblock":
                a, b = self.sel_range()
                body = self.text.get(a, b) or "코드"
                self.replace(a, b, ed.BLOCK["codeblock"][FMT].replace("{}", body, 1))
            else:
                a, _ = self.sel_range()
                at = self.text.index(f"{a} lineend")
                empty = not self.text.get(f"{a} linestart", at).strip()
                self.replace(at, at, ("" if empty else "\n\n") + ed.BLOCK[arg][FMT] + "\n")

    # ------------------------------------------------------------ 웹 클리퍼 서버
    def start_clipper(self):
        if self.srv or not st.read_config().get("clipEnabled", True):
            return
        self.srv, self.port = clipserver.start(self.store, st.clipper_token, lambda: self.clip_q.put(1))
        if self.srv and self.port != clipserver.DEFAULT_PORT:   # 확장은 보통 기본 포트(41184)에 맞춰 두므로, 밀렸으면 알려 준다(비면 자동으로 돌아간다)
            self.status.config(text=tr('웹 클리퍼가 {0}번 포트로 열렸습니다({1}번을 다른 프로그램이 쓰는 중). 비면 자동으로 {2}번으로 옮깁니다.').format(self.port, clipserver.DEFAULT_PORT, clipserver.DEFAULT_PORT))

    def retake_default_port(self):
        """기본 포트(41184)를 다른 프로그램(예: 조플린, 아직 안 닫힌 앱의 옛 창)이 쓰고 있어서 옆 포트로 밀려 열렸다면, 비는 대로 기본 포트로 옮긴다.
        확장 프로그램의 포트는 그대로인데 서버만 옮겨 가 있으면 클리퍼가 '끊긴' 것처럼 된다."""
        if not self.srv or self.port == clipserver.DEFAULT_PORT:
            return
        srv, port = clipserver.start(self.store, st.clipper_token, lambda: self.clip_q.put(1), ports=[clipserver.DEFAULT_PORT])
        if not srv:
            return
        try:
            self.srv.shutdown()
            self.srv.server_close()
        except Exception:  # noqa: BLE001
            pass
        self.srv, self.port = srv, port
        self.status.config(text=tr('웹 클리퍼가 {0}번 포트로 돌아왔습니다.').format(port))

    def stop_clipper(self):
        if self.srv:
            try:
                self.srv.shutdown()
                self.srv.server_close()
            except Exception:  # noqa: BLE001
                pass
        self.srv = self.port = None

    def poll_clip(self):
        got = False
        try:
            while True:
                self.clip_q.get_nowait()
                got = True
        except queue.Empty:
            pass
        if got:
            self.reload_notes()
            self.status.config(text=tr("웹 클리퍼에서 새 노트가 들어왔습니다 ") + time.strftime("%H:%M:%S"))
        self.clip_tick = getattr(self, "clip_tick", 0) + 1
        if self.clip_tick % 8 == 0:   # 약 5초마다
            self.retake_default_port()
        self.root.after(600, self.poll_clip)

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
        self.capture_nb_height()
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
        self.ow.txt.bind("<Control-d>", lambda e: (self.toggle_favorite(), "break")[1])
        self.ow.txt.bind("<Control-f>", lambda e: "break")
        for w in (self.text, self.view):   # 글자 칸의 기본 Ctrl+F(커서를 한 글자 오른쪽으로)는 막는다
            w.bind("<Control-f>", lambda e: (self.on_ctrl_f(), "break")[1])
            w.bind("<Control-d>", lambda e: (self.toggle_favorite(), "break")[1])   # 글자 칸의 기본 Ctrl+D(오른쪽 글자 지우기)는 즐겨찾기로 바꾼다
        r.bind_all("<F3>", lambda e: self.find_step(1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Shift-F3>", lambda e: self.find_step(-1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Control-comma>", lambda e: self.show_options("general"))
        r.bind_all("<F1>", lambda e: self.open_manual())
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


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    if not os.environ.get("IAT_NO_SINGLE") and not single.acquire():   # (IAT_NO_SINGLE: 시험용 — 실행 중인 앱을 건드리지 않고 따로 띄운다) 이미 실행 중(창이 열려 있거나 트레이에 있음): 그 앱에 창을 열어 달라고 알렸으니 여기서는 끝낸다
        return
    App().run()


if __name__ == "__main__":
    main()
