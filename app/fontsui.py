"""글꼴과 ttk 모양(테마 적용)을 맞추는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import notes_shared as _shared  # noqa: E402   (글꼴 설정을 공용 모듈과 맞춘다)


class FontsMixin:
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
