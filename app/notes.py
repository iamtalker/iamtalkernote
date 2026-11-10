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
from favoritesui import FavoritesMixin  # noqa: E402   (즐겨찾기의: favoritesui.py)
from notelist import NoteListMixin  # noqa: E402   (노트: notelist.py)
from savedsearch import SavedSearchMixin  # noqa: E402   (저장된: savedsearch.py)
from notebooks import NotebooksMixin  # noqa: E402   (노트북과: notebooks.py)
from toolsmenu import ToolsMenuMixin  # noqa: E402   (도구: toolsmenu.py)
from embedded import EmbeddedMixin  # noqa: E402   (도구: 글자로 박힌 그림 일괄 분리: embedded.py)
from menubar import MenuBarMixin  # noqa: E402   (메뉴줄(파일·편집·보기·이동·도구·도움말)을: menubar.py)
from fontsui import FontsMixin  # noqa: E402   (글꼴과: fontsui.py)
from outlinermix import OutlinerMixin  # noqa: E402   (아웃라이너·렌더링 글 고치기: outlinermix.py)
from rendersync import RenderSyncMixin  # noqa: E402   (렌더링: rendersync.py)
from noteio import NoteIOMixin  # noqa: E402   (노트를: noteio.py)
from restorepoints import RestorePointMixin  # noqa: E402   (복원: restorepoints.py)
from optionsui import OptionsMixin  # noqa: E402   (설정: optionsui.py)
from noteinfo import NoteInfoMixin  # noqa: E402   (노트: noteinfo.py)
from clipmixin import ClipperServerMixin  # noqa: E402   (웹: clipmixin.py)
from formattools import FormatToolsMixin  # noqa: E402   (서식: formattools.py)


class App(EmbeddedMixin, DialogsMixin, SearchBoxMixin, TagEditMixin, WikiUIMixin, FindBarMixin, DocFoldersMixin, FormatToolsMixin, ClipperServerMixin, NoteInfoMixin, OptionsMixin, RestorePointMixin, NoteIOMixin, RenderSyncMixin, OutlinerMixin, FontsMixin, MenuBarMixin, ToolsMenuMixin, NotebooksMixin, SavedSearchMixin, NoteListMixin, FavoritesMixin):
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
        opt_line = tk.Frame(top, bg=C["bg"])   # 두 번째 줄: 자동완성 · 문서 내부 검색
        opt_line.pack(fill="x", pady=(3, 0))
        left_actions = tk.Frame(action_bar, bg=C["bg"])
        left_actions.pack(side="left")
        right_actions = tk.Frame(action_bar, bg=C["bg"])
        right_actions.pack(side="right")
        self.new_btn = Btn(opt_line, tr("＋ 새 노트"), self.new_note, kind="primary", bold=True, pady=5)   # 두 번째 줄 끝(문서 내부 검색 오른쪽)
        refresh = Btn(right_actions, "⟳", self.refresh_all, pady=5, font=(self.ui, 12))
        refresh.pack(side="right", padx=(7, 0))
        self.tip(refresh, tr("새로 고침 (F5): 탐색기 등 앱 밖에서 폴더·노트를 지우거나 옮겼을 때 다시 읽습니다"))
        self.search_btn = Btn(left_actions, tr("검색"), self.search_now, bold=True, pady=5)
        self.search_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.search_btn.pack(side="left", padx=(4, 0))   # 치는 즉시 검색하지만, 눌러서 바로 다시 검색할 수도 있다
        self.advanced_search_btn = Btn(left_actions, tr("고급 검색"), self.open_advanced_search, pady=5)
        self.advanced_search_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.advanced_search_btn.pack(side="left", padx=(7, 0))
        self.v_suggest = tk.BooleanVar(value=bool(st.read_config().get("searchSuggest", False)))
        self.ac_on = self.v_suggest.get()

        def set_suggest_bar():
            self.ac_on = self.v_suggest.get()
            st.write_config(searchSuggest=self.ac_on)
            if not self.ac_on:
                self.ac_hide()
        tk.Checkbutton(opt_line, text=tr("자동완성"), variable=self.v_suggest, command=set_suggest_bar, takefocus=False,
                       bg=C["bg"], activebackground=C["bg"], fg=C["sub"], selectcolor=C["bg"], cursor="hand2", font=(self.ui, 9)).pack(side="left")
        self.new_btn.pack(side="left", padx=(12, 0))
        self.tip(self.search_btn, tr("자동완성 체크: 입력하는 동안 제목·태그 후보를 보여 줍니다"))
        self.random_btn = Btn(left_actions, tr("랜덤"), self.open_random_note, pady=5)   # 고급 검색 오른쪽: 랜덤 노트
        self.random_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.random_btn.pack(side="left", padx=(7, 0))
        self.tip(self.random_btn, tr("랜덤 노트 열기"))
        self.nav_row = tk.Frame(left_actions, bg=C["bg"])   # 목록 안에서 앞·뒤 노트로(문서 내부 검색 체크 오른쪽, 갱신 단추 쪽)
        self.nav_row.pack(side="left", padx=(7, 0))
        self.prev_btn = Btn(self.nav_row, "←", lambda: self.step_note(-1), pady=5, font=(self.ui, 11))
        self.prev_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.prev_btn.pack(side="left")
        self.next_btn = Btn(self.nav_row, "→", lambda: self.step_note(1), pady=5, font=(self.ui, 11))
        self.next_btn.configure(highlightthickness=1, highlightbackground=C["line"])
        self.next_btn.pack(side="left", padx=(4, 0))
        self.tip(self.prev_btn, tr("이전 노트"))
        self.tip(self.next_btn, tr("다음 노트"))
        self.v_content = tk.BooleanVar(value=self.docs.content_search)
        self.opt_row = tk.Frame(opt_line, bg=C["bg"])
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
        self.ac_gap = tk.Frame(f, bg=C["bg"])   # 자동완성 후보가 뜨면 이 자리에 들어가고, 아래의 노트 목록이 그만큼 밀려 내려간다
        self.ac_gap.pack(fill="x")
        self.ac_gap.pack_propagate(False)   # 높이는 후보 목록이 차지하는 만큼만 정한다
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
                self.opt_row.pack(side="left", padx=(8, 0), before=self.new_btn)
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
