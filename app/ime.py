"""윈도 입력기(IME)가 지금 조합 중인 글자를 알아낸다.
한글을 칠 때 마지막 글자(예: '신이' 의 '이')는 다음 글자를 치거나 방향키로 확정하기 전까지 입력칸의 값에 들어가지 않는다.
자동완성처럼 '치는 즉시' 반응해야 하는 곳에서 그 글자까지 함께 보려고 쓴다. Windows 전용, 실패하면 빈 글을 돌려준다."""
import ctypes
import sys
from ctypes import wintypes

GCS_COMPSTR = 0x0008
NI_COMPOSITIONSTR, CPS_CANCEL = 0x0015, 0x0004

if sys.platform == "win32":
    # 앱의 다른 곳이 쓰는 windll.* 와 인자 형식 설정이 겹치지 않게 이 모듈 전용 핸들을 쓴다
    _imm, _user = ctypes.WinDLL("imm32"), ctypes.WinDLL("user32")
    _user.GetFocus.restype = wintypes.HWND
    _imm.ImmGetContext.argtypes = [wintypes.HWND]
    _imm.ImmGetContext.restype = ctypes.c_void_p
    _imm.ImmReleaseContext.argtypes = [wintypes.HWND, ctypes.c_void_p]
    _imm.ImmGetCompositionStringW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    _imm.ImmGetCompositionStringW.restype = ctypes.c_long
    _imm.ImmNotifyIME.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
    _imm.ImmSetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _imm.ImmSetCompositionFontW.restype = wintypes.BOOL


class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", ctypes.c_long), ("lfWidth", ctypes.c_long), ("lfEscapement", ctypes.c_long), ("lfOrientation", ctypes.c_long),
                ("lfWeight", ctypes.c_long), ("lfItalic", ctypes.c_ubyte), ("lfUnderline", ctypes.c_ubyte), ("lfStrikeOut", ctypes.c_ubyte),
                ("lfCharSet", ctypes.c_ubyte), ("lfOutPrecision", ctypes.c_ubyte), ("lfClipPrecision", ctypes.c_ubyte), ("lfQuality", ctypes.c_ubyte),
                ("lfPitchAndFamily", ctypes.c_ubyte), ("lfFaceName", ctypes.c_wchar * 32)]


def set_font(family, height_px, bold=False):
    """입력기가 조합 중인 글자를 그릴 글꼴을 입력칸과 같게 맞춘다(안 맞추면 입력기 기본 글꼴로 그려져 칠 때 글자가 잠깐 커 보인다).
    height_px 는 음수(글자 높이 픽셀). 성공하면 True"""
    if sys.platform != "win32":
        return False
    try:
        hwnd = _user.GetFocus()
        himc = _imm.ImmGetContext(hwnd) if hwnd else None
        if not himc:
            return False
        try:
            lf = LOGFONTW()
            lf.lfHeight, lf.lfWeight, lf.lfCharSet, lf.lfFaceName = int(height_px), 700 if bold else 400, 1, (family or "")[:31]   # DEFAULT_CHARSET
            return bool(_imm.ImmSetCompositionFontW(himc, ctypes.byref(lf)))
        finally:
            _imm.ImmReleaseContext(hwnd, himc)
    except Exception:  # noqa: BLE001
        return False


def composing():
    """지금 포커스를 가진 칸에서 입력기가 조합 중인 글자('' 이면 없음)"""
    if sys.platform != "win32":
        return ""
    try:
        hwnd = _user.GetFocus()
        himc = _imm.ImmGetContext(hwnd) if hwnd else None
        if not himc:
            return ""
        try:
            n = _imm.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)   # 바이트 수
            if n <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(n // 2 + 1)
            _imm.ImmGetCompositionStringW(himc, GCS_COMPSTR, buf, n)
            return buf.value
        finally:
            _imm.ImmReleaseContext(hwnd, himc)
    except Exception:  # noqa: BLE001
        return ""


def cancel():
    """조합 중인 글자를 버린다(자동완성으로 글을 통째로 바꿀 때, 조합 중이던 글자가 나중에 또 붙지 않게)"""
    if sys.platform != "win32":
        return
    try:
        hwnd = _user.GetFocus()
        himc = _imm.ImmGetContext(hwnd) if hwnd else None
        if himc:
            try:
                _imm.ImmNotifyIME(himc, NI_COMPOSITIONSTR, CPS_CANCEL, 0)
            finally:
                _imm.ImmReleaseContext(hwnd, himc)
    except Exception:  # noqa: BLE001
        pass
