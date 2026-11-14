"""노트 칸 안에 Edge WebView2(브라우저)를 띄워 가져온 파일을 보여 준다: pdf 는 브라우저의 pdf 보기로,
음악·동영상은 가져온 폴더(하위 폴더 포함)의 파일을 재생 목록으로 묶은 재생 화면(폴더 고르기·랜덤·반복)으로.
assets/WebView2Loader.dll(마이크로소프트 WebView2 SDK)과 PC 에 설치된 WebView2 런타임을 표준 라이브러리 ctypes 의 COM 호출로만 쓴다.
로더나 런타임이 없으면 available() 이 False 라서, 부른 쪽은 예전 방식(윈도 미리보기 처리기 → 뽑은 글)으로 돌아간다.
Windows 전용.

Viewer 는 winpreview.Preview 와 같은 모양(show·resize·unload)이라 App.pv 자리에 그대로 들어간다."""
import ctypes
import html
import json
import os
import pathlib
import re
import sys
from ctypes import POINTER, WINFUNCTYPE, byref, c_int, c_long, c_ulong, c_void_p, c_wchar_p, wintypes

import winpreview

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
LOADER = os.path.join(HERE, "assets", "WebView2Loader.dll")

AUDIO_EXT = ("mp3", "flac", "m4a", "ogg", "wav", "opus")          # 브라우저가 재생할 수 있는 소리 형식(wma 는 못 한다)
VIDEO_EXT = ("mp4", "webm", "ogv", "m4v")
MEDIA_EXT = AUDIO_EXT + VIDEO_EXT
WEB_EXT = ("pdf",) + MEDIA_EXT                                    # WebView2 로 보여 줄 형식

HRESULT = c_long            # 실패 값을 예외로 바꾸지 않고 숫자로 받는다
E_NOINTERFACE = -2147467262
IID_UNKNOWN = "00000000-0000-0000-c000-000000000046"
IID_ENV_DONE = "4e8a3389-c9d8-4bd2-b6b5-124fee6cc14d"            # ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler
IID_CTL_DONE = "6c4819f3-c9b7-4260-8127-c9f5bde7f68c"            # ICoreWebView2CreateCoreWebView2ControllerCompletedHandler

_loader = None      # None: 아직 안 읽음, False: 쓸 수 없음
_runtime = None     # WebView2 런타임이 설치돼 있는가(한 번만 확인)
_keep = []          # 콜백 객체(가상 함수 표와 함수들). 브라우저가 부를 수 있으니 프로그램이 끝날 때까지 살려 둔다


def _load():
    global _loader
    if _loader is None:
        _loader = False
        if sys.platform == "win32" and os.path.isfile(LOADER):
            try:
                dll = ctypes.WinDLL(LOADER)
                dll.CreateCoreWebView2EnvironmentWithOptions.argtypes = [c_wchar_p, c_wchar_p, c_void_p, c_void_p]
                dll.CreateCoreWebView2EnvironmentWithOptions.restype = HRESULT
                dll.GetAvailableCoreWebView2BrowserVersionString.argtypes = [c_wchar_p, POINTER(c_void_p)]
                dll.GetAvailableCoreWebView2BrowserVersionString.restype = HRESULT
                _loader = dll
            except (OSError, AttributeError):   # 32비트 파이썬 등: 로더를 못 읽으면 없는 것으로 친다
                _loader = False
    return _loader


def available():
    """로더 DLL 이 있고 WebView2 런타임이 설치돼 있으면 True"""
    global _runtime
    if _runtime is None:
        _runtime = False
        dll = _load()
        if dll:
            ver = c_void_p()
            try:
                if dll.GetAvailableCoreWebView2BrowserVersionString(None, byref(ver)) == 0 and ver.value:
                    _runtime = bool(ctypes.wstring_at(ver.value))
                    ctypes.windll.ole32.CoTaskMemFree(ver)
            except OSError:
                _runtime = False
    return _runtime


def supports(ext):
    """이 확장자(점 없이)를 WebView2 로 보여 줄 수 있는가"""
    return ext.lower().lstrip(".") in WEB_EXT and available()


def can_show(ext):
    """노트 칸 안에 원본으로 보여 줄 방법(WebView2 또는 윈도 미리보기 처리기)이 있는가"""
    return supports(ext) or winpreview.available(ext)


def _com(p, index, restype, argtypes, *args):
    """COM 객체 p 의 가상 함수 표에서 index 번째 함수를 부른다"""
    vtable = ctypes.cast(c_void_p(p), POINTER(c_void_p))[0]
    addr = ctypes.cast(vtable, POINTER(c_void_p))[index]
    return WINFUNCTYPE(restype, c_void_p, *argtypes)(addr)(p, *args)


def _handler(iid, on_done):
    """'끝나면 불러 줄' COM 콜백 객체(IUnknown + Invoke(HRESULT, 결과 객체))를 만들어 그 주소를 돌려준다"""
    def query(this, riid, out):
        g = riid.contents
        asked = "%08x-%04x-%04x-%s-%s" % (g.Data1, g.Data2, g.Data3, bytes(g.Data4[:2]).hex(), bytes(g.Data4[2:]).hex())
        if asked in (IID_UNKNOWN, iid):
            out[0] = this
            return 0
        out[0] = None
        return E_NOINTERFACE

    def invoke(this, hr, result):
        try:
            on_done(hr, result)
        except Exception:  # noqa: BLE001  (콜백 안의 오류가 브라우저 쪽으로 넘어가지 않게)
            pass
        return 0

    fns = [WINFUNCTYPE(HRESULT, c_void_p, POINTER(winpreview.GUID), POINTER(c_void_p))(query),
           WINFUNCTYPE(c_ulong, c_void_p)(lambda this: 2),      # AddRef·Release: 이 객체는 지우지 않으니 세지 않는다
           WINFUNCTYPE(c_ulong, c_void_p)(lambda this: 1),
           WINFUNCTYPE(HRESULT, c_void_p, HRESULT, c_void_p)(invoke)]
    vtable = (c_void_p * 4)(*[ctypes.cast(f, c_void_p).value for f in fns])
    obj = (c_void_p * 1)(ctypes.addressof(vtable))
    _keep.extend(fns + [vtable, obj])
    return ctypes.addressof(obj)


def data_dir():
    """브라우저 자료(캐시 등)와 재생 화면 파일을 두는 곳: 설정 파일 옆의 webview 폴더"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "iamtalkernote", "webview")
    os.makedirs(d, exist_ok=True)
    return d


def file_url(path):
    return pathlib.Path(os.path.abspath(path)).as_uri()


def folder_media(path):
    """path 와 같은 폴더의 소리·동영상 파일(이름 순). path 자신은 반드시 들어간다"""
    path = os.path.abspath(path)
    found = {os.path.normcase(path): path}
    try:
        for item in os.scandir(os.path.dirname(path)):
            if item.is_file() and os.path.splitext(item.name)[1].lower().lstrip(".") in MEDIA_EXT:
                found.setdefault(os.path.normcase(item.path), item.path)
    except OSError:
        pass
    return sorted(found.values(), key=lambda p: natural(os.path.basename(p)))


def natural(name):
    """이름 순 정렬 열쇠: 숫자는 수로 견준다('2 곡' 이 '10 곡' 앞)"""
    return [(0, int(part), "") if part.isdigit() else (1, 0, part.casefold()) for part in re.split(r"(\d+)", name) if part]


media_roots = lambda: []   # noqa: E731   가져온 폴더들의 경로를 돌려주는 함수. 앱이 시작할 때 바꿔 끼운다
MAX_TRACKS = 20000         # 재생 목록에 넣는 파일 수의 상한(그 이상은 연 파일의 폴더만)


def media_library(path):
    """재생 목록에 넣을 파일을 모은다 → (폴더 목록, 곡 목록, 연 파일의 번호).
    path 가 가져온 폴더 안에 있으면 그 가져온 폴더 전체(하위 폴더 포함)를, 아니면 path 의 폴더만 모은다.
    폴더 목록은 [{"key": 번호, "label": 보여 줄 이름, "rel": 기준 폴더에서 본 경로('/' 로 나눔, 기준 폴더 자신은 '')}],
    곡은 {"name", "url", "video", "dir": 폴더 번호}. 기준 폴더(가져온 폴더, 없으면 path 의 폴더)의 경로도 돌려준다"""
    path = os.path.abspath(path)
    home = os.path.dirname(path)
    same = lambda a, b: os.path.normcase(a) == os.path.normcase(b)  # noqa: E731
    root = None
    for r in media_roots():
        r = os.path.abspath(r)
        try:
            inside = same(os.path.commonpath([r, path]), r)
        except ValueError:      # 드라이브가 다르다
            inside = False
        if inside and (root is None or len(r) > len(root)):
            root = r
    groups = {}                 # 폴더 경로 → 그 안의 파일들
    if root:
        count = 0
        for folder, subs, names in os.walk(root):
            subs[:] = [d for d in subs if not d.startswith(".")]
            found = [os.path.join(folder, n) for n in names if os.path.splitext(n)[1].lower().lstrip(".") in MEDIA_EXT]
            if found:
                groups[folder] = found
                count += len(found)
            if count > MAX_TRACKS:
                groups, root = {}, None
                break
    if not root:
        groups = {home: folder_media(path)}
    mine = next((d for d in groups if same(d, home)), None)
    if mine is None:
        mine = home
        groups[mine] = []
    if not any(same(p, path) for p in groups[mine]):
        groups[mine].append(path)
    base = root or home

    def label(d):
        if same(d, base):
            return os.path.basename(base.rstrip("\\/")) or base
        return os.path.relpath(d, base).replace("\\", " / ")

    order = sorted(groups, key=lambda d: (not same(d, base), natural(os.path.relpath(d, base))))
    dirs, tracks, start = [], [], 0
    for key, d in enumerate(order):
        dirs.append({"key": key, "label": label(d), "rel": "" if same(d, base) else os.path.relpath(d, base).replace("\\", "/")})
        for p in sorted(groups[d], key=lambda p: natural(os.path.basename(p))):
            if same(p, path):
                start = len(tracks)
            tracks.append({"name": os.path.basename(p), "url": file_url(p), "dir": key,
                           "video": os.path.splitext(p)[1].lower().lstrip(".") in VIDEO_EXT})
    return dirs, tracks, start, base


PLAYER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
:root { color-scheme: light dark; }
html, body { height: 100%; margin: 0; }
body { display: flex; flex-direction: column; font: 15px "Malgun Gothic", "Segoe UI", sans-serif; background: Canvas; color: CanvasText; }
#now { padding: 14px 18px 2px; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
#where { padding: 0 18px 6px; font-size: 13px; opacity: .65; min-height: 1.3em; }
#stage { padding: 4px 18px 10px; }
video { display: block; width: 100%; max-height: 60vh; background: #000; }
video.audio { height: 54px; background: transparent; }
#bar { padding: 0 18px 10px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
button, select { font: inherit; padding: 4px 12px; }
select { max-width: 100%; }
button.on { background: Highlight; color: HighlightText; border-color: Highlight; }
#count { margin-left: auto; opacity: .65; }
ol { flex: 1; overflow: auto; margin: 0; padding: 0; list-style: none; border-top: 1px solid color-mix(in srgb, CanvasText 18%, transparent); }
li.t { padding: 8px 18px; cursor: pointer; overflow-wrap: anywhere; }
li.t:hover { background: color-mix(in srgb, CanvasText 8%, transparent); }
li.t.on { background: color-mix(in srgb, Highlight 28%, transparent); font-weight: 600; }
li.t.bad { opacity: .5; text-decoration: line-through; }
li.h { padding: 10px 18px 4px; font-size: 13px; font-weight: 600; color: GrayText; position: sticky; top: 0; background: Canvas; }
</style></head><body>
<div id="now"></div><div id="where"></div>
<div id="stage"><video id="v" controls></video></div>
<div id="bar">
<select id="scope" title="재생 목록에 넣을 폴더"></select>
<button id="prev">◀ 이전</button><button id="next">다음 ▶</button>
<button id="shuffle" title="목록을 섞어서 재생">랜덤</button>
<button id="repeat" title="누를 때마다: 반복 안 함 → 전체 반복 → 한 곡 반복"></button>
<span id="count"></span></div>
<ol id="list"></ol>
<script>
const tracks = __TRACKS__, dirs = __DIRS__, home = tracks[__START__].dir, base = __BASE__;
const v = document.getElementById('v'), list = document.getElementById('list'), scopeBox = document.getElementById('scope');
const shuffleBtn = document.getElementById('shuffle'), repeatBtn = document.getElementById('repeat');
const REPEAT = {off: '반복 안 함', all: '전체 반복', one: '한 곡 반복'};
const keep = {   // 랜덤·반복·'하위 폴더까지' 선택은 다음에 열 때도 그대로
  get(k, d) { try { return localStorage.getItem('iat.' + k) ?? d; } catch (e) { return d; } },
  set(k, x) { try { localStorage.setItem('iat.' + k, x); } catch (e) {} }
};
let cur = __START__;                       // 지금 곡(tracks 의 번호)
let scope = 'd:' + home;                   // 목록의 범위: 'd:폴더 번호'(그 폴더만) 또는 't:경로'(그 폴더와 하위 폴더)
let view = [];                             // 목록에 보이는 곡들
let order = [], pos = 0;                   // 재생 순서와 그 안의 지금 자리
let shuffle = keep.get('shuffle', '0') === '1';
let repeat = REPEAT[keep.get('repeat', 'off')] ? keep.get('repeat', 'off') : 'off';
let failed = 0;                            // 연달아 못 읽은 곡 수(전부 못 읽을 때 끝없이 넘기지 않게)
const rows = new Map();                    // 곡 번호 → 목록의 줄

function mix(a) {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
function makeOrder(curFirst) {
  order = view.slice();
  if (shuffle) {
    mix(order);
    const at = order.indexOf(cur);
    if (curFirst && at > 0) { order.splice(at, 1); order.unshift(cur); }
  }
  pos = order.indexOf(cur);
}
function mark() {
  const t = tracks[cur];
  document.getElementById('now').textContent = t.name;
  document.getElementById('where').textContent = dirs.length > 1 ? dirs[t.dir].label : '';
  const at = view.indexOf(cur);
  document.getElementById('count').textContent = (at < 0 ? '–' : at + 1) + ' / ' + view.length;
  rows.forEach((li, i) => li.classList.toggle('on', i === cur));
  if (rows.has(cur)) rows.get(cur).scrollIntoView({block: 'nearest'});
}
function under(rel, tree) { return tree === '' || rel === tree || rel.startsWith(tree + '/'); }
function inScope(t) {
  return scope[0] === 'd' ? t.dir === Number(scope.slice(2)) : under(dirs[t.dir].rel, scope.slice(2));
}
function setScope(value) {
  scope = value;
  scopeBox.value = value;
  view = tracks.map((t, i) => i).filter(i => inScope(tracks[i]));
  const many = new Set(view.map(i => tracks[i].dir)).size > 1;
  list.textContent = '';
  rows.clear();
  let last = -1;
  for (const i of view) {
    const t = tracks[i];
    if (many && t.dir !== last) {
      const h = document.createElement('li');
      h.className = 'h';
      h.textContent = dirs[t.dir].label;
      list.appendChild(h);
      last = t.dir;
    }
    const li = document.createElement('li');
    li.className = 't';
    li.textContent = t.name;
    li.onclick = () => { load(i, true); pos = order.indexOf(i); };
    list.appendChild(li);
    rows.set(i, li);
  }
  makeOrder(true);
  mark();
}
function load(i, play) {
  cur = i;
  const t = tracks[i];
  v.className = t.video ? '' : 'audio';
  v.src = t.url;
  mark();
  if (play) v.play().catch(() => {});
}
function step(d, play) {
  if (!order.length) return;
  let p = pos + d;
  if (pos < 0) p = d > 0 ? 0 : order.length - 1;       // 지금 곡이 이 목록에 없다: 목록의 처음(끝)부터
  else if (p < 0 || p >= order.length) {
    if (repeat !== 'all') return;
    if (shuffle) { makeOrder(false); if (order.length > 1 && order[d > 0 ? 0 : order.length - 1] === cur) order.reverse(); }
    p = d > 0 ? 0 : order.length - 1;
  }
  pos = p;
  load(order[p], play);
}
function showButtons() {
  shuffleBtn.classList.toggle('on', shuffle);
  repeatBtn.textContent = REPEAT[repeat];
  repeatBtn.classList.toggle('on', repeat !== 'off');
  v.loop = repeat === 'one';
}
v.onended = () => step(1, true);
v.onplaying = () => { failed = 0; };
v.onerror = () => {
  if (rows.has(cur)) rows.get(cur).classList.add('bad');
  if (++failed < order.length) step(1, true);
};
document.getElementById('prev').onclick = () => step(-1, !v.paused);
document.getElementById('next').onclick = () => step(1, !v.paused);
shuffleBtn.onclick = () => { shuffle = !shuffle; keep.set('shuffle', shuffle ? '1' : '0'); makeOrder(true); showButtons(); };
repeatBtn.onclick = () => { repeat = {off: 'all', all: 'one', one: 'off'}[repeat]; keep.set('repeat', repeat); showButtons(); };
const where = rel => base + (rel ? '/' + rel : '');     // 범위로 고른 폴더의 전체 경로(기억해 둘 때 쓴다)
scopeBox.onchange = () => {
  const value = scopeBox.value;
  keep.set('tree', value[0] === 't' ? where(value.slice(2)) : '');
  setScope(value);
};
const trees = [];                                       // 하위 폴더까지 묶어 고를 수 있는 폴더(음악이 든 폴더가 둘 이상 딸린 것)
if (dirs.length > 1) {
  const add = (group, value, text) => { const o = document.createElement('option'); o.value = value; o.textContent = text; group.appendChild(o); };
  const group = label => { const g = document.createElement('optgroup'); g.label = label; scopeBox.appendChild(g); return g; };
  const one = group('폴더 하나');
  dirs.forEach(d => add(one, 'd:' + d.key, d.label + ' (' + tracks.filter(t => t.dir === d.key).length + '곡)'));
  const seen = new Set();
  dirs.forEach(d => {
    const parts = d.rel ? d.rel.split('/') : [];
    for (let n = 0; n <= parts.length; n++) seen.add(parts.slice(0, n).join('/'));
  });
  const more = group('하위 폴더까지');
  [...seen].sort((a, b) => a.localeCompare(b, 'ko', {numeric: true})).forEach(rel => {
    if (dirs.filter(d => under(d.rel, rel)).length < 2) return;
    trees.push(rel);
    const name = rel === '' ? dirs.find(d => d.rel === '')?.label ?? base.split('/').pop() : rel.replaceAll('/', ' / ');
    add(more, 't:' + rel, name + ' + 하위 폴더 (' + tracks.filter(t => under(dirs[t.dir].rel, rel)).length + '곡)');
  });
} else scopeBox.style.display = 'none';
showButtons();
// 지난번에 '하위 폴더까지'로 고른 폴더가 있고 지금 연 파일이 그 안에 있을 때만 그 범위를 잇는다.
// 그 밖(다른 폴더의 파일을 열었을 때)에는 연 파일의 폴더만 넣어, 상관없는 폴더가 섞이지 않게 한다.
const saved = keep.get('tree', '');
const savedRel = saved === base ? '' : saved.startsWith(base + '/') ? saved.slice(base.length + 1) : null;
setScope(savedRel !== null && trees.includes(savedRel) && under(dirs[home].rel, savedRel) ? 't:' + savedRel : 'd:' + home);
load(cur, false);
</script></body></html>
"""


def write_player(path):
    """path(소리·동영상 파일)를 재생하는 화면(html)을 만들어 그 주소를 돌려준다: 재생 목록, 폴더 고르기, 랜덤, 반복.
    file:// 주소의 파일을 재생하려면 화면도 파일이어야 해서, 글자로 넘기지 않고 파일로 쓴다."""
    dirs, tracks, start, base = media_library(path)
    dump = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")  # noqa: E731
    page = (PLAYER_HTML.replace("__TITLE__", html.escape(os.path.basename(path)))
            .replace("__TRACKS__", dump(tracks)).replace("__DIRS__", dump(dirs)).replace("__START__", str(start))
            .replace("__BASE__", dump(os.path.normcase(base).replace("\\", "/").rstrip("/"))))
    out = os.path.join(data_dir(), "player.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return file_url(out)


def page_url(path):
    """path 를 보여 줄 주소: 소리·동영상은 재생 화면, 그 밖(pdf)은 파일 주소 그대로"""
    if os.path.splitext(path)[1].lower().lstrip(".") in MEDIA_EXT:
        return write_player(path)
    return file_url(path)


class WebView:
    """창 하나(HWND) 안의 브라우저 하나. 처음 show() 때 만들고, 그 뒤로는 주소만 바꿔 다시 쓴다.
    만드는 일은 뒤에서 끝나므로(끝나면 콜백), show() 는 요청만 해 두고 바로 돌아온다."""

    def __init__(self):
        self.env = None       # ICoreWebView2Environment
        self.ctl = None       # ICoreWebView2Controller
        self.view = None      # ICoreWebView2
        self.hwnd = None      # 브라우저를 붙인 창
        self.url = None       # 보여 줄 주소(브라우저가 만들어지기 전이면 만들어진 뒤에 연다)
        self.size = (10, 10)
        self.creating = False
        self.failed = False

    def show(self, hwnd, path, width, height):
        """보여 주기를 시작했으면 True. 로더·런타임이 없거나 브라우저를 만들지 못했으면 False"""
        if self.failed or not available():
            return False
        try:
            url = page_url(path)
        except OSError:
            return False
        return self.show_url(hwnd, url, width, height)

    def show_url(self, hwnd, url, width, height):
        """주소 url 을 창 hwnd 안에 보여 준다. 같은 창·같은 주소라면 다시 열지 않는다(재생이 끊기지 않게)"""
        if self.failed or not available():
            return False
        if self.ctl and self.hwnd == hwnd and self.url == url:
            self.size = (max(width, 10), max(height, 10))
            try:
                self._bounds()
                _com(self.ctl, 4, HRESULT, [c_int], 1)     # put_IsVisible
            except OSError:
                return False
            return True
        if self.ctl and self.hwnd != hwnd:   # 붙일 창이 바뀌었다: 새로 만든다
            self.close()
        self.hwnd, self.url, self.size = hwnd, url, (max(width, 10), max(height, 10))
        if self.ctl:
            self._open()
            return True
        if not self.creating:
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 2)   # 화면 쓰레드는 STA (이미 돼 있으면 그대로)
            except OSError:
                pass
            self.creating = True
            hr = _load().CreateCoreWebView2EnvironmentWithOptions(None, data_dir(), None, _handler(IID_ENV_DONE, self._on_env))
            if hr != 0:
                self.creating = False
                self.failed = True
                return False
        return True

    def _on_env(self, hr, env):
        if hr != 0 or not env:
            self.creating, self.failed = False, True
            return
        _com(env, 1, c_ulong, [])   # AddRef: 콜백이 끝나면 부른 쪽이 자기 몫을 놓는다. 잡아 두지 않으면 객체가 사라진다
        self.env = env
        if _com(env, 3, HRESULT, [wintypes.HWND, c_void_p], self.hwnd, _handler(IID_CTL_DONE, self._on_ctl)) != 0:   # CreateCoreWebView2Controller
            self.creating, self.failed = False, True

    def _on_ctl(self, hr, ctl):
        self.creating = False
        if hr != 0 or not ctl:
            self.failed = True
            return
        _com(ctl, 1, c_ulong, [])   # AddRef (위와 같은 이유: 안 하면 브라우저 창이 부모 없이 숨은 채 남는다)
        self.ctl = ctl
        view = c_void_p()
        _com(ctl, 25, HRESULT, [POINTER(c_void_p)], byref(view))   # get_CoreWebView2
        self.view = view.value
        if self.url:
            self._open()
        else:                       # 만들어지는 사이에 닫혔다
            _com(ctl, 4, HRESULT, [c_int], 0)

    def _open(self):
        self._bounds()
        _com(self.ctl, 4, HRESULT, [c_int], 1)                     # put_IsVisible
        if self.view:
            _com(self.view, 5, HRESULT, [c_wchar_p], self.url)     # Navigate

    def _bounds(self):
        _com(self.ctl, 6, HRESULT, [wintypes.RECT], wintypes.RECT(0, 0, *self.size))   # put_Bounds

    def resize(self, width, height):
        self.size = (max(width, 10), max(height, 10))
        if self.ctl and self.url:
            try:
                self._bounds()
            except OSError:
                pass

    def unload(self):
        """화면을 비우고 숨긴다(재생도 멈춘다). 브라우저는 다음에 다시 쓰려고 남겨 둔다"""
        was, self.url = self.url, None
        if self.ctl and was:
            try:
                if self.view:
                    _com(self.view, 5, HRESULT, [c_wchar_p], "about:blank")
                _com(self.ctl, 4, HRESULT, [c_int], 0)
            except OSError:
                pass

    def close(self):
        """브라우저를 닫는다(앱을 끝낼 때, 붙일 창이 바뀔 때)"""
        ctl, view, self.ctl, self.view, self.url = self.ctl, self.view, None, None, None
        try:
            if ctl:
                _com(ctl, 24, HRESULT, [])       # Close
            if view:
                _com(view, 2, c_ulong, [])       # Release
            if ctl:
                _com(ctl, 2, c_ulong, [])
        except OSError:
            pass


class Viewer:
    """노트 칸에 원본을 보여 주는 것 하나: WebView2 로 볼 수 있는 형식이면 WebView2 로, 아니면 윈도 미리보기 처리기로."""

    def __init__(self):
        self.web = WebView()
        self.native = winpreview.Preview()
        self.using = None

    def show(self, hwnd, path, width, height):
        self.unload()
        ext = os.path.splitext(path)[1]
        if supports(ext) and self.web.show(hwnd, path, width, height):
            self.using = self.web
            return True
        if self.native.show(hwnd, path, width, height):
            self.using = self.native
            return True
        return False

    def resize(self, width, height):
        if self.using:
            self.using.resize(width, height)

    def unload(self):
        using, self.using = self.using, None
        if using:
            using.unload()

    def close(self):
        self.unload()
        self.web.close()
