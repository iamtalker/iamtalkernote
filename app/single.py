"""앱을 한 번에 하나만 실행한다. 이미 실행 중(창이 열려 있거나 트레이에 들어가 있음)이면 두 번째 실행은 아무것도 열지 않고,
실행 중인 앱에 "창을 열어 달라"는 신호만 보내고 끝난다. 이름 붙은 뮤텍스(실행 중인지 표시)와 이름 붙은 이벤트(신호)를 쓴다.
Windows 전용(다른 운영체제에서는 항상 첫 번째 실행으로 본다)."""
import ctypes
import sys
from ctypes import wintypes

MUTEX = "Local\\iamtalkernote.single"      # Local\ = 같은 윈도 로그인 세션 안에서만
EVENT = "Local\\iamtalkernote.show"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002

_mutex = _event = None   # 앱이 끝날 때까지 핸들을 살려 둔다(프로세스가 끝나면 윈도가 알아서 풀어 준다)

if sys.platform == "win32":
    _k = ctypes.WinDLL("kernel32", use_last_error=True)
    _u = ctypes.WinDLL("user32")
    _k.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    _k.CreateMutexW.restype = wintypes.HANDLE
    _k.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    _k.CreateEventW.restype = wintypes.HANDLE
    _k.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _k.OpenEventW.restype = wintypes.HANDLE
    _k.SetEvent.argtypes = [wintypes.HANDLE]
    _k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k.WaitForSingleObject.restype = wintypes.DWORD
    _k.CloseHandle.argtypes = [wintypes.HANDLE]
    _u.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]


def acquire():
    """첫 번째 실행이면 True(이후 signaled() 로 신호를 받는다). 이미 실행 중이면 그 앱에 신호를 보내고 False"""
    global _mutex, _event
    if sys.platform != "win32":
        return True
    ctypes.set_last_error(0)
    _mutex = _k.CreateMutexW(None, False, MUTEX)
    if _mutex and ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        _event = _k.CreateEventW(None, False, False, EVENT)   # 자동 초기화: 신호를 한 번 받으면 꺼진다
        return True
    if _mutex is None:   # 뮤텍스를 못 만들면 막지 않는다(앱이 아예 안 켜지는 것보다 낫다)
        return True
    ev = _k.OpenEventW(EVENT_MODIFY_STATE, False, EVENT)
    if ev:
        _u.AllowSetForegroundWindow(0xFFFFFFFF)   # 실행 중인 앱이 창을 앞으로 가져올 수 있게 허락한다(ASFW_ANY)
        _k.SetEvent(ev)
        _k.CloseHandle(ev)
    return False


def signaled():
    """다른 쪽에서 '창을 열어 달라'고 신호를 보냈으면 True(한 번 확인하면 꺼진다)"""
    if sys.platform != "win32" or not _event:
        return False
    return _k.WaitForSingleObject(_event, 0) == 0
