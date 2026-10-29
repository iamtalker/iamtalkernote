"""iamtalkernote — 위키나루 기반 마크다운 노트 앱 (표준 라이브러리 tkinter).

    pythonw iamtalkernote.pyw          (콘솔 창 없이)      또는   python notes.py

조플린처럼: 메뉴줄(파일·편집·보기·이동·도구·도움말) · 노트북/태그 사이드바 · 노트 목록 · 서식 도구줄이 있는 에디터.
위키나루의 마크다운 렌더링·문법 해설, 폴더검색의 검색, 조플린 클리퍼 플러스(웹 클리퍼) 연동.
노트는 .md 파일로 저장된다.
"""
import base64
import bisect
import hashlib
import math
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from urllib.parse import unquote
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bulk  # noqa: E402
import cleanup  # noqa: E402
import clipserver  # noqa: E402
import docs as docidx  # noqa: E402   (노트 폴더 밖의 pdf·txt·mp3 … 가져오기)
import editor as ed # noqa: E402   (위키나루: 서식 도구·그림 불러오기)
import ime  # noqa: E402   (한글 입력기가 조합 중인 글자를 자동완성에서 보려고)
import preview  # noqa: E402
import search  # noqa: E402
import snapshots as sn  # noqa: E402
import single  # noqa: E402   (앱을 한 번에 하나만: 두 번째 실행은 실행 중인 앱의 창을 열어 달라고 알리고 끝난다)
import store as st  # noqa: E402
import tray  # noqa: E402   (닫기 버튼을 누르면 앱을 끄지 않고 알림 영역 아이콘으로)
import updater  # noqa: E402
import wikiconv  # noqa: E402
import winpreview  # noqa: E402   (윈도 미리보기 처리기를 노트 화면 안에: pdf·mp3 …)
from version import VERSION  # noqa: E402

APP = "iamtalkernote"
LIST_CHUNK = 100   # 노트 목록은 이만큼씩 이어서 그린다(스크롤하면 계속)
VIEWABLE = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".pdf", ".txt"}   # 안 쓰는 미디어 목록에서 눌렀을 때 바로 열어도 되는 파일(실행 파일 등은 위치만 보여 준다)
SOURCE_LINE = re.compile(r"\A[ \t]*원본:[ \t]*<?https?://[^\s>]+>?[ \t]*(?:\r?\n)+")   # 글 맨 위의 '원본: <주소>' 줄
DOC_RESCAN_SECONDS = 300   # 앱을 열어 두는 동안 가져온 폴더를 이 간격(초)마다 훑어 바뀐 파일만 다시 읽는다
PREVIEW_EXT = ("pdf", *docidx.AUDIO_EXT, *docidx.OFFICE_EXT)   # 윈도 미리보기 처리기로 원본을 보여 줄 형식(txt·md 같은 글 파일은 글로)
MORE_MAX = 4000      # 목록을 이어 그릴 때 한 번에 붙이는 노트 수의 상한(이미 그린 만큼을 붙이되 이 이상은 안 붙인다)
MORE_MAX_SEARCH = 600  # 검색 중에는 노트마다 본문을 읽어 미리 보기를 만들어서 더 적게
MORE_SCREENS = 4  # 목록 아래에 남은 글이 이만큼의 화면보다 적어지면 미리 다음 노트들을 이어 그린다
ALL = "*"
FMT = "markdown"

# 밝고 차분한 색 하나(보라) + 슬레이트 회색
C = dict(ed.THEME)
C.update(bg="#ffffff", panel="#f6f7f9", line="#e6e8ec", text="#1f2937", muted="#8a93a2", sub="#4b5563",
         accent="#7c3aed", accent_d="#6d28d9", soft="#efe9fe", hover="#eceef2", seg="#eceef2",
         danger_bg="#fee2e2", danger="#b91c1c", sel="#ddd6fe", code="#f3f4f6", mark="#fde68a")
C.update(thumb="#cfd4dc", thumb_h="#aab1bd", on_accent="#ffffff", accent_h="#8b4cf0")
BASE = dict(C)   # 기본(라이트 보라) 값. 테마를 바꿀 때마다 여기서 다시 시작한다

DEFAULT_THEME = "라이트 보라"
_DARK = dict(bg="#1f2128", panel="#181a20", line="#32353f", text="#e6e8ee", muted="#8d95a5", sub="#b7bdc9",
             hover="#2a2d36", seg="#2a2d36", code="#272a33", mark="#6f5f12", danger_bg="#4a1f24", danger="#f87171",
             thumb="#454a57", thumb_h="#5b6170")
THEMES = {   # BASE 와 다른 값만 적는다
    "라이트 보라": {},
    "라이트 파랑": dict(accent="#2563eb", accent_d="#1d4ed8", soft="#dbeafe", sel="#bfdbfe"),
    "라이트 초록": dict(accent="#059669", accent_d="#047857", soft="#d1fae5", sel="#a7f3d0"),
    "라이트 분홍": dict(accent="#db2777", accent_d="#be185d", soft="#fce7f3", sel="#fbcfe8"),
    "세피아": dict(bg="#fbf5e9", panel="#f3ead8", line="#e4d7bd", text="#3b2f20", muted="#8c7b62", sub="#5d4e3a",
                 accent="#b45309", accent_d="#92400e", soft="#f5e2c3", hover="#efe4cb", seg="#efe4cb", sel="#ecd3a5",
                 code="#f0e6d0", mark="#f7d774", thumb="#d8c9aa", thumb_h="#bba980"),
    "다크 보라": dict(_DARK, accent="#a78bfa", accent_d="#8b5cf6", soft="#2f2a52", sel="#4a3f85"),
    "다크 파랑": dict(_DARK, accent="#60a5fa", accent_d="#3b82f6", soft="#1f3556", sel="#2f5384"),
}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(a, b, t):
    """a 와 b 를 섞는다 (t=0 이면 a, 1 이면 b)"""
    x, y = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x[i] * (1 - t) + y[i] * t) for i in range(3))


def luminance(h):
    r, g, b = (v / 255 for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def compute_theme(name, accent=None):
    """테마 이름(과 직접 고른 강조색)으로 색 사전을 만든다(화면은 건드리지 않는다)"""
    t = dict(BASE)
    t.update(THEMES.get(name, {}))
    if accent:
        dark = luminance(t["bg"]) < 0.5
        t["accent"] = accent
        t["accent_d"] = blend(accent, "#000000", 0.25)
        t["soft"] = blend(accent, t["bg"], 0.78 if dark else 0.88)
        t["sel"] = blend(accent, t["bg"], 0.6 if dark else 0.72)
    t["accent_h"] = blend(t["accent"], "#ffffff", 0.18)
    t["on_accent"] = "#ffffff" if luminance(t["accent"]) < 0.6 else "#1f2937"
    return t


def apply_theme(name, accent=None):
    """전역 색(C)을 바꾼다. 이미 만들어진 화면은 App.rebuild_ui 로 다시 그려야 반영된다."""
    t = compute_theme(name if name in THEMES else DEFAULT_THEME, accent)
    C.clear()
    C.update(t)
    Btn.refresh_kinds()


UI = "TkDefaultFont"   # App 이 맑은 고딕 등으로 바꾼다
TAG_LINE = re.compile(r"^[ \t]*(?:태그|tags?)[ \t]*[:：][ \t]*(.+)$", re.I | re.M)
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


HASH_FAST = re.compile(r"#([A-Za-z_가-힣][\w가-힣\-]*)")
BAD_PREV = set("#&/(=-.:[?")   # 이런 글자 바로 뒤의 #는 태그가 아니다(주소의 #앵커, 제목 등)
URL_RE = re.compile(r"(?:https?|ftp)://[^\s<>\]\)]+|file:///[^\s<>\]\)]+", re.I)   # 주소 속의 #(앵커·댓글 번호 …)는 태그가 아니다


def hashtags(text):
    """본문 속 #태그. '#' 가 있는 자리만 훑어서 빠르다."""
    out = []
    for m in HASH_FAST.finditer(text):
        i = m.start()
        if i:
            p = text[i - 1]
            if p.isalnum() or p == "_" or p in BAD_PREV:
                continue
        out.append(m.group(1))
    return out


def line_tags(body):
    """'태그: a, b' 줄에 적힌 태그들(줄 순서대로). 링크·괄호·긴 조각은 태그가 아니다(블로그의 'Tags: [블로그](주소)' 같은 줄)"""
    out = []
    if "태그" in body or "tag" in body or "Tag" in body or "TAG" in body:
        for m in TAG_LINE.finditer(body):
            for t in re.split(r"[,\s]+", m.group(1)):
                t = t.strip().lstrip("#")
                if t and len(t) <= 30 and not re.search(r"[\[\]()/<>]", t) and t not in out:
                    out.append(t)
    return out


def mask_protected(text):
    """코드·그림·주소 덩어리를 같은 길이의 공백으로 가린다(줄바꿈은 그대로): 그 속의 #는 태그가 아니라서 건너뛰되, 글자 위치는 그대로라
    찾은 자리를 원문에서 그대로 바꿀 수 있다('#태그http://…' 처럼 주소가 붙어 있어도 '#태그' 만 잡힌다)."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))   # noqa: E731
    return URL_RE.sub(blank, CODE_RE.sub(blank, st.DATA_IMG.sub(blank, text)))


def body_after_fm(body):
    """머리말(--- … ---)을 뺀 본문. 머리말의 title 등에 든 #는 태그가 아니고 이름 변경·삭제로 고칠 수도 없어서 태그를 찾을 때 뺀다"""
    m = st.FM_RE.match(body)
    return body[m.end():] if m else body


def note_tags(body):
    """태그: 머리말 tags, '태그: a, b' 줄, 본문 속 #해시태그(코드·주소·제목 제외).
    대부분의 노트에는 태그가 없으므로, 필요할 때만 무거운 처리를 한다."""
    tags = set(st.parse_meta(body)["tags"])
    rest = body_after_fm(body)
    tags.update(line_tags(rest))
    if "#" in rest and hashtags(rest):
        tags.update(hashtags(mask_protected(rest)))   # 후보가 있을 때만 코드·그림·주소를 가리고 다시 확인
    return tags


TAG_OK = re.compile(r"^[A-Za-z_가-힣][\w가-힣\-]*$")   # 본문에 '#이름' 으로 쓸 수 있는 이름


def clean_tag_name(name):
    """입력한 태그 이름을 정리한다: 앞의 # 를 떼고 공백은 _ 로. 쓸 수 없으면 ''"""
    t = re.sub(r"\s+", "_", (name or "").strip().lstrip("#").strip())
    return t if t and len(t) <= 30 and not re.search(r"[\[\]()/<>,]", t) else ""


def edit_tag(body, old, new):
    """노트 본문에서 태그 old 를 new 로 바꾼다(new 가 None 이면 지운다) → (새 본문, 센 수)
    태그는 세 군데에서 온다: 머리말 tags('fm'), 글 아래의 '태그: #a #b' 줄('line'), 본문 속 #해시태그('inline').
    코드·주소 속의 #는 태그가 아니라서 건드리지 않고, 본문에 못 쓰는 이름(공백·기호가 든 것)으로는 본문 #태그를 못 바꿔서 'stuck' 으로 센다."""
    counts = {"fm": 0, "line": 0, "inline": 0, "stuck": 0}
    body, counts["fm"] = st.fm_edit_tags(body, lambda t: (new if new else None) if t == old else t)
    m = st.FM_RE.match(body)
    head, rest = (body[:m.end()], body[m.end():]) if m else ("", body)
    for m in reversed(list(TAG_LINE.finditer(rest))):   # 글 아래의 '태그: …' 줄
        toks = re.findall(r"[^,\s]+", m.group(1))
        if not any(t.lstrip("#") == old and len(t) <= 31 for t in toks):
            continue
        out = []
        for t in toks:
            if t.lstrip("#") == old:
                t = ("#" if t.startswith("#") else "") + new if new else None
            if t and t.lstrip("#") not in [x.lstrip("#") for x in out]:
                out.append(t)
        counts["line"] += 1
        if out:
            rest = rest[:m.start()] + rest[m.start():m.start(1)] + " ".join(out) + rest[m.end():]
        else:   # 줄에 태그가 하나도 안 남으면 줄째로 지운다
            end = m.end() + 1 if rest[m.end():m.end() + 1] == "\n" else m.end()
            rest = rest[:m.start()] + rest[end:]
    if "#" in rest:   # 본문 속 #해시태그(note_tags 와 같은 방법으로 찾는다: 코드·주소 속 #는 건너뛴다)
        masked = mask_protected(rest)
        out, pos = [], 0
        for mm in HASH_FAST.finditer(masked):
            i = mm.start()
            if mm.group(1) != old or (i and (masked[i - 1].isalnum() or masked[i - 1] == "_" or masked[i - 1] in BAD_PREV)):
                continue
            if new is None:   # 지우기: '#이름' 과 바로 뒤의 공백 하나
                end = mm.end() + 1 if rest[mm.end():mm.end() + 1] == " " else mm.end()
                out.append(rest[pos:i])
                pos = end
            elif TAG_OK.match(new):
                out.append(rest[pos:i] + "#" + new)
                pos = mm.end()
            else:
                counts["stuck"] += 1
                continue
            counts["inline"] += 1
        rest = "".join(out) + rest[pos:]
    return head + rest, counts


def add_tag(body, tag):
    """노트에 태그를 더한다 → (새 본문, 더했는가). 이미 있으면 그대로. 글 아래의 '태그:' 줄 끝에 붙이고, 줄이 없으면 만든다."""
    if tag in note_tags(body):
        return body, False
    m = st.FM_RE.match(body)
    head, rest = (body[:m.end()], body[m.end():]) if m else ("", body)
    ms = list(TAG_LINE.finditer(rest))
    if ms:
        rest = rest[:ms[0].end()] + " #" + tag + rest[ms[0].end():]
    else:
        tail = "" if rest.endswith("\n\n") else ("\n" if rest.endswith("\n") else "\n\n")
        rest += f"{tail}태그: #{tag}\n"
    return head + rest, True


# 문법 해설 사이드바에 더 넣은 서식 (렌더러가 실제로 그리는 것만)
WRAP_X = {"sup": ("<sup>", "</sup>", "위첨자"), "sub": ("<sub>", "</sub>", "아래첨자"), "wiki": ("[[", "]]", "노트 제목"),
          "auto": ("<", ">", "https://"), "math": ("$", "$", "수식"), "tag": ("#", "", "태그")}
LINE_X = {"task": ("- [ ] ", r"^[-*+] \[[ xX]\] ")}
PLACEHOLDER_X = {"task": "할 일"}
TPL = {   # 이름: (넣을 글({} 자리에 고른 글), {} 기본 글)
    "code_lang": ("```python\n{}\n```", "코드"),
    "math_block": ("$$\n{}\n$$", "수식"),
    "details": ("<details>\n<summary>제목</summary>\n\n{}\n\n</details>", "내용"),
    "toc": ("[toc]", ""),
}


def syntax_entries():
    """[(묶음, 이름, 쓰는 모양, 동작)]"""
    H = lambda lv: ed.set_heading("제목", lv, FMT)  # noqa: E731
    return [
        *[("제목", f"제목 {lv}", H(lv), ("heading", lv)) for lv in range(1, 7)],
        ("글자", "굵게", "**글**", ("wrap", "b")),
        ("글자", "기울임", "*글*", ("wrap", "i")),
        ("글자", "취소선", "~~글~~", ("wrap", "s")),
        ("글자", "코드", "`글`", ("wrap", "code")),
        ("글자", "위 첨자", "x<sup>2</sup>", ("wrap", "sup")),
        ("글자", "아래 첨자", "H<sub>2</sub>O", ("wrap", "sub")),
        ("목록·인용", "글머리 목록", "- 항목", ("line", "ul")),
        ("목록·인용", "번호 목록", "1. 항목", ("line", "ol")),
        ("목록·인용", "체크 목록", "- [ ] 할 일", ("line", "task")),
        ("목록·인용", "인용", "> 글", ("line", "quote")),
        ("목록·인용", "들여쓰기", "  - 하위 항목", ("indent", 1)),
        ("목록·인용", "내어쓰기", "한 단계 올림", ("indent", -1)),
        ("넣기", "링크", "[글](주소)", ("wrap", "link")),
        ("넣기", "노트 링크", "[[노트 제목]]", ("wrap", "wiki")),
        ("넣기", "자동 링크", "<https://…>", ("wrap", "auto")),
        ("넣기", "그림", "![글](그림.png)", ("wrap", "img")),
        ("넣기", "유튜브 영상", "[▶ 유튜브에서 보기](<https://…", ("wrap", "video")),
        ("넣기", "표", "| 제목1 | 제목2 | …", ("block", "table")),
        ("넣기", "가로줄", "---", ("block", "hr")),
        ("넣기", "코드 블록", "``` …", ("block", "codeblock")),
        ("넣기", "언어 지정 코드", "```python …", ("tpl", "code_lang")),
        ("확장", "수식 (줄 안)", "$a^2$", ("wrap", "math")),
        ("확장", "수식 (블록)", "$$ … $$", ("tpl", "math_block")),
        ("확장", "접기", "<details> …", ("tpl", "details")),
        ("확장", "목차", "[toc]", ("tpl", "toc")),
        ("확장", "각주", "[^1] … [^1]: 내용", ("footnote",)),
        ("확장", "날짜·시간", time.strftime("%Y-%m-%d %H:%M"), ("datetime",)),
        ("확장", "태그", "#태그", ("wrap", "tag")),
    ]


class Btn(tk.Frame):
    """납작한 버튼(위키나루 방식): 평소엔 배경과 한 몸, 마우스를 올리면 연보라, 누르면 진해지면서 1px 눌린다.
    kind: ghost · icon · tab(보기 탭) · primary · danger · nav(왼쪽 메뉴)"""
    KINDS = {}

    @classmethod
    def refresh_kinds(cls):
        cls.KINDS = {
            "ghost": dict(bg=C["bg"], fg=C["sub"], hbg=C["soft"], hfg=C["accent"], pbg=C["sel"], abg=C["soft"], afg=C["accent"]),
            "icon": dict(bg=C["bg"], fg=C["text"], hbg=C["soft"], hfg=C["text"], pbg=C["sel"], abg=C["soft"], afg=C["accent"]),
            "tab": dict(bg=C["bg"], fg=C["muted"], hbg=C["soft"], hfg=C["accent"], pbg=C["sel"], abg=C["soft"], afg=C["accent"]),
            "primary": dict(bg=C["accent"], fg=C["on_accent"], hbg=C["accent_h"], hfg=C["on_accent"], pbg=C["accent_d"],
                            abg=C["accent_d"], afg=C["on_accent"]),
            "danger": dict(bg=C["bg"], fg=C["muted"], hbg=C["danger_bg"], hfg=C["danger"], pbg=C["danger_bg"], abg=C["danger_bg"], afg=C["danger"]),
            "nav": dict(bg=C["panel"], fg=C["sub"], hbg=C["hover"], hfg=C["text"], pbg=C["line"], abg=C["soft"], afg=C["accent"]),
        }

    def __init__(self, parent, text, command=None, kind="ghost", bg=None, bold=False, padx=12, pady=4, font=None, **kw):
        k = dict(self.KINDS[kind])
        if bg and kind != "primary":
            k["bg"] = bg
        self.k, self.kind, self.command = k, kind, command
        self.on = self.hover = self.pressed = False
        self.enabled = True
        super().__init__(parent, bg=k["bg"])
        self.label = tk.Label(self, text=text, bg=k["bg"], fg=k["fg"], cursor="hand2", padx=padx, pady=pady,
                              font=font or ((UI, 10, "bold") if bold else (UI, 10)), bd=0, **kw)
        self.label.pack(fill="both", expand=True, padx=(0, 1), pady=(0, 1))
        for w in (self, self.label):
            w.bind("<Enter>", lambda e: self.set_hover(True))
            w.bind("<Leave>", lambda e: self.set_hover(False))
            w.bind("<ButtonPress-1>", self.press)
            w.bind("<ButtonRelease-1>", self.release)
        self.paint()

    def configure(self, cnf=None, **kw):
        fwd = {a: kw.pop(a) for a in ("text", "font", "wraplength") if a in kw}
        if fwd:
            self.label.configure(**fwd)
        if cnf or kw:
            super().configure(cnf, **kw)

    config = configure

    def set_hover(self, v):
        self.hover = v
        self.paint()

    def press(self, e):
        if self.enabled:
            self.pressed = True
            self.paint()

    def release(self, e):
        was = self.pressed
        self.pressed = False
        self.paint()
        if was and self.enabled and self.command:
            x, y = self.winfo_pointerx() - self.winfo_rootx(), self.winfo_pointery() - self.winfo_rooty()
            if 0 <= x < self.winfo_width() and 0 <= y < self.winfo_height():
                self.command()

    def look(self, face, fg, pressed=False):
        self.config(bg=face)
        # 누르는 동안엔 글자가 아래-오른쪽으로 1px 밀려 눌린 느낌이 난다
        self.label.pack_configure(padx=(1, 0) if pressed else (0, 1), pady=(1, 0) if pressed else (0, 1))
        self.label.config(bg=face, fg=fg)

    def paint(self):
        k = self.k
        if not self.enabled:
            self.look(k["bg"], C["line"])
            self.label.config(cursor="arrow")
            return
        self.label.config(cursor="hand2")
        if self.pressed:
            self.look(k["pbg"], k["afg"] if self.kind in ("primary", "danger", "tab", "nav", "ghost") else k["hfg"], True)
        elif self.on:
            self.look(k["abg"], k["afg"])
        elif self.hover:
            self.look(k["hbg"], k["hfg"])
        else:
            self.look(k["bg"], k["fg"])

    def set_on(self, on):
        self.on = on
        self.paint()



Btn.refresh_kinds()


def autohide(sb, target):
    """내용이 넘칠 때만 스크롤바가 나타난다."""
    def setter(lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            sb.pack_forget()
        else:
            sb.pack(side="right", fill="y", before=target)
        sb.set(lo, hi)
    return setter


class App:
    def __init__(self):
        global UI
        theme = st.read_config().get("theme", {})
        apply_theme(theme.get("name", DEFAULT_THEME), theme.get("accent"))
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
        self.mono = next((f for f in ("D2Coding", "Consolas", "Courier New") if f in fams), "TkFixedFont")
        self.size = 11
        self.style_ttk()

        view = st.read_config().get("view", {})
        self.show = {k: bool(view.get(k, d)) for k, d in (("notebooks", True), ("list", True), ("tags", False), ("syntax", True))}
        self.mode = view.get("mode") if view.get("mode") in ("edit", "split", "view") else "split"
        self.store = st.Store()
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
        self.tray = tray.Tray(os.path.join(HERE, "assets", "icon.ico"), f"{APP} {VERSION}")   # 닫기(X)를 누르면 들어가는 트레이 아이콘(마우스를 올리면 버전이 보인다: 트레이에 구버전이 남아 있는지 알아보려고)
        self.tray_hidden = self.tray_was_zoomed = False
        for cls in ("Entry", "Text"):    # 어느 칸에서 한글을 쳐도 조합 중인 글자가 그 칸 글꼴로 보이게
            self.root.bind_class(cls, "<FocusIn>", self.match_ime_font, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_keys()
        self.set_mode(self.mode)
        self.relayout()
        self.reload_notes(background=True)
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
                        darkcolor=C["thumb"], gripcount=0, width=9, relief="flat")
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
        m.add_command(label="새 노트", accelerator="Ctrl+N", command=self.new_note)
        m.add_command(label="새 노트북", accelerator="Ctrl+Shift+N", command=self.add_notebook)
        m.add_command(label="새 하위 노트북", command=self.add_subnotebook)
        m.add_separator()
        m.add_command(label="폴더 가져오기…", command=lambda: self.show_options("imports"))
        m.add_command(label="지금의 검색 저장…", command=self.save_search)
        m.add_separator()
        m.add_command(label="복원 지점…", command=self.show_snapshots)
        m.add_command(label="휴지통…", command=self.show_trash)
        m.add_separator()
        m.add_command(label="종료", accelerator="Alt+F4", command=self.quit)
        mb.add_cascade(label="파일", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="실행 취소", accelerator="Ctrl+Z", command=lambda: self.text_do("edit_undo"))
        m.add_command(label="다시 실행", accelerator="Ctrl+Y", command=lambda: self.text_do("edit_redo"))
        m.add_separator()
        m.add_command(label="잘라내기", accelerator="Ctrl+X", command=lambda: self.text.event_generate("<<Cut>>"))
        m.add_command(label="복사", accelerator="Ctrl+C", command=lambda: self.text.event_generate("<<Copy>>"))
        m.add_command(label="붙여넣기", accelerator="Ctrl+V", command=lambda: self.text.event_generate("<<Paste>>"))
        m.add_command(label="모두 선택", accelerator="Ctrl+A", command=lambda: (self.text.tag_add("sel", "1.0", "end-1c"), self.text.focus_set()))
        m.add_separator()
        m.add_command(label="굵게", accelerator="Ctrl+B", command=act(("wrap", "b")))
        m.add_command(label="기울임꼴", accelerator="Ctrl+I", command=act(("wrap", "i")))
        m.add_command(label="취소선", command=act(("wrap", "s")))
        m.add_command(label="링크 만들기", accelerator="Ctrl+K", command=act(("wrap", "link")))
        m.add_command(label="코드", command=act(("wrap", "code")))
        m.add_separator()
        m.add_command(label="번호 매기기 목록", command=act(("line", "ol")))
        m.add_command(label="글머리 기호 목록", command=act(("line", "ul")))
        m.add_command(label="인용", command=act(("line", "quote")))
        h = tk.Menu(m, tearoff=0)
        for lv in (1, 2, 3, 4):
            h.add_command(label=f"제목 {lv}", command=act(("heading", lv)))
        h.add_command(label="본문", command=act(("heading", 0)))
        m.add_cascade(label="제목", menu=h)
        m.add_command(label="가로줄", command=act(("block", "hr")))
        m.add_command(label="표", command=act(("block", "table")))
        m.add_command(label="코드 블록", command=act(("block", "codeblock")))
        m.add_command(label="날짜 및 시간 삽입", accelerator="Ctrl+Shift+T", command=self.insert_datetime)
        m.add_separator()
        m.add_command(label="문서에서 찾기", accelerator="Ctrl+F", command=lambda: self.cur and self.show_find())
        m.add_command(label="모든 파일에서 검색", accelerator="Ctrl+Shift+F", command=self.focus_search)
        m.add_separator()
        m.add_command(label="노트 속성…", command=self.show_properties)
        m.add_command(label="노트 버전…", command=self.show_versions)
        m.add_command(label="전체 변경 이력…", command=self.show_journal)
        mb.add_cascade(label="편집", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_checkbutton(label="노트북 보기", variable=self.v["notebooks"], command=self.on_view_toggle)
        m.add_checkbutton(label="태그 보기", variable=self.v["tags"], command=self.on_view_toggle)
        m.add_checkbutton(label="노트 목록 보기", accelerator="Ctrl+Shift+L", variable=self.v["list"], command=self.on_view_toggle)
        m.add_checkbutton(label="문법 해설 보기", accelerator="Ctrl+/", variable=self.v["syntax"], command=self.on_view_toggle)
        m.add_separator()
        for key, label in (("edit", "마크다운만"), ("split", "마크다운 + 렌더링"), ("view", "렌더링만")):
            m.add_radiobutton(label=label, value=key, variable=self.v_mode, command=lambda k=key: self.set_mode(k))
        m.add_command(label="편집기 레이아웃 전환", accelerator="Ctrl+L", command=lambda: self.cur and self.cycle_mode())
        mb.add_cascade(label="보기", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="뒤로", accelerator="Ctrl+-", command=lambda: self.go(-1))
        m.add_command(label="앞으로", accelerator="Ctrl++", command=lambda: self.go(1))
        mb.add_cascade(label="이동", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="중복 노트 찾기…", command=self.show_duplicates)
        m.add_command(label="스크랩 군더더기 정리…", command=self.show_cleanup)
        m.add_command(label="안 쓰는 미디어 파일 정리…", command=self.show_unused_media)
        mb.add_cascade(label="도구", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="옵션…", accelerator="Ctrl+,", command=lambda: self.show_options("general"))
        m.add_separator()
        m.add_command(label="폴더 설정… (노트·리소스 폴더)", command=lambda: self.show_options("folders"))
        m.add_separator()
        m.add_command(label="글꼴·크기…", command=lambda: self.show_options("fonts"))
        m.add_command(label="테마·색상…", command=lambda: self.show_options("theme"))
        m.add_command(label="노트 버전 설정…", command=lambda: self.show_options("versions"))
        m.add_command(label="웹 클리퍼 설정…", command=lambda: self.show_options("clipper"))
        mb.add_cascade(label="설정", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="검색 문법", command=self.help_search)
        m.add_separator()
        m.add_command(label="업데이트 확인…", command=self.check_update)
        m.add_command(label=f"{APP} 정보 (버전 {VERSION})", command=lambda: messagebox.showinfo(
            APP, f"{APP} {VERSION}\n\n위키나루 기반 마크다운 노트 앱\n노트는 .md 파일로 저장됩니다.\n\n저장 폴더: " + self.store.root
            + "\n\nhttps://github.com/" + updater.REPO, parent=self.root))
        mb.add_cascade(label="도움말", menu=m)
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

    def run_task(self, title, work, done, text="노트를 읽는 중…", cancellable=True):
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
            Btn(top, "취소", stop, padx=14, pady=3).pack()
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
        self.run_task("복원 지점 만드는 중", lambda prog, cancel: self.snap.create(label, prog, cancel), lambda pid: then(),
                      text=f"\"{label}\" 복원 지점을 만드는 중… (처음 한 번은 오래 걸립니다)")

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
                self.snap.create("자동")
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
                self.status.config(text="복원 지점을 만들었습니다.")
        poll()

    def show_snapshots(self):
        """파일 > 복원 지점: 어느 시점의 모든 노트를 기억해 두었다가 그 상태로 되돌린다"""
        top = self.tool_window("복원 지점", "800x520")
        tk.Label(top, text="복원 지점은 그 시점의 노트 목록을 기억해 두고, 앱이 노트를 바꾸기 직전에 바뀌기 전 내용만 따로 보관합니다(그림·첨부는 제외). 고르면 노트를 그 시점으로 되돌리고, 그 뒤에 새로 생긴 노트는 휴지통으로 보냅니다. 앱 밖에서 고친 노트는 되돌릴 수 없어 건드리지 않습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=760, padx=16, pady=10).pack(fill="x")
        cfgrow = tk.Frame(top, bg=C["bg"])
        cfgrow.pack(side="bottom", fill="x", padx=16, pady=(0, 6))
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=10)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("when", "label", "count"), show="headings", selectmode="browse")
        for col, text, w, anc in (("when", "시각", 170, "w"), ("label", "이름", 300, "w"), ("count", "노트 수", 90, "e")):
            tv.heading(col, text=text)
            tv.column(col, width=w, anchor=anc, stretch=col == "label")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        info = tk.Label(cfgrow, text="", bg=C["bg"], fg=C["muted"], font=(self.ui, 9))
        cfg = self.snap_cfg()
        auto_var, cnt_var, day_var = tk.BooleanVar(value=cfg["auto"]), tk.StringVar(value=str(cfg["count"])), tk.StringVar(value=str(cfg["days"]))

        def refresh():
            tv.delete(*tv.get_children())
            pts = self.snap.points()
            for p in pts:
                tv.insert("", "end", iid=p["id"], values=(time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(p["created"])), p["label"] or "수동", f"{p['count']:,}"))
            mb = self.snap.usage() / 1048576
            info.config(text=f"지점 {len(pts)}개 · 보관 중인 내용 {mb:,.1f}MB")

        def save_cfg(*_):
            try:
                st.write_config(snap_auto=auto_var.get(), snap_count=max(1, int(cnt_var.get())), snap_days=max(0, int(day_var.get())))
            except ValueError:
                pass

        def make():
            self.run_task("복원 지점 만드는 중", lambda prog, cancel: self.snap.create("수동", prog, cancel, force=True),
                          lambda pid: refresh(), text="복원 지점을 만드는 중… (처음 한 번은 오래 걸립니다)")

        def restore():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "되돌릴 복원 지점을 먼저 고르세요.", parent=top)
            pid = sel[0]

            def after_diff(d):
                if not (d["change"] or d["add"] or d["remove"] or d["lost"]):
                    return messagebox.showinfo(APP, "지금 노트가 이 복원 지점과 같습니다.", parent=top)
                if not messagebox.askyesno(APP, f"이 시점으로 되돌릴까요?\n\n  내용을 되돌릴 노트  {len(d['change']):,}개\n  지워졌던 것을 되살릴 노트  {len(d['add']):,}개\n"
                                                 f"  그 뒤에 생긴 노트(휴지통으로 보냄)  {len(d['remove']):,}개\n"
                                                 + (f"  앱 밖에서 고쳐서 되돌릴 수 없는 노트(그대로 둠)  {len(d['lost']):,}개\n" if d["lost"] else "")
                                                 + "\n되돌리기 직전 상태도 복원 지점으로 남기므로 다시 돌아올 수 있습니다.", parent=top):
                    return
                self.flush()

                def go():
                    def done(res):
                        self.close_note()
                        self.reload_notes()
                        refresh()
                        messagebox.showinfo(APP, "되돌렸습니다.\n" + f"내용 {res[0]:,}개 · 되살림 {res[1]:,}개 · 휴지통 {res[2]:,}개"
                                            + (f"\n되돌릴 수 없어 그대로 둔 노트 {res[3]:,}개" if res[3] else ""), parent=top)
                    self.run_task("복원 중", lambda prog, cancel: self.snap.restore(pid, prog, cancel), done, text="노트를 되돌리는 중…")
                self.checkpoint("복원 직전", go)
            self.run_task("비교 중", lambda prog, cancel: self.snap.diff(pid, prog, cancel), after_diff, text="지금 노트와 비교하는 중…")

        def delete():
            sel = tv.selection()
            if sel and messagebox.askyesno(APP, "이 복원 지점을 지울까요?", parent=top):
                self.snap.delete(sel[0])
                refresh()

        def prune():
            c = self.snap_cfg()
            n = self.snap.prune(c["count"], c["days"])
            refresh()
            messagebox.showinfo(APP, f"{n}개를 정리했습니다." if n else "정리할 지점이 없습니다.", parent=top)
        Btn(btns, "지금 복원 지점 만들기", make, padx=12, pady=3).pack(side="left")
        Btn(btns, "이 지점으로 되돌리기", restore, kind="primary", padx=12, pady=3).pack(side="left", padx=6)
        Btn(btns, "지우기", delete, kind="danger", padx=12, pady=3).pack(side="right")
        Btn(btns, "오래된 것 정리", prune, padx=12, pady=3).pack(side="right", padx=6)
        tk.Checkbutton(cfgrow, text="하루에 한 번 자동으로 만들기", variable=auto_var, command=save_cfg, bg=C["bg"], activebackground=C["bg"], font=(self.ui, 9)).pack(side="left")
        for label, var, hi in (("  보관: 최근", cnt_var, 500), ("개 이거나", None, 0), ("", day_var, 3650)):
            if var is None:
                tk.Label(cfgrow, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
                continue
            if label:
                tk.Label(cfgrow, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
            sp = tk.Spinbox(cfgrow, from_=0, to=hi, textvariable=var, width=5, command=save_cfg, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                            highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 9), buttonbackground=C["panel"])
            sp.pack(side="left", ipady=1, padx=3)
            sp.bind("<FocusOut>", save_cfg)
        tk.Label(cfgrow, text="일 안의 것", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="left")
        info.pack(side="right")
        refresh()

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

    def show_trash(self):
        """파일 > 휴지통: 지운 노트·노트북을 보관 기간(기본 30일) 동안 두고, 복원하거나 바로 지운다"""
        top = self.tool_window("휴지통", "760x500")
        head = tk.Frame(top, bg=C["bg"])
        head.pack(fill="x", padx=16, pady=(12, 6))
        info = tk.Label(head, text="", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left")
        info.pack(side="left")
        days_var = tk.StringVar(value=str(self.store.trash_days))
        tk.Label(head, text="일", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right")

        def set_days(*_):
            try:
                st.write_config(trash_days=max(0, int(days_var.get())))
            except ValueError:
                pass
            refresh()
        sp = tk.Spinbox(head, from_=0, to=3650, textvariable=days_var, width=5, command=set_days, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                        highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 10), buttonbackground=C["panel"])
        sp.pack(side="right", ipady=2, padx=4)
        sp.bind("<FocusOut>", set_days)
        sp.bind("<Return>", set_days)
        tk.Label(head, text="보관 기간 (0 = 자동으로 지우지 않음)", bg=C["bg"], fg=C["muted"], font=(self.ui, 9)).pack(side="right")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("kind", "where", "deleted", "left"), selectmode="extended", show="headings")
        for col, text, w, anchor in (("kind", "종류", 70, "w"), ("where", "이름 · 원래 위치", 360, "w"), ("deleted", "지운 때", 130, "w"), ("left", "남은 기간", 90, "e")):
            tv.heading(col, text=text)
            tv.column(col, width=w, anchor=anchor, stretch=col == "where")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)

        def refresh():
            tv.delete(*tv.get_children())
            days = self.store.trash_days
            items = self.store.trash_items()
            for it in items:
                left = "-" if not days else "%d일" % max(0, math.ceil(days - (time.time() - it["deleted"]) / 86400))
                tv.insert("", "end", iid=it["id"], values=("저장 폴더" if it["root"] else "파일 묶음" if it["into"] else "노트북" if it["dir"] else "노트", it["rel"], time.strftime("%Y.%m.%d %H:%M", time.localtime(it["deleted"])), left))
            info.config(text=f"{len(items)}개 — 지운 지 {days}일이 지나면 완전히 지워집니다." if days else f"{len(items)}개 — 자동으로 지우지 않습니다.")
        refresh()

        def restore():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "복원할 항목을 먼저 고르세요.", parent=top)
            fail = 0
            for tid in sel:
                try:
                    self.store.restore_trash(tid)
                except OSError:
                    fail += 1
            self.reload_notes()
            refresh()
            if fail:
                messagebox.showerror(APP, f"{fail}개를 복원하지 못했습니다.", parent=top)

        def remove():
            sel = tv.selection()
            if sel and messagebox.askyesno(APP, f"고른 {len(sel)}개를 완전히 지울까요? 되돌릴 수 없습니다.", parent=top):
                for tid in sel:
                    self.store.delete_trash(tid)
                refresh()

        def empty():
            n = len(tv.get_children())
            if n and messagebox.askyesno(APP, f"휴지통의 {n}개를 모두 완전히 지울까요? 되돌릴 수 없습니다.", parent=top):
                self.store.empty_trash()
                refresh()
        Btn(btns, "복원", restore, kind="primary", padx=14, pady=3).pack(side="left")
        Btn(btns, "선택한 항목 완전히 삭제", remove, kind="danger", padx=12, pady=3).pack(side="left", padx=6)
        Btn(btns, "휴지통 비우기", empty, kind="danger", padx=12, pady=3).pack(side="right")

    def show_duplicates(self):
        """도구 > 중복 노트 찾기: 같은 원본 주소 · 같은 본문 · 같은 제목에 비슷한 본문을 묶어 보여 주고, 골라서 휴지통으로"""
        self.scan_notes("중복 노트 찾기", lambda notes, prog, cancel: cleanup.find_duplicates(notes, prog, cancel), self.duplicates_dialog)

    def duplicates_dialog(self, groups):
        if not groups:
            return messagebox.showinfo(APP, "중복으로 보이는 노트가 없습니다.", parent=self.root)
        top = self.tool_window(f"중복 노트 — {len(groups):,}묶음", native=True)
        tk.Label(top, text="제목이 같은 노트 중 본문이 완전히 같은 것과 비슷한 것을 나눠 보여 줍니다. 노트를 하나 누르면 그 노트가 열립니다.\n"
                           "지울 노트는 Ctrl/Shift 로 여러 개 고른 뒤 휴지통으로 보내세요. 완전히 같은 것은 단추 하나로 최근 것만 남기고 정리할 수 있습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16)
        tv = ttk.Treeview(wrap, columns=("nb", "mtime", "size"), selectmode="extended")
        tv.heading("#0", text="제목")
        tv.heading("nb", text="노트북")
        tv.heading("mtime", text="수정")
        tv.heading("size", text="크기")
        tv.column("#0", width=380)
        tv.column("nb", width=140)
        tv.column("mtime", width=130, stretch=False)
        tv.column("size", width=80, anchor="e", stretch=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        path_of, kind_groups = {}, {"same": [], "similar": []}   # kind_groups: 종류 → 묶음 줄(iid) 목록
        quiet = {"on": False}   # 코드로 줄을 고를 때는 노트를 열지 않는다

        def is_same(why):
            return set(why) == {"본문이 같음"}

        def fill():
            tv.delete(*tv.get_children())
            path_of.clear()
            for v in kind_groups.values():
                v.clear()
            for key, label, pick in (("same", "본문이 완전히 같음", is_same), ("similar", "본문이 비슷함", lambda w: not is_same(w))):
                part = [(why, notes) for why, notes in groups if pick(why)]
                if not part:
                    continue
                cat = tv.insert("", "end", text=f"{label} — {len(part):,}묶음, 노트 {sum(len(n) for _, n in part):,}개", open=True)
                for why, notes in part:
                    g = tv.insert(cat, "end", text=f"{notes[0]['title']} — {len(notes)}개", open=True)
                    kind_groups[key].append(g)
                    for n in notes:
                        iid = tv.insert(g, "end", text=n["title"], values=(self.nb_label(n["nb"]), time.strftime("%Y.%m.%d %H:%M", time.localtime(n["mtime"])), f"{n['size']:,}B"))
                        path_of[iid] = n["path"]
        fill()

        def old_of(key):   # 묶음마다 가장 최근에 고친 것만 남기고 나머지
            sel = []
            for g in kind_groups[key]:
                sel += tv.get_children(g)[1:]
            return sel

        def pick_old(key):
            sel = old_of(key)
            if not sel:
                return messagebox.showinfo(APP, "해당하는 중복이 없습니다.", parent=top)
            quiet["on"] = True
            tv.selection_set(sel)
            tv.see(sel[0])
            top.after(50, lambda: quiet.update(on=False))

        def on_select(e=None):   # 노트 하나를 누르면 그 노트로 연결(여러 개를 고르는 중에는 열지 않는다)
            sel = tv.selection()
            if not quiet["on"] and len(sel) == 1 and sel[0] in path_of:
                self.open_path_note(path_of[sel[0]])

        def trash_same():
            sel = old_of("same")
            if not sel:
                return messagebox.showinfo(APP, "본문이 완전히 같은 노트가 없습니다.", parent=top)
            if not messagebox.askyesno(APP, f"본문이 완전히 같은 {len(kind_groups['same']):,}묶음에서 가장 최근에 고친 것만 남기고\n"
                                            f"나머지 {len(sel):,}개를 휴지통으로 보낼까요?\n({self.store.trash_days}일 동안 보관하며 복원할 수 있습니다)", parent=top):
                return
            trash([path_of[i] for i in sel], confirm=False)

        def trash(paths=None, confirm=True):
            if paths is None:
                paths = [path_of[i] for i in tv.selection() if i in path_of]
            if not paths:
                return messagebox.showinfo(APP, "지울 노트를 먼저 고르세요.", parent=top)
            if confirm and not messagebox.askyesno(APP, f"고른 노트 {len(paths)}개를 휴지통으로 보낼까요?", parent=top):
                return
            gone = set(paths)

            def go():
                self.trash_notes(paths)
                for k, (why, notes) in enumerate(list(groups)):
                    groups[k] = (why, [n for n in notes if n["path"] not in gone])
                groups[:] = [g for g in groups if len(g[1]) > 1]
                if not groups:
                    top.destroy()
                    return messagebox.showinfo(APP, "정리했습니다.", parent=self.root)
                fill()
            self.checkpoint("중복 노트 정리 전", go) if len(paths) >= 5 else go()
        tv.bind("<<TreeviewSelect>>", on_select)
        Btn(btns, "완전히 같은 것: 최근 것만 남기고 삭제", trash_same, kind="danger", padx=12, pady=3).pack(side="left")
        Btn(btns, "비슷한 것: 최근 것만 남기고 고르기", lambda: pick_old("similar"), padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고, 열어 보기·휴지통 메뉴를 띄운다
            row = tv.identify_row(e.y)
            if row and row not in tv.selection():
                quiet["on"] = True
                tv.selection_set(row)
                top.after(50, lambda: quiet.update(on=False))
            sel = [i for i in tv.selection() if i in path_of]
            menu.delete(0, "end")
            menu.add_command(label="노트 열어 보기", command=lambda: self.open_path_note(path_of[sel[0]]), state="normal" if sel else "disabled")
            menu.add_command(label=f"휴지통으로 보내기 ({len(sel)}개)" if len(sel) > 1 else "휴지통으로 보내기", command=trash, state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        tv.bind("<Button-3>", on_menu)

    def show_journal(self):
        """편집 > 전체 변경 이력: 모든 노트의 저장·생성·삭제·이름 바꿈·이동·복원을 시간순으로"""
        top = self.tool_window("전체 변경 이력", "860x540")
        tk.Label(top, text="모든 노트의 변경을 최근 순으로 보여 줍니다(같은 노트의 연속 저장은 1분에 한 번만 기록). 더블클릭하면 그 노트를 엽니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
        flt = tk.Frame(top, bg=C["bg"])
        flt.pack(fill="x", padx=16)
        names = {"edit": "수정", "create": "새 노트", "delete": "삭제", "restore": "복원", "rename": "이름 바꿈", "move": "이동", "cleanup": "군더더기 정리", "tags": "태그 정리"}
        var = tk.StringVar(value="전체")
        for label in ["전체"] + list(names.values()):
            tk.Radiobutton(flt, text=label, value=label, variable=var, command=lambda: fill(), indicatoron=False, bd=0, padx=8, pady=2,
                           bg=C["bg"], selectcolor=C["soft"], activebackground=C["soft"], font=(self.ui, 9)).pack(side="left", padx=1)
        wrap = tk.Frame(top, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 12))
        tv = ttk.Treeview(wrap, columns=("when", "ev", "path", "d"), show="headings", selectmode="browse")
        for col, text, w, stretch in (("when", "시각", 130, False), ("ev", "종류", 90, False), ("path", "노트", 420, True), ("d", "내용", 150, False)):
            tv.heading(col, text=text)
            tv.column(col, width=w, stretch=stretch)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        recs = self.store.journal_read()
        rel_of = {}
        rec_of = {}

        def fill():
            tv.delete(*tv.get_children())
            rel_of.clear()
            rec_of.clear()
            want = var.get()
            shown = 0
            for r in recs:
                label = names.get(r["ev"], r["ev"])
                if want != "전체" and label != want:
                    continue
                path = r["path"] + (" → " + r["to"] if r.get("to") else "")
                iid = tv.insert("", "end", values=(time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(r["t"])), label, path, r.get("d", "")))
                rel_of[iid] = r.get("to") or r["path"]
                rec_of[iid] = r
                shown += 1
                if shown >= 3000:
                    break
        fill()

        def open_sel(e=None):
            sel = tv.selection()
            if not sel:
                return
            full = os.path.normcase(os.path.join(self.store.root, rel_of[sel[0]].replace("/", os.sep)))
            n = next((x for x in self.all_notes if os.path.normcase(x["path"]) == full), None)
            if n:
                self.open_note(n)
            else:
                messagebox.showinfo(APP, "이 노트는 지금 없습니다(삭제되었거나 이름이 바뀌었습니다). 휴지통에서 찾아 보세요.", parent=top)
        tv.bind("<Double-1>", open_sel)

        def undo():
            sel = tv.selection()
            if not sel:
                return messagebox.showinfo(APP, "되돌릴 변경을 고르세요.", parent=top)
            r = rec_of.get(sel[0])
            if not r:
                return
            if r["ev"] not in ("edit", "create", "delete", "rename", "move"):
                return messagebox.showinfo(APP, "이 종류의 변경은 이력에서 되돌릴 수 없습니다.", parent=top)
            what = {"edit": "이 수정 직전의 내용으로 되돌릴까요?\n(지금 내용은 새 버전으로 남겨 둡니다)", "create": "이 새 노트를 휴지통으로 보낼까요?",
                    "delete": "휴지통에서 복원할까요?", "rename": "원래 이름으로 되돌릴까요?", "move": "원래 노트북으로 되돌릴까요?"}[r["ev"]]
            if not messagebox.askyesno(APP, r["path"] + "\n\n" + what, parent=top):
                return
            self.flush()
            cur_path = self.cur["path"] if self.cur else None
            try:
                msg = self.store.undo_event(r)
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            self.reload_notes()
            if cur_path:   # 열어 둔 노트가 바뀌었으면 다시 연다
                fresh = next((x for x in self.all_notes if os.path.normcase(x["path"]) in (os.path.normcase(cur_path),)
                              or os.path.normcase(x["path"]) == os.path.normcase(os.path.join(self.store.root, r["path"].replace("/", os.sep)))), None)
                if fresh:
                    self.open_note(fresh)
            recs[:] = self.store.journal_read()
            fill()
            messagebox.showinfo(APP, msg, parent=top)
        menu = tk.Menu(top, tearoff=0)
        menu.add_command(label="이 변경 되돌리기", command=undo)

        def on_menu(e):
            iid = tv.identify_row(e.y)
            if iid:
                tv.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)
        tv.bind("<Button-3>", on_menu)
        bar = tk.Frame(top, bg=C["bg"])
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        Btn(bar, "이 변경 되돌리기", undo, kind="primary", padx=14).pack(side="right")

    def show_unused_media(self):
        """도구 > 안 쓰는 미디어 파일 정리: 어떤 노트도 가리키지 않는 그림·첨부를 찾아 한꺼번에 휴지통으로"""
        self.scan_notes("안 쓰는 미디어 파일 찾기", lambda notes, prog, cancel: cleanup.unused_media(self.store, notes, prog, cancel), self.unused_media_dialog)

    def unused_media_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, "안 쓰는 미디어 파일이 없습니다.", parent=self.root)
        total = sum(s for _, s in found)
        top = self.tool_window(f"안 쓰는 미디어 파일 — {len(found):,}개", "760x520", native=True)

        def mb(n):
            return f"{n / 1048576:,.1f}MB" if n >= 1048576 else f"{n / 1024:,.0f}KB"
        tk.Label(top, text=f"어떤 노트도 가리키지 않는 파일 {len(found):,}개 ({mb(total)}). 휴지통으로 보내면 {self.store.trash_days}일 동안 복원할 수 있습니다.\n"
                           "(노트의 이전 버전 기록이 가리키는 그림은 확인하지 않으므로, 오래된 버전으로 되돌릴 때 그림이 빠질 수 있습니다.)",
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
                return messagebox.showinfo(APP, "먼저 파일을 고르세요.", parent=top)
            if not messagebox.askyesno(APP, f"{len(items):,}개 파일을 휴지통으로 보낼까요?", parent=top):
                return
            try:
                n = self.store.trash_files([p for p, _ in items], self.store.media_dir)
            except OSError as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            top.destroy()
            messagebox.showinfo(APP, f"{n:,}개 파일을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)", parent=self.root)
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
        Btn(btns, "모두 휴지통으로", lambda: trash(list(found)), kind="danger", padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고, 열기·위치 열기·휴지통 메뉴를 띄운다
            i = lb.nearest(e.y)
            if 0 <= i < lb.size() and i not in lb.curselection():
                lb.selection_clear(0, "end")
                lb.selection_set(i)
            sel = list(lb.curselection())
            one = len(sel) == 1
            menu.delete(0, "end")
            menu.add_command(label="파일 열기", command=open_one, state="normal" if one else "disabled")
            menu.add_command(label="파일 위치 열기", command=open_sel, state="normal" if sel else "disabled")
            menu.add_command(label=f"휴지통으로 보내기 ({len(sel)}개)" if len(sel) > 1 else "휴지통으로 보내기",
                             command=lambda: trash([found[k] for k in lb.curselection()]), state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        lb.bind("<Button-3>", on_menu)

    def show_cleanup(self):
        """도구 > 스크랩 군더더기 정리: 노트마다 지울 줄을 미리 보여 주고, 골라서 적용(적용 전 내용은 노트 버전으로 남는다)"""
        self.scan_notes("스크랩 군더더기 찾기", lambda notes, prog, cancel: cleanup.scan_junk(notes, prog, cancel), self.cleanup_dialog)

    def cleanup_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, "정리할 군더더기(맨위로·공유하기·댓글 쓰기 같은 줄)가 없습니다.", parent=self.root)
        top = self.tool_window(f"스크랩 군더더기 — 노트 {len(found):,}개", native=True)
        tk.Label(top, text="지울 줄이 있는 노트입니다. 노트를 고르면 지워질 줄을 보여 줍니다. 적용하면 이전 내용이 노트 버전으로 남습니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        left = tk.Frame(top, bg=C["panel"], width=320)
        left.pack(side="left", fill="y", padx=(16, 0))
        left.pack_propagate(False)
        lb = tk.Listbox(left, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none", selectmode="extended",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lsb = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=autohide(lsb, lb))
        lb.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        pwrap = tk.Frame(top, bg=C["panel"])
        pwrap.pack(side="left", fill="both", expand=True, padx=16)
        pv = tk.Text(pwrap, wrap="word", state="disabled", relief="flat", bd=0, highlightthickness=0, bg=C["panel"], fg=C["text"],
                     font=(self.mono, 10), padx=14, pady=10)
        psb = ttk.Scrollbar(pwrap, orient="vertical", command=pv.yview)
        pv.config(yscrollcommand=autohide(psb, pv))
        pv.pack(side="left", fill="both", expand=True)
        pv.tag_configure("rm", foreground=C["danger"], overstrike=True)

        def fill():
            lb.delete(0, "end")
            for n, new, removed in found:
                lb.insert("end", f"{n['title']}  ({len(removed)}줄)")

        def show(e=None):
            sel = lb.curselection()
            if not sel:
                return
            n, new, removed = found[sel[-1]]
            if len(sel) == 1:   # 노트 하나를 누르면 그 노트로 연결
                self.open_path_note(n["path"])
            pv.config(state="normal")
            pv.delete("1.0", "end")
            pv.insert("end", f"{n['title']} — {self.nb_label(n['nb'])}\n지워지는 줄 {len(removed)}개:\n\n")
            for no, line, why in removed[:300]:
                pv.insert("end", f"{no:>5}  [{why}] {line}\n", "rm")
            pv.config(state="disabled")
        fill()
        lb.bind("<<ListboxSelect>>", show)

        def apply(items):
            if not items:
                return messagebox.showinfo(APP, "정리할 노트를 먼저 고르세요.", parent=top)
            if st.version_settings()["keep"] <= 0 and not messagebox.askyesno(
                    APP, "노트 버전 기록이 꺼져 있어 적용하면 되돌릴 수 없습니다. 그래도 적용할까요?", parent=top):
                return
            if not messagebox.askyesno(APP, f"노트 {len(items)}개에서 군더더기 줄을 지울까요?", parent=top):
                return
            cur_path = self.cur["path"] if self.cur else None
            self.flush()

            def go():
                done = 0
                for n, new, removed in items:
                    try:   # 수정 시각은 그대로 두고(touch=False), 이전 내용은 버전으로 남긴다(force)
                        self.store.save(n["path"], new, versioned=True, force=True, touch=False, ev="cleanup")
                        done += 1
                    except OSError:
                        pass
                    found[:] = [f for f in found if f[0]["path"] != n["path"]]
                self.reload_notes()
                m = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                if m:
                    self.open_note(m, record=False)
                messagebox.showinfo(APP, f"{done}개 노트를 정리했습니다.", parent=top)
                if not found:
                    return top.destroy()
                fill()
                pv.config(state="normal")
                pv.delete("1.0", "end")
                pv.config(state="disabled")
            self.checkpoint("군더더기 정리 전", go) if len(items) >= 5 else go()

        def selected():
            return [found[i] for i in lb.curselection()]
        Btn(btns, "모두 정리", lambda: apply(list(found)), kind="primary", padx=12, pady=3).pack(side="right")

        menu = tk.Menu(top, tearoff=0)

        def on_menu(e):   # 우클릭: 누른 줄이 고른 줄 안이 아니면 그 줄만 고르고(미리 보기도 갱신), 열어 보기·정리 메뉴를 띄운다
            i = lb.nearest(e.y)
            if 0 <= i < lb.size() and i not in lb.curselection():
                lb.selection_clear(0, "end")
                lb.selection_set(i)
                show()
            sel = selected()
            menu.delete(0, "end")
            menu.add_command(label="노트 열어 보기", command=lambda: self.open_path_note(sel[0][0]["path"]), state="normal" if sel else "disabled")
            menu.add_command(label=f"선택한 노트 정리 ({len(sel)}개)" if len(sel) > 1 else "이 노트 정리",
                             command=lambda: apply(selected()), state="normal" if sel else "disabled")
            menu.tk_popup(e.x_root, e.y_root)
        lb.bind("<Button-3>", on_menu)

    # ------------------------------------------------------------ 도움말 > 업데이트 확인
    def check_update(self):
        """GitHub 의 최신 릴리스를 확인하고, 새 버전이면 내려받아 exe 를 바꾸고 다시 시작한다(소스로 실행 중이면 릴리스 페이지만 안내)"""
        self.run_task("업데이트 확인", lambda prog, cancel: updater.latest(), self.update_found, text="최신 버전을 확인하는 중…")

    def update_found(self, rel):
        if not updater.is_newer(rel["tag"], VERSION):
            return messagebox.showinfo(APP, f"최신 버전입니다.\n현재 {VERSION}, 최신 릴리스 {rel['tag']}", parent=self.root)
        news = updater.whats_new(rel["body"])
        head = f"새 버전 {rel['tag']} 이 나왔습니다. (현재 {VERSION})\n\n{news}\n\n"
        if not (ed.FROZEN and rel["asset_url"] and rel["sha"]):   # 소스로 실행 중이거나 자동으로 바꿀 파일이 없으면 페이지만
            why = "소스로 실행 중이라 자동으로 바꾸지 않습니다. " if not ed.FROZEN else ""
            if messagebox.askyesno(APP, head + why + "릴리스 페이지를 열까요?", parent=self.root):
                webbrowser.open(rel["url"])
            return
        ans = messagebox.askyesnocancel(
            APP, head + "예: 지금 업데이트(내려받아 바꾸고 자동으로 다시 시작)\n아니오: 릴리스 페이지 열기\n취소: 나중에", parent=self.root)
        if ans is None:
            return
        if not ans:
            return webbrowser.open(rel["url"])
        self.run_task("업데이트 내려받기", lambda prog, cancel: updater.download(rel, prog, cancel), self.update_downloaded,
                      text=f"{rel['tag']} 을 내려받는 중… (KB)")

    def update_downloaded(self, path):
        if not path:
            return
        self.flush()
        try:
            updater.apply(path)
        except OSError as ex:
            return messagebox.showerror(APP, f"업데이트를 시작하지 못했습니다.\n{ex}", parent=self.root)
        self.quit()   # 앱이 끝나야 실행 파일이 풀려서 바뀐다. 바뀐 뒤 새 버전이 자동으로 다시 시작된다.

    def help_search(self):
        messagebox.showinfo("검색 문법", "공백 = AND\n회의록 AND (예산 OR 일정) NOT 취소\n\"정확한 구절\"\n"
                            "& | ! 기호도 AND OR NOT 으로 쓸 수 있습니다(대문자만 연산자로 인식).\n\n"
                            "태그는 본문의 #태그, 또는 '태그: a, b' 줄에서 모읍니다.", parent=self.root)

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
    def section_head(self, parent, title, action=None):
        h = tk.Frame(parent, bg=C["bg"])
        h.pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(h, text=title, bg=C["bg"], fg=C["muted"], font=(self.ui, 9, "bold")).pack(side="left")
        if action:
            Btn(h, "＋", action, kind="ghost", bg=C["bg"], padx=6, pady=0).pack(side="right")

    def fit_count(self, tree, texts):
        """숫자 칸의 폭을 가장 긴 숫자에 맞춘다(고정 폭이면 13,902 같은 큰 수가 잘린다)"""
        f = tkfont.Font(family=self.ui, size=10)
        w = max([f.measure(t) for t in texts] + [24]) + 28
        tree.column("n", width=w, minwidth=w, stretch=False)

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
        self.section_head(self.nb_sec, "노트북", self.add_notebook)
        self.nbtree = self.make_tree(self.nb_sec)
        self.nbtree.bind("<<TreeviewSelect>>", self.on_nb_select)
        self.nbtree.bind("<Delete>", lambda e: self.delete_notebook())
        self.nbtree.bind("<Button-3>", self.on_nb_menu)
        self.nbmenu = tk.Menu(self.root, tearoff=0)
        self.tag_sec = tk.Frame(self.left_pane, bg=C["bg"])
        self.section_head(self.tag_sec, "태그")
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
        Btn(top, "＋ 새 노트", self.new_note, kind="primary", bold=True, pady=6).pack(side="right", padx=(8, 0))
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
        self.ph =tk.Label(box, text="검색  (예: 회의록 AND 예산)", bg=C["panel"], fg=C["muted"], font=(self.ui, 10))
        self.ph.bind("<Button-1>", lambda e: self.search_entry.focus_set())
        self.search_entry.bind("<FocusIn>", lambda e: self.update_placeholder())    # 안내 문구가 커서를 가리지 않게
        self.search_entry.bind("<FocusOut>", lambda e: self.update_placeholder())
        self.ac_init()
        bar = tk.Frame(f, bg=C["bg"])
        bar.pack(fill="x", padx=10, pady=(0, 2))
        self.sort_names = {"relevance": "관련도순", "time": "수정순", "ctime": "생성순", "title": "제목순"}
        self.sort_btns = {k: Btn(bar, v, lambda k=k: self.sort_by(k), padx=6, pady=3) for k, v in self.sort_names.items()}
        self.b_date = Btn(bar, "기간", self.toggle_date, padx=6, pady=3)
        for b in (*self.sort_btns.values(), self.b_date):
            b.pack(side="left", padx=1)
        # 가져온 파일의 '문서 안 글'까지 찾을지(끄면 이름·경로·태그·메모만 찾아서 빠르고 결과가 짧다). 가져온 폴더가 있을 때만 보인다
        self.v_content = tk.BooleanVar(value=self.docs.content_search)
        self.opt_row = tk.Frame(f, bg=C["bg"])      # 정렬 줄이 이미 꽉 차서 체크박스는 아래 줄에 둔다
        self.cb_content = tk.Checkbutton(self.opt_row, text="문서 안 글 포함", variable=self.v_content, command=self.on_content_toggle, relief="flat",
                                         bd=0, takefocus=False, bg=C["bg"], fg=C["sub"], activebackground=C["soft"], selectcolor=C["bg"],
                                         cursor="hand2", font=(self.ui, 9))
        self.cb_content.pack(side="left")
        self.tip(self.cb_content, "켜면 가져온 pdf·txt 등의 본문까지 찾고, 끄면 파일 이름·경로·태그·메모만 찾습니다")
        b_save = Btn(bar, "검색 저장", self.save_search, padx=6, pady=3)   # 지금의 검색식·기간·태그·정렬을 '저장된 검색'으로
        b_save.pack(side="right", padx=1)
        self.tip(b_save, "지금의 검색을 왼쪽 '저장된 검색'에 이름을 붙여 저장합니다(스마트 폴더)")
        self.tip(self.sort_btns["time"], "마지막으로 고친 시각 순 (조플린 내보내기 노트는 머리말의 updated)")
        self.tip(self.sort_btns["ctime"], "만든 시각 순 (조플린 내보내기 노트는 머리말의 created)")
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
        Btn(self.date_row, "지우기", lambda: (self.d_from.set(""), self.d_to.set("")), padx=8, pady=2).pack(side="left", padx=6)
        tk.Label(self.date_row, text="예) 2021.01.01", bg=C["bg"], fg=C["muted"], font=(self.ui, 8)).pack(side="left")
        self.count = tk.Label(f, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=16)
        self.count.pack(fill="x", pady=(6, 4))
        self.update_content_check()
        tk.Frame(f, height=1, bg=C["line"]).pack(fill="x")
        body = tk.Frame(f, bg=C["bg"])
        body.pack(fill="both", expand=True)
        self.lst = tk.Text(body, wrap="word", cursor="arrow", relief="flat", bd=0, highlightthickness=0, bg=C["bg"],
                           fg=C["text"], font=self.fonts["base"], padx=0, pady=0, state="disabled", exportselection=False)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.lst.yview)
        hide = autohide(sb, self.lst)

        def on_scroll(lo, hi):
            hide(lo, hi)
            if self.rendered < len(self.results) and (1 - float(hi)) < MORE_SCREENS * (float(hi) - float(lo)):
                self.root.after_idle(self.more_cards)
        self.lst.config(yscrollcommand=on_scroll)
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

    # ------------------------------------------------------------ 검색창 자동완성 (최근 검색 · 파일 제목 · 태그)
    def ac_init(self):
        old = getattr(self, "ac_top", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        self.ac_top = self.ac_list = None
        self.ac_items, self.ac_job, self.ac_click, self.ac_sig = [], None, False, None
        self.ac_titles = (None, [])      # (캐시 열쇠, [(제목, 소문자 제목)])
        self.ac_tagc = (0.0, {})         # (만든 시각, {태그: 개수})
        e = self.search_entry
        e.bind("<Down>", self.ac_down)
        e.bind("<Up>", self.ac_up)
        e.bind("<Return>", self.ac_enter)
        e.bind("<Escape>", self.ac_esc)
        e.bind("<FocusOut>", self.ac_focus_out, add="+")
        e.bind("<Button-1>", lambda ev: self.root.after(30, self.ac_show), add="+")   # 비어 있는 칸을 누르면 최근 검색
        e.bind("<FocusIn>", lambda ev: None if self.ac_visible() else setattr(self, "ac_sig", self.ac_signature()), add="+")   # 칸에 들어간 것만으로는 후보를 띄우지 않는다
        self.ac_ready = True
        if not getattr(self, "ac_polling", False):
            self.ac_polling = True
            self.ac_poll()

    def match_ime_font(self, ev=None, widget=None):
        """한글 입력기의 조합 글꼴을 지금 칸(입력칸·편집 칸 …)의 글꼴과 같게 맞춘다 — 안 맞추면 치는 글자가 잠깐 더 크게 보인다"""
        w = widget or (ev.widget if ev is not None else None)
        try:
            f = tkfont.Font(root=self.root, font=w.cget("font"))
            size = f.actual("size")
            px = size if size < 0 else -round(size * float(self.root.tk.call("tk", "scaling")))   # 음수 = 글자 높이 픽셀
            return ime.set_font(f.actual("family"), px, f.actual("weight") == "bold")
        except (tk.TclError, AttributeError):
            return False

    def ac_signature(self):
        """입력칸의 값 + 한글 입력기가 아직 확정하지 않은 조합 중인 글자. 이게 바뀌면 후보를 다시 띄운다"""
        return (self.q.get(), ime.composing())

    def ac_poll(self):
        """치는 즉시 후보를 띄운다. 한글은 마지막 글자가 확정되기 전에는 입력칸의 값(StringVar)에 안 들어가서, 값이 바뀔 때를 기다리면 방향키를 눌러야 뜬다 → 조합 중인 글자까지 보며 0.12초마다 확인"""
        self.root.after(120, self.ac_poll)
        if not getattr(self, "ac_ready", False):
            return
        try:
            if self.root.focus_get() is not self.search_entry:   # 후보 창이 뜨며 잠깐 포커스가 빠져도 기준값은 그대로 둔다(안 그러면 다음 변화를 한 번 놓친다)
                return
        except KeyError:
            return
        sig = self.ac_signature()
        if sig[1] and not getattr(self, "ime_font_set", False):   # 조합이 막 시작됐으면 그 글꼴을 입력칸에 맞춘다(한 조합에 한 번)
            self.ime_font_set = self.match_ime_font(widget=self.search_entry)
        elif not sig[1]:
            self.ime_font_set = False
        if self.ac_sig is None:
            self.ac_sig = sig
            return
        if sig != self.ac_sig:
            self.ac_sig = sig
            self.ac_show()

    def search_history(self):
        return [h for h in st.read_config().get("searchHist", []) if isinstance(h, str)]

    def remember_search(self, q):
        q = (q or "").strip()
        if not q:
            return
        hist = [h for h in self.search_history() if h != q and not q.lower().startswith(h.lower())]   # 치다 만 앞부분은 같이 쌓지 않는다
        st.write_config(searchHist=([q] + hist)[:30])

    def ac_tags(self):
        """{태그: 개수} (노트 + 가져온 파일). 자주 만들지 않게 5초 동안 기억"""
        t0, counts = self.ac_tagc
        if time.time() - t0 > 5:
            counts = {}
            for n in self.all_notes:
                for t in n["tags"]:
                    counts[t] = counts.get(t, 0) + 1
            for t, c in self.docs.tag_counts().items():
                counts[t] = counts.get(t, 0) + c
            self.ac_tagc = (time.time(), counts)
        return counts

    def ac_candidates(self):
        """지금 커서 앞의 낱말에 맞는 후보 → [(종류, 보여 줄 글, 넣을 글, 바꿀 시작, 바꿀 끝)] (최대 8개)"""
        text = self.q.get() + ime.composing()   # 조합 중인 마지막 글자까지 (아직 입력칸 값에 안 들어 있다)
        pos = len(text)   # 커서 위치는 쓰지 않는다: 한글 입력기(IME)는 커서를 한 글자씩 늦게 옮겨서, 치는 낱말이 비어 보이거나 한 글자 전 글이 잡힌다
        m = re.search(r"\S*$", text)
        start, tok = m.start(), m.group(0)
        lead = re.match(r'^[(!&|"]+', tok)      # 괄호·부정·따옴표는 낱말 앞에서 떼어 둔다
        quoted = bool(lead and '"' in lead.group(0))
        if lead:
            start += lead.end()
            tok = tok[lead.end():]
        items = []
        hist = self.search_history()
        if not text.strip():        # 빈 칸: 최근 검색
            return [("최근", h, h, 0, len(text)) for h in hist[:8]]
        low = tok.lower()
        if low.startswith("#"):                   # 태그만: '#' 만 쳤을 때는 띄우지 않고, '#신' 처럼 한 글자라도 더 쳐야 그 글자로 시작하는 태그를 보여 준다
            key = low[1:]
            if not key:
                return []
            tags = sorted(self.ac_tags().items(), key=lambda kv: (-kv[1], kv[0].lower()))
            return [("태그", f"#{t}   ({c:,})", f"#{t}", start, pos) for t, c in tags if t.lower().startswith(key)][:8]
        if not tok:
            return []
        key = (id(self.notes), len(self.notes))   # 그냥 글자를 치면 제목만(태그는 # 를 눌렀을 때만, 최근 검색은 빈 칸일 때만)
        if self.ac_titles[0] != key:
            self.ac_titles = (key, [(n["title"], n["title"].lower()) for n in self.notes])
        seen, titles = set(), []
        for title, tl in self.ac_titles[1]:
            if low in tl and tl not in seen:
                seen.add(tl)
                titles.append((not tl.startswith(low), len(tl), title))
        for _p, _l, title in sorted(titles)[:8]:
            if len(items) >= 8:
                break
            plain = re.fullmatch(r"[^\s()\"&|!]+", title) is not None
            ins = title if plain and not quoted else (title + '"' if quoted else f'"{title}"')
            items.append(("제목", title, ins, start, pos))
        return items[:8]

    def ac_show(self):
        self.ac_job = None
        if self.root.focus_get() is not self.search_entry:
            return
        self.ac_items = self.ac_candidates()
        if not self.ac_items:
            return self.ac_hide()
        if self.ac_list is None:
            # 별도 창(Toplevel)이 아니라 목록 칸 위에 겹쳐 놓는 위젯이다: 별도 창은 뜰 때 입력칸의 키보드 포커스를 가져가서 계속 칠 수 없다
            lb = self.ac_list = self.ac_top = tk.Listbox(self.listf, relief="flat", bd=0, activestyle="none", exportselection=False, takefocus=0,
                                                         highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["line"],
                                                         bg=C["bg"], fg=C["text"], selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10))
            lb.bind("<ButtonPress-1>", lambda ev: (setattr(self, "ac_click", True), "break")[1])      # 눌러도 입력칸의 포커스가 옮겨 가지 않게
            lb.bind("<ButtonRelease-1>", lambda ev: self.ac_pick(lb.nearest(ev.y)))
            lb.bind("<Motion>", lambda ev: (lb.selection_clear(0, "end"), lb.selection_set(lb.nearest(ev.y))))
        lb = self.ac_list
        lb.delete(0, "end")
        for kind, label, _ins, _a, _b in self.ac_items:   # 제목·태그는 # 로 구분되니 표시를 달지 않고, 최근 검색만 '최근' 을 붙인다
            lb.insert("end", f"최근   {label}" if kind == "최근" else label)
        lb.config(height=len(self.ac_items))
        box = self.search_entry.master
        lb.place(in_=self.listf, x=box.winfo_rootx() - self.listf.winfo_rootx(),
                 y=box.winfo_rooty() - self.listf.winfo_rooty() + box.winfo_height() + 1, width=box.winfo_width())
        lb.lift()

    def ac_hide(self):
        if self.ac_job:
            self.root.after_cancel(self.ac_job)
            self.ac_job = None
        self.ac_click = False
        if self.ac_list is not None:
            self.ac_list.place_forget()
        self.ac_items = []

    def ac_visible(self):
        return self.ac_list is not None and bool(self.ac_items) and self.ac_list.winfo_ismapped()

    def ac_move(self, step):
        lb = self.ac_list
        cur = lb.curselection()
        i = (cur[0] + step) if cur else (0 if step > 0 else len(self.ac_items) - 1)
        i = max(0, min(len(self.ac_items) - 1, i))
        lb.selection_clear(0, "end")
        lb.selection_set(i)
        lb.see(i)

    def ac_down(self, ev=None):
        if not self.ac_visible():
            self.ac_show()
            return "break"
        self.ac_move(1)
        return "break"

    def ac_up(self, ev=None):
        if self.ac_visible():
            self.ac_move(-1)
            return "break"

    def ac_enter(self, ev=None):
        if self.ac_visible() and self.ac_list.curselection():
            self.ac_pick(self.ac_list.curselection()[0])
            return "break"
        self.ac_hide()
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.remember_search(self.q.get())
        return "break"

    def ac_esc(self, ev=None):
        if self.ac_visible():
            self.ac_hide()
            return "break"

    def ac_pick(self, i):
        """고른 후보를 검색어에 넣고 바로 찾는다"""
        if not (0 <= i < len(self.ac_items)):
            return self.ac_hide()
        _kind, _label, ins, a, b = self.ac_items[i]
        text = self.q.get()
        new = text[:a] + ins + text[b:]   # (조합 중이던 글자는 입력칸 값에 없으므로 자연히 빠진다)
        self.ac_hide()
        ime.cancel()                          # 조합 중이던 글자가 나중에 또 붙지 않게
        self.q.set(new)
        self.ac_sig = (new, "")               # 이 값 바꿈이 또 후보를 띄우지 않게
        self.search_entry.focus_set()
        self.search_entry.icursor(a + len(ins))
        self.remember_search(new)

    def ac_focus_out(self, ev=None):
        if self.ac_click:                     # 후보를 누르는 중이면 ButtonRelease 가 처리한다
            return
        self.root.after(150, self.ac_hide)
        if self.q.get().strip() and self.results:
            self.remember_search(self.q.get())

    def clear_search(self):
        """검색어를 지우고 전체 목록으로 돌아간다(기간 필터와 태그 거르기는 그대로)"""
        self.q.set("")
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.refresh()
        self.search_entry.focus_set()

    def update_placeholder(self):
        if self.q.get():
            self.clear_btn.place(relx=1.0, x=-8, rely=0.5, anchor="e")
        else:
            self.clear_btn.place_forget()
        if self.q.get() or self.root.focus_get() is self.search_entry:
            self.ph.place_forget()
        else:
            self.ph.place(x=10, rely=0.5, anchor="w")

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
        self.empty = tk.Label(f, text="노트를 선택하거나 새로 만드세요\nCtrl+N", bg=C["bg"], fg=C["muted"], font=(self.ui, 11), justify="center")
        self.main = tk.Frame(f, bg=C["bg"])
        head = tk.Frame(self.main, bg=C["bg"])
        head.pack(fill="x", padx=18, pady=(14, 6))
        self.title_var = tk.StringVar()
        # 문법 체크박스(위키나루처럼): 제목줄 맨 오른쪽, 노트 속성(ⓘ) 아이콘의 오른쪽
        sb = tk.Checkbutton(head, text="문법", variable=self.v["syntax"], command=self.on_view_toggle, relief="flat", bd=0,
                            takefocus=False, bg=C["bg"], fg=C["text"], activebackground=C["soft"], selectcolor=C["bg"],
                            cursor="hand2", font=(self.ui, 10))
        sb.pack(side="right", padx=(2, 2))
        sb.bind("<Enter>", lambda e: sb.config(bg=C["soft"]), add="+")
        sb.bind("<Leave>", lambda e: sb.config(bg=C["bg"]), add="+")
        self.tip(sb, "문법 해설 사이드바 보이기/숨기기 (Ctrl+/)")
        info = Btn(head, "ⓘ", self.show_properties, kind="icon", padx=8, pady=2, font=(self.ui, 13))
        info.pack(side="right", padx=(6, 0))
        self.tip(info, "노트 속성")
        # 보기 탭 (좌우 분할 / 렌더링만 / 원문만)
        seg = tk.Frame(head, bg=C["line"], padx=1, pady=1)
        seg.pack(side="right", padx=(8, 0))
        self.mode_btns = {}
        for m, label, hint in (("split", "좌우 분할", "마크다운과 렌더링을 나란히"), ("view", "렌더링만", "렌더링 결과만 크게"),
                               ("edit", "원문만", "마크다운 원문만 크게(집중 편집)")):
            b = Btn(seg, label, lambda m=m: self.set_mode(m), kind="tab", padx=9, pady=3)
            b.pack(side="left")
            self.tip(b, hint)
            self.mode_btns[m] = b
        self.mode_seg = seg
        self.doc_toggle = Btn(head, "", self.toggle_doc_view, kind="tab", padx=9, pady=3)   # 가져온 문서: 원본 미리보기 ↔ 뽑은 글(찾기). 평소엔 숨김
        self.memo_btn = Btn(head, "메모", self.edit_memo, kind="tab", padx=9, pady=3)       # 가져온 문서: 메모 붙이기. 평소엔 숨김
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
        self.tag_edit = None   # 태그를 고치는 중이면 (입력칸, 안내 라벨)
        tk.Frame(self.main, height=1, bg=C["line"]).pack(side="bottom", fill="x")
        self.body = tk.Frame(self.main, bg=C["panel"])
        self.body.pack(fill="both", expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        # 문서 안에서 찾기 막대(Ctrl+F 로 보이고 Esc 로 닫는다). 평소엔 숨겨 둔다.
        self.findbar = tk.Frame(self.main, bg=C["soft"])
        self.find_var = tk.StringVar()
        self.find_hits, self.find_i, self.find_job = [], -1, None
        tk.Label(self.findbar, text="문서에서 찾기", bg=C["soft"], fg=C["sub"], font=(self.ui, 9), padx=14).pack(side="left")
        self.find_entry = tk.Entry(self.findbar, textvariable=self.find_var, width=30, relief="flat", bg=C["bg"], fg=C["text"],
                                   insertbackground=C["accent"], highlightthickness=1, highlightbackground=C["line"],
                                   highlightcolor=C["accent"], font=(self.ui, 10))
        self.find_entry.pack(side="left", pady=5, ipady=2)
        self.find_count = tk.Label(self.findbar, text="", bg=C["soft"], fg=C["muted"], font=(self.ui, 9), padx=10, width=9, anchor="w")
        self.find_count.pack(side="left")
        for label, cmd in (("▲", lambda: self.find_step(-1)), ("▼", lambda: self.find_step(1)), ("✕", self.hide_find)):
            Btn(self.findbar, label, cmd, padx=8, pady=1).pack(side="left", padx=1)
        tk.Label(self.findbar, text="Enter 다음 · Shift+Enter 이전 · Esc 닫기", bg=C["soft"], fg=C["muted"], font=(self.ui, 8), padx=12).pack(side="left")
        self.find_var.trace_add("write", lambda *a: self.find_run())
        self.find_entry.bind("<Return>", lambda e: self.find_step(1))
        self.find_entry.bind("<Shift-Return>", lambda e: self.find_step(-1))
        self.find_entry.bind("<Escape>", lambda e: self.hide_find())
        ring = dict(highlightthickness=2, highlightbackground=C["line"], highlightcolor=C["accent"], relief="flat", bd=0)

        self.edit_frame = tk.Frame(self.body, bg=C["panel"])
        self.pane_head(self.edit_frame, "마크다운", "편집")
        box = tk.Frame(self.edit_frame, bg=C["panel"])
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(box, wrap="word", undo=True, maxundo=-1, font=(self.mono, self.size) + (("bold",) if self.note_bold else ()), padx=14, pady=10,
                            tabs=("1c",), bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
                            selectbackground=C["sel"], selectforeground=C["text"], spacing2=3, **ring)
        sb1 = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.config(yscrollcommand=autohide(sb1, self.text))
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<<Modified>>", self.on_modified)

        # 윈도 미리보기 처리기가 그림을 그리는 자리. 한 번 미리보기를 품은 틀은 숨겼다 다시 붙이면 화면에 안 올라오므로(Tk 의 map/unmap)
        # 숨기지 않고 항상 이 자리에 둔 채 위로 올리고(미리보기) 아래로 내린다(평소). 평소에는 편집·렌더링 칸이 그 위를 완전히 덮는다.
        self.pv_frame = tk.Frame(self.body, bg=C["bg"])
        self.pv_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.pv_frame.lower()
        self.pv_frame.bind("<Configure>", lambda e: self.pv_active and self.pv.resize(e.width, e.height))

        self.view_frame = tk.Frame(self.body, bg=C["panel"])
        self.pane_head(self.view_frame, "렌더링", "읽기 전용")
        box2 = tk.Frame(self.view_frame, bg=C["panel"])
        box2.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.view = tk.Text(box2, wrap="word", state="disabled", font=self.fonts["base"], padx=18, pady=12, cursor="arrow",
                            bg=C["bg"], fg=C["text"], selectbackground=C["sel"], selectforeground=C["text"], spacing2=3, **ring)
        sb2 = ttk.Scrollbar(box2, orient="vertical", command=self.view.yview)
        self.view.config(yscrollcommand=autohide(sb2, self.view))
        self.view.pack(side="left", fill="both", expand=True)
        self.configure_tags()
        self.view.bind("<Button-1>", self.on_view_click)
        box2.bind("<Configure>", self.on_view_resize)
        self.view.bind("<Button-3>", self.on_view_menu)
        self.text.bind("<Button-3>", self.on_text_menu)
        self.show_empty(True)

    def show_empty(self, on):
        if on:
            self.main.pack_forget()
            self.empty.pack(fill="both", expand=True)
        else:
            self.empty.pack_forget()
            self.main.pack(fill="both", expand=True)

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
        v.tag_configure("fnref")
        v.tag_configure("quote", foreground=C["muted"])
        v.tag_configure("hr", foreground=C["line"])
        for n in range(1, 7):
            v.tag_configure(f"h{n}", font=self.hfonts[n], spacing1=6, spacing3=2)
        for n in range(1, preview.MAX_LEVEL + 1):
            v.tag_configure(f"M{n}", lmargin1=20 * n, lmargin2=20 * n)
            v.tag_configure(f"B{n}", lmargin1=20 * (n - 1) + 6, lmargin2=20 * n)
        v.tag_raise("link")
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
        self.tip(close, "문법 해설 닫기 (Ctrl+/)")
        tk.Label(hd, text="문법 해설", anchor="w", font=(self.ui, 11, "bold"), padx=16, bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Label(f, text="마크다운", anchor="w", font=(self.ui, 9), padx=16, bg=C["bg"], fg=C["muted"]).pack(fill="x", pady=(0, 8))
        tk.Label(f, text="누르면 커서 자리에 넣고, 글을 고르고 누르면 감쌉니다.\nCtrl+B 굵게 · Ctrl+I 기울임 · Ctrl+K 링크",
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
                parent = self.tree.insert("", "end", text=g, open=True, values=("",), tags=("group",))
            self.actions[self.tree.insert(parent, "end", text=example, values=(name,), tags=("item",))] = action

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
        if key == "@docs":
            return "가져온 폴더"
        if key.startswith("@smart"):
            s = next((x for x in self.smart_list() if "@smart:" + x["id"] == key), None)
            return s["name"] if s else "저장된 검색"
        if key.startswith("@doc:"):
            f = next((f for f in self.docs.folders() if f["id"] == key[5:]), None)
            return f.get("name") or f["path"] if f else "가져온 폴더"
        if not key or key == ALL:
            return self.store.root_name if key == "" else "모든 파일"
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
            return messagebox.showinfo(APP, "저장할 검색이 없습니다. 검색어나 기간, 태그를 먼저 정하세요.", parent=self.root)
        lst = self.smart_list()
        cond = {"q": q, "d_from": f, "d_to": t, "tag": tag or "", "sort": self.sort, "asc": self.asc}
        if overwrite:
            for s in lst:
                if s["id"] == overwrite:
                    s.update(cond)
            sid = overwrite
        else:
            name = simpledialog.askstring("검색 저장", "이 검색의 이름:", initialvalue=q or (f"# {tag}" if tag else "검색"), parent=self.root)
            if not name or not name.strip():
                return
            sid = secrets.token_hex(4)
            lst.append({"id": sid, "name": name.strip(), **cond})
        st.write_config(smart=lst)
        self.nb = "@smart:" + sid
        self.reload_notebooks()
        self.status.config(text="검색을 저장했습니다 (왼쪽 '저장된 검색')")

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
            name = simpledialog.askstring("이름 바꾸기", "저장된 검색의 이름:", initialvalue=s["name"], parent=self.root)
            if name and name.strip():
                lst = self.smart_list()
                for x in lst:
                    if x["id"] == sid:
                        x["name"] = name.strip()
                st.write_config(smart=lst)
                self.reload_notebooks()

        def delete():
            if not messagebox.askyesno(APP, f"저장된 검색 「{s['name']}」을(를) 지울까요?\n(노트와 파일은 그대로입니다)", parent=self.root):
                return
            st.write_config(smart=[x for x in self.smart_list() if x["id"] != sid])
            if self.nb == key:
                self.nb = ALL
                self.apply_loaded(self.all_notes)
            else:
                self.reload_notebooks()
        return [("이름 바꾸기…", rename), ("지금의 검색으로 덮어쓰기", lambda: self.save_search(overwrite=sid)), ("삭제", delete)]

    def in_nb(self, n):
        """지금 고른 노트북에 속한 노트인가 (하위 노트북의 노트 포함)"""
        if self.nb == ALL:
            return True
        if self.nb == "":
            return n["nb"] == ""
        return n["nb"] == self.nb or n["nb"].startswith(self.nb + "/")

    def reload_notebooks(self):
        names = self.store.notebooks()
        dfolders = self.docs.folders()
        doc_keys = (["@docs"] + ["@doc:" + f["id"] for f in dfolders]) if dfolders else []
        smarts = self.smart_list()
        smart_keys = (["@smarts"] + ["@smart:" + s["id"] for s in smarts]) if smarts else []
        if self.nb not in (ALL, "") and self.nb not in names and self.nb not in doc_keys and self.nb not in smart_keys:
            self.nb = ALL
        self.nb_keys = [ALL, ""] + names + doc_keys + smart_keys
        dcounts = self.docs.counts() if dfolders else {}
        direct = {}
        for n in self.all_notes:
            direct[n["nb"]] = direct.get(n["nb"], 0) + 1
        total = lambda key: sum(c for k, c in direct.items() if k == key or k.startswith(key + "/"))  # noqa: E731
        self.quiet = True
        self.nbtree.delete(*self.nbtree.get_children())
        idx = {key: i for i, key in enumerate(self.nb_keys)}
        for i, key in enumerate(self.nb_keys):
            if key == ALL:
                label, count, parent = "모든 파일", len(self.all_notes) + sum(dcounts.values()), ""   # 노트 + 가져온 문서
            elif key == "":
                label, count, parent = self.store.root_name, None, ""   # 저장 폴더 줄에는 숫자를 달지 않는다(아래 노트북들이 실제 내용)
            elif key == "@docs":
                label, count, parent = "가져온 폴더", sum(dcounts.values()), ""
            elif key.startswith("@doc:"):
                label, count, parent = self.nb_label(key), dcounts.get(key[5:], 0), f"nb{idx['@docs']}"
            elif key == "@smarts":
                label, count, parent = "저장된 검색", None, ""
            elif key.startswith("@smart:"):
                label, count, parent = self.nb_label(key), None, f"nb{idx['@smarts']}"
            else:
                label, count = self.nb_short(key), total(key)
                # 최상위 노트북은 저장 폴더 항목(scrapbook) 아래에 들여써서 보여 준다
                parent = f"nb{idx[key.rsplit('/', 1)[0]]}" if "/" in key else f"nb{idx['']}"
            self.nbtree.insert(parent, "end", iid=f"nb{i}", text="  " + label, values=("" if count is None else f"{count:,}",), open=True)
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
            self.tagtree.insert("", "end", iid=f"tg{i}", text="  # " + t, values=(f"{counts[t]:,}",))
        if self.tag in self.tag_keys:
            self.tagtree.selection_set(f"tg{self.tag_keys.index(self.tag)}")
        self.fit_count(self.tagtree, [f"{c:,}" for c in list(counts.values())[:200]])
        self.quiet = False

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
        if key == "@smarts":   # 머리글: 고를 수 없다. 원래 선택으로 되돌린다
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
        if key.startswith("@smart"):   # 저장된 검색
            if key == "@smarts":
                m.add_command(label="지금의 검색 저장…", command=self.save_search)
            else:
                for label, cmd in self.smart_menu(key) or []:
                    m.add_command(label=label, command=cmd)
            return m.tk_popup(e.x_root, e.y_root)
        if key.startswith("@doc"):   # 가져온 폴더: 원본 파일은 건드리지 않는다
            if key.startswith("@doc:"):
                m.add_command(label="다시 읽기", command=lambda: self.scan_docs(key[5:]))
                m.add_command(label="목록에서 빼기 (원본 파일은 그대로)", command=lambda: self.remove_doc_folder(key[5:]))
            else:
                m.add_command(label="모두 다시 읽기", command=lambda: self.scan_docs())
            m.add_command(label="가져오기 설정…", command=lambda: self.show_options("imports"))
            return m.tk_popup(e.x_root, e.y_root)
        if key == ALL:   # '모든 노트'는 노트북이 아니므로 최상위에 새 노트북을 만든다
            m.add_command(label="새 노트북 만들기", command=self.add_notebook)
        else:            # 저장 폴더(최상위)도 노트북처럼 상위가 될 수 있다
            m.add_command(label="하위 노트북 만들기", command=lambda: self.add_notebook(parent=key, show_parent=True))
        if key != ALL:
            m.add_command(label="저장 폴더 전체 삭제(휴지통)" if key == "" else "노트북 삭제(휴지통)", command=self.delete_notebook)
        m.tk_popup(e.x_root, e.y_root)

    def add_subnotebook(self):
        """고른 노트북(저장 폴더 자체 포함) 안에 하위 노트북을 만든다. '모든 노트'를 골랐으면 최상위에 만든다."""
        parent = self.md_nb()
        self.add_notebook(parent=parent, show_parent=not (self.nb == ALL or self.nb.startswith("@")))

    def add_notebook(self, parent="", show_parent=False):
        where = f"\n상위: {self.nb_label(parent)}" if (parent or show_parent) else ""
        name = simpledialog.askstring("새 하위 노트북" if (parent or show_parent) else "새 노트북", "노트북 이름" + where, parent=self.root)
        if not name or not name.strip():
            return
        try:
            folder = self.store.create_notebook(name, parent)
        except OSError as ex:
            return messagebox.showerror(APP, f"노트북을 만들지 못했습니다.\n{ex}")
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
        if not messagebox.askyesno(APP, f"노트북 \"{self.nb_label(key)}\"을(를) 휴지통으로 보낼까요?\n(하위 노트북과 안의 노트도 함께 가며, {self.store.trash_days}일 동안 보관합니다)", parent=self.root):
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
        msg = (f"저장 폴더 \"{self.store.root_name}\" 전체를 휴지통으로 보낼까요?\n\n{root}\n\n"
               f"안의 노트 {len(self.all_notes)}개, 노트북 {len(books)}개"
               + (", 리소스 폴더(그림)" if inside else "") + ", 노트 버전 기록이 모두 함께 갑니다.\n"
               + ("" if inside else "(리소스 폴더는 저장 폴더 밖에 있어서 그대로 남습니다.)\n")
               + f"\n앱의 휴지통에서 {self.store.trash_days}일 동안 보관하며 복원할 수 있습니다.")
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
            self.status.config(text="저장 폴더의 내용을 휴지통으로 보냈습니다. (파일 → 휴지통에서 복원)")
        self.checkpoint("저장 폴더 삭제 전", go)

    def choose_root(self):
        d = filedialog.askdirectory(parent=self.root, initialdir=self.store.root, title="노트를 저장할 폴더")
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
            self.status.config(text=f"가져온 폴더: 파일 {total:,}개 (새로 읽은 것 {read:,}, 사라진 것 {gone:,})")
        self.run_task("가져온 폴더 읽는 중", lambda prog, cancel: self.docs.scan(prog, cancel, only), done,
                      text="가져온 폴더의 문서를 읽는 중… (처음 한 번은 오래 걸립니다)")

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
        if not f or not messagebox.askyesno(APP, f"「{f['path']}」을(를) 가져온 폴더 목록에서 뺄까요?\n(원본 파일은 그대로 두고, 이 앱의 색인만 지웁니다)", parent=self.root):
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
        self.count.config(text="노트를 불러오는 중…")
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
                    self.count.config(text=f"처음 한 번 색인을 만드는 중… {d:,} / {t:,}")
                return self.root.after(80, poll)
            if gen != self.load_gen:
                return    # 그 사이에 다른 읽기가 있었으면 버린다
            if kind == "ok":
                self.apply_loaded(val)
            else:
                self.count.config(text="노트를 불러오지 못했습니다: " + val)
        self.root.after(80, poll)

    def read_all_notes(self):
        self.load_prog = (0, 0)
        return self.store.list_notes(ALL, tagger=note_tags, progress=lambda d, t: setattr(self, "load_prog", (d, t)))

    def apply_loaded(self, loaded, keep_scroll=False):
        keep = self.cur["path"] if self.cur else None
        self.all_notes = loaded
        if self.nb.startswith("@doc"):   # 가져온 폴더를 골랐으면 목록은 노트가 아니라 가져온 문서
            self.notes = self.docs.list_docs(self.nb[5:] if self.nb.startswith("@doc:") else None)
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

    def schedule_search(self):
        if self.search_job:
            self.root.after_cancel(self.search_job)
        self.search_job = self.root.after(180, self.refresh)

    def refresh(self, keep_page=False):
        """검색·정렬을 다시 하고 목록을 그린다. keep_page=True 는 자동 저장 때처럼 보던 자리를 유지"""
        self.search_job = None
        pool = [n for n in self.notes if self.tag in n["tags"]] if self.tag else self.notes
        self.results, self.words = search.run(pool, self.q.get(), self.sort, self.asc, self.d_from.get(), self.d_to.get(),
                                           index=self.docs if self.nb.startswith("@doc") else
                                           docidx.Combined(self.store, self.docs) if self.scope_all() else self.store)
        self.draw_list(keep_scroll=keep_page)

    def draw_list(self, keep_scroll=False):
        total = len(self.results)
        searching = self.q.get().strip() or self.d_from.get().strip() or self.d_to.get().strip() or self.tag
        unit = "파일" if self.scope_all() or self.nb.startswith("@doc") else "노트"
        text = f"{len(self.notes):,}개 중 {total:,}개 찾음" if searching else f"{total:,}개의 {unit}"
        if self.tag:
            text += f"  ·  # {self.tag}"
        self.count.config(text=text)
        L = self.lst
        if not keep_scroll:
            self.multi.clear()
        top = L.yview()[0] if keep_scroll else 0.0   # 자동 저장·삭제 때만 스크롤을 유지하고, 정렬·검색·노트북을 바꾸면 맨 위부터
        top_line = L.index("@0,0") if keep_scroll else None   # 목록이 줄어도 같은 자리에 머물도록 맨 위 줄로 되돌린다
        want = max(LIST_CHUNK, self.rendered) if keep_scroll else LIST_CHUNK
        L.config(state="normal")
        L.delete("1.0", "end")
        L.config(state="disabled")
        self.cards, self.card_starts, self.rendered, self.next_line = [], [], 0, 1
        self.append_cards(want)
        L.yview_moveto(top)
        if top_line:
            L.yview(top_line)
        self.mark_selected()
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
            if self.scope_all() or n["nb"] != self.nb:   # 모든 노트이거나 하위 노트북의 노트면 어느 노트북인지 보여 준다
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
        self.status.config(text=f"노트 {len(self.multi)}개 선택됨 (우클릭: 휴지통·이동, Esc: 해제)" if self.multi else "")

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
        if not items or not messagebox.askyesno(APP, f"고른 노트 {len(items)}개를 휴지통으로 보낼까요?\n({self.store.trash_days}일 동안 보관하며 복원할 수 있습니다)", parent=self.root):
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
            messagebox.showerror(APP, f"{fail}개 노트를 옮기지 못했습니다.", parent=self.root)

    def card_at(self, e):
        line = int(self.lst.index(f"@{e.x},{e.y}").split(".")[0])
        i = bisect.bisect_right(self.card_starts, line) - 1
        if i >= 0 and line <= self.cards[i][1]:
            return self.cards[i][2]
        return None

    def on_list_click(self, e):
        n = self.card_at(e)
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
            messagebox.showerror(APP, f"파일을 열지 못했습니다.\n{ex}", parent=self.root)

    def doc_menu(self, e, n):
        self.open_note(n)
        lm = self.listmenu
        lm.delete(0, "end")
        lm.add_command(label="기본 프로그램으로 열기", command=lambda: self.open_doc_file(n))
        lm.add_command(label="태그 추가·고치기…", command=self.edit_tags)
        lm.add_command(label="메모…", command=self.edit_memo)
        lm.add_separator()
        lm.add_command(label="파일 위치 열기", command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_command(label="경로 복사", command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(n["path"])))
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    def on_list_menu(self, e):
        """노트 우클릭 메뉴 (조플린: 삭제 · 노트북으로 이동 · 링크 복사 …)"""
        n = self.card_at(e)
        if not n:
            return
        if isinstance(n, docidx.Doc):
            return self.doc_menu(e, n)
        if self.multi and n["path"] in self.multi:   # 여러 개를 고른 채 그 안에서 우클릭
            return self.multi_menu(e)
        self.clear_multi()
        self.open_note(n)
        self.ctx_note = n
        lm, mm = self.listmenu, self.movemenu
        lm.delete(0, "end")
        mm.delete(0, "end")
        for key in [""] + self.store.notebooks():
            label = ("    " * key.count("/") + (self.nb_short(key) if key else self.store.root_name))
            mm.add_command(label=label, command=lambda k=key: self.move_note(n, k), state="disabled" if key == n["nb"] else "normal")
        lm.add_cascade(label="노트북으로 이동", menu=mm)
        lm.add_command(label="태그 추가…", command=lambda: self.tag_new([n]))
        lm.add_command(label="노트 링크 복사", command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(f"[[{n['title']}]]")))
        lm.add_command(label="노트 속성…", command=self.show_properties)
        lm.add_command(label="노트 버전…", command=self.show_versions)
        lm.add_command(label="파일 위치 열기", command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(n["path"])]))
        lm.add_separator()
        lm.add_command(label="삭제", command=self.delete_note)
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    def multi_menu(self, e):
        lm, mm = self.listmenu, self.movemenu
        lm.delete(0, "end")
        mm.delete(0, "end")
        for key in [""] + self.store.notebooks():
            label = ("    " * key.count("/") + (self.nb_short(key) if key else self.store.root_name))
            mm.add_command(label=label, command=lambda k=key: self.move_multi(k))
        lm.add_cascade(label=f"노트 {len(self.multi)}개를 노트북으로 이동", menu=mm)
        lm.add_command(label=f"노트 {len(self.multi)}개에 태그 추가…", command=lambda: self.tag_new(list(self.multi.values())))
        lm.add_command(label=f"노트 {len(self.multi)}개 휴지통으로", command=self.trash_multi)
        lm.add_separator()
        lm.add_command(label="선택 해제", command=self.clear_multi)
        lm.tk_popup(e.x_root, e.y_root)
        return "break"

    def move_note(self, n, nb):
        self.flush()
        try:
            new = self.store.move(n["path"], nb)
        except OSError as ex:
            return messagebox.showerror(APP, f"노트를 옮기지 못했습니다.\n{ex}")
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
            self.status.config(text=f"원본 미리보기 (윈도 기본 프로그램)   ·   {n['path']}   ·   글로 바꾸면 Ctrl+F 로 찾을 수 있습니다")
        else:
            self.apply_layout("edit")
            body = n.read()
            if not body.strip():
                body = ("(이 파일에서 뽑은 글이 없습니다.)\n\n" if n["ext"] not in docidx.AUDIO_EXT else "") + "위치: " + n["path"]
            if n.get("memo"):
                body = "[메모]\n" + n["memo"] + "\n\n" + "─" * 24 + "\n\n" + body
            n["body"] = body
            self.text.config(state="normal", wrap="word")
            self.set_text(body)
            self.text.config(state="disabled")
            self.text.yview_moveto(0)
            self.status.config(text=f"가져온 파일 (읽기 전용)   ·   {n['path']}   ·   더블클릭이나 우클릭 → 기본 프로그램으로 열기")
            if self.findbar.winfo_ismapped():
                self.find_run()
        if can:
            if not self.doc_toggle.winfo_ismapped():
                self.doc_toggle.pack(side="right", padx=(8, 0), before=self.mode_seg)
            self.doc_toggle.config(text="뽑은 글로 보기" if self.pv_active else "원본으로 보기")
        else:
            self.doc_toggle.pack_forget()
        if not self.memo_btn.winfo_ismapped():
            self.memo_btn.pack(side="right", padx=(8, 0), before=self.doc_toggle if self.doc_toggle.winfo_ismapped() else self.mode_seg)
        self.memo_btn.config(text="메모 ●" if n.get("memo") else "메모")
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
        self.set_text(n["body"])
        self.text.yview_moveto(0)
        self.dirty = False
        self.update_status()
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
        msg = (f"이 노트에는 그림 {count}개({size / 1_000_000:.1f}MB)가 글자로 본문에 박혀 있어 열 때 느립니다.\n\n"
               "그림을 리소스 폴더의 파일로 분리할까요?\n(그림은 그대로 보이고 노트는 작아집니다)")
        if not messagebox.askyesno(APP, msg, parent=self.root):
            return
        body, moved = self.store.extract_images(self.text.get("1.0", "end-1c"), n["nb"])
        self.text.config(wrap="word")
        self.set_text(body)
        self.dirty = True
        self.flush()
        self.render()
        self.status.config(text=f"그림 {moved}개를 리소스 폴더로 옮겼습니다")

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
        self.dirty = False
        self.show_empty(True)

    def on_modified(self, e=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.loading or not self.cur:
            return
        self.dirty = True
        self.find_later()   # 찾기 막대가 열려 있으면 바뀐 글에서 다시 찾는다
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(600, self.flush)
        if self.mode != "edit":
            if self.render_job:
                self.root.after_cancel(self.render_job)
            self.render_job = self.root.after(200 if len(self.text.get("1.0", "end")) < 40000 else 700, self.render)

    def flush(self):
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
            return self.status.config(text="저장 실패: " + str(ex))
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
        self.update_status("저장됨 " + time.strftime("%H:%M:%S"))

    def update_status(self, extra=""):
        if self.cur and self.doc_open:   # 가져온 파일: 아랫줄 상태 글은 그대로 두고 태그만 갱신
            if not self.tag_edit:
                tags = sorted(self.cur.get("tags", ()))
                shown = "   ".join("# " + t for t in tags[:6]) + (f"   … +{len(tags) - 6}" if len(tags) > 6 else "")
                self.tagbtn.config(text=shown or "# 태그 추가", fg=C["accent"] if tags else C["muted"])
            return
        if self.cur:
            self.status.config(text=f"{self.nb_label(self.cur['nb'])}/{os.path.basename(self.cur['path'])}   ·   "
                                    f"{len(self.cur['body']):,}자" + (f"   ·   {extra}" if extra else "") + "   ·")
            if not self.tag_edit:
                tags = sorted(self.cur.get("tags", ()))
                shown = "   ".join("# " + t for t in tags[:6]) + (f"   … +{len(tags) - 6}" if len(tags) > 6 else "")
                self.tagbtn.config(text=shown or "# 태그 추가", fg=C["accent"] if tags else C["muted"])

    def edit_tags(self, e=None):
        """맨 아래 줄의 태그를 누르면 그 자리에 입력칸이 열린다: 공백이나 쉼표로 나눠 쓰고 Enter 로 저장, Esc 로 취소"""
        if not self.cur or self.tag_edit:
            return
        self.flush()
        tags = sorted(self.cur.get("tags", ()))
        var = tk.StringVar(value=" ".join("#" + t for t in tags) + (" " if tags else "#"))
        ent = tk.Entry(self.statusbar, textvariable=var, width=36, relief="flat", bg=C["panel"], fg=C["text"], insertbackground=C["accent"],
                       highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"], font=(self.ui, 9))
        hint = tk.Label(self.statusbar, text="Enter 저장 · Esc 취소", bg=C["bg"], fg=C["muted"], font=(self.ui, 8), padx=8)
        self.tagbtn.pack_forget()
        ent.pack(side="left", pady=2, ipady=1)
        hint.pack(side="left")
        self.tag_edit = (ent, hint)
        ent.focus_set()
        ent.icursor("end")
        ent.bind("<Return>", lambda e: self.finish_tags(True))
        ent.bind("<KP_Enter>", lambda e: self.finish_tags(True))
        ent.bind("<Escape>", lambda e: self.finish_tags(False))
        ent.bind("<FocusOut>", lambda e: self.finish_tags(True))

    def finish_tags(self, save):
        if not self.tag_edit:
            return
        ent, hint = self.tag_edit
        self.tag_edit = None          # FocusOut 이 되풀이로 불리지 않게 먼저 비운다
        value = ent.get()
        ent.destroy()
        hint.destroy()
        self.tagbtn.pack(side="left")
        if save and self.cur:
            self.apply_tags(value)
        self.update_status()
        if self.cur:
            (self.text if self.mode != "view" else self.lst).focus_set()

    def apply_tags(self, value):
        """입력칸의 태그로 노트를 고친다. 글 맨 아래의 '태그: #a #b' 줄에 적는다(없으면 만든다).
        본문 속 #해시태그나 머리말 tags 로 생긴 태그는 여기서 지울 수 없어서(글 자체를 고쳐야 한다) 알려 준다."""
        if self.doc_open:
            return self.apply_doc_tags(value)
        want = []
        for t in re.split(r"[,\s]+", value):
            t = t.strip().lstrip("#").strip()
            if t and len(t) <= 30 and not re.search(r"[\[\]()/<>]", t) and t not in want:
                want.append(t)
        T = self.text
        body = T.get("1.0", "end-1c")
        have = note_tags(body)
        off = len(body) - len(body_after_fm(body))   # 머리말의 'tags:' 줄을 '태그:' 줄로 착각해 건드리지 않게 머리말 뒤부터만 본다
        on_line = line_tags(body[off:])
        removed = have - set(want)
        stuck = sorted(t for t in removed if t not in on_line)       # 줄에 없는 태그는 지울 수 없다
        keep = [t for t in on_line if t not in removed]
        new_line = keep + [t for t in want if t not in have]
        if set(new_line) == set(on_line):
            if stuck:
                self.status.config(text="본문에 직접 쓴 #태그는 여기서 못 지웁니다: " + " ".join("#" + t for t in stuck))
            return
        line = "태그: " + " ".join("#" + t for t in new_line) if new_line else ""
        T.edit_separator()
        spans = [(m.start() + off, m.end() + off) for m in TAG_LINE.finditer(body[off:])]
        if spans:
            for k, (a, b) in reversed(list(enumerate(spans))):
                if k == 0 and line:
                    T.delete(f"1.0+{a}c", f"1.0+{b}c")
                    T.insert(f"1.0+{a}c", line)
                else:   # 둘째 줄부터(또는 태그가 없어졌으면 첫 줄도) 줄째로 지운다
                    end = b + 1 if b < len(body) else b
                    T.delete(f"1.0+{a}c", f"1.0+{end}c")
        else:
            tail = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
            T.insert("end-1c", f"{tail}{line}\n")
        T.edit_separator()
        self.dirty = True
        self.flush()                                                  # 바로 저장하고 목록·사이드바·상태 줄을 갱신
        if stuck:
            self.status.config(text="태그를 저장했습니다. 본문에 직접 쓴 #태그는 못 지웁니다: " + " ".join("#" + t for t in stuck))
        else:
            self.update_status("태그 저장됨")

    # ------------------------------------------------------------ 태그 목록: 우클릭으로 추가·이름 바꾸기·삭제
    def on_tag_menu(self, e):
        """태그 목록 우클릭: 이름 변경 · 삭제(둘 다 그 태그가 든 모든 노트에서). Ctrl/Shift+클릭으로 여러 개를 골랐으면 그 태그들 모두"""
        row = self.tagtree.identify_row(e.y)
        if not row:
            return
        if row not in self.tagtree.selection():   # 고른 태그들 밖을 누르면 그 태그 하나만 고른다
            self.tagtree.selection_set(row)
        tags = [self.tag_keys[int(i[2:])] for i in self.tagtree.selection()]
        m = tk.Menu(self.root, tearoff=0)
        if len(tags) == 1:
            m.add_command(label="태그 이름 변경…", command=lambda: self.tag_rename(tags))
            m.add_command(label="태그 삭제…", command=lambda: self.tag_delete(tags))
        else:
            m.add_command(label=f"태그 {len(tags)}개를 하나의 이름으로 바꾸기(합치기)…", command=lambda: self.tag_rename(tags))
            m.add_command(label=f"태그 {len(tags)}개 삭제…", command=lambda: self.tag_delete(tags))
        m.tk_popup(e.x_root, e.y_root)
        return "break"

    def apply_doc_tags(self, value):
        """가져온 파일의 태그: 원본은 건드리지 않고 앱의 DB 에만 적는다(입력칸의 태그가 곧 전체 태그)"""
        n = self.cur
        want = [t for t in (clean_tag_name(x) for x in re.split(r"[,\s]+", value)) if t]
        want = list(dict.fromkeys(want))
        if set(want) != set(n.get("tags", ())):
            self.docs.set_annot(n["path"], tags=want)
            n["tags"] = set(want)
            self.reload_tags()
            self.refresh(keep_page=True)
            self.status.config(text="태그를 저장했습니다 (원본 파일은 그대로)")
        self.update_status()

    def edit_memo(self):
        """가져온 파일에 메모를 붙인다: 앱의 DB 에만 저장되고 검색에도 잡힌다(원본 파일은 그대로)"""
        n = self.cur
        if not (self.doc_open and n):
            return
        top = self.tool_window("메모 — " + n["title"], "520x340")
        tk.Label(top, text="이 파일에 붙이는 메모입니다. 원본 파일은 건드리지 않고 앱의 DB 에만 저장되며, 검색에도 잡힙니다.",
                 bg=C["bg"], fg=C["muted"], font=(self.ui, 9), anchor="w", justify="left", wraplength=480, padx=16, pady=10).pack(fill="x")
        btns = tk.Frame(top, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        box = tk.Text(top, wrap="word", font=(self.ui, 10), bg=C["panel"], fg=C["text"], insertbackground=C["accent"], relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"], padx=10, pady=8, undo=True)
        box.pack(fill="both", expand=True, padx=16)
        box.insert("1.0", n.get("memo", ""))
        box.focus_set()

        def save():
            memo = box.get("1.0", "end-1c").strip()
            self.docs.set_annot(n["path"], memo=memo)
            n["memo"] = memo
            top.destroy()
            self.refresh(keep_page=True)
            if self.cur is n:
                self.show_doc(n, native=self.pv_active)
        Btn(btns, "저장", save, kind="primary", bold=True, padx=22, pady=5).pack(side="right")
        Btn(btns, "취소", top.destroy, padx=14, pady=5).pack(side="right", padx=8)

    def tag_new(self, targets):
        """노트 목록에서 고른 노트(들)에 태그를 붙인다(공백·쉼표로 여러 개 가능)"""
        who = f"노트 {len(targets)}개" if len(targets) > 1 else "이 노트"
        name = simpledialog.askstring("태그 추가", f"{who}에 추가할 태그를 적으세요.\n(공백이나 쉼표로 여러 개, 앞의 # 는 없어도 됩니다)", parent=self.root)
        if name is None:
            return
        tags = [t for t in (clean_tag_name(x) for x in re.split(r"[,\s]+", name)) if t]
        if not tags:
            return messagebox.showinfo(APP, "쓸 수 있는 태그가 없습니다. (비었거나 30자를 넘거나 [ ] ( ) / < > 가 들어 있습니다)", parent=self.root)
        self.tag_add_to(targets, list(dict.fromkeys(tags)))

    def tag_add_to(self, targets, tags):
        """노트(들)에 태그들을 더한다: 글 아래의 '태그:' 줄에 적는다"""
        self.flush()
        cur_path = self.cur["path"] if self.cur else None
        done = 0
        for n in targets:
            try:
                body, changed = n.read(), False
                for t in tags:
                    body, ok = add_tag(body, t)
                    changed = changed or ok
                if changed:
                    self.store.save(n["path"], body, versioned=True, force=True, ev="tags")
                    done += 1
            except OSError as ex:
                return messagebox.showerror(APP, f"태그를 더하지 못했습니다.\n{ex}", parent=self.root)
        self.after_tag_change(cur_path)
        self.status.config(text=f"태그 {' '.join('#' + t for t in tags)} 를 노트 {done}개에 더했습니다"
                                + ("" if done == len(targets) else f" (나머지 {len(targets) - done}개는 이미 있음)"))

    def tag_rename(self, tags):
        """tags(하나 이상)를 모두 새 이름 하나로 바꾼다. 여러 개를 골랐으면 그 이름으로 합쳐진다"""
        if len(tags) == 1:
            title, ask, suggest = "태그 이름 바꾸기", f"'{tags[0]}' 의 새 이름 (공백은 _ 로 바뀝니다):", re.sub(r"\s+", "_", tags[0])
        else:
            title, suggest = "태그 합치기", re.sub(r"\s+", "_", tags[0])
            ask = f"선택한 태그 {len(tags)}개({', '.join(tags[:4])}{' …' if len(tags) > 4 else ''})를\n모두 이 이름 하나로 바꿉니다 (공백은 _ 로 바뀝니다):"
        name = simpledialog.askstring(title, ask, initialvalue=suggest, parent=self.root)
        if name is None:
            return
        new = clean_tag_name(name)
        if not new:
            return messagebox.showinfo(APP, "쓸 수 없는 이름입니다. (비었거나 30자를 넘거나 [ ] ( ) / < > , 가 들어 있습니다)", parent=self.root)
        if tags == [new]:
            return
        self.tag_apply(tags, new)

    def tag_delete(self, tags):
        self.tag_apply(tags, None)

    def tag_apply(self, tags, new):
        """태그들(tags)을 가진 모든 노트에서 new 로 바꾸거나(None 이면 지우고) 미리 몇 곳이 바뀌는지 보여 준 뒤 적용한다"""
        self.flush()
        want = set(tags)
        targets = [n for n in self.all_notes if want & n["tags"]]
        names = ", ".join(f"'{t}'" for t in tags[:5]) + (f" 외 {len(tags) - 5}개" if len(tags) > 5 else "")

        def scan(prog, cancel):
            out, total = [], {"fm": 0, "line": 0, "inline": 0, "stuck": 0}
            for i, n in enumerate(targets):
                if cancel():
                    return None
                if i % 50 == 0:
                    prog(i, len(targets))
                body = orig = n.read()
                for t in tags:
                    if t == new:
                        continue
                    body, c = edit_tag(body, t, new)
                    for k in total:
                        total[k] += c[k]
                if body != orig:
                    out.append((n, body))
            return out, total

        def confirm(res):
            if res is None:
                return
            items, c = res
            dcount = self.docs.tag_use_count(tags)   # 가져온 파일에 붙인 같은 태그(원본은 그대로, 앱의 DB 만 바뀐다)
            if not items and not dcount:
                return messagebox.showinfo(APP, "바꿀 곳이 없습니다." + (f"\n(본문 속 #태그 {c['stuck']}곳은 이 이름으로 바꿀 수 없습니다)" if c["stuck"] else ""), parent=self.root)
            parts = [f"{label} {c[k]}곳" for k, label in (("fm", "머리말"), ("line", "태그 줄"), ("inline", "본문 #태그")) if c[k]]
            what = (f"{names} → '{new}' 로 " + ("합칩니다" if len(tags) > 1 else "바꿉니다")) if new else f"{names} 를 지웁니다"
            extra = ""
            if new is None and c["inline"]:
                extra += "\n본문 속 #태그는 글에서 그 글자가 지워집니다."
            if c["stuck"]:
                extra += f"\n본문 속 #태그 {c['stuck']}곳은 '{new}' 가 본문 태그로 쓸 수 없는 이름이라 그대로 남습니다."
            if dcount:
                parts.append(f"가져온 파일 {dcount:,}개")
            if not messagebox.askyesno(APP, f"{what}.\n\n노트 {len(items):,}개 ({', '.join(parts)}){extra}\n\n"
                                            "이전 내용은 노트 버전으로 남고, 수정 시각은 바뀌지 않습니다. 계속할까요?", parent=self.root):
                return
            self.checkpoint("태그 정리 전", lambda: self.tag_write(items, tags, new)) if len(items) >= 5 else self.tag_write(items, tags, new)
        self.run_task("태그 확인", scan, confirm, text="태그가 든 노트를 확인하는 중…")

    def tag_write(self, items, tags, new):
        cur_path = self.cur["path"] if self.cur else None
        top = self.tool_window("태그 바꾸는 중", "420x110", native=True)
        msg = tk.Label(top, text="", bg=C["bg"], fg=C["text"], font=(self.ui, 10), pady=24)
        msg.pack()
        top.protocol("WM_DELETE_WINDOW", lambda: None)
        done = 0
        for i, (n, body) in enumerate(items):
            if i % 10 == 0:
                msg.config(text=f"노트의 태그를 바꾸는 중… {i:,} / {len(items):,}")
                top.update()
            try:   # 수정 시각은 그대로 두고(touch=False), 이전 내용은 버전으로 남긴다(force)
                self.store.save(n["path"], body, versioned=True, force=True, touch=False, ev="tags")
                done += 1
            except OSError:
                pass
        top.destroy()
        dn = self.docs.rename_tags(tags, new)   # 가져온 파일의 태그
        if self.tag in tags:
            self.tag = new
        self.after_tag_change(cur_path)
        messagebox.showinfo(APP, f"노트 {done:,}개" + (f", 가져온 파일 {dn:,}개" if dn else "") + "의 태그를 " + ("바꿨습니다." if new else "지웠습니다."), parent=self.root)

    def after_tag_change(self, cur_path):
        """태그를 바꾼 뒤: 노트를 다시 읽고 사이드바·목록·열려 있던 노트를 갱신한다"""
        self.reload_notes()
        self.reload_tags()
        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
        if n:
            self.open_note(n, record=False)   # 바뀐 글을 다시 읽어 와서 낡은 내용으로 덮어쓰지 않게

    def commit_title(self):
        if not self.cur or self.doc_open:
            return
        new = self.title_var.get().strip()
        if new == self.cur["title"]:
            return
        self.flush()
        try:
            title, path = self.store.rename(self.cur["path"], new)
        except OSError as ex:
            self.title_var.set(self.cur["title"])
            return messagebox.showerror(APP, f"제목을 바꾸지 못했습니다.\n{ex}")
        self.title_var.set(title)
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
            return messagebox.showerror(APP, f"노트를 만들지 못했습니다.\n{ex}")
        self.close_note()
        self.reload_notes()
        n = next((x for x in self.notes if x["path"] == made["path"]), None)
        if n:
            self.open_note(n)
            self.title_entry.focus_set()
            self.title_entry.select_range(0, "end")

    def delete_note(self):
        if self.doc_open:
            return messagebox.showinfo(APP, "가져온 파일은 여기서 지우지 않습니다(원본 파일은 그대로 둡니다).\n목록에서 빼려면 노트북 칸의 가져온 폴더를 우클릭하세요.", parent=self.root)
        if not self.cur or not messagebox.askyesno(APP, f"이 노트를 휴지통으로 보낼까요?\n({self.store.trash_days}일 동안 보관하며 파일 → 휴지통에서 복원할 수 있습니다)", parent=self.root):
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

    # ------------------------------------------------------------ 보기 모드·렌더링 (위키나루)
    # ------------------------------------------------------------ 문서 안에서 찾기
    def find_target(self):
        """찾은 곳을 옮겨 다니는 칸: 렌더링만 볼 때는 렌더링 화면, 그 밖에는 편집 칸(둘 다 보이면 양쪽에 강조하고 편집 칸으로 옮긴다)"""
        return self.view if self.mode == "view" and not self.doc_open else self.text

    def show_find(self):
        if not self.cur:
            return
        if self.doc_open and self.pv_active:   # 윈도 미리보기 안에서는 앱이 찾을 수 없으니, 색인해 둔 글로 바꿔서 찾는다
            self.show_doc(self.cur, native=False)
        for w in (self.text, self.view):
            w.tag_configure("find", background=C["mark"], foreground=C["text"])
            w.tag_configure("findcur", background="#ff9f43", foreground="#000000")
        if not self.findbar.winfo_ismapped():
            self.findbar.pack(side="top", fill="x", before=self.body)
        try:   # 편집 칸에서 한 줄을 골라 둔 채 눌렀으면 그 글자로 바로 찾는다
            sel = self.text.get("sel.first", "sel.last") if self.focus_in_text() else ""
        except tk.TclError:
            sel = ""
        if sel and "\n" not in sel and len(sel) <= 80:
            self.find_var.set(sel)
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")
        self.find_run()

    def focus_in_text(self):
        return self.root.focus_get() is self.text

    def hide_find(self, focus=True):
        if not self.findbar.winfo_ismapped():
            return
        self.findbar.pack_forget()
        for w in (self.text, self.view):
            w.tag_remove("find", "1.0", "end")
            w.tag_remove("findcur", "1.0", "end")
        self.find_hits, self.find_i = [], -1
        if focus and self.cur:
            self.find_target().focus_set()

    def find_matches(self, w, needle, limit=5000):
        out, pos = [], "1.0"
        n = tk.IntVar()
        while len(out) < limit:
            pos = w.search(needle, pos, "end", nocase=True, count=n)
            if not pos:
                break
            n_chars = max(1, n.get())
            out.append((pos, f"{pos}+{n_chars}c"))
            pos = f"{pos}+{n_chars}c"
        return out

    def find_run(self, goto=True):
        """찾을 글자가 바뀌었거나 내용이 바뀌면 일치하는 곳을 모두 강조하고, 지금 위치 다음(없으면 처음)의 것으로 이동한다"""
        if not self.findbar.winfo_ismapped():
            return
        for w in (self.text, self.view):
            w.tag_remove("find", "1.0", "end")
            w.tag_remove("findcur", "1.0", "end")
        needle = self.find_var.get()
        prim = self.find_target()
        old_i = self.find_i
        self.find_hits, self.find_i = [], -1
        if not needle:
            return self.find_count.config(text="", fg=C["muted"])
        shown = [self.text] if self.mode == "edit" else ([self.view] if self.mode == "view" else [self.text, self.view])
        for w in shown:
            hits = self.find_matches(w, needle)
            for a, b in hits:
                w.tag_add("find", a, b)
            if w is prim:
                self.find_hits = hits
        if not self.find_hits:
            return self.find_count.config(text="없음", fg=C["danger"])
        if goto:   # 편집 칸이면 커서 다음의 것, 렌더링 화면이면 처음 것
            at = prim.index("insert") if prim is self.text else "1.0"
            i = next((k for k, (a, _) in enumerate(self.find_hits) if prim.compare(a, ">=", at)), 0)
        else:
            i = min(max(old_i, 0), len(self.find_hits) - 1)
        self.find_goto(i, move=goto)

    def find_goto(self, i, move=True):
        prim = self.find_target()
        self.find_i = i
        a, b = self.find_hits[i]
        prim.tag_remove("findcur", "1.0", "end")
        prim.tag_add("findcur", a, b)
        prim.tag_raise("findcur")
        if move:
            prim.see(a)
            if prim is self.text:
                prim.mark_set("insert", a)
        self.find_count.config(text=f"{i + 1} / {len(self.find_hits):,}", fg=C["muted"])

    def find_step(self, d):
        if not self.find_hits:
            return self.find_run()
        self.find_goto((self.find_i + d) % len(self.find_hits))

    def find_later(self):
        """내용이 바뀌는 중(타이핑)에는 잠시 뒤에 한 번만 다시 찾는다"""
        if not self.findbar.winfo_ismapped():
            return
        if self.find_job:
            self.root.after_cancel(self.find_job)
        self.find_job = self.root.after(300, lambda: self.find_run(goto=False))

    def on_ctrl_f(self, e=None):
        """Ctrl+F: 노트가 열려 있으면 그 문서에서 찾기, 아니면(또는 목록 검색칸에 있으면) 모든 노트에서 검색. 모든 노트 검색은 Ctrl+Shift+F"""
        if self.cur and self.root.focus_get() is not self.search_entry:
            return self.show_find()
        self.focus_search()

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

    def apply_layout(self, m):
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
        if not self.cur or self.mode == "edit" or self.doc_open:
            return
        title = self.title_var.get()
        try:
            # 클리퍼가 맨 위에 적는 '원본: <주소>' 줄은 렌더링 화면에서만 숨긴다(문서 정보의 URL 은 이 줄에서 읽는다)
            src = SOURCE_LINE.sub("", self.text.get("1.0", "end-1c"), count=1)
            doc = wikiconv.parse(src, bulk.SYNTAX[FMT], title)
            segs = preview.layout(doc)
        except Exception as ex:  # noqa: BLE001  (읽기 도구가 못 읽은 글도 편집은 계속할 수 있게)
            return self.status.config(text="렌더링 오류: " + str(ex))
        self.draw_view(segs)

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
        self.img_w_used = self.img_avail()
        self.has_imgs = any(extra and extra[0] == "img" for _, _, extra in segs)
        top = v.yview()[0]
        v.config(state="normal")
        v.delete("1.0", "end")
        self.links.clear()
        self.photos.clear()
        self.img_files.clear()
        for t, tags, extra in segs:
            tg = list(tags)
            if "b" in tg and "i" in tg:
                tg.append("bi")
            if extra and extra[0] == "link":
                key = "L%d" % len(self.links)
                self.links[key] = extra[1:]
                tg.append(key)
            if extra and extra[0] == "img" and self.show_image(extra[1], extra[3] if len(extra) > 3 else 0):
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
        v.config(state="disabled")
        v.yview_moveto(top)
        self.find_later()   # 다시 그렸으면 찾은 곳의 강조도 다시 한다

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
            m.add_command(label="그림 파일 위치 열기", command=lambda: self.reveal_file(path), state="normal" if path else "disabled")
            m.add_separator()
        m.add_command(label="복사", command=lambda: v.event_generate("<<Copy>>"), state="normal" if v.tag_ranges("sel") else "disabled")
        m.add_command(label="모두 선택", command=lambda: v.tag_add("sel", "1.0", "end-1c"))
        m.tk_popup(e.x_root, e.y_root)

    def on_text_menu(self, e):
        t = self.text
        t.focus_set()
        has_sel = bool(t.tag_ranges("sel"))
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="실행 취소", command=lambda: t.event_generate("<<Undo>>"))
        m.add_command(label="다시 실행", command=lambda: t.event_generate("<<Redo>>"))
        m.add_separator()
        m.add_command(label="잘라내기", command=lambda: t.event_generate("<<Cut>>"), state="normal" if has_sel else "disabled")
        m.add_command(label="복사", command=lambda: t.event_generate("<<Copy>>"), state="normal" if has_sel else "disabled")
        m.add_command(label="붙여넣기", command=lambda: t.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label="모두 선택", command=lambda: t.tag_add("sel", "1.0", "end-1c"))
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
        if sys.platform == "win32" and st.read_config().get("video_open", "app") == "app" and wikiconv.tree.youtube_id(url):
            for exe in (os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
                if os.path.isfile(exe):
                    subprocess.Popen([exe, f"--app={url}", "--window-size=980,640"])
                    return
        webbrowser.open(url)

    def follow(self, kind, target):
        if kind == "url":
            if re.match(r"(?i)^(https?|ftp|mailto):", target):
                self.open_url(target)
            return
        # 위키 링크 [[문서]] → 같은 노트북의 같은 이름 노트
        want = target.split("#")[0].strip().lower()
        pool = [n for n in self.all_notes if n["title"].lower() == want]
        pool.sort(key=lambda n: n["nb"] != (self.cur["nb"] if self.cur else ""))
        if pool:
            path = pool[0]["path"]
            if pool[0] not in self.notes:
                self.nb = ALL
                self.reload_notes()
            return self.open_note(next(n for n in self.notes if n["path"] == path))
        if messagebox.askyesno(APP, f"\"{target}\" 노트가 없습니다. 새로 만들까요?", parent=self.root):
            nb = self.cur["nb"] if self.cur else ""
            made = self.store.create_note(nb, target.split("#")[0].strip() or "제목 없음")
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
            self.status.config(text=f"웹 클리퍼가 {self.port}번 포트로 열렸습니다({clipserver.DEFAULT_PORT}번을 다른 프로그램이 쓰는 중). 비면 자동으로 {clipserver.DEFAULT_PORT}번으로 옮깁니다.")

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
        self.status.config(text=f"웹 클리퍼가 {port}번 포트로 돌아왔습니다.")

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
            self.status.config(text="웹 클리퍼에서 새 노트가 들어왔습니다 " + time.strftime("%H:%M:%S"))
        self.clip_tick = getattr(self, "clip_tick", 0) + 1
        if self.clip_tick % 8 == 0:   # 약 5초마다
            self.retake_default_port()
        self.root.after(600, self.poll_clip)

    # ------------------------------------------------------------ 노트 속성 (조플린의 ⓘ)
    def show_properties(self):
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, "먼저 노트를 여세요." if not self.cur else "가져온 파일에는 노트 속성이 없습니다.", parent=self.root)
        self.flush()
        n = self.cur
        meta = st.parse_meta(n["body"])
        top = tk.Toplevel(self.root)
        top.title("노트 속성")
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.resizable(False, False)
        top.geometry(f"+{self.root.winfo_x() + 160}+{self.root.winfo_y() + 90}")
        f = tk.Frame(top, bg=C["bg"], padx=26, pady=20)
        f.pack()
        tk.Label(f, text="노트 속성", bg=C["bg"], fg=C["text"], font=(self.ui, 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))  # noqa: E731
        state = {"r": 1}

        def row(label, value="", btn=None, link=None, copyable=False):
            r = state["r"]
            state["r"] += 1
            tk.Label(f, text=label, bg=C["bg"], fg=C["muted"], font=(self.ui, 10, "bold"), anchor="nw", width=9).grid(row=r, column=0, sticky="nw", pady=5)
            if copyable:
                var = tk.StringVar(value=value)
                tk.Entry(f, textvariable=var, state="readonly", width=46, relief="flat", bd=0, bg=C["panel"], readonlybackground=C["panel"],
                         fg=C["text"], highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 9)).grid(row=r, column=1, sticky="w", pady=4, ipady=3)
            else:
                v = tk.Label(f, text=value or "—", bg=C["bg"], fg=C["accent"] if link else C["text"], anchor="w", justify="left",
                             wraplength=360, font=(self.ui, 10, "underline") if link else (self.ui, 10), cursor="hand2" if link else "")
                v.grid(row=r, column=1, sticky="w", pady=5)
                if link:
                    v.bind("<Button-1>", lambda e: link())
            if btn:
                Btn(f, btn[0], btn[1], padx=8, pady=1).grid(row=r, column=2, sticky="w", padx=(8, 0))

        def edit_time(kind):
            label = "갱신됨" if kind == "updated" else "생성됨"
            cur_t = n["mtime"] if kind == "updated" else n.get("ctime", n["mtime"])
            ans = simpledialog.askstring(f"{label} 변경", "형식: 2023-03-21 20:24:00", initialvalue=fmt(cur_t), parent=top)
            if not ans:
                return
            t = st.parse_time(ans)
            if t is None:
                return messagebox.showerror(APP, "날짜를 읽지 못했습니다. 예: 2023-03-21 20:24:00", parent=top)
            try:
                self.store.set_dates(n["path"], updated=t if kind == "updated" else None, created=t if kind == "created" else None)
            except (OSError, ValueError) as ex:
                return messagebox.showerror(APP, str(ex), parent=top)
            path = n["path"]
            top.destroy()
            self.reload_notes()
            again = next((x for x in self.notes if x["path"] == path), None)
            if again:
                self.open_note(again, record=False)
                self.show_properties()

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        url = st.note_source(n["body"], meta)
        nvers = len(self.store.versions(n["path"]))
        row("제목", n["title"])
        row("위치", self.nb_label(n["nb"]))
        row("파일", n["path"], ("복사", lambda: copy(n["path"])), copyable=True)
        row("갱신됨", fmt(n["mtime"]), ("✎", lambda: edit_time("updated")))
        row("생성됨", fmt(n.get("ctime", n["mtime"])), ("✎", lambda: edit_time("created")) if meta["created"] else None)
        if meta["fm"] and (meta["updated"] or meta["created"]):
            row("날짜 출처", "노트 머리말(front matter)의 날짜")
        else:
            row("날짜 출처", "파일의 수정·생성 시각")
        row("URL", url, link=(lambda: webbrowser.open(url)) if url else None)
        if meta["author"]:
            row("작성자", meta["author"])
        tags = sorted(n.get("tags", ()))
        row("태그", "   ".join("# " + t for t in tags))
        text = n["body"]
        row("크기", f"{len(text):,}자 · {text.count(chr(10)) + 1:,}줄")
        row("노트 역사", f"이전 버전 {nvers}개 보기" if nvers else "저장된 이전 버전 없음",
            link=(lambda: (top.destroy(), self.show_versions())) if nvers else None)
        row("마크업", "Markdown")
        bf = tk.Frame(f, bg=C["bg"])
        bf.grid(row=state["r"], column=0, columnspan=3, sticky="e", pady=(16, 0))
        Btn(bf, "닫기", top.destroy, kind="primary", padx=22, pady=5).pack()
        top.bind("<Escape>", lambda e: top.destroy())

    # ------------------------------------------------------------ 노트 버전
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
        self.update_status("복원됨 " + time.strftime("%H:%M:%S"))

    def show_versions(self):
        """편집 > 노트 버전…: 이 노트의 이전 내용을 보고, 골라서 되돌린다."""
        if not self.cur or self.doc_open:
            return messagebox.showinfo(APP, "먼저 노트를 여세요." if not self.cur else "가져온 파일에는 노트 버전이 없습니다.", parent=self.root)
        self.flush()
        n = self.cur
        top = tk.Toplevel(self.root)
        top.title("노트 버전 — " + n["title"])
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.geometry(f"860x540+{self.root.winfo_x() + 90}+{self.root.winfo_y() + 60}")
        top.minsize(640, 400)
        left = tk.Frame(top, bg=C["panel"], width=250)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="저장된 버전", bg=C["panel"], fg=C["text"], font=(self.ui, 11, "bold"), anchor="w", padx=16, pady=14).pack(fill="x")
        lb = tk.Listbox(left, bg=C["panel"], fg=C["text"], relief="flat", bd=0, highlightthickness=0, activestyle="none",
                        selectbackground=C["soft"], selectforeground=C["accent"], font=(self.ui, 10), exportselection=False)
        lb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        right = tk.Frame(top, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        info = tk.Label(right, text="", anchor="w", bg=C["bg"], fg=C["muted"], font=(self.ui, 9), padx=16, pady=10, justify="left")
        info.pack(fill="x")
        btns = tk.Frame(right, bg=C["bg"])
        btns.pack(side="bottom", fill="x", padx=16, pady=12)
        pv = tk.Text(right, wrap="word", state="disabled", relief="flat", bd=0, highlightthickness=0, bg=C["panel"], fg=C["text"],
                     font=(self.mono, 10), padx=14, pady=10)
        pv.pack(fill="both", expand=True, padx=16)
        vs = []

        def fill():
            nonlocal vs
            vs = self.store.versions(n["path"])
            lb.delete(0, "end")
            for ts, size, _ in vs:
                lb.insert("end", time.strftime("%Y.%m.%d  %H:%M:%S", time.localtime(ts)) + f"   {size:,}B")
            if vs:
                lb.selection_set(0)
                show(None)
            else:
                v = st.version_settings()
                info.config(text="저장된 버전이 없습니다." if v["keep"] else "노트 버전 기록이 꺼져 있습니다. 설정 > 노트 버전 설정에서 켤 수 있습니다.")
                pv.config(state="normal")
                pv.delete("1.0", "end")
                pv.config(state="disabled")

        def show(e):
            sel = lb.curselection()
            if not sel:
                return
            ts, size, fp = vs[sel[0]]
            text = self.store.read_version(fp)
            info.config(text=f"{time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(ts))} 의 내용  ·  지금 {len(n['body']):,}자 / 이 버전 {len(text):,}자")
            pv.config(state="normal", wrap="none" if max((len(x) for x in text.split("\n")), default=0) > 20000 else "word")
            pv.delete("1.0", "end")
            pv.insert("1.0", text[:200000] + ("\n\n… (이하 생략)" if len(text) > 200000 else ""))
            pv.config(state="disabled")

        def restore():
            sel = lb.curselection()
            if not sel:
                return
            ts, _, fp = vs[sel[0]]
            if not messagebox.askyesno(APP, f"{time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(ts))} 버전으로 되돌릴까요?\n"
                                            "(지금 내용은 새 버전으로 남겨 두므로 다시 돌아올 수 있습니다)", parent=top):
                return
            body = self.store.read_version(fp)
            self.store.snapshot(n["path"], body, max(1, st.version_settings()["count"]), 0)
            self.apply_body(body)
            top.destroy()

        def delete():
            sel = lb.curselection()
            if sel and messagebox.askyesno(APP, "이 버전을 삭제할까요?", parent=top):
                self.store.delete_version(vs[sel[0]][2])
                fill()

        lb.bind("<<ListboxSelect>>", show)
        Btn(btns, "닫기", top.destroy, padx=16).pack(side="right")
        Btn(btns, "삭제", delete, kind="danger", padx=14).pack(side="right", padx=6)
        Btn(btns, "이 버전으로 되돌리기", restore, kind="primary", bold=True, padx=16).pack(side="right")
        fill()

    # ------------------------------------------------------------ 테마
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

    def set_theme(self, name, accent="keep"):
        old = st.read_config().get("theme", {})
        acc = old.get("accent") if accent == "keep" else accent
        st.write_config(theme={"name": name, "accent": acc})
        apply_theme(name, acc)
        self.rebuild_ui()
        self.show_options("theme")

    # ------------------------------------------------------------ 옵션 (설정 > 옵션: 왼쪽 탭 + 오른쪽 내용)
    def show_options(self, tab="general"):
        if getattr(self, "opt", None) and self.opt.winfo_exists():
            self.opt.destroy()
        top = self.opt = tk.Toplevel(self.root)
        top.title("옵션")
        top.configure(bg=C["bg"])
        top.transient(self.root)
        top.geometry(f"720x640+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 50}")
        top.minsize(640, 600)
        nav = tk.Frame(top, bg=C["panel"], width=170)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text="옵션", bg=C["panel"], fg=C["text"], font=(self.ui, 12, "bold"), anchor="w", padx=18, pady=16).pack(fill="x")
        content = tk.Frame(top, bg=C["bg"], padx=28, pady=22)
        content.pack(side="left", fill="both", expand=True)
        foot = tk.Frame(top, bg=C["bg"])
        tabs = {}

        def lab(p, t, **k):
            return tk.Label(p, text=t, bg=C["bg"], fg=k.pop("fg", C["text"]), anchor="w", justify="left",
                            font=k.pop("font", (self.ui, 10)), **k)

        def title(p, t, sub=""):
            lab(p, t, font=(self.ui, 14, "bold")).pack(anchor="w")
            if sub:
                lab(p, sub, fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(2, 14))

        def hr(p):
            tk.Frame(p, height=1, bg=C["line"]).pack(fill="x", pady=14)

        def field(p, label, var, width, button=None):
            row = tk.Frame(p, bg=C["bg"])
            row.pack(fill="x", pady=3)
            lab(row, label, width=8).pack(side="left")
            tk.Entry(row, textvariable=var, width=width, state="readonly", relief="flat", bd=0, bg=C["panel"],
                     readonlybackground=C["panel"], fg=C["text"], highlightthickness=1, highlightbackground=C["line"],
                     font=(self.ui, 10)).pack(side="left", ipady=4, fill="x", expand=button is None)
            if button:
                Btn(row, button[0], button[1], padx=10, pady=3).pack(side="left", padx=6)

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        def general(p):
            title(p, "일반", "노트를 저장하는 곳과 시작할 때의 보기를 정합니다.")
            lab(p, "노트와 그림을 저장하는 폴더는 설정 > 폴더 설정에서 바꿉니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")
            hr(p)
            lab(p, "편집기 보기", font=(self.ui, 10, "bold")).pack(anchor="w")
            for key, label in (("edit", "마크다운만"), ("split", "마크다운 + 렌더링 (분할)"), ("view", "렌더링만")):
                tk.Radiobutton(p, text=label, value=key, variable=self.v_mode, command=lambda k=key: self.set_mode(k),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            hr(p)
            lab(p, "창의 닫기(X) 버튼", font=(self.ui, 10, "bold")).pack(anchor="w")
            ca = tk.StringVar(value=self.close_action())
            for key, label in (("tray", "작업표시줄 알림 영역(트레이)으로 보내기 — 앱은 계속 실행됩니다"), ("quit", "바로 종료")):
                tk.Radiobutton(p, text=label, value=key, variable=ca, command=lambda: st.write_config(closeAction=ca.get()),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            lab(p, "트레이 아이콘을 누르면 창이 다시 열리고, 우클릭 → 종료로 끕니다. 파일 → 종료(와 트레이의 종료)는 언제나 바로 끕니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=500).pack(anchor="w", pady=(2, 0))
            hr(p)
            lab(p, "화면 구성", font=(self.ui, 10, "bold")).pack(anchor="w")
            for key, label in (("notebooks", "노트북 보기"), ("tags", "태그 보기"), ("list", "노트 목록 보기"), ("syntax", "문법 해설 보기")):
                tk.Checkbutton(p, text=label, variable=self.v[key], command=self.on_view_toggle, bg=C["bg"],
                               activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")

        def clipper(p):
            title(p, "웹 클리퍼", "조플린 클리퍼 플러스(크롬 확장)로 웹 페이지를 이 앱에 바로 저장합니다.")
            on = tk.BooleanVar(value=bool(st.read_config().get("clipEnabled", True)))
            status = lab(p, "", fg=C["muted"], font=(self.ui, 9))
            port_var, tok_var = tk.StringVar(), tk.StringVar(value=st.clipper_token())

            def refresh_state():
                if self.srv:
                    status.config(text=f"실행 중 — 127.0.0.1:{self.port} (이 컴퓨터에서만 접속됩니다)", fg="#15803d")
                elif on.get():
                    status.config(text="켜져 있지만 서버를 열지 못했습니다(41184~41194 포트가 모두 사용 중).", fg=C["danger"])
                else:
                    status.config(text="꺼져 있음", fg=C["muted"])
                port_var.set(str(self.port or ""))

            def toggle():
                st.write_config(clipEnabled=bool(on.get()))
                if on.get():
                    self.start_clipper()
                else:
                    self.stop_clipper()
                refresh_state()
            tk.Checkbutton(p, text="웹 클리퍼 서비스 사용", variable=on, command=toggle, bg=C["bg"],
                           activebackground=C["bg"], font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")
            status.pack(anchor="w", pady=(2, 10))
            field(p, "포트", port_var, 10)

            def regen():
                if messagebox.askyesno("토큰 새로 만들기", "새 토큰을 만들면 크롬 확장 옵션의 토큰도 바꿔야 합니다.\n계속할까요?", parent=top):
                    tok_var.set(secrets.token_hex(24))
                    st.write_config(clipToken=tok_var.get())
            field(p, "토큰", tok_var, 50, ("복사", lambda: copy(tok_var.get())))
            Btn(p, "토큰 새로 만들기", regen, padx=10, pady=3).pack(anchor="w", padx=(64, 0), pady=(2, 0))
            hr(p)
            store_url = "https://chromewebstore.google.com/detail/joplin-clipper-plus/fbieoidncnoalmenkkpbcbomppoenfoa"
            lab(p, "크롬 웹스토어", font=(self.ui, 10, "bold")).pack(anchor="w")
            link = tk.Label(p, text=store_url, bg=C["bg"], fg=C["accent"], cursor="hand2", font=(self.ui, 9, "underline"),
                            anchor="w", justify="left", wraplength=480)
            link.pack(anchor="w", pady=(4, 0))
            link.bind("<Button-1>", lambda e: webbrowser.open(store_url))
            git_url = "https://github.com/iamtalker/joplin-clipper-plus"
            lab(p, "GitHub (소스·설치 방법)", font=(self.ui, 10, "bold")).pack(anchor="w", pady=(12, 0))
            glink = tk.Label(p, text=git_url, bg=C["bg"], fg=C["accent"], cursor="hand2", font=(self.ui, 9, "underline"), anchor="w")
            glink.pack(anchor="w", pady=(4, 0))
            glink.bind("<Button-1>", lambda e: webbrowser.open(git_url))
            refresh_state()

        def imports_tab(p):
            title(p, "가져오기", "노트 폴더 밖의 폴더에 있는 pdf·txt·mp3 등을 읽어 노트처럼 검색합니다. 원본 파일은 건드리지 않고 읽기만 합니다.")
            cfg = self.docs.cfg()
            avail = docidx.available()
            lab(p, "가져올 폴더", font=(self.ui, 10, "bold")).pack(anchor="w")
            box = tk.Frame(p, bg=C["bg"])
            box.pack(fill="x", pady=(4, 0))
            lb = tk.Listbox(box, height=5, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1, highlightbackground=C["line"],
                            selectbackground=C["soft"], selectforeground=C["text"], activestyle="none", font=(self.ui, 10), exportselection=False)
            lb.pack(fill="x", ipady=2)
            ids = []

            def fill():
                lb.delete(0, "end")
                ids.clear()
                counts = self.docs.counts()
                for f in self.docs.folders():
                    ids.append(f["id"])
                    lb.insert("end", f"{f['path']}    ({counts.get(f['id'], 0):,}개)")
            fill()

            def add():
                path = filedialog.askdirectory(title="가져올 폴더 고르기", parent=top, mustexist=True)
                if not path:
                    return
                path = os.path.normpath(path)
                r = os.path.normcase(self.store.root)
                if os.path.normcase(path) == r or os.path.normcase(path).startswith(r + os.sep) or r.startswith(os.path.normcase(path) + os.sep):
                    return messagebox.showwarning(APP, "노트 폴더와 겹치는 폴더는 가져올 수 없습니다(노트는 이미 읽고 있습니다).", parent=top)
                if not self.docs.add_folder(path):
                    return messagebox.showinfo(APP, "이미 가져온 폴더입니다.", parent=top)
                fill()
                self.after_docs_changed()
                if messagebox.askyesno(APP, "지금 이 폴더의 파일을 읽어 색인할까요?\n(파일이 많으면 처음 한 번은 오래 걸리고, 이후에는 바뀐 파일만 읽습니다)", parent=top):
                    self.scan_docs(self.docs.fid(path))

            def remove():
                sel = lb.curselection()
                if sel:
                    self.remove_doc_folder(ids[sel[0]])
                    fill()
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", pady=(8, 0))
            Btn(row, "폴더 추가…", add, padx=12, pady=3).pack(side="left")
            Btn(row, "목록에서 빼기", remove, padx=12, pady=3).pack(side="left", padx=6)
            Btn(row, "지금 다시 읽기", lambda: self.scan_docs(), padx=12, pady=3).pack(side="left")
            lab(p, "빼도 원본 파일은 그대로입니다. 앱을 켜고 잠시 뒤 바뀐 파일은 저절로 다시 읽습니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(6, 0))
            hr(p)

            lab(p, "읽을 파일 종류 (고른 확장자만 읽습니다)", font=(self.ui, 10, "bold")).pack(anchor="w")
            common = ["pdf", "txt", "md", "mp3", "docx", "pptx", "xlsx", "csv", "html", "m4a", "flac", "wav", "ogg", "log", "json"]
            chosen = {e.lower().lstrip(".") for e in cfg["exts"]}
            vars_ = {e: tk.BooleanVar(value=e in chosen) for e in common}
            extra = tk.StringVar(value=" ".join(sorted(chosen - set(common))))

            def save_exts(*_):
                exts = [e for e in common if vars_[e].get()]
                exts += [x.lower().lstrip(".") for x in re.split(r"[\s,;]+", extra.get()) if x.strip(".")]
                c = self.docs.cfg()
                c["exts"] = exts or list(docidx.DEFAULT_EXTS)
                self.docs.save_cfg(c)
            grid = tk.Frame(p, bg=C["bg"])
            grid.pack(anchor="w", pady=(6, 0))
            for i, e in enumerate(common):
                tk.Checkbutton(grid, text="." + e, variable=vars_[e], command=save_exts, bg=C["bg"], activebackground=C["bg"], selectcolor=C["bg"],
                               font=(self.ui, 10), width=7, anchor="w").grid(row=i // 5, column=i % 5, sticky="w")
            erow = tk.Frame(p, bg=C["bg"])
            erow.pack(anchor="w", pady=(6, 0))
            lab(erow, "그 밖의 확장자").pack(side="left")
            ent = tk.Entry(erow, textvariable=extra, width=24, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1,
                           highlightbackground=C["line"], insertbackground=C["accent"], font=(self.ui, 10))
            ent.pack(side="left", padx=8, ipady=3)
            ent.bind("<FocusOut>", save_exts)
            ent.bind("<Return>", save_exts)
            missing = [n for n, ok in (("pdf", "pypdf"), ("mp3", "tinytag")) if n not in avail]
            lab(p, "글을 읽는 도구가 없는 확장자는 파일 이름만 색인됩니다. 종류를 바꾼 뒤에는 '지금 다시 읽기'를 누르세요."
                + (f"\n(이 컴퓨터에는 {', '.join(missing)} 라이브러리가 없어 해당 형식은 이름만 색인됩니다)" if missing else ""),
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(6, 0))
            hr(p)

            content = tk.BooleanVar(value=cfg["content"])

            def save_content():
                c = self.docs.cfg()
                c["content"] = bool(content.get())
                self.docs.save_cfg(c)
            tk.Checkbutton(p, text="문서 안의 글도 색인 (pdf·txt·docx 본문, mp3 태그와 가사)", variable=content, command=save_content, bg=C["bg"],
                           activebackground=C["bg"], selectcolor=C["bg"], font=(self.ui, 10)).pack(anchor="w")
            lab(p, "끄면 파일 이름과 경로로만 찾습니다(빠르고 DB 가 작아집니다). 문서를 열어 둔 상태에서 Ctrl+F 로 그 문서 안에서 찾는 것은 켜든 끄든 쓸 수 있습니다.",
                fg=C["muted"], font=(self.ui, 9), wraplength=500).pack(anchor="w", pady=(2, 0))

        def versions_tab(p):
            title(p, "노트 버전", "노트를 고칠 때마다 이전 내용을 노트별로 보관해 두고, 나중에 골라서 되돌릴 수 있습니다.")
            cfg = st.read_config().get("versions", {})
            enabled = tk.BooleanVar(value=bool(cfg.get("enabled", True)))
            keep = tk.StringVar(value=str(cfg.get("keep", 10)))
            minutes = tk.StringVar(value=str(int(float(cfg.get("minutes", 1)))))

            def apply(*_):
                try:
                    k = max(1, min(200, int(keep.get())))
                except ValueError:
                    k = 10
                try:
                    m = max(0, min(1440, int(minutes.get())))
                except ValueError:
                    m = 5
                keep.set(str(k))
                minutes.set(str(m))
                st.write_config(versions={"enabled": bool(enabled.get()), "keep": k, "minutes": m})
                spin_state()

            def spin_state():
                for w in (sp1, sp2):
                    w.config(state="normal" if enabled.get() else "disabled")
            tk.Checkbutton(p, text="노트 버전 기록 사용", variable=enabled, command=apply, bg=C["bg"], activebackground=C["bg"],
                           font=(self.ui, 10), selectcolor=C["bg"]).pack(anchor="w")

            def spin(label, var, lo, hi, unit):
                row = tk.Frame(p, bg=C["bg"])
                row.pack(fill="x", pady=6)
                lab(row, label, width=18).pack(side="left")
                w = tk.Spinbox(row, from_=lo, to=hi, textvariable=var, width=6, command=apply, relief="flat", bd=0, bg=C["panel"],
                               highlightthickness=1, highlightbackground=C["line"], font=(self.ui, 10), buttonbackground=C["panel"])
                w.pack(side="left", ipady=4)
                w.bind("<Return>", apply)
                w.bind("<FocusOut>", apply)
                lab(row, unit, fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=8)
                return w
            sp1 = spin("노트당 보관 개수", keep, 1, 200, "개 (넘으면 오래된 것부터 지웁니다)")
            sp2 = spin("새 버전 간격", minutes, 0, 1440, "분 (0 = 자동 저장할 때마다)")
            spin_state()
            hr(p)
            lab(p, "버전을 만드는 때: ① 노트를 연 뒤 처음 고칠 때(그 직전 내용)  ② 그 뒤로는 '새 버전 간격'이 지난 뒤 고칠 때.\n"
                   "예) 간격 1분이면, 한 노트를 계속 고치는 동안 1분에 한 번씩 버전이 남습니다.\n"
                   "버전은 저장 폴더의 .history 폴더에 노트별로 보관됩니다(노트북으로 보이지 않습니다).\n"
                   "노트의 이름을 바꾸거나 다른 노트북으로 옮겨도 버전 기록이 따라갑니다.\n"
                   "보기: 편집 > 노트 버전…  또는 노트 목록에서 우클릭", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")
            Btn(p, "이 노트의 버전 보기", lambda: (top.destroy(), self.show_versions()), padx=12, pady=4).pack(anchor="w", pady=(14, 0))

        def theme_tab(p):
            title(p, "테마·색상", "노트 전체의 색을 고릅니다. 누르면 바로 적용됩니다.")
            cfg = st.read_config().get("theme", {})
            cur_name = cfg.get("name", DEFAULT_THEME)
            cur_acc = cfg.get("accent")
            grid = tk.Frame(p, bg=C["bg"])
            grid.pack(fill="x")

            def card(i, tname):
                t = compute_theme(tname, cur_acc if tname == cur_name else None)
                chosen = tname == cur_name
                f = tk.Frame(grid, bg=C["accent"] if chosen else C["line"], padx=2, pady=2, cursor="hand2")
                f.grid(row=i // 3, column=i % 3, padx=(0, 10), pady=(0, 10))
                body = tk.Frame(f, bg=t["bg"], width=150, height=84)
                body.pack()
                body.pack_propagate(False)
                tk.Frame(body, bg=t["panel"], width=34).pack(side="left", fill="y")
                right = tk.Frame(body, bg=t["bg"])
                right.pack(side="left", fill="both", expand=True)
                tk.Label(right, text=tname, bg=t["bg"], fg=t["text"], font=(self.ui, 9, "bold")).pack(anchor="w", padx=8, pady=(12, 4))
                chips = tk.Frame(right, bg=t["bg"])
                chips.pack(anchor="w", padx=8)
                for col, w in ((t["accent"], 30), (t["soft"], 22), (t["line"], 14)):
                    tk.Frame(chips, bg=col, width=w, height=9).pack(side="left", padx=(0, 4))
                tk.Label(right, text="✓ 사용 중" if chosen else "", bg=t["bg"], fg=t["accent"], font=(self.ui, 8)).pack(anchor="w", padx=8, pady=(6, 0))
                for w in (f, body, right, *right.winfo_children(), *chips.winfo_children()):
                    w.bind("<Button-1>", lambda e, n=tname: self.root.after(20, lambda: self.set_theme(n)))
            for i, tname in enumerate(THEMES):
                card(i, tname)
            hr(p)
            lab(p, "강조색", font=(self.ui, 10, "bold")).pack(anchor="w")
            row = tk.Frame(p, bg=C["bg"])
            row.pack(fill="x", pady=8)
            tk.Frame(row, bg=C["accent"], width=34, height=22, highlightthickness=1, highlightbackground=C["line"]).pack(side="left")
            lab(row, cur_acc or "테마 기본색", fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=10)

            def choose():
                rgb, hexa = colorchooser.askcolor(color=C["accent"], title="강조색 고르기", parent=top)
                if hexa:
                    self.root.after(20, lambda: self.set_theme(cur_name, hexa))
            Btn(row, "색 고르기…", choose, padx=12, pady=4).pack(side="left")
            Btn(row, "테마 기본색으로", lambda: self.root.after(20, lambda: self.set_theme(cur_name, None)), padx=12, pady=4).pack(side="left", padx=6)
            lab(p, "강조색은 선택된 글, 버튼, 링크, 태그 등에 쓰이는 포인트 색입니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w")

            hr(p)
            lab(p, "유튜브 영상", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "노트 안의 유튜브 영상은 썸네일로 보이고, 누르면 재생 창이 열립니다.", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 4))
            vo = tk.StringVar(value=st.read_config().get("video_open", "app"))
            for key, label in (("app", "작은 재생 창 (Edge 앱 창, 주소창 없음)"), ("browser", "기본 브라우저")):
                tk.Radiobutton(p, text=label, value=key, variable=vo, command=lambda: st.write_config(video_open=vo.get()),
                               bg=C["bg"], activebackground=C["bg"], font=(self.ui, 10)).pack(anchor="w")

        def folders_tab(p):
            title(p, "폴더", "노트와 그림(리소스)을 저장하는 폴더를 정합니다.")
            root_var, media_var = tk.StringVar(), tk.StringVar()
            mode_note = lab(p, "", fg=C["muted"], font=(self.ui, 9))

            def refresh():
                root_var.set(self.store.root)
                media_var.set(self.store.media_dir)
                if self.store.media_is_vault:
                    mode_note.config(text="현재: 볼트 안 .resources (숨김)")
                else:
                    mode_note.config(text="현재: 예전 방식의 리소스 폴더입니다. 「볼트 안으로 옮기기」를 누르면 그림을 .resources 로 옮기고 노트의 링크도 고칩니다.")

            def change_root():
                if self.choose_root():
                    refresh()

            def apply_media(mode, path=None):
                new = self.store.media_dir_for(mode, path)
                old = self.store.media_dir
                same = os.path.normcase(os.path.abspath(new)) == os.path.normcase(os.path.abspath(old))
                migrate = False
                count = self.store.count_media()
                if not same and count:
                    ans = messagebox.askyesnocancel(
                        "리소스 폴더 변경", f"기존 리소스 {count}개를 새 폴더로 옮기고 노트의 그림 링크도 고칠까요?\n\n"
                        "예: 옮기고 링크 수정 (권장)\n아니오: 설정만 바꿈 (기존 파일과 링크는 그대로)\n취소: 변경 안 함", parent=top)
                    if ans is None:
                        return
                    migrate = bool(ans)
                self.flush()
                cur_path = self.cur["path"] if self.cur else None

                def go():
                    if not migrate:
                        try:
                            return finish(self.store.set_media(mode, path, False))
                        except (OSError, ValueError) as ex:
                            return messagebox.showerror(APP, f"리소스 폴더를 바꾸지 못했습니다.\n{ex}", parent=top)
                    self.run_task("리소스 폴더 옮기는 중", lambda prog, cancel: self.store.set_media(mode, path, True, prog),
                                  finish, text="리소스를 옮기고 노트의 링크를 고치는 중…", cancellable=False)

                def finish(res):
                    moved, relinked = res
                    self.reload_notes()
                    n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                    if n:
                        self.open_note(n, record=False)   # 링크가 바뀐 글을 다시 읽어 와서 낡은 내용으로 덮어쓰지 않게
                    refresh()
                    if migrate:
                        messagebox.showinfo(APP, f"리소스 {moved}개를 옮기고 노트 {relinked}개의 링크를 고쳤습니다.", parent=top)
                self.checkpoint("리소스 폴더 이전 전", go) if migrate else go()   # 노트의 링크가 바뀌므로 먼저 복원 지점

            def adopt_folder():
                """마크다운마다 미디어 폴더 이름이 다르니, 고른 폴더를 .resources 로 바꾸고 모든 노트의 링크도 고친다(확인 후)"""
                old = filedialog.askdirectory(title="미디어(그림·첨부)가 들어 있는 폴더 고르기", initialdir=self.store.root, mustexist=True, parent=top)
                if not old:
                    return
                old = os.path.normpath(old)
                why = self.store.check_media_folder(old)
                if why:
                    return messagebox.showwarning(APP, why, parent=top)

                def confirm(res):
                    files, notes = res
                    if not files:
                        return messagebox.showinfo(APP, "이 폴더에는 옮길 파일이 없습니다.", parent=top)
                    if not messagebox.askyesno(
                            "미디어 폴더를 .resources 로 바꾸기",
                            f"「{old}」\n\n안의 {files:,}개 항목을 볼트의 .resources 로 옮기고,\n모든 노트 중 {notes:,}개의 그림·링크 경로를 고칩니다.\n"
                            "(.md 노트는 옮기지 않고, 이름이 겹치는 파일은 번호를 붙입니다. 먼저 복원 지점을 만듭니다.)\n\n바꿀까요?", parent=top):
                        return
                    self.flush()
                    cur_path = self.cur["path"] if self.cur else None

                    def finish(r):
                        moved, relinked = r
                        self.reload_notes()
                        n = next((x for x in self.notes if x["path"] == cur_path), None) if cur_path else None
                        if n:
                            self.open_note(n, record=False)
                        refresh()
                        messagebox.showinfo(APP, f"{moved:,}개 항목을 옮기고 노트 {relinked:,}개의 링크를 고쳤습니다.\n이제 새 그림도 .resources 에 저장됩니다.", parent=top)
                    self.checkpoint("미디어 폴더 이전 전", lambda: self.run_task(
                        "미디어 폴더 옮기는 중", lambda prog, cancel: self.store.move_media_folder(old, prog), finish,
                        text="파일을 옮기고 노트의 링크를 고치는 중…", cancellable=False))
                self.run_task("확인하는 중", lambda prog, cancel: self.store.preview_media_folder(old, prog), confirm, text="노트에서 이 폴더를 가리키는 링크를 세는 중…")

            lab(p, "노트 폴더", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "노트북 = 폴더(하위 폴더는 하위 노트북), 노트 = .md 파일", fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 6))
            field(p, "경로", root_var, 52, ("변경…", change_root))
            Btn(p, "노트 폴더 열기", lambda: os.startfile(self.store.root), padx=10, pady=3).pack(anchor="w", padx=(64, 0), pady=(4, 0))
            hr(p)
            lab(p, "그림·첨부 (볼트 안 숨김 폴더)", font=(self.ui, 10, "bold")).pack(anchor="w")
            lab(p, "웹 클리퍼로 저장한 그림 등은 노트 폴더(볼트) 안의 숨김 폴더 .resources 에 저장되고,\n노트에는 노트 위치 기준의 상대 경로로 연결됩니다. 따로 지정할 필요가 없습니다.",
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", pady=(0, 6))
            field(p, "경로", media_var, 52)
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", padx=(64, 0), pady=(6, 0))
            move_btn = Btn(row, "볼트 안으로 옮기기", lambda: apply_media("vault"), padx=10, pady=3)
            move_btn.pack(side="left")
            Btn(row, "열기", lambda: (self.store.ensure_media(), os.startfile(self.store.media_dir)), padx=10, pady=3).pack(side="left", padx=6)
            Btn(row, "다른 폴더를 .resources 로 바꾸기…", adopt_folder, padx=10, pady=3).pack(side="left")
            lab(p, "노트가 쓰던 미디어 폴더 이름이 다르면(attachments, images 등) 그 폴더를 직접 골라 .resources 로 모으고,\n모든 노트의 링크를 한꺼번에 고칩니다. 고른 뒤 몇 곳이 바뀌는지 보여 주고 확인을 받습니다.",
                fg=C["muted"], font=(self.ui, 9)).pack(anchor="w", padx=(64, 0), pady=(6, 0))
            mode_note.pack(anchor="w", padx=(64, 0), pady=(8, 0))
            refresh()
            if self.store.media_is_vault:
                move_btn.pack_forget()

        def fonts_tab(p):
            title(p, "글꼴", "노트 목록과 노트의 글자 크기·굵기를 정합니다. 적용을 누르면 바로 바뀝니다.")
            fc = self.font_cfg()
            ls, lb = tk.StringVar(value=str(fc["list_size"])), tk.BooleanVar(value=fc["list_bold"])
            ns, nb = tk.StringVar(value=str(fc["note_size"])), tk.BooleanVar(value=fc["note_bold"])

            def section(name, size_var, bold_var, lo, hi):
                lab(p, name, font=(self.ui, 10, "bold")).pack(anchor="w", pady=(6, 4))
                row = tk.Frame(p, bg=C["bg"])
                row.pack(fill="x")
                lab(row, "글자 크기", width=9).pack(side="left")
                tk.Spinbox(row, from_=lo, to=hi, textvariable=size_var, width=5, relief="flat", bd=0, bg=C["panel"], fg=C["text"],
                           insertbackground=C["accent"], highlightthickness=1, highlightbackground=C["line"],
                           font=(self.ui, 10), buttonbackground=C["panel"]).pack(side="left", ipady=4)
                lab(row, "pt", fg=C["muted"], font=(self.ui, 9)).pack(side="left", padx=6)
                tk.Checkbutton(row, text="굵게", variable=bold_var, bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                               selectcolor=C["bg"], font=(self.ui, 10)).pack(side="left", padx=18)
            section("노트 목록", ls, lb, 8, 20)
            prev1 = lab(p, "노트 목록 제목 미리보기", fg=C["text"])
            prev1.pack(anchor="w", pady=(8, 0))
            hr(p)
            section("노트 (에디터·렌더링)", ns, nb, 8, 28)
            prev2 = lab(p, "노트 본문 미리보기 — 가나다라 ABC abc 123", fg=C["text"])
            prev2.pack(anchor="w", pady=(8, 0))

            def preview(*_):
                try:
                    a, b = int(float(ls.get())), int(float(ns.get()))
                except ValueError:
                    return
                prev1.config(font=(self.ui, max(8, min(20, a)), "bold" if lb.get() else "normal"))
                prev2.config(font=(self.ui, max(8, min(28, b)), "bold" if nb.get() else "normal"))
            for v in (ls, lb, ns, nb):
                v.trace_add("write", preview)
            preview()
            row = tk.Frame(p, bg=C["bg"])
            row.pack(anchor="w", pady=(22, 0))
            Btn(row, "적용", lambda: self.root.after(20, lambda: self.set_fonts(ls.get(), lb.get(), ns.get(), nb.get())),
                kind="primary", bold=True, padx=22, pady=5).pack(side="left")
            Btn(row, "기본값으로", lambda: self.root.after(20, lambda: self.set_fonts(10, False, 11, False)), padx=14, pady=5).pack(side="left", padx=8)

        pages = (("general", "일반", general), ("folders", "폴더", folders_tab), ("imports", "가져오기", imports_tab), ("fonts", "글꼴", fonts_tab), ("theme", "테마·색상", theme_tab), ("versions", "노트 버전", versions_tab), ("clipper", "웹 클리퍼", clipper))

        def select(key):
            for k, b in tabs.items():
                b.set_on(k == key)
            for w in content.winfo_children():
                w.destroy()
            dict((k, f) for k, _, f in pages)[key](content)

        for key, label, _ in pages:
            b = Btn(nav, label, lambda k=key: select(k), kind="nav", padx=18, pady=8, anchor="w")
            b.pack(fill="x", padx=8, pady=1)
            tabs[key] = b
        foot.pack(side="bottom", fill="x", padx=28, pady=(0, 16), before=content)
        Btn(foot, "닫기", top.destroy, kind="primary", padx=22, pady=5).pack(side="right")
        select(tab)

    # ------------------------------------------------------------ 단축키·종료
    def bind_keys(self):
        r = self.root
        r.bind_all("<Control-n>", lambda e: self.new_note())
        r.bind_all("<Control-N>", lambda e: self.add_notebook())
        r.bind_all("<Control-l>", lambda e: self.cur and self.cycle_mode())
        r.bind_all("<Control-e>", lambda e: self.cur and self.cycle_mode())
        r.bind_all("<Control-L>", lambda e: (self.v["list"].set(not self.show["list"]), self.on_view_toggle()))
        r.bind_all("<Control-slash>", lambda e: self.toggle_syntax())
        r.bind_all("<Control-f>", lambda e: self.on_ctrl_f())
        r.bind_all("<Control-F>", lambda e: self.focus_search())
        for w in (self.text, self.view):   # 글자 칸의 기본 Ctrl+F(커서를 한 글자 오른쪽으로)는 막는다
            w.bind("<Control-f>", lambda e: (self.on_ctrl_f(), "break")[1])
        r.bind_all("<F3>", lambda e: self.find_step(1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Shift-F3>", lambda e: self.find_step(-1) if self.findbar.winfo_ismapped() else None)
        r.bind_all("<Control-comma>", lambda e: self.show_options("general"))
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
    if not single.acquire():   # 이미 실행 중(창이 열려 있거나 트레이에 있음): 그 앱에 창을 열어 달라고 알렸으니 여기서는 끝낸다
        return
    App().run()


if __name__ == "__main__":
    main()
