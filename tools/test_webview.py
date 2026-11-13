"""노트 칸 안 브라우저(WebView2)로 가져온 음악·pdf 를 보는지 시험. 임시 APPDATA·임시 폴더만 쓴다(소리는 끈 채로 재생한다).
py -3 -X utf8 tools/test_webview.py            (IAT_SHOT=폴더 를 주면 화면을 png 로 남긴다)"""
import ctypes
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave
from ctypes import WINFUNCTYPE, c_int, c_void_p, c_wchar_p, wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    if "stage" in globals():
        stage[0] = name
    fails += 0 if ok else 1


tmp = tempfile.mkdtemp(prefix="webview-")
vault = os.path.join(tmp, "v")
music = os.path.join(tmp, "가져온 음악")
os.makedirs(vault)
os.makedirs(music)


def tone(name, hz, seconds=3):
    os.makedirs(os.path.dirname(os.path.join(music, name)), exist_ok=True)
    with wave.open(os.path.join(music, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / 8000))) for i in range(8000 * seconds)))


tone("가 첫 곡.wav", 440)
tone("나 #2 곡 100%.wav", 550)      # 주소에서 따로 적어야 하는 글자(#, %, 빈칸)
tone("다 끝 곡.wav", 660)
for n in ("1 노래.wav", "2 노래.wav", "10 노래.wav"):   # 하위 폴더(숫자는 수로 견줘 정렬)
    tone("애니/" + n, 700)
tone("애니/OST/삽입곡.wav", 750)
tone("케이팝/한 곡.wav", 800)
PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
with open(os.path.join(music, "문서 1.pdf"), "wb") as f:
    f.write(PDF)
with open(os.path.join(music, "글.txt"), "w", encoding="utf-8") as f:
    f.write("목록에 끼면 안 되는 글 파일")

os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"root": vault, "imports": {"folders": [{"path": music, "name": "음악"}], "exts": ["pdf", "wav", "txt"], "content": False}}))
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
os.environ["IAT_NO_SINGLE"] = "1"
import winwebview as wv  # noqa: E402

names = [os.path.basename(p) for p in wv.folder_media(os.path.join(music, "나 #2 곡 100%.wav"))]
check("같은 폴더의 소리 파일만 이름 순으로 모은다", names == ["가 첫 곡.wav", "나 #2 곡 100%.wav", "다 끝 곡.wav"])
dirs, tracks, start, base = wv.media_library(os.path.join(music, "애니", "2 노래.wav"))
check("가져온 폴더 밖의 파일은 그 폴더만 목록에 넣는다(하위 폴더도 넣지 않는다)", [d["label"] for d in dirs] == ["애니"] and len(tracks) == 3 and tracks[start]["name"] == "2 노래.wav")
wv.media_roots = lambda: [music]
dirs, tracks, start, base = wv.media_library(os.path.join(music, "애니", "2 노래.wav"))
check("가져온 폴더 안의 파일은 하위 폴더까지 모은다(폴더별, 숫자 순)",
      [d["label"] for d in dirs] == ["가져온 음악", "애니", "애니 / OST", "케이팝"] and [d["rel"] for d in dirs] == ["", "애니", "애니/OST", "케이팝"]
      and [t["name"] for t in tracks if t["dir"] == 1] == ["1 노래.wav", "2 노래.wav", "10 노래.wav"]
      and len(tracks) == 8 and tracks[start]["name"] == "2 노래.wav" and os.path.normcase(base) == os.path.normcase(music))
check("wma·글 파일은 WebView2 로 보지 않는다", not wv.supports("wma") and not wv.supports("txt"))

if not wv.available():
    print("  (이 컴퓨터에는 WebView2 런타임이나 로더가 없어 앱 시험은 건너뜁니다)")
    sys.exit(1 if fails else 0)

import notes  # noqa: E402

app = notes.App()
if os.environ.get("IAT_SHOT"):
    app.root.attributes("-topmost", True)   # 화면을 찍을 때만 맨 위로
stage = ["시작"]
app.root.bind("<Unmap>", lambda e: e.widget is app.root and print("  (창이 화면에서 내려감: %s, '%s' 뒤, 앞 창=%s)" % (app.root.state(), stage[0], ctypes.windll.user32.GetForegroundWindow() == ctypes.windll.user32.GetParent(app.root.winfo_id()))), add="+")


def pump(n=30):
    for _ in range(n):
        app.root.update()
        time.sleep(0.02)


def wait(cond, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        pump(5)
        if cond():
            return True
    return False


def js(code):
    """브라우저 화면에서 스크립트를 돌려 결과(JSON 을 푼 값)를 받는다"""
    got = []
    done = wv._handler("49511172-cc67-4bca-9923-137112f4c4cc", lambda hr, res: got.append(ctypes.wstring_at(res) if res else "null"))
    wv._com(app.pv.web.view, 29, wv.HRESULT, [c_wchar_p, c_void_p], code, done)   # ExecuteScript
    wait(lambda: got, 10)
    return json.loads(got[0]) if got else None


user32 = ctypes.WinDLL("user32")
user32.EnumChildWindows.argtypes = [wintypes.HWND, c_void_p, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, c_wchar_p, c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]


def browser_shown():
    """미리보기 칸 안에 보이는 브라우저 창이 있는가"""
    found = []

    def each(h, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, buf, 64)
        if buf.value.startswith("Chrome_WidgetWin") and user32.IsWindowVisible(h):
            found.append(h)
        return 1
    user32.EnumChildWindows(app.pv_frame.winfo_id(), WINFUNCTYPE(c_int, wintypes.HWND, wintypes.LPARAM)(each), 0)
    return bool(found)


def shot(name):
    d = os.environ.get("IAT_SHOT")
    if not d:
        return
    app.root.lift()
    pump(25)
    x, y, w, h = app.root.winfo_rootx(), app.root.winfo_rooty(), app.root.winfo_width(), app.root.winfo_height()
    ps = ("Add-Type -AssemblyName System.Drawing; $bmp=New-Object System.Drawing.Bitmap %d,%d; "
          "$g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen(%d,%d,0,0,$bmp.Size); $bmp.Save('%s')"
          % (w, h, x, y, os.path.join(d, name).replace("'", "''")))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)


pump(60)
app.docs.scan()
docs = {os.path.basename(d["path"]): d for d in app.docs.list_docs()}
check("가져온 폴더의 파일이 색인됐다", {"가 첫 곡.wav", "나 #2 곡 100%.wav", "다 끝 곡.wav", "문서 1.pdf"} <= set(docs))

# 음악: 재생 목록 화면
app.open_doc(docs["나 #2 곡 100%.wav"])
check("음악 파일을 열면 노트 칸에 원본 보기가 켜진다(WebView2)", app.pv_active and app.pv.using is app.pv.web)
check("브라우저가 만들어진다", wait(lambda: app.pv.web.view))
check("재생 화면이 열린다", wait(lambda: (js("document.querySelectorAll('#list li.t').length") or 0) == 3))
check("브라우저 창이 미리보기 칸 안에 보인다", browser_shown())
check("연 파일이 목록에서 골라져 있다", js("document.querySelector('li.on').textContent") == "나 #2 곡 100%.wav")
check("파일을 읽어 길이를 안다(주소의 #·%·빈칸 처리)", wait(lambda: abs((js("v.duration") or 0) - 3) < 0.2))
check("열기만 해서는 재생하지 않는다", js("v.paused") is True)
shot("music.png")
js("v.muted = true; v.play(); 1")
check("재생된다", wait(lambda: (js("v.currentTime") or 0) > 0.3 and js("v.paused") is False))
js("v.currentTime = 2.8; 1")
check("곡이 끝나면 다음 곡으로 넘어가 이어서 재생한다",
      wait(lambda: js("document.querySelector('li.on').textContent") == "다 끝 곡.wav" and js("v.paused") is False))
js("document.querySelector('#list li.t').click(); 1")
check("목록에서 곡을 누르면 그 곡을 재생한다", wait(lambda: js("document.getElementById('now').textContent") == "가 첫 곡.wav" and (js("v.currentTime") or 0) > 0.1))

# 폴더 고르기·반복·랜덤
now = lambda: js("document.getElementById('now').textContent")  # noqa: E731
names_shown = lambda: js("[...document.querySelectorAll('#list li.t')].map(x => x.textContent)")  # noqa: E731
check("폴더 고르기에 폴더 하나씩, 그리고 하위 폴더까지 묶은 것이 곡 수와 함께 나온다",
      js("[...scopeBox.options].map(o => o.textContent)") == ["가져온 음악 (3곡)", "애니 (3곡)", "애니 / OST (1곡)", "케이팝 (1곡)",
                                                               "가져온 음악 + 하위 폴더 (8곡)", "애니 + 하위 폴더 (4곡)"])
check("처음에는 연 파일의 폴더만 목록에 있다", js("scopeBox.value") == "d:0" and len(names_shown()) == 3)
js("scopeBox.value = 'd:1'; scopeBox.onchange(); 1")
check("다른 폴더를 고르면 그 폴더의 곡이 목록에 나온다", names_shown() == ["1 노래.wav", "2 노래.wav", "10 노래.wav"])
check("폴더를 바꿔도 듣던 곡은 계속 재생된다", now() == "가 첫 곡.wav" and js("v.paused") is False)
js("document.getElementById('next').click(); 1")
check("'다음'을 누르면 고른 폴더의 첫 곡으로 간다", wait(lambda: now() == "1 노래.wav" and js("v.paused") is False))
js("document.querySelectorAll('#list li.t')[2].click(); 1")
wait(lambda: now() == "10 노래.wav" and (js("v.duration") or 0) > 2)
js("v.currentTime = 2.8; 1")
check("반복 안 함: 마지막 곡이 끝나면 멈춘다", wait(lambda: js("v.ended") is True) and now() == "10 노래.wav")
js("repeatBtn.click(); 1")
check("반복 단추를 누르면 '전체 반복'이 된다", js("repeatBtn.textContent") == "전체 반복")
js("v.play(); 1")
wait(lambda: js("v.paused") is False)
js("v.currentTime = 2.8; 1")
check("전체 반복: 마지막 곡이 끝나면 첫 곡으로 돌아가 재생한다", wait(lambda: now() == "1 노래.wav" and js("v.paused") is False))
js("repeatBtn.click(); 1")
check("한 번 더 누르면 '한 곡 반복'이 된다", js("repeatBtn.textContent") == "한 곡 반복" and js("v.loop") is True)
wait(lambda: (js("v.duration") or 0) > 2)
js("v.currentTime = 2.8; 1")
pump(40)
check("한 곡 반복: 곡이 끝나도 같은 곡을 처음부터 다시 재생한다", now() == "1 노래.wav" and js("v.paused") is False and (js("v.currentTime") or 9) < 2.5)
js("repeatBtn.click(); 1")
check("한 번 더 누르면 '반복 안 함'으로 돌아온다", js("repeatBtn.textContent") == "반복 안 함" and js("v.loop") is False)
js("scopeBox.value = 't:애니'; scopeBox.onchange(); 1")
check("'애니 + 하위 폴더'를 고르면 그 아래 폴더의 곡까지만 나온다",
      names_shown() == ["1 노래.wav", "2 노래.wav", "10 노래.wav", "삽입곡.wav"] and js("[...document.querySelectorAll('#list li.h')].map(x => x.textContent)") == ["애니", "애니 / OST"])
app.open_doc(docs["2 노래.wav"])
check("그 범위 안의 다른 파일을 열면 범위가 그대로다", wait(lambda: now() == "2 노래.wav") and js("scopeBox.value") == "t:애니" and len(names_shown()) == 4)
app.open_doc(docs["한 곡.wav"])
check("범위 밖(다른 폴더)의 파일을 열면 그 파일의 폴더만 나온다(다른 폴더와 섞이지 않는다)",
      wait(lambda: now() == "한 곡.wav") and js("scopeBox.value") == "d:3" and names_shown() == ["한 곡.wav"])
js("v.muted = true; scopeBox.value = 't:'; scopeBox.onchange(); 1")
check("'가져온 음악 + 하위 폴더'를 고르면 모든 폴더의 곡이 폴더 이름 줄과 함께 나온다",
      len(names_shown()) == 8 and js("[...document.querySelectorAll('#list li.h')].map(x => x.textContent)") == ["가져온 음악", "애니", "애니 / OST", "케이팝"])
js("shuffleBtn.click(); 1")
check("랜덤을 켜면 지금 곡부터 시작해 모든 곡을 한 번씩 도는 순서가 된다",
      js("shuffle && order.length === 8 && new Set(order).size === 8 && order[0] === cur") is True)
seen = [now()]
for _ in range(7):
    js("document.getElementById('next').click(); 1")
    seen.append(now())
check("랜덤: '다음'으로 8곡을 겹치지 않게 모두 돈다", len(set(seen)) == 8)
js("document.getElementById('next').click(); 1")
check("랜덤 + 반복 안 함: 다 돌면 더 넘어가지 않는다", now() == seen[-1])
js("repeatBtn.click(); document.getElementById('next').click(); 1")
check("랜덤 + 전체 반복: 다 돌면 새로 섞어 이어 간다(같은 곡이 연달아 나오지 않게)", now() != seen[-1] and js("new Set(order).size") == 8)
app.open_doc(docs["삽입곡.wav"])
check("다른 파일을 열어도 랜덤·반복과 (그 파일이 든) 범위 선택이 그대로다",
      wait(lambda: now() == "삽입곡.wav") and js("shuffle") is True and js("repeat") == "all" and js("scopeBox.value") == "t:" and len(names_shown()) == 8)
js("shuffleBtn.click(); repeatBtn.click(); repeatBtn.click(); 1")

# 다른 파일로: pdf
app.open_doc(docs["문서 1.pdf"])
check("pdf 를 열면 같은 브라우저로 보인다", app.pv_active and app.pv.using is app.pv.web)
check("pdf 주소가 열린다", wait(lambda: str(js("location.href") or "").endswith(".pdf")))
check("브라우저 창이 계속 보인다 (창 상태: %s)" % app.root.state(), browser_shown())   # 시험 중에 창을 최소화하면 실패한다
shot("pdf.png")

# 글로 보기 ↔ 원본으로 보기
app.toggle_doc_view()
pump(20)
check("'뽑은 글로 보기'를 누르면 브라우저가 숨는다", not app.pv_active and not browser_shown())
app.toggle_doc_view()
check("'원본으로 보기'를 누르면 다시 보인다", app.pv_active and wait(browser_shown))

# 글 파일은 예전대로 글로
app.open_doc(docs["글.txt"])
pump(20)
check("글 파일은 편집 칸에 글로 보인다", not app.pv_active and not browser_shown())

# 닫기: 재생이 멈추고 창이 숨는다
app.open_doc(docs["가 첫 곡.wav"])
wait(lambda: now() == "가 첫 곡.wav")
js("v.muted = true; v.play(); 1")
wait(lambda: js("v.paused") is False)
app.close_note()
pump(20)
check("노트를 닫으면 브라우저가 숨고 화면이 비워진다(재생 멈춤)",
      not app.pv_active and not browser_shown() and wait(lambda: js("location.href") == "about:blank"))

app.pv.close()
app.root.destroy()
sys.exit(1 if fails else 0)
