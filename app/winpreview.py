"""윈도 '미리보기 처리기'(탐색기 미리보기 창이 쓰는 것)를 불러와서 파일을 앱 창 안에 그대로 보여 준다.
pdf 는 Edge/Acrobat, mp3 는 Windows Media Player 등 그 확장자에 등록된 프로그램이 직접 그린다(재생 막대·쪽 넘기기도 그 프로그램 것).
표준 라이브러리 ctypes 의 COM 호출만 쓴다. 처리기가 없거나 실패하면 False 를 돌려주니, 부른 쪽은 글 보기로 되돌아간다.
Windows 전용."""
import ctypes
import os
import sys
from ctypes import POINTER, WINFUNCTYPE, byref, c_ubyte, c_ulong, c_ushort, c_void_p, wintypes

IID_PREVIEW = "{8895b1c6-b41f-4c1c-a562-0d564250836f}"      # IPreviewHandler (확장자 아래 ShellEx 키 이름이기도 하다)
IID_INIT_STREAM = "{b824b49d-22ac-4161-ac8a-9916e8fa3f7f}"  # IInitializeWithStream
IID_INIT_FILE = "{b7d14566-0509-4cce-a71f-0a554233bd9b}"    # IInitializeWithFile
IID_INIT_ITEM = "{7f73be3f-fb79-493c-a6c7-7ee14e245841}"    # IInitializeWithItem

if sys.platform == "win32":
    HRESULT = ctypes.HRESULT
    ole32 = ctypes.OleDLL("ole32")
    shlwapi = ctypes.OleDLL("shlwapi")
    shell32 = ctypes.OleDLL("shell32")


class GUID(ctypes.Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]


def guid(s):
    g = GUID()
    ole32.CLSIDFromString(s, byref(g))
    return g


def handler_clsid(ext):
    """확장자(점 없이)에 등록된 미리보기 처리기의 CLSID 문자열. 없으면 None"""
    if sys.platform != "win32":
        return None
    import winreg
    ext = "." + ext.lower().lstrip(".")

    def read(key):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key + "\\ShellEx\\" + IID_PREVIEW) as k:
                return winreg.QueryValueEx(k, "")[0]
        except OSError:
            return None
    clsid = read(ext)
    if clsid is None:   # 확장자가 프로그램 이름(ProgID)을 거쳐 연결된 경우
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as k:
                clsid = read(winreg.QueryValueEx(k, "")[0])
        except OSError:
            pass
    return clsid


def available(ext):
    return handler_clsid(ext) is not None


class Com:
    """COM 객체 포인터 하나. 가상 함수 표(vtable)의 n 번째 함수를 불러 쓴다."""

    def __init__(self, ptr):
        self.ptr = c_void_p(ptr)

    def call(self, index, argtypes, *args, ret=HRESULT if sys.platform == "win32" else None):
        vtbl = ctypes.cast(self.ptr, POINTER(c_void_p))[0]
        fn = ctypes.cast(vtbl, POINTER(c_void_p))[index]
        return WINFUNCTYPE(ret, c_void_p, *argtypes)(fn)(self.ptr, *args)

    def query(self, iid):
        out = c_void_p()
        self.call(0, [POINTER(GUID), POINTER(c_void_p)], byref(guid(iid)), byref(out))
        return Com(out.value)

    def release(self):
        if self.ptr and self.ptr.value:
            try:
                self.call(2, [], ret=c_ulong)
            except Exception:  # noqa: BLE001
                pass
            self.ptr = c_void_p(0)


class Preview:
    """창 하나(HWND) 안에 파일 하나를 미리보기로 띄운다. 쓰고 나면 unload() 로 정리한다."""

    def __init__(self):
        self.handler = None
        self.keep = []   # 초기화에 쓴 스트림 등(미리보기가 떠 있는 동안 살려 둔다)
        self.inited = False

    def show(self, hwnd, path, width, height):
        """성공하면 True. 처리기가 없거나 초기화·그리기에 실패하면 False"""
        self.unload()
        if sys.platform != "win32":
            return False
        ext = os.path.splitext(path)[1]
        clsid = handler_clsid(ext)
        if not clsid:
            return False
        try:
            if not self.inited:
                try:
                    ole32.CoInitializeEx(None, 2)   # 앱 화면 쓰레드는 STA
                except OSError:
                    pass                           # 이미 초기화돼 있음
                self.inited = True
            obj = None
            for ctx in (0x4, 0x17):                # 별도 프로세스(prevhost)에서 먼저, 안 되면 아무 데서나
                out = c_void_p()
                try:
                    ole32.CoCreateInstance(byref(guid(clsid)), None, ctx, byref(guid(IID_PREVIEW)), byref(out))
                    obj = Com(out.value)
                    break
                except OSError:
                    continue
            if obj is None:
                return False
            self.handler = obj
            self._initialize(obj, os.path.abspath(path))
            rect = wintypes.RECT(0, 0, max(width, 10), max(height, 10))
            obj.call(3, [wintypes.HWND, POINTER(wintypes.RECT)], hwnd, byref(rect))   # SetWindow
            obj.call(5, [])                                                          # DoPreview
            return True
        except Exception:  # noqa: BLE001  (처리기가 이상하게 동작해도 앱은 글 보기로 돌아간다)
            self.unload()
            return False

    def _initialize(self, obj, path):
        """처리기가 요구하는 방식(스트림 → 파일)으로 파일을 알려 준다"""
        try:
            init = obj.query(IID_INIT_STREAM)
            stream = c_void_p()
            shlwapi.SHCreateStreamOnFileEx(path, 0x20, 0x80, False, None, byref(stream))   # STGM_READ|SHARE_DENY_WRITE
            s = Com(stream.value)
            self.keep += [init, s]
            init.call(3, [c_void_p, wintypes.DWORD], s.ptr, 0)
            return
        except OSError:
            pass
        init = obj.query(IID_INIT_FILE)
        self.keep.append(init)
        init.call(3, [wintypes.LPCWSTR, wintypes.DWORD], path, 0)

    def resize(self, width, height):
        if self.handler:
            try:
                rect = wintypes.RECT(0, 0, max(width, 10), max(height, 10))
                self.handler.call(4, [POINTER(wintypes.RECT)], byref(rect))   # SetRect
            except Exception:  # noqa: BLE001
                pass

    def unload(self):
        h, self.handler = self.handler, None
        if h:
            try:
                h.call(6, [])   # Unload
            except Exception:  # noqa: BLE001
                pass
            h.release()
        for c in self.keep:
            c.release()
        self.keep = []
