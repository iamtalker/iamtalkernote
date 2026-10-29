"""작업표시줄 오른쪽 아래 알림 영역(트레이)의 아이콘. 창의 X 버튼을 누르면 앱을 끄지 않고 여기로 들어간다.
외부 라이브러리 없이 ctypes 로 숨은 창 + Shell_NotifyIcon 을 쓴다. 아이콘 클릭·메뉴 선택은 별도 쓰레드에서 일어나므로
on_event("show" | "quit") 를 부르는 대신 큐에 넣어 두고, 앱 화면 쪽이 주기적으로 꺼내 쓴다.
Windows 전용."""
import ctypes
import queue
import sys
import threading
from ctypes import wintypes

WM_USER_TRAY = 0x0401
WM_CLOSE, WM_NULL, WM_DESTROY = 0x0010, 0x0000, 0x0002
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
NIM_ADD, NIM_DELETE = 0, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
MF_STRING, MF_SEPARATOR = 0, 0x800
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
ID_SHOW, ID_QUIT = 1001, 1002
LRESULT = ctypes.c_ssize_t

if sys.platform == "win32":
    # 앱의 다른 곳이 쓰는 windll.* 와 함수 객체(인자 형식 설정)를 공유하지 않도록 이 모듈 전용 핸들을 따로 만든다
    user32, shell32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("shell32"), ctypes.WinDLL("kernel32")
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterClassW.argtypes = [ctypes.c_void_p]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.LoadImageW.restype = wintypes.HANDLE
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC if sys.platform == "win32" else ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class Tray:
    """아이콘 하나. start() 로 보이고 stop() 으로 지운다. 눌린 것은 events 큐에 "show" / "quit" 로 쌓인다."""

    def __init__(self, icon_path, tip, labels=("열기", "종료")):
        self.icon_path, self.tip, self.labels = icon_path, tip, labels
        self.events = queue.Queue()
        self.hwnd = None
        self.thread = None
        self.ready = threading.Event()
        self.ok = False

    def start(self):
        """아이콘을 보인다 → 성공 여부(실패하면 부른 쪽이 그냥 작업표시줄로 최소화한다)"""
        if sys.platform != "win32":
            return False
        if self.thread and self.thread.is_alive():
            return self.ok
        self.ready.clear()
        self.ok = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.ready.wait(3)
        return self.ok

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self.thread:
            self.thread.join(2)
        self.hwnd = None

    def _menu(self, hwnd):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_SHOW, self.labels[0])
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, self.labels[1])
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)   # 이걸 안 하면 메뉴 밖을 눌러도 메뉴가 안 닫힌다
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if cmd == ID_SHOW:
            self.events.put("show")
        elif cmd == ID_QUIT:
            self.events.put("quit")

    def _run(self):
        def proc(hwnd, msg, wparam, lparam):
            if msg == WM_USER_TRAY:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.events.put("show")
                elif lparam == WM_RBUTTONUP:
                    self._menu(hwnd)
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._proc = WNDPROC(proc)   # 쓰는 동안 살려 둔다
        try:
            inst = kernel32.GetModuleHandleW(None)
            cls = WNDCLASS()
            cls.lpfnWndProc, cls.hInstance, cls.lpszClassName = self._proc, inst, "iamtalkernote_tray"
            user32.UnregisterClassW("iamtalkernote_tray", inst)   # 앞에서 쓴 창 종류가 해제된 콜백을 가리킨 채 남아 있으면 안 된다
            user32.RegisterClassW(ctypes.byref(cls))
            self.hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "iamtalkernote_tray", 0, 0, 0, 0, 0, wintypes.HWND(-3), None, inst, None)   # -3 = 메시지 전용 창
            if not self.hwnd:
                self.err = ctypes.get_last_error() or kernel32.GetLastError()
            if not self.hwnd:
                return
            icon = user32.LoadImageW(None, self.icon_path, 1, 16, 16, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd, nid.uID, nid.uFlags = self.hwnd, 1, NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage, nid.hIcon, nid.szTip = WM_USER_TRAY, icon, self.tip[:127]
            self.ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
            self.ready.set()
            if self.ok:
                msg = wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        finally:
            try:
                user32.UnregisterClassW("iamtalkernote_tray", kernel32.GetModuleHandleW(None))
            except Exception:  # noqa: BLE001
                pass
            self.ready.set()
