"""화면 캡처 확인 도구: 창 하나를 '그 창 그대로' PNG 로 저장한다(다른 창이 위를 가려도, 사용자 창을 건드리지 않고). 윈도 PrintWindow 사용.

  py -3 -I -X utf8 tools/shot.py app [출력.png] [초]   임시 설정·임시 노트 폴더로 앱을 띄워 몇 초 뒤 창을 찍고 그 프로세스만 끈다
  py -3 -I -X utf8 tools/shot.py hwnd <핸들> [출력.png]   이미 떠 있는 창(핸들)을 찍는다

시험 코드에서:  import shot;  shot.grab(root.winfo_id(), "out.png")   (tk 창은 winfo_id() 의 부모 창을 쓴다 → shot.tk_hwnd(root))
사용자의 실제 노트 폴더·설정은 쓰지 않는다(임시 APPDATA)."""
import ctypes
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def tk_hwnd(root):
    """tk 최상위 창의 실제 윈도 핸들(winfo_id 는 안쪽 창이라 부모를 쓴다)"""
    root.update()
    return user32.GetParent(root.winfo_id()) or root.winfo_id()


def grab(hwnd, path):
    """hwnd 창을 path(PNG)로 저장하고 (너비, 높이)를 돌려준다"""
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        raise OSError("창 크기를 읽을 수 없습니다")
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        raise OSError("창이 보이지 않습니다(최소화)")
    hdc = user32.GetDC(None)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        if not user32.PrintWindow(hwnd, mdc, 2):          # 2 = PW_RENDERFULLCONTENT
            raise OSError("PrintWindow 실패")
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, hdc)
    return w, h


def find_hwnd(pid, timeout=30):
    """프로세스 pid 의 보이는 최상위 창 중 가장 큰 것"""
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            r = wintypes.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            found.append(((r.right - r.left) * (r.bottom - r.top), h))
        return True
    end = time.time() + timeout
    while time.time() < end:
        found.clear()
        user32.EnumWindows(EnumProc(cb), 0)
        if found and max(found)[0] > 100 * 100:
            return max(found)[1]
        time.sleep(0.5)
    raise TimeoutError("앱 창을 찾지 못했습니다")


def shot_app(out, wait=6):
    """임시 APPDATA·임시 노트 폴더로 앱을 띄워 창을 찍는다. 끄는 것은 그 프로세스(PID)만"""
    here = os.path.dirname(os.path.abspath(__file__))
    tmp = tempfile.mkdtemp(prefix="shot-")
    vault = os.path.join(tmp, "vault")
    os.makedirs(os.path.join(vault, "여행"), exist_ok=True)
    os.makedirs(os.path.join(vault, "아웃라이너"), exist_ok=True)
    for name, body in (("회의록.md", "# 회의록\n\n- 안건\n    - 일정\n"), ("여행/제주 계획.md", "3박 4일 렌터카 #여행\n"), ("아웃라이너/계획.md", "- 장보기\n    - 우유\n")):
        with open(os.path.join(vault, name), "w", encoding="utf-8") as f:
            f.write(body)
    appdata = os.path.join(tmp, "appdata")
    os.makedirs(os.path.join(appdata, "iamtalkernote"), exist_ok=True)
    with open(os.path.join(appdata, "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
        f.write('{"root": %s}' % __import__("json").dumps(vault))
    env = dict(os.environ, APPDATA=appdata, IAT_NO_SINGLE="1")  # 한 번에 하나만 실행하는 잠금을 건너뛴다(사용자의 앱을 건드리지 않게)
    p = subprocess.Popen([sys.executable, "-X", "utf8", os.path.join(here, "..", "app", "iamtalkernote.pyw")], env=env)
    try:
        time.sleep(wait)
        hwnd = find_hwnd(p.pid)
        time.sleep(1)
        return grab(hwnd, out)
    finally:
        p.terminate()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "app":
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(tempfile.gettempdir(), "iat-shot.png")
        print(out, shot_app(out, float(sys.argv[3]) if len(sys.argv) > 3 else 6))
    elif mode == "hwnd" and len(sys.argv) > 2:
        out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(tempfile.gettempdir(), "iat-shot.png")
        print(out, grab(int(sys.argv[2]), out))
    else:
        print(__doc__)
