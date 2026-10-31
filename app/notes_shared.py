"""notes.py 와 그 믹스인들이 함께 쓰는 것: 가져오기, 상수, 색(테마), 납작한 버튼, 보조 함수.
notes.py 의 머리에서 그대로 옮겨 왔다(동작 변경 없음). UI 글꼴 이름은 App 이 정해 이 모듈의 UI 도 같이 바꾼다."""
import base64
import bisect
import hashlib
import math
import os
import queue
import re
import secrets
import sqlite3
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
import syncengine  # noqa: E402   (동기화 엔진: Syncthing 을 받아 숨겨 실행하고 제어)
import syncui  # noqa: E402   (옵션의 '동기화' 탭, 앱을 켤 때 동기화 이어 주기)
import docs as docidx  # noqa: E402   (노트 폴더 밖의 pdf·txt·mp3 … 가져오기)
import editor as ed # noqa: E402   (위키나루: 서식 도구·그림 불러오기)
import ime  # noqa: E402   (한글 입력기가 조합 중인 글자를 자동완성에서 보려고)
import preview  # noqa: E402
import search  # noqa: E402
import similar  # noqa: E402   (비슷한 노트 찾기)
import snapshots as sn  # noqa: E402
import single  # noqa: E402   (앱을 한 번에 하나만: 두 번째 실행은 실행 중인 앱의 창을 열어 달라고 알리고 끝난다)
import store as st  # noqa: E402
import tray  # noqa: E402   (닫기 버튼을 누르면 앱을 끄지 않고 알림 영역 아이콘으로)
import updater  # noqa: E402
import wikiconv  # noqa: E402
import viewdelete  # noqa: E402
import tagac  # noqa: E402
import favorites  # noqa: E402
from outliner.widget import OutlineEditor  # noqa: E402
from planner import model as pm  # noqa: E402
from planner.view import PlannerView  # noqa: E402
import wikilinks  # noqa: E402
import syncsettings  # noqa: E402
import winpreview  # noqa: E402   (윈도 미리보기 처리기를 노트 화면 안에: pdf·mp3 …)
from version import VERSION  # noqa: E402

APP = "iamtalkernote"
LIST_CHUNK = 100   # 노트 목록은 이만큼씩 이어서 그린다(스크롤하면 계속)
VIEWABLE = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".pdf", ".txt"}   # 안 쓰는 미디어 목록에서 눌렀을 때 바로 열어도 되는 파일(실행 파일 등은 위치만 보여 준다)
def utf16_len(t):
    """Tk 글 위치는 UTF-16 단위(이모지 같은 글자는 2칸)라서 위치를 셀 때 쓴다"""
    return len(t) if t.isascii() else len(t.encode("utf-16-le")) // 2


def idx_to_u16(t, i):
    """파이썬 글자 위치 i → Tk(UTF-16) 위치"""
    return i if t.isascii() else len(t[:i].encode("utf-16-le")) // 2


def u16_to_idx(t, u):
    """Tk(UTF-16) 위치 → 파이썬 글자 위치"""
    if t.isascii():
        return u
    n = 0
    for i, ch in enumerate(t):
        if n >= u:
            return i
        n += 2 if ord(ch) > 0xFFFF else 1
    return len(t)


SOURCE_LINE = re.compile(r"\A[ \t]*원본:[ \t]*<?https?://[^\s>]+>?[ \t]*(?:\r?\n)+")   # 글 맨 위의 '원본: <주소>' 줄
DOC_RESCAN_SECONDS = 300   # 앱을 열어 두는 동안 가져온 폴더를 이 간격(초)마다 훑어 바뀐 파일만 다시 읽는다
PREVIEW_EXT = ("pdf", *docidx.AUDIO_EXT, *docidx.OFFICE_EXT)   # 윈도 미리보기 처리기로 원본을 보여 줄 형식(txt·md 같은 글 파일은 글로)
MORE_MAX = 4000      # 목록을 이어 그릴 때 한 번에 붙이는 노트 수의 상한(이미 그린 만큼을 붙이되 이 이상은 안 붙인다)
MORE_MAX_SEARCH = 600  # 검색 중에는 노트마다 본문을 읽어 미리 보기를 만들어서 더 적게
MORE_SCREENS = 4  # 목록 아래에 남은 글이 이만큼의 화면보다 적어지면 미리 다음 노트들을 이어 그린다
ALL = "*"
FAVS = "@favs"   # 노트북 목록의 즐겨찾기 항목
TRASH = "@trash"  # 노트북 목록 맨 아래의 휴지통(누르면 오른쪽에 지운 것들과 내용 미리보기). 검색에는 잡히지 않는다
CAL = "@cal"      # 노트북 목록의 달력·할일 항목(누르면 오른쪽에 달력과 할일이 뜬다)
QUICK = "@quick"   # 노트북 목록의 '바로가기' 묶음 머리글(즐겨찾기·아웃라이너·달력)
OUTL = "아웃라이너"   # 이 폴더(와 그 하위)의 노트는 WorkFlowy 식 아웃라이너 편집기로 연다(파일은 그냥 마크다운 목록 .md)
FRONT = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)\s*", re.S)
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
from tagtext import *  # noqa: E402,F401,F403   (태그 글 처리: hashtags·note_tags·edit_tag … 화면 없는 함수들)


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
