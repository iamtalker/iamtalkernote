"""날짜 입력 창: 위의 입력칸에 직접 쓰거나(20260914 · 2026-09-14), 아래 달력에서 날을 눌러 고른다.
새 단추를 늘리지 않으려고 달력은 늘 펼쳐 두고, 날을 누르면 입력칸이 채워진다(더블클릭하면 바로 확인)."""
import datetime
import tkinter as tk

from . import model as M


def ask(parent, colors, ui, title, prompt, initial=""):
    """날짜 글자(입력한 그대로)를 돌려준다. 취소하면 None"""
    C = colors
    d = tk.Toplevel(parent)
    d.title(title)
    d.configure(bg=C["bg"])
    d.transient(parent.winfo_toplevel())
    d.resizable(False, False)
    out = {"v": None}
    tk.Label(d, text=prompt, bg=C["bg"], fg=C["text"], font=(ui, 10), anchor="w", justify="left").pack(fill="x", padx=16, pady=(14, 6))
    var = tk.StringVar(value=initial)
    e = tk.Entry(d, textvariable=var, relief="flat", bd=0, bg=C["panel"], fg=C["text"], insertbackground=C["text"], font=(ui, 11),
                 highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"])
    e.pack(fill="x", padx=16, ipady=4)
    base = M.parse_loose(initial) or M.iso(datetime.date.today())
    cur = M.parse(base) or datetime.date.today()
    st = {"y": cur.year, "m": cur.month}
    head = tk.Frame(d, bg=C["bg"])
    head.pack(fill="x", padx=16, pady=(10, 2))
    title_l = tk.Label(head, text="", bg=C["bg"], fg=C["text"], font=(ui, 10, "bold"))
    grid = tk.Frame(d, bg=C["line"])
    grid.pack(padx=16, pady=(0, 8))
    cells = []

    def shift(step):
        m = st["m"] + step
        st["y"] += (m - 1) // 12
        st["m"] = (m - 1) % 12 + 1
        draw()

    for txt, step in (("◀", -1), ("▶", 1)):
        lb = tk.Label(head, text=txt, bg=C["bg"], fg=C["muted"], cursor="hand2", padx=8)
        lb.bind("<Button-1>", lambda ev, s=step: shift(s))
        lb.pack(side="left")
        if step == -1:
            title_l.pack(side="left", expand=True)
    for c, w in enumerate("일월화수목금토"):
        tk.Label(grid, text=w, width=4, bg=C["panel"], fg=C["danger"] if c == 0 else (C["accent"] if c == 6 else C["muted"]), font=(ui, 9)).grid(
            row=0, column=c, padx=(0, 1), pady=(0, 1), sticky="nsew")
    for i in range(42):
        lb = tk.Label(grid, text="", width=4, bg=C["bg"], fg=C["text"], font=(ui, 10), cursor="hand2", pady=3)
        lb.grid(row=1 + i // 7, column=i % 7, padx=(0, 1), pady=(0, 1), sticky="nsew")
        cells.append(lb)

    def pick(day, confirm=False):
        var.set(M.iso(day))
        draw()
        if confirm:
            ok()

    def draw():
        title_l.config(text=f"{st['y']}년 {st['m']}월")
        days = M.month_grid(st["y"], st["m"])
        chosen = M.parse_loose(var.get())
        today = M.iso(datetime.date.today())
        for lb, day in zip(cells, days):
            s = M.iso(day)
            fg = C["muted"] if day.month != st["m"] else (C["danger"] if day.weekday() == 6 else (C["accent"] if day.weekday() == 5 else C["text"]))
            lb.config(text=str(day.day), fg=fg, bg=C["accent"] if s == chosen else C["bg"],
                      highlightthickness=1, highlightbackground=C["accent"] if s == today else C["bg"])
            if s == chosen:
                lb.config(fg=C.get("on_accent", "#ffffff"))
            lb.bind("<Button-1>", lambda ev, dd=day: pick(dd))
            lb.bind("<Double-Button-1>", lambda ev, dd=day: pick(dd, True))

    def ok(ev=None):
        out["v"] = var.get()
        d.destroy()

    def cancel(ev=None):
        d.destroy()

    def follow(*_):
        v = M.parse_loose(var.get())          # 입력칸에 쓴 날짜로 달력도 따라간다
        if v:
            st["y"], st["m"] = int(v[:4]), int(v[5:7])
        draw()

    var.trace_add("write", follow)
    btns = tk.Frame(d, bg=C["bg"])
    btns.pack(fill="x", padx=16, pady=(0, 14))
    for text, cmd, fg in (("확인", ok, C["accent"]), ("취소", cancel, C["muted"])):
        lb = tk.Label(btns, text=text, bg=C["bg"], fg=fg, font=(ui, 10, "bold" if text == "확인" else "normal"), cursor="hand2", padx=12, pady=4)
        lb.bind("<Button-1>", lambda ev, c=cmd: c())
        lb.pack(side="right")
    d.bind("<Return>", ok)
    d.bind("<Escape>", cancel)
    draw()
    d.update_idletasks()
    x = parent.winfo_toplevel().winfo_rootx() + 80
    y = parent.winfo_toplevel().winfo_rooty() + 80
    d.geometry(f"+{x}+{y}")
    d.grab_set()
    e.focus_set()
    e.select_range(0, "end")
    d.wait_window()
    return out["v"]
