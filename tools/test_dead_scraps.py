"""빈 스크랩의 출처 주소 확인(죽은 글 정리) 시험: py -3 -I -X utf8 tools/test_dead_scraps.py"""
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
tmp = tempfile.mkdtemp(prefix="deadscraps-")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
vault = os.path.join(tmp, "vault")
os.makedirs(vault)

import cleanup  # noqa: E402
import store as st  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path
        if p.startswith("/ok"):
            code, body = 200, b"hello"
        elif p == "/gone":
            code, body = 404, b"x"
        elif p == "/gone410":
            code, body = 410, b"x"
        elif p == "/login":
            code, body = 403, b"x"
        elif p == "/boom":
            code, body = 500, b"x"
        elif p.startswith("/moved"):
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        elif p == "/":
            code, body = 200, b"home"
        else:
            code, body = 404, b"x"
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_HEAD = do_GET

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]

want = {"/ok/1": "alive", "/gone": "dead", "/gone410": "dead", "/login": "blocked", "/boom": "unknown", "/moved/post/123": "dead"}
for path, status in want.items():
    got = cleanup.check_url(base + path, timeout=5)
    check("%s -> %s (got %s)" % (path, status, got), got == status)
check("name that does not resolve is dead", cleanup.check_url("http://no-such-host-zzqx.invalid/a/1", timeout=5) == "dead")
check("unsupported scheme is unknown", cleanup.check_url("ftp://example.com/a", timeout=5) == "unknown")

# 인터넷이 안 되면 아무것도 죽은 것으로 보지 않는다
real_online = cleanup.online
cleanup.online = lambda timeout=6: False
check("offline -> None", cleanup.check_urls([base + "/gone"]) is None)
cleanup.online = lambda timeout=6: True
res = cleanup.check_urls([base + "/ok/1", base + "/gone", base + "/ok/1"])
check("check_urls dedups and maps", res == {base + "/ok/1": "alive", base + "/gone": "dead"})
cleanup.online = real_online

# 창: 확인 → 죽은 빈 노트만 휴지통
try:
    import tkinter as tk
    from tkinter import messagebox
    import embedded
    import notes_shared
    import toolsmenu

    s = st.Store(root=vault)
    notes = []
    for key, path in {"살아있음": "/ok/2", "없어짐": "/gone", "로그인": "/login", "첫화면": "/moved/x/9"}.items():
        p = os.path.join(vault, key + ".md")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("---\nsource: %s%s\n---\n\n" % (base, path))
        notes.append({"nb": "", "title": key, "path": p})
    cleanup._refetchable = lambda url: True   # 시험 서버는 127.0.0.1 이라 '다시 받을 수 없는 주소' 거르기를 끈다
    empties, repaired = cleanup.empty_scraps(notes)
    check("four empty notes found", len(empties) == 4)

    root = tk.Tk()
    root.geometry("900x600+50+50")
    notes_shared.Btn.refresh_kinds()
    asked, trashed = [], []
    messagebox.askyesno = lambda *a, **k: (asked.append(a[1]), True)[1]
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showerror = lambda *a, **k: None

    class Fake(embedded.EmbeddedMixin):
        ui = "Malgun Gothic"
        tool_window = toolsmenu.ToolsMenuMixin.tool_window

        def __init__(self):
            self.root, self.store = root, s

        def run_task(self, title, work, done, text=None, cancellable=True):
            done(work(lambda a, b: None, lambda: False))

        def scan_notes(self, title, work, done):
            done(work(notes, lambda a, b: None, lambda: False))

        def trash_notes(self, paths):
            trashed.extend(os.path.basename(p) for p in paths)
            return len(paths)

        def goto_note(self, p):
            pass

    fake = Fake()
    fake.empty_scraps_dialog((empties, repaired))
    root.update()
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    btns = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, notes_shared.Btn):
                btns.append(c)
            walk(c)
    walk(top)
    btn = next(b for b in btns if b.label.cget("text") == "주소 확인 · 죽은 글 정리")
    btn.command()
    root.update()
    check("asked twice (connect, trash)", len(asked) == 2)
    check("only the gone note and the home-redirect note were trashed", sorted(trashed) == ["없어짐.md", "첫화면.md"])
    # 빈 노트 모두 휴지통으로: 다시 받지 않고 한 번에 정리
    trashed.clear()
    asked.clear()
    btn_all = next(b for b in btns if b.label.cget("text") == "빈 노트 모두 휴지통으로")
    btn_all.command()
    root.update()
    check("trash-all asks once and sends every empty note", len(asked) == 1 and sorted(trashed) == sorted(["없어짐.md", "로그인.md", "살아있음.md", "첫화면.md"]))
    root.destroy()
except Exception as e:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    check("dialog flow: %r" % e, False)

print("FAILS:", fails)
sys.exit(1 if fails else 0)
