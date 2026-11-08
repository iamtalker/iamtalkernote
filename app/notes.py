"""iamtalkernote — 위키나루 기반 마크다운 노트 앱 (표준 라이브러리 tkinter).

    pythonw iamtalkernote.pyw          (콘솔 창 없이)      또는   python notes.py

조플린처럼: 메뉴줄(파일·편집·보기·이동·도구·도움말) · 노트북/태그 사이드바 · 노트 목록 · 서식 도구줄이 있는 에디터.
위키나루의 마크다운 렌더링·문법 해설, 폴더검색의 검색, 조플린 클리퍼 플러스(웹 클리퍼) 연동.
노트는 .md 파일로 저장된다.
"""
from notes_shared import *  # noqa: E402,F401,F403   (가져오기·상수·색·Btn·보조 함수: notes_shared.py)
import notes_shared as _shared  # noqa: E402
import autotitle  # noqa: E402   (제목 없이 쓴 새 노트: 본문 첫 줄을 제목으로)
import pdflink  # noqa: E402   (본문이 pdf 링크 하나뿐인 노트는 pdf 뷰어로: pdflink.py)
import time  # noqa: E402   (그림 변환을 기다리는 시간 재기: render)
from dialogs import DialogsMixin  # noqa: E402   (큰 대화창들: dialogs.py)
from langbtn import LangButton  # noqa: E402   (오른쪽 위 언어 단추: langbtn.py)
from searchbox import SearchBoxMixin  # noqa: E402   (검색창 자동완성·입력기 글꼴: searchbox.py)
from findbar import FindBarMixin  # noqa: E402   (문서에서 찾기 막대(Ctrl+F): findbar.py)
from wikiui import WikiUIMixin  # noqa: E402   (위키 링크(켜짐 확인·[[ 자동완성·연결된 노트 보기): wikiui.py)
from tagedit import TagEditMixin  # noqa: E402   (태그 편집(맨 아래 태그 박스·메모·이름 바꾸기·삭제·합치기): tagedit.py)
from docfolders import DocFoldersMixin  # noqa: E402   (가져온 폴더 읽기·색인: docfolders.py)
from outlinermix import OutlinerMixin  # noqa: E402   (아웃라이너·렌더링 글 고치기: outlinermix.py)
from rendersync import RenderSyncMixin  # noqa: E402   (렌더링: rendersync.py)
from noteio import NoteIOMixin  # noqa: E402   (노트를: noteio.py)
from restorepoints import RestorePointMixin  # noqa: E402   (복원: restorepoints.py)
from optionsui import OptionsMixin  # noqa: E402   (설정: optionsui.py)
from noteinfo import NoteInfoMixin  # noqa: E402   (노트: noteinfo.py)
from clipmixin import ClipperServerMixin  # noqa: E402   (웹: clipmixin.py)
from formattools import FormatToolsMixin  # noqa: E402   (서식: formattools.py)


class App(DialogsMixin, SearchBoxMixin, TagEditMixin, WikiUIMixin, FindBarMixin, DocFoldersMixin, FormatToolsMixin, ClipperServerMixin, NoteInfoMixin, OptionsMixin, RestorePointMixin, NoteIOMixin, RenderSyncMixin, OutlinerMixin):
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
        self.pick_families()
        self.size = 11
        self.style_ttk()

        view = st.read_config().get("view", {})
        self.show = {k: bool(view.get(k, d)) for k, d in (("notebooks", True), ("list", True), ("tags", False), ("syntax", True))}
        self.mode = view.get("mode") if view.get("mode") in ("edit", "split", "view") else "split"
        self.store = st.Store()
        self.fav = favorites.Favorites(syncsettings.control_dir())   # 즐겨찾기(설정 폴더의 작은 파일, 폰과 맞춤)
        self.store.tagger = note_tags   # 색인에 태그도 함께 기억
        self.docs = docidx.DocIndex()  # 가져온 폴더의 문서 색인
        try:
            docidx.remove_old_export(self.store.root)   # 예전 '가져온 문서 요약'(.imported)은 이제 안 쓰니 치운다
        except Exception:  # noqa: BLE001
            pass
        self.doc_open = False          # 가져온 문서(읽기 전용)를 열어 둔 중인가
        self.doc_scanning = False      # 가져온 폴더를 뒤에서 다시 읽는 중인가(겹쳐 돌지 않게)
        self.doc_scan_progress = None
        self.doc_scan_last = None      # 마지막 가져온 폴더 색인 결과(옵션 화면에 완료 상태를 남김)
        self.pv = winpreview.Preview() # 윈도 미리보기 처리기(pdf → Edge, mp3 → Media Player …)
        self.pdf_note = None           # 본문이 pdf 링크 하나뿐인 노트를 열어 둔 중이면 그 pdf 경로
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
        if (self.nb == FAVS and not self.feat["favs"]) or (self.nb == CAL and not self.feat["cal"]) \
                or (not self.feat["outl"] and (self.nb == OUTL or self.nb.startswith(OUTL + "/"))):
            self.nb = ALL              # 꺼 둔 기능의 항목을 보던 채로 닫았으면 처음 목록을 만들기 전에 '모든 파일' 로 (뒤에서 바꾸면 목록이 비어 남는다)
        self.tag = None                # 태그로 거르는 중이면 그 태그
        self.tag_none = False
        self.tag_global = bool(cfg.get("tagGlobal", False))
        self.tag_sort = "name" if cfg.get("tagSort") == "name" else "frequency"
        self.adv_conditions = []
        self.nb_keys, self.tag_keys = [], []
        self.nb_open = {}              # 노트북 목록에서 펼침(True)·접음(False)을 사용자가 정한 항목. 정한 적 없으면 가져온 폴더 쪽은 접고 나머지는 펼친다
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
        self.title_save_job = None
        self.resize_job = None        # 렌더링 칸 너비가 바뀐 뒤 그림 크기를 다시 맞추는 예약
        self.img_w_used, self.has_imgs = None, False   # 마지막으로 그릴 때 쓴 그림 너비 / 그 글에 그림이 있는지
        self.imgs, self.img_q, self.photos = {}, queue.Queue(), []
        self.local_img_q, self.local_img_lock, self.local_img_worker = queue.Queue(), threading.Lock(), False
        self.gif_jobs, self.gif_sources, self.gif_generation = set(), [], 0
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
                "note_size": num("note_size", 11, 8, 28), "note_bold": bool(c.get("note_bold", False)),
                "family": str(c.get("family", "") or ""), "mono_family": str(c.get("mono_family", "") or "")}

    UI_FONTS = ("맑은 고딕", "Malgun Gothic", "Segoe UI")
    MONO_FONTS = ("D2Coding", "Consolas", "Courier New")

    def pick_families(self):
        """화면 글꼴(self.ui)과 고정폭 글꼴(self.mono)을 정한다: 옵션 → 글꼴에서 고른 것(설치되어 있을 때)이 먼저, 없으면 기본 순서.
        (이 PC 에 나눔고딕 같은 글꼴이 있으면 옵션에서 고를 수 있다)"""
        fams = set(tkfont.families())
        c = st.read_config().get("fonts", {})
        want = lambda key, default: c.get(key) if c.get(key) in fams else next((f for f in default if f in fams), None)  # noqa: E731
        UI = self.ui = want("family", self.UI_FONTS) or "TkDefaultFont"
        _shared.UI = UI   # notes_shared 의 납작한 버튼 등도 같은 글꼴을 쓰게
        self.mono = want("mono_family", self.MONO_FONTS) or "TkFixedFont"

    def set_fonts(self, ls, lb, ns, nb, family=None, mono=None):
        def num(v, d, lo, hi):
            try:
                return max(lo, min(hi, int(float(v))))
            except (TypeError, ValueError):
                return d
        old = st.read_config().get("fonts", {})
        st.write_config(fonts={"list_size": num(ls, 10, 8, 20), "list_bold": bool(lb),
                               "note_size": num(ns, 11, 8, 28), "note_bold": bool(nb),
                               "family": old.get("family", "") if family is None else family,
                               "mono_family": old.get("mono_family", "") if mono is None else mono})
        self.pick_families()
        self.rebuild_ui()
        self.show_options("fonts")

    def make_fonts(self):
        fc = self.font_cfg()
        self.size = sz = fc["note_size"]
        self.note_bold = fc["note_bold"]
        fam = self.ui
        F = lambda **kw: tkfont.Font(family=kw.pop("family", fam), size=kw.pop("size", sz), **kw)  # noqa: E731
        self.fonts = {"base": F(weight="bold" if fc["note_bold"] else "normal"), "b": F(weight="bold"), "i": F(slant="italic"), "bi": F(weight="bold", slant="italic"),
                      "mono": F(family=self.mono, size=max(sz - 1, 8)), "table": F(size=max(sz - 1, 8)), "tableb": F(size=max(sz - 1, 8), weight="bold"), "small": F(size=max(sz - 3, 7)),
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
        m.add_command(label=tr("글자만 붙여넣기"), accelerator="Ctrl+Shift+V", command=self.plain_paste)
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
        m.add_command(label=tr("새로 고침"), accelerator="F5", command=self.refresh_all)
        m.add_separator()
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
        m.add_command(label=tr("자동 태그 추가…"), command=self.show_auto_tags)
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
        return h

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
        nb_head = self.section_head(self.nb_sec, tr("노트북"))
        for icon, opened, hint in (("📁", False, tr("모두 접음")), ("📂", True, tr("모두 펼침"))):   # pack(side=right) 라서 먼저 놓은 것이 오른쪽 끝
            b = Btn(nb_head, icon, lambda o=opened: self.nb_set_all(o), kind="ghost", bg=C["bg"], padx=4, pady=0, font=("Segoe UI Emoji", 10))
            b.pack(side="right")
            self.tip(b, hint)
        self.nbtree = self.make_tree(self.nb_sec)
        self.nbtree.bind("<<TreeviewSelect>>", self.on_nb_select)
        self.nbtree.bind("<<TreeviewOpen>>", lambda e: self.on_nb_toggle(True))
        self.nbtree.bind("<<TreeviewClose>>", lambda e: self.on_nb_toggle(False))
        self.nbtree.bind("<Delete>", lambda e: self.delete_notebook())
        self.nbtree.bind("<Button-3>", self.on_nb_menu)
        self.nbmenu = tk.Menu(self.root, tearoff=0)
        self.tag_sec = tk.Frame(self.left_pane, bg=C["bg"])
        tag_head = self.section_head(self.tag_sec, tr("태그"), clear=self.clear_tag)
        self.tag_scope_btn = Btn(tag_head, tr("전체 범위") if self.tag_global else tr("현재 범위"), self.toggle_tag_scope,
                                 kind="ghost", padx=5, pady=0, font=(self.ui, 8))
        self.tag_scope_btn.pack(side="right")
        self.tip(self.tag_scope_btn, tr("태그 목록 범위를 전체와 현재 노트북 사이에서 바꿉니다"))
        self.tag_sort_btn = Btn(tag_head, tr("이름순") if self.tag_sort == "name" else tr("빈도순"), self.show_tag_sort,
                                padx=5, pady=0, font=(self.ui, 8))
        self.tag_sort_btn.pack(side="right")
        self.tip(self.tag_sort_btn, tr("태그 정렬: 빈도순 또는 이름순 (한글·영문 구분)"))
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
        top.pack(fill="x", padx=14, pady=(14, 4))
        search_row = tk.Frame(top, bg=C["bg"])
        search_row.pack(fill="x")
        box = tk.Frame(search_row, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"])
        box.pack(side="left", fill="x", expand=True)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: (self.schedule_search(), self.update_placeholder()))
        self.search_entry = tk.Entry(box, textvariable=self.q, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                                     insertbackground=C["text"], insertwidth=2, insertborderwidth=0, insertontime=600, insertofftime=400,
                                     font=(self.ui, 10))   # 세로 막대 커서가 깜빡인다
        self.search_entry.pack(fill="x", padx=(10, 32), pady=7)
        self.history_btn = Btn(search_row, "◷", self.show_search_history, padx=6, pady=4, font=(self.ui, 12))
        self.history_btn.pack(side="left", padx=(7, 0))
        self.tip(self.history_btn, tr("최근 검색"))
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
        action_bar = tk.Frame(top, bg=C["bg"])
        action_bar.pack(fill="x", pady=(5, 0))
        left_actions = tk.Frame(action_bar, bg=C["bg"])
        left_actions.pack(side="left")
        right_actions = tk.Frame(action_bar, bg=C["bg"])
        right_actions.pack(side="right")
        Btn(right_actions, tr("＋ 새 노트"), self.new_note, kind="primary", bold=True, pady=5).pack(side="right", padx=(7, 0))
        refresh = Btn(right_actions, "⟳", self.refresh_all, pady=5, font=(self.ui, 12))
        refresh.pack(side="right", padx=(7, 0))
        self.tip(refresh, tr("새로 고침 (F5): 탐색기 등 앱 밖에서 폴더·노트를 지우거나 옮겼을 때 다시 읽습니다"))
        self.search_btn = Btn(left_actions, tr("검색"), self.search_now, bold=True, pady=5)
        self.search_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.search_btn.pack(side="left", padx=(4, 0))   # 치는 즉시 검색하지만, 눌러서 바로 다시 검색할 수도 있다
        self.advanced_search_btn = Btn(left_actions, tr("고급 검색"), self.open_advanced_search, pady=5)
        self.advanced_search_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.advanced_search_btn.pack(side="left", padx=(7, 0))
        self.v_content = tk.BooleanVar(value=self.docs.content_search)
        self.opt_row = tk.Frame(left_actions, bg=C["bg"])
        self.cb_content = tk.Checkbutton(self.opt_row, text=tr("문서 내부 검색"), variable=self.v_content, command=self.on_content_toggle, relief="flat",
                                         bd=0, takefocus=False, bg=C["bg"], fg=C["sub"], activebackground=C["soft"], selectcolor=C["bg"],
                                         cursor="hand2", font=(self.ui, 9))
        self.cb_content.pack(side="left")
        self.tip(self.cb_content, tr("켜면 가져온 pdf·txt 등의 본문까지 찾고, 끄면 파일 제목만 찾습니다"))
        bar = tk.Frame(f, bg=C["bg"])
        bar.pack(fill="x", padx=10, pady=(0, 2))
        self.sort_names = {"relevance": tr("관련도순"), "time": tr("수정순"), "ctime": tr("생성순"), "title": tr("제목순")}
        self.sort_btns = {k: Btn(bar, v, lambda k=k: self.sort_by(k), padx=6, pady=3) for k, v in self.sort_names.items()}
        self.b_date = Btn(bar, tr("기간"), self.toggle_date, padx=6, pady=3)
        for b in (*self.sort_btns.values(), self.b_date):
            b.pack(side="left", padx=1)
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
        """'문서 내부 검색' 체크박스는 가져온 폴더가 있을 때만 보인다"""
        if self.docs.folders():
            if not self.opt_row.winfo_ismapped():
                self.opt_row.pack(side="left", padx=(8, 0))
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
        self.title_var.trace_add("write", self.schedule_title_commit)
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
        self.title_entry.bind("<FocusOut>", lambda e: self.schedule_title_commit())

        self.tag_row = tk.Frame(self.main, bg=C["bg"])
        self.tag_row.pack(fill="x", padx=18, pady=(0, 3))
        self.tagbtn = Btn(self.tag_row, tr("태그 추가"), self.edit_tags, kind="primary", padx=10, pady=3)
        self.tagbtn.pack(side="left", padx=(0, 8))
        self.tag_labels = tk.Label(self.tag_row, text="", anchor="w", bg=C["bg"], fg=C["accent"], font=(self.ui, 9), cursor="hand2", pady=2)
        self.tag_labels.pack(side="left")
        self.tag_labels.bind("<Button-1>", self.edit_tags)
        tk.Frame(self.main, height=1, bg=C["line"]).pack(fill="x")
        self.statusbar = tk.Frame(self.main, bg=C["bg"])
        self.statusbar.pack(side="bottom", fill="x")
        self.status = tk.Label(self.statusbar, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=18, pady=4)
        self.status.pack(side="left")
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
        # 원문 편집 칸 위의 최소 서식 툴바(원문만·좌우 분할에서도 서식과 그림 첨부를 쓸 수 있게)
        tools = self.edit_tools = tk.Frame(self.edit_frame, bg=C["panel"])
        tools.pack(fill="x", padx=10, pady=(0, 4))
        self.undo_btn = Btn(tools, "↶", lambda: self.text_do("edit_undo"), kind="icon", padx=8, pady=1)
        self.redo_btn = Btn(tools, "↷", lambda: self.text_do("edit_redo"), kind="icon", padx=8, pady=1)
        self.undo_btn.pack(side="left", padx=1)
        self.redo_btn.pack(side="left", padx=1)
        self.tip(self.undo_btn, tr("실행 취소 (Ctrl+Z)"))
        self.tip(self.redo_btn, tr("다시 실행 (Ctrl+Y)"))
        tk.Frame(tools, width=1, bg=C["line"]).pack(side="left", fill="y", padx=6, pady=3)
        for label, hint, act in (("B", tr("굵게 (Ctrl+B)"), ("wrap", "b")), ("I", tr("기울임 (Ctrl+I)"), ("wrap", "i")), ("S", tr("취소선"), ("wrap", "s")),
                                 ("H", tr("제목"), ("heading", 2)), ("•", tr("글머리 목록"), ("line", "ul")), ("1.", tr("번호 목록"), ("line", "ol")),
                                 ("☐", tr("할 일"), ("line", "task")), ("❝", tr("인용"), ("line", "quote")), ("</>", tr("코드"), ("wrap", "code")),
                                 ("🔗", tr("링크"), ("wrap", "link")), ("🖼", tr("그림·파일 첨부 (리소스 폴더로 복사)"), None)):
            b = Btn(tools, label, (lambda a=act: self.run_action(a)) if act else self.attach_files, kind="icon", padx=8, pady=1,
                    font=(self.ui, 10, "bold" if label in ("B", "H") else "normal"))
            b.pack(side="left", padx=1)
            self.tip(b, hint)
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
        # 숨기지 않고 본문 전체에 place 한 채 위로 올리고(미리보기) 아래로 내린다(평소). grid 칸 너비에 영향을 받지 않는다.
        self.pv_frame = tk.Frame(self.body, bg=C["bg"])
        self.pv_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
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
        self.view.bind("<<Copy>>", self.view_copy)                       # 표·서식을 HTML 로도 복사(웹 에디터에 표로 붙음)
        self.text.bind("<<Paste>>", self.text_paste)                     # 웹에서 복사한 표(HTML)는 마크다운 표로
        self.text.bind("<Control-Shift-V>", self.plain_paste)            # 언제나 글자만 붙인다
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
        # 표(탭 정지점으로 열을 맞추므로 고정폭이 아니어도 된다): 칸마다 태그 테두리가 격자선. 이웃한 칸은 이름이 달라야 선이 그려진다(preview.table_px)
        # Tk 는 태그 이름이 아니라 속성(배경·테두리)이 같으면 이웃한 글을 한 상자로 합치므로, 이웃한 칸의 배경을 눈에 안 띄게 1단계씩 달리한다
        def near(color, k):
            ch = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
            return "#%02x%02x%02x" % tuple(c - k if c >= 128 else c + k for c in ch)
        for rp in (0, 1):
            for cp in (0, 1):
                v.tag_configure("tb%d%d" % (rp, cp), font=f["table"], background=near(C["bg"], rp * 2 + cp), relief="groove", borderwidth=1)
        for cp in (0, 1):
            v.tag_configure("th%d" % cp, font=f["tableb"], background=near(C["code"], cp), relief="groove", borderwidth=1)   # 머리행(굵게)
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
        for nm in TABLE_TAGS:
            v.tag_raise(nm)
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
            fid, rel = self.doc_key_parts(key)
            if rel:
                return rel.rsplit("/", 1)[-1]
            f = next((f for f in self.docs.folders() if f["id"] == fid), None)
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
        if not (q or f or t or tag or self.tag_none or self.adv_conditions):
            return messagebox.showinfo(APP, tr("저장할 검색이 없습니다. 검색어나 기간, 태그를 먼저 정하세요."), parent=self.root)
        lst = self.smart_list()
        cond = {"q": q, "d_from": f, "d_to": t, "tag": tag or "", "tag_none": self.tag_none,
                "advanced": [dict(x) for x in self.adv_conditions], "sort": self.sort, "asc": self.asc}
        if overwrite:
            for s in lst:
                if s["id"] == overwrite:
                    s.update(cond)
            sid = overwrite
        else:
            default_name = "태그 없음" if self.tag_none else f"# {tag}" if tag else "고급 검색" if self.adv_conditions else "검색"
            name = simpledialog.askstring(tr("검색 저장"), tr("이 검색의 이름:"), initialvalue=q or tr(default_name), parent=self.root)
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
        self.tag_none = bool(s.get("tag_none", False))
        self.adv_conditions = [dict(x) for x in s.get("advanced", []) if isinstance(x, dict)]
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
        outl_names = [n for n in names if n == OUTL or n.startswith(OUTL + "/")]
        dfolders = self.docs.folders()
        doc_keys = ["@docs"] if dfolders else []
        doc_counts = self.docs.counts() if dfolders else {}
        for folder in dfolders:
            root_key = "@doc:" + folder["id"]
            doc_keys.append(root_key)
            subfolders = self.docs.subfolders(folder["id"])
            for rel, count in sorted(subfolders.items(), key=lambda item: (item[0].count("/"), item[0].lower())):
                doc_key = root_key + "/" + rel
                doc_keys.append(doc_key)
                doc_counts[doc_key] = count
        smarts = self.smart_list()
        smart_keys = (["@smarts"] + ["@smart:" + s["id"] for s in smarts]) if smarts else []
        if self.nb not in (ALL, "", FAVS, QUICK, CAL, TRASH) and self.nb not in names and self.nb not in doc_keys and self.nb not in smart_keys:
            self.nb = ALL
        if not self.feat["outl"] and self.nb in outl_names:
            self.nb = ALL
        outl = outl_names if self.feat["outl"] else []
        quick = ([FAVS] if self.feat["favs"] else []) + outl + ([CAL] if self.feat["cal"] else [])
        if self.nb == CAL and not self.feat["cal"]:
            self.nb = ALL
        if self.nb == FAVS and not self.feat["favs"]:
            self.nb = ALL
        self.nb_keys = [ALL] + ([QUICK] + quick if quick else []) + [""] + [n for n in names if n not in outl_names] + doc_keys + smart_keys + [TRASH]
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
                label, count, parent = tr("모든 파일"), len(self.all_notes) + sum(doc_counts.get(f["id"], 0) for f in dfolders), ""   # 노트 + 가져온 문서
            elif key == "":
                label, count, parent = self.store.root_name, None, ""   # 저장 폴더 줄에는 숫자를 달지 않는다(아래 노트북들이 실제 내용)
            elif key == "@docs":
                n_docs = sum(doc_counts.get(f["id"], 0) for f in dfolders)
                label, count, parent = tr("가져온 폴더"), n_docs or None, ""
            elif key.startswith("@doc:"):
                fid, rel = self.doc_key_parts(key)
                root_key = "@doc:" + fid
                label = self.nb_label(key)
                # 최상위 가져온 폴더는 하위 폴더까지 포함한 전체 수, 하위 폴더는 그 폴더 아래 수.
                n_docs = doc_counts.get(fid, 0) if not rel else doc_counts.get(key, 0)
                count = n_docs or None
                parent_key = root_key + ("/" + rel.rpartition("/")[0] if "/" in rel else "") if rel else "@docs"
                parent = f"nb{idx[parent_key]}"
            elif key == "@smarts":
                label, count, parent = tr("저장된 검색"), None, ""
            elif key.startswith("@smart:"):
                label, count, parent = self.nb_label(key), None, f"nb{idx['@smarts']}"
            else:
                label, count = self.nb_short(key), total(key)
                # 최상위 노트북은 저장 폴더 항목(scrapbook) 아래에 들여써서 보여 준다
                parent = f"nb{idx[key.rsplit('/', 1)[0]]}" if "/" in key else f"nb{idx['']}"
            self.nbtree.insert(parent, "end", iid=f"nb{i}", text="  " + label + ("" if count is None else f"   {count:,}"), values=("" if count is None else f"{count:,}",),
                               open=self.nb_open.get(key, not key.startswith("@doc:")))   # 가져온 폴더(와 그 하위 폴더)는 기본으로 접어 둔다
        self.nbtree.selection_set(f"nb{idx[self.nb]}")
        self.nbtree.see(f"nb{idx[self.nb]}")   # 고른 항목이 접힌 폴더 안이면 그 위쪽만 펼쳐 보인다
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
        if self.tag_global:
            sources = self.all_notes
            doc_counts = self.docs.tag_counts()
            untagged = sum(not n["tags"] for n in sources) + self.docs.untagged_count()
        else:
            sources = self.notes
            doc_counts = {}
            untagged = sum(not n["tags"] for n in sources)
        for n in sources:
            for t in n["tags"]:
                counts[t] = counts.get(t, 0) + 1
        for t, c in doc_counts.items():
            counts[t] = counts.get(t, 0) + c
        self.tag_keys = [None] + tagac.ordered_tags(counts, getattr(self, "tag_sort", "frequency"))
        self.quiet = True
        self.tagtree.delete(*self.tagtree.get_children())
        self.tagtree.insert("", "end", iid="tg0", text=f"  {tr('태그 없음')}   {untagged:,}", values=(f"{untagged:,}",))
        for i, t in enumerate(self.tag_keys[1:], 1):
            self.tagtree.insert("", "end", iid=f"tg{i}", text="  # " + t + f"   {counts[t]:,}", values=(f"{counts[t]:,}",))
        selection = self.tagtree.selection()
        if selection:
            self.tagtree.selection_remove(*selection)
        if self.tag_none:
            self.tagtree.selection_set("tg0")
        elif self.tag in self.tag_keys[1:]:
            self.tagtree.selection_set(f"tg{self.tag_keys.index(self.tag)}")
        self.fit_count(self.tagtree, [f"{untagged:,}"] + [f"{c:,}" for c in list(counts.values())[:200]])
        self.quiet = False

    def show_tag_sort(self):
        if getattr(self, "tag_sort_menu", None):
            self.tag_sort_menu.destroy()
        menu = self.tag_sort_menu = tk.Menu(self.root, tearoff=0)
        selected = self.tag_sort_selection = tk.StringVar(master=self.root, value=self.tag_sort)
        for value, label in (("frequency", tr("빈도순")), ("name", tr("이름순 (한글 → 영어)"))):
            menu.add_radiobutton(label=label, variable=selected, value=value,
                                 command=lambda value=value: self.change_tag_sort(value))
        try:
            menu.tk_popup(self.tag_sort_btn.winfo_rootx(), self.tag_sort_btn.winfo_rooty() + self.tag_sort_btn.winfo_height())
        finally:
            menu.grab_release()

    def change_tag_sort(self, mode):
        self.tag_sort = "name" if mode == "name" else "frequency"
        st.write_config(tagSort=self.tag_sort)
        self.tag_sort_btn.config(text=tr("이름순") if self.tag_sort == "name" else tr("빈도순"))
        self.reload_tags()

    def toggle_tag_scope(self):
        self.tag_global = not self.tag_global
        st.write_config(tagGlobal=self.tag_global)
        self.tag_scope_btn.config(text=tr("전체 범위") if self.tag_global else tr("현재 범위"))
        self.reload_tags()

    def clear_tag(self):
        if self.tag or self.tag_none:
            self.tag = None
            self.tag_none = False
            self.tagtree.selection_remove(*self.tagtree.selection())
            self.refresh()

    def on_tag_click(self, e):
        row = self.tagtree.identify_row(e.y)
        if not row or e.state & 0x5:   # Ctrl/Shift+클릭은 여러 개 고르기라서 노트를 거르지 않는다
            return
        tag = self.tag_keys[int(row[2:])]
        if tag is None:
            self.tag_none = not self.tag_none
            self.tag = None
        else:
            self.tag_none = False
            self.tag = None if tag == self.tag else tag   # 선택된 태그를 다시 누르면 해제
        if self.tag is None and not self.tag_none:
            self.tagtree.selection_remove(*self.tagtree.selection())
        self.refresh()

    def on_nb_toggle(self, opened):
        """노트북 목록에서 삼각형을 눌러 펼치거나 접은 것을 기억한다(목록을 다시 그려도 그대로 두려고)"""
        if self.quiet:
            return
        iid = self.nbtree.focus()
        if iid and iid.startswith("nb") and iid[2:].isdigit() and int(iid[2:]) < len(self.nb_keys):
            self.nb_open[self.nb_keys[int(iid[2:])]] = opened

    def nb_set_all(self, opened):
        """노트북 목록의 하위가 있는 항목을 모두 펼치거나 모두 접는다"""
        def walk(parent=""):
            for c in self.nbtree.get_children(parent):
                if self.nbtree.get_children(c):
                    self.nbtree.item(c, open=opened)
                    self.nb_open[self.nb_keys[int(c[2:])]] = opened
                walk(c)
        walk()

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
                fid, rel = self.doc_key_parts(key)
                m.add_command(label=tr("다시 읽기"), command=lambda: self.scan_docs(fid))
                if not rel:
                    m.add_command(label=tr("목록에서 빼기 (원본 파일은 그대로)"), command=lambda: self.remove_doc_folder(fid))
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
            self.nb, self.tag, self.tag_none, self.adv_conditions = ALL, None, False, []
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
        self.nb, self.tag, self.tag_none, self.adv_conditions = ALL, None, False, []
        self.hist, self.hpos = [], -1
        self.close_note()
        self.reload_notes()
        return True

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

    def refresh_all(self, e=None):
        """전체 새로 고침(F5·⟳): 탐색기 등 앱 밖에서 노트북·노트를 지우거나 옮겼을 때, 껐다 켜지 않고 노트·노트북·태그·즐겨찾기·달력·가져온 문서를 다시 읽는다"""
        self.flush()
        for fn in (self.fav.invalidate, self.planner.sync):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        self.reload_notes(keep_scroll=True)
        if self.docs.folders():
            self.rescan_docs_bg()
        self.status.config(text=tr("새로 고쳤습니다"))
        return "break"

    def read_all_notes(self):
        self.load_prog = (0, 0)
        return self.store.list_notes(ALL, tagger=note_tags, progress=lambda d, t: setattr(self, "load_prog", (d, t)))

    def apply_loaded(self, loaded, keep_scroll=False):
        keep = self.cur["path"] if self.cur else None
        self.all_notes = loaded
        if self.nb.startswith("@doc"):   # 가져온 폴더를 골랐으면 목록은 노트가 아니라 가져온 문서
            fid = self.doc_key_parts(self.nb)[0] if self.nb.startswith("@doc:") else None
            self.notes = self.docs.list_docs(fid)
            if fid:
                root = self.doc_root(fid)
                rel = self.doc_key_parts(self.nb)[1]
                if root:
                    cur = self.dnorm(os.path.join(root, *rel.split("/"))) if rel else self.dnorm(root)
                    self.notes = [n for n in self.notes if self.dnorm(os.path.dirname(n["path"])) == cur
                                  or self.dnorm(os.path.dirname(n["path"])).startswith(cur + os.sep)]
                else:
                    self.notes = []
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

    def open_advanced_search(self):
        top = tk.Toplevel(self.root)
        top.title(tr("고급 검색"))
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.resizable(False, False)
        top.geometry(f"700x310+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 80}")
        tk.Label(top, text=tr("조건을 고르고 AND·OR·NOT으로 결합합니다. NOT은 앞 조건에 이어 제외합니다."),
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")

        old = {c.get("field"): c for c in self.adv_conditions if isinstance(c, dict)}
        known_tags = {t for n in self.all_notes for t in n["tags"]}
        known_tags.update(self.docs.tag_counts())
        no_tag_label = "◌ " + tr("태그 없음")
        tag_options = [no_tag_label] + ["#" + t for t in sorted(known_tags, key=str.lower)]
        folders = self.docs.folders()
        folder_labels = [f'{f.get("name") or f["path"]} ({f["path"]})' for f in folders]
        folder_by_label = dict(zip(folder_labels, (f["id"] for f in folders)))
        extensions = sorted({"md"} | {str(x).lower().lstrip(".") for x in self.docs.cfg().get("exts", []) if x})

        body = tk.Frame(top, bg=C["bg"], padx=16)
        body.pack(fill="both", expand=True)
        rows = []

        def add_row(field, label, value):
            previous = old.get(field, {})
            row = tk.Frame(body, bg=C["bg"])
            row.pack(fill="x", pady=3)
            enabled = tk.BooleanVar(value=field in old)
            tk.Checkbutton(row, text=tr(label), variable=enabled, bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                           selectcolor=C["bg"], font=(self.ui, 9), width=15, anchor="w").pack(side="left")
            op = tk.StringVar(value=previous.get("op", "AND"))
            combo = ttk.Combobox(row, textvariable=op, values=("AND", "OR", "NOT"), width=6, state="readonly")
            combo.pack(side="left", padx=(0, 8))
            entry = None
            if field == "date":
                start = tk.StringVar(value=previous.get("from", ""))
                end = tk.StringVar(value=previous.get("to", ""))
                tk.Label(row, text=tr("시작"), bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                tk.Entry(row, textvariable=start, width=13).pack(side="left", padx=(4, 10))
                tk.Label(row, text=tr("끝"), bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                tk.Entry(row, textvariable=end, width=13).pack(side="left", padx=(4, 0))
                entry = (start, end)
            else:
                options = {"tag": tag_options, "folder": folder_labels, "extension": extensions}[field]
                entry = tk.StringVar()
                if field == "tag":
                    entry.set(no_tag_label if previous.get("untagged") else "#" + previous.get("value", "") if previous else "")
                elif field == "folder":
                    entry.set(next((name for name, fid in folder_by_label.items() if fid == previous.get("value")), ""))
                else:
                    entry.set(previous.get("value", ""))
                ttk.Combobox(row, textvariable=entry, values=options, width=42, state="readonly").pack(side="left", fill="x", expand=True)
            rows.append((field, enabled, op, entry))

        add_row("date", "기간", None)
        add_row("tag", "태그", None)
        add_row("folder", "가져온 폴더", None)
        add_row("extension", "확장자", None)

        def apply():
            conditions = []
            for field, enabled, op, value in rows:
                if not enabled.get():
                    continue
                cond = {"field": field}
                if field == "date":
                    start, end = (v.get().strip() for v in value)
                    if not start and not end:
                        return messagebox.showinfo(APP, tr("기간을 하나 이상 입력하세요."), parent=top)
                    if (start and search.parse_date(start) is None) or (end and search.parse_date(end, True) is None):
                        return messagebox.showerror(APP, tr("날짜 형식을 확인하세요. 예: 20240131"), parent=top)
                    cond.update({"from": start, "to": end})
                elif field == "tag":
                    selected = value.get()
                    if not selected:
                        return messagebox.showinfo(APP, tr("태그를 선택하세요."), parent=top)
                    if selected == no_tag_label:
                        cond["untagged"] = True
                    else:
                        cond["value"] = selected[1:] if selected.startswith("#") else selected
                elif field == "folder":
                    selected = value.get()
                    if selected not in folder_by_label:
                        return messagebox.showinfo(APP, tr("가져온 폴더를 선택하세요."), parent=top)
                    cond["value"] = folder_by_label[selected]
                else:
                    selected = value.get().strip().lower().lstrip(".")
                    if not selected:
                        return messagebox.showinfo(APP, tr("확장자를 선택하세요."), parent=top)
                    cond["value"] = selected
                cond["op"] = op.get()
                conditions.append(cond)
            self.adv_conditions = conditions
            top.destroy()
            self.refresh()

        buttons = tk.Frame(top, bg=C["bg"], padx=16, pady=12)
        buttons.pack(fill="x")
        Btn(buttons, tr("취소"), top.destroy, padx=14).pack(side="right", padx=(6, 0))
        Btn(buttons, tr("검색 적용"), apply, kind="primary", padx=14).pack(side="right")
        top.bind("<Escape>", lambda _e: top.destroy())
        top.grab_set()

    def schedule_search(self):
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.search_job = self.root.after(180, self.refresh)

    def refresh(self, keep_page=False):
        """검색·정렬을 다시 하고 목록을 그린다. keep_page=True 는 자동 저장 때처럼 보던 자리를 유지"""
        self.search_job = None
        if self.tag_none:
            pool = [n for n in self.notes if not n["tags"]]
        elif self.tag:
            pool = [n for n in self.notes if self.tag in n["tags"]]
        else:
            pool = self.notes
        if self.nb.startswith("@doc:"):
            fid, rel = self.doc_key_parts(self.nb)
            root = self.doc_root(fid)
            if root:
                cur = self.dnorm(os.path.join(root, *rel.split("/"))) if rel else self.dnorm(root)
                searching_docs = bool(self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip()
                                      or self.tag or self.tag_none or self.adv_conditions)
                if searching_docs:
                    pool = [n for n in pool if self.dnorm(os.path.dirname(n["path"])) == cur
                            or self.dnorm(os.path.dirname(n["path"])).startswith(cur + os.sep)]
                else:
                    pool = [n for n in pool if self.dnorm(os.path.dirname(n["path"])) == cur]
        self.bad_dates = search.bad_dates(self.q.get(), self.d_from.get(), self.d_to.get()) + search.bad_advanced_dates(self.adv_conditions)
        if self.bad_dates:   # 날짜를 읽을 수 없으면 기간 없이 찾지 말고 비워서 알린다
            self.results, self.words = [], []
        else:
            self.results, self.words = search.run(pool, self.q.get(), self.sort, self.asc, self.d_from.get(), self.d_to.get(),
                                                  index=None if self.nb == TRASH else self.docs if self.nb.startswith("@doc") else
                                                  docidx.Combined(self.store, self.docs) if self.scope_all() else self.store)
            if self.adv_conditions:
                self.results = [n for n in self.results if search.advanced_match(n, self.adv_conditions, self.sort)]
        self.draw_list(keep_scroll=keep_page)

    @staticmethod
    def dnorm(path):
        return os.path.normcase(os.path.normpath(path))

    @staticmethod
    def doc_key_parts(key):
        """가져온 폴더 노드 키 → (등록 폴더 ID, 상대 하위 폴더 경로)."""
        fid, _, rel = key[5:].partition("/")
        return fid, rel

    def doc_root(self, fid):
        folder = next((f for f in self.docs.folders() if f["id"] == fid), None)
        return os.path.normpath(folder["path"]) if folder else None

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
        searching = self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip() or self.tag or self.tag_none or self.adv_conditions
        unit = i18n.unit("파일") if self.scope_all() or self.nb.startswith("@doc") else i18n.unit("노트")
        text = tr('{0:,}개 중 {1:,}개 찾음').format(len(self.notes), total) if searching else tr('{0:,}개의 {1}').format(total, unit)
        if getattr(self, "bad_dates", None):
            text = tr("날짜를 읽을 수 없습니다: ") + ", ".join(self.bad_dates) + tr("  (예: date:20200202-20221231)")
        if self.tag:
            text += f"  ·  # {self.tag}"
        elif self.tag_none:
            text += "  ·  " + tr("태그 없음")
        if self.adv_conditions:
            text += "  ·  " + tr("고급 검색")
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
            if self.sort == "ctime" and n.get("created_known") is False:
                meta += " " + tr("(기준일)")
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
                self.fav_move(n["path"], self.store.move(n["path"], nb))
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

    def open_with_program(self, ext):
        """확장자에 지정해 둔 연결 프로그램 경로(없거나 파일이 없어졌으면 None). 옵션에 따로 두지 않고 우클릭으로 지정한다."""
        exe = (st.read_config().get("openWith") or {}).get(ext.lower().lstrip("."))
        return exe if isinstance(exe, str) and os.path.isfile(exe) else None

    def set_open_with(self, ext, exe):
        table = dict(st.read_config().get("openWith") or {})
        key = ext.lower().lstrip(".")
        if exe:
            table[key] = exe
        else:
            table.pop(key, None)
        st.write_config(openWith=table)

    def pick_open_with(self, n):
        ext = n["ext"]
        exe = filedialog.askopenfilename(parent=self.root, title=tr('.{0} 파일을 열 프로그램 고르기').format(ext),
                                         filetypes=[(tr("프로그램"), "*.exe"), (tr("모든 파일"), "*.*")])
        if exe:
            self.set_open_with(ext, os.path.normpath(exe))

    def open_doc_file(self, n):
        exe = self.open_with_program(n["ext"])
        try:
            if exe:   # 사용자가 이 확장자에 지정한 프로그램(예: zip → 만화 뷰어). 셸을 거치지 않고 경로를 인자로만 넘긴다
                paths = [os.path.normpath(n["path"])]
                # WaterView/NeeView 같은 미디어 뷰어는 여러 경로를 한 번에
                # 넘기면 재생목록으로 연다. 가져온 파일을 한 곡씩 여는 대신
                # 같은 폴더의 오디오·동영상만 모아 현재 파일부터 재생한다.
                media_exts = set(docidx.AUDIO_EXT) | {"mp4", "webm", "ogv", "mov", "avi", "mkv"}
                if n.get("ext", "").lower() in media_exts:
                    folder = os.path.dirname(os.path.normpath(n["path"]))
                    try:
                        siblings = []
                        for item in os.scandir(folder):
                            if item.is_file() and os.path.splitext(item.name)[1].lower().lstrip(".") in media_exts:
                                siblings.append(os.path.normpath(item.path))
                        current = paths[0].casefold()
                        paths += sorted((p for p in siblings if p.casefold() != current), key=str.casefold)
                    except OSError:
                        pass
                # WaterView/NeeView는 --slideshow on으로 파일 종료 후 다음
                # 항목으로 자동 진행한다. 다른 연결 프로그램에는 옵션을
                # 넘기지 않는다.
                viewer = os.path.basename(exe).lower()
                launch = [exe]
                if viewer in {"waterview.exe", "neeview.exe"} and len(paths) > 1:
                    launch += ["--slideshow", "on"]
                subprocess.Popen([*launch, *paths])
            else:
                os.startfile(n["path"])
        except OSError as ex:
            messagebox.showerror(APP, tr('파일을 열지 못했습니다.\n{0}').format(ex), parent=self.root)

    def doc_menu(self, e, n):
        self.open_note(n)
        lm = self.listmenu
        lm.delete(0, "end")
        lm.add_command(label=tr("연결 프로그램으로 열기") if self.open_with_program(n["ext"]) else tr("기본 프로그램으로 열기"), command=lambda: self.open_doc_file(n))
        lm.add_command(label=tr('.{0} 파일을 열 프로그램 지정…').format(n["ext"]), command=lambda: self.pick_open_with(n))
        if self.open_with_program(n["ext"]):
            lm.add_command(label=tr('.{0} 연결 해제 (윈도 기본 프로그램으로)').format(n["ext"]), command=lambda: self.set_open_with(n["ext"], None))
        lm.add_command(label=tr("태그 추가·고치기…"), command=self.edit_tags)
        lm.add_command(label=tr("메모…"), command=self.edit_memo)
        lm.add_separator()
        lm.add_command(label=tr("파일 위치 열기"), command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_command(label=tr("경로 복사"), command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(n["path"])))
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    # ---- 즐겨찾기(설정 폴더의 작은 파일에 적어 폰과 맞춘다)
    def fav_move(self, old_path, new_path):
        """이름을 바꾸거나 옮긴 노트의 즐겨찾기를 새 경로로 옮긴다"""
        try:
            self.fav.move(favorites.rel_of(self.store.root, old_path), favorites.rel_of(self.store.root, new_path))
        except Exception:  # noqa: BLE001
            pass

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
        if st.conflict_of(os.path.basename(n["path"])):
            lm.add_command(label=tr("동기화 충돌 해결…"), command=lambda: self.conflict_dialog(n))
            lm.add_separator()
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
            self.fav_move(n["path"], new)
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
