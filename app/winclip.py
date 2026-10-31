"""윈도 클립보드의 HTML 형식('HTML Format') 읽기·쓰기.

웹 페이지의 표·서식 글은 클립보드에 글자만 있는 형식과 HTML 형식이 함께 담긴다. Tk Text 의 복사·붙여넣기는 글자만 다루므로,
표를 웹 에디터에 붙이거나(복사) 웹의 표를 노트로 붙이려면(붙여넣기) 이 형식을 직접 다뤄야 한다. 윈도 전용(다른 운영체제에서는 아무것도 안 한다)."""
import re
import sys

START, END = "<!--StartFragment-->", "<!--EndFragment-->"
CF_UNICODETEXT = 13


def fragment_of(data):
    """'HTML Format' 바이트 → 복사한 부분의 HTML 글(UTF-8). 머리의 StartFragment·EndFragment 위치나 주석 표시로 자른다"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    data = data.split(b"\x00", 1)[0]
    text = data.decode("utf-8", "replace")
    a, b = text.find(START), text.find(END)
    if a >= 0 and b > a:
        return text[a + len(START):b]
    m1, m2 = re.search(rb"StartFragment:(\d+)", data), re.search(rb"EndFragment:(\d+)", data)
    if m1 and m2 and int(m2.group(1)) > int(m1.group(1)):
        return data[int(m1.group(1)):int(m2.group(1))].decode("utf-8", "replace")
    i = text.lower().find("<html")
    return text[i:] if i >= 0 else text


def cf_html(fragment):
    """HTML 조각 → 'HTML Format' 바이트(UTF-8, 머리의 위치는 바이트 단위 10자리)"""
    pre, post = "<html><body>\r\n" + START, END + "\r\n</body></html>"
    head = "Version:0.9\r\nStartHTML:%010d\r\nEndHTML:%010d\r\nStartFragment:%010d\r\nEndFragment:%010d\r\n"
    n = len(head % (0, 0, 0, 0))
    b_pre, b_frag, b_post = (x.encode("utf-8") for x in (pre, fragment, post))
    sh = n
    sf = sh + len(b_pre)
    ef = sf + len(b_frag)
    eh = ef + len(b_post)
    return (head % (sh, eh, sf, ef)).encode("ascii") + b_pre + b_frag + b_post


def _api():
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    u32.RegisterClipboardFormatW.restype = wintypes.UINT
    u32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    u32.GetClipboardData.argtypes = [wintypes.UINT]
    u32.GetClipboardData.restype = wintypes.HANDLE
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.SetClipboardData.restype = wintypes.HANDLE
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalAlloc.restype = wintypes.HANDLE
    k32.GlobalLock.argtypes = [wintypes.HANDLE]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalSize.argtypes = [wintypes.HANDLE]
    k32.GlobalSize.restype = ctypes.c_size_t
    k32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    return ctypes, u32, k32


def _open(u32):
    import time
    for _ in range(6):                       # 다른 프로그램이 클립보드를 잠시 쥐고 있을 수 있다
        if u32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_html():
    """클립보드의 HTML 조각(없으면 None)"""
    if sys.platform != "win32":
        return None
    ctypes, u32, k32 = _api()
    fmt = u32.RegisterClipboardFormatW("HTML Format")
    if not fmt or not u32.IsClipboardFormatAvailable(fmt) or not _open(u32):
        return None
    try:
        h = u32.GetClipboardData(fmt)
        p = k32.GlobalLock(h) if h else None
        if not p:
            return None
        try:
            data = ctypes.string_at(p, k32.GlobalSize(h))
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()
    return fragment_of(data)


def _put(ctypes, u32, k32, fmt, data):
    h = k32.GlobalAlloc(0x0002, len(data))      # GMEM_MOVEABLE
    p = k32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    return bool(u32.SetClipboardData(fmt, h))   # 성공하면 클립보드가 메모리를 넘겨받는다


def set_text_html(plain, fragment):
    """클립보드에 글자(CF_UNICODETEXT)와 HTML 형식을 함께 넣는다 → 성공 여부"""
    if sys.platform != "win32":
        return False
    ctypes, u32, k32 = _api()
    fmt = u32.RegisterClipboardFormatW("HTML Format")
    if not fmt or not _open(u32):
        return False
    try:
        u32.EmptyClipboard()
        ok = _put(ctypes, u32, k32, CF_UNICODETEXT, (plain.replace("\r\n", "\n").replace("\n", "\r\n") + "\0").encode("utf-16-le"))
        ok = _put(ctypes, u32, k32, fmt, cf_html(fragment) + b"\0") and ok
        return ok
    finally:
        u32.CloseClipboard()
