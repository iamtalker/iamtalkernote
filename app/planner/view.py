"""달력·할일·공수 화면: 위에 달력(공휴일 표시), 아래에 할일 목록, 맨 아래에 이 달의 공수 요약(공수달력을 켰을 때)."""
import datetime
import tkinter as tk
from tkinter import simpledialog, ttk

from . import model as M

WEEK = "일월화수목금토"


class PlannerView(tk.Frame):
    def __init__(self, master, colors, ui, planner, get_cfg, set_cfg=None):
        """get_cfg() → {'gongsu': bool, 'wage': 원, 'meal': 원} (설정에서 읽는다). set_cfg(키, 값) 은 달력 위의 단가·일비 칸에서 고친 값을 설정에 적는다"""
        super().__init__(master, bg=colors["bg"])
        self.C, self.ui, self.pl, self.get_cfg, self.set_cfg = colors, ui, planner, get_cfg, set_cfg
        today = datetime.date.today()
        self.year, self.month, self.sel = today.year, today.month, M.iso(today)
        self.only_sel = tk.BooleanVar(value=False)
        self.cells = []
        C = colors
        head = tk.Frame(self, bg=C["bg"])
        head.pack(fill="x", padx=18, pady=(14, 6))
        for text, step in (("◀", -1), ("▶", 1)):
            b = tk.Label(head, text=text, bg=C["bg"], fg=C["muted"], font=(ui, 12), cursor="hand2", padx=8)
            b.bind("<Button-1>", lambda e, s=step: self.shift(s))
            b.pack(side="left")
            if step == -1:
                self.title = tk.Label(head, text="", bg=C["bg"], fg=C["text"], font=(ui, 14, "bold"), width=11)
                self.title.pack(side="left")
        today_b = tk.Label(head, text="오늘", bg=C["bg"], fg=C["accent"], font=(ui, 10), cursor="hand2", padx=10)
        today_b.bind("<Button-1>", lambda e: self.goto(datetime.date.today()))
        today_b.pack(side="left")
        self.rate = tk.Frame(self, bg=C["bg"])         # 공수달력을 켰을 때만: 단가·일비를 달력에서 바로 입력
        self.rate_vars = {}
        for key, label in (("wage", "단가(1공수)"), ("meal", "일비(하루)")):
            tk.Label(self.rate, text=label, bg=C["bg"], fg=C["muted"], font=(ui, 9)).pack(side="left", padx=(0, 4))
            var = tk.StringVar()
            e = tk.Entry(self.rate, textvariable=var, width=10, justify="right", relief="flat", bd=0, bg=C["panel"], fg=C["text"], insertbackground=C["text"],
                         highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"], font=(ui, 10))
            e.pack(side="left", ipady=3)
            tk.Label(self.rate, text="원", bg=C["bg"], fg=C["muted"], font=(ui, 9)).pack(side="left", padx=(2, 14))
            e.bind("<Return>", lambda ev, k=key: self.save_rate(k))
            e.bind("<FocusOut>", lambda ev, k=key: self.save_rate(k))
            self.rate_vars[key] = var
        self.sumlab = tk.Label(self, text="", bg=C["bg"], fg=C["text"], font=(ui, 10), anchor="w", justify="left", padx=18)
        self.sumlab.pack(fill="x")
        bottom = tk.Frame(self, bg=C["bg"])            # 할일 입력칸·목록은 창이 낮아도 가려지지 않게 먼저 아래에 자리를 잡는다(달력이 남는 만큼만 쓴다)
        bottom.pack(side="bottom", fill="x")
        grid = tk.Frame(self, bg=C["line"])
        grid.pack(fill="both", expand=True, padx=18, pady=(8, 0))
        for c in range(7):
            grid.grid_columnconfigure(c, weight=1, uniform="d")
            tk.Label(grid, text=WEEK[c], bg=C["panel"], fg=C["danger"] if c == 0 else (C["accent"] if c == 6 else C["muted"]),
                     font=(ui, 9)).grid(row=0, column=c, sticky="nsew", padx=(0, 1), pady=(0, 1))
        for i in range(42):
            lb = tk.Label(grid, text="", bg=C["bg"], fg=C["text"], font=(ui, 9), anchor="nw", justify="left", padx=4, pady=2, height=3, cursor="hand2",
                          highlightthickness=1, highlightbackground=C["bg"])
            lb.grid(row=1 + i // 7, column=i % 7, sticky="nsew", padx=(0, 1), pady=(0, 1))
            lb.bind("<Button-1>", lambda e, i=i: self.click(i, e))
            self.cells.append(lb)
        mid = tk.Frame(bottom, bg=C["bg"])
        mid.pack(fill="x", padx=18, pady=(12, 4))
        tk.Label(mid, text="할일", bg=C["bg"], fg=C["text"], font=(ui, 11, "bold")).pack(side="left")
        tk.Checkbutton(mid, text="선택한 날만", variable=self.only_sel, command=self.draw_todos, bg=C["bg"], activebackground=C["bg"],
                       selectcolor=C["bg"], font=(ui, 9), fg=C["muted"]).pack(side="right")
        bar = tk.Frame(bottom, bg=C["bg"])
        bar.pack(fill="x", padx=18)
        self.entry = tk.Entry(bar, relief="flat", bd=0, bg=C["panel"], fg=C["text"], insertbackground=C["text"], font=(ui, 10),
                              highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["accent"])
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry.bind("<Return>", lambda e: self.add_undated())
        for text, fn in (("추가", self.add_undated), ("선택한 날짜로", self.give_date), ("날짜 없애기", self.clear_date), ("삭제", self.delete)):
            b = tk.Label(bar, text=text, bg=C["panel"], fg=C["text"], font=(ui, 9), cursor="hand2", padx=8, pady=5)
            b.bind("<Button-1>", lambda e, fn=fn: fn())
            b.pack(side="left", padx=(6, 0))
        wrap = tk.Frame(bottom, bg=C["bg"])
        wrap.pack(fill="x", padx=18, pady=(6, 14))
        self.tree = ttk.Treeview(wrap, style="Flat.Treeview", columns=("date",), show="tree", selectmode="browse", height=6)
        self.tree.column("#0", stretch=True, width=300)
        self.tree.column("date", width=90, anchor="e", stretch=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("done", foreground=C["muted"])
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.refresh()

    # ---- 달력
    def shift(self, step):
        m = self.month + step
        self.year += (m - 1) // 12
        self.month = (m - 1) % 12 + 1
        self.refresh()

    def goto(self, d):
        self.year, self.month, self.sel = d.year, d.month, M.iso(d)
        self.refresh()

    def refresh(self):
        C, cfg = self.C, self.get_cfg()
        self.title.config(text=f"{self.year}년 {self.month}월")
        hol = {**self.pl.holidays_for(self.year - 1), **self.pl.holidays_for(self.year), **self.pl.holidays_for(self.year + 1)}
        today = M.iso(datetime.date.today())
        days = M.month_grid(self.year, self.month)
        self.days = days
        for lb, d in zip(self.cells, days):
            s = M.iso(d)
            red = d.weekday() == 6 or s in hol
            fg = C["danger"] if red else (C["accent"] if d.weekday() == 5 else C["text"])
            if d.month != self.month:
                fg = C["muted"]
            lines = [str(d.day) + (" " + hol[s] if s in hol else "")]
            todos = [t for t in self.pl.on(s) if not t["done"]]
            if todos:
                lines.append("● " + (todos[0]["text"][:6] + ("…" if len(todos[0]["text"]) > 6 or len(todos) > 1 else "")))
            if cfg["gongsu"] and s in self.pl.gongsu:
                lines.append("공수 " + M.fmt_gongsu(self.pl.gongsu[s]))
            lb.config(text="\n".join(lines), fg=fg, bg=C["soft"] if s == self.sel else C["bg"],
                      highlightbackground=C["accent"] if s == today else (C["soft"] if s == self.sel else C["bg"]))
        if cfg["gongsu"]:
            if not self.rate.winfo_ismapped():
                self.rate.pack(fill="x", padx=18, pady=(0, 4), before=self.sumlab)
            for k in ("wage", "meal"):
                if self.focus_get() is not None and str(self.focus_get()).startswith(str(self.rate)):
                    break                                  # 입력 중이면 칸을 덮어쓰지 않는다
                self.rate_vars[k].set(f"{cfg[k]:,}" if cfg[k] else "")
            r = self.pl.summary(self.year, self.month, cfg["wage"], cfg["meal"])
            self.sumlab.config(text=(f"공수 합계 {M.fmt_gongsu(r['gongsu'])}  ·  출근 {r['days']}일  ·  일당 {r['pay']:,}원  +  일비 {r['meal']:,}원"
                                     f"  =  총 {r['sum']:,}원"))
        else:
            self.rate.pack_forget()
            self.sumlab.config(text="")
        self.draw_todos()

    def save_rate(self, key):
        s = self.rate_vars[key].get().replace(",", "").strip()
        try:
            v = int(float(s)) if s else 0
        except ValueError:
            return
        if self.set_cfg and self.get_cfg()[key] != v:
            self.set_cfg(key, v)
            self.refresh()

    def click(self, i, e):
        d = self.days[i]
        self.sel = M.iso(d)
        if (d.year, d.month) != (self.year, self.month):
            self.year, self.month = d.year, d.month
        self.refresh()
        cfg = self.get_cfg()
        m = tk.Menu(self, tearoff=0)
        if cfg["gongsu"]:
            for v in ("0.5", "1", "1.5", "2"):
                m.add_command(label=f"공수 {v}", command=lambda v=v: self.set_gongsu(float(v)))
            m.add_command(label="공수 직접 입력…", command=self.ask_gongsu)
            m.add_command(label="공수 지우기", command=lambda: self.set_gongsu(0))
            m.add_separator()
        m.add_command(label="이 날 할일 추가…", command=self.add_dated)
        m.tk_popup(e.x_root, e.y_root)

    def set_gongsu(self, v):
        self.pl.set_gongsu(self.sel, v)
        self.refresh()

    def ask_gongsu(self):
        s = simpledialog.askstring("공수", f"{self.sel} 공수(예: 1, 1.5, 2)", parent=self)
        try:
            if s:
                self.set_gongsu(float(s))
        except ValueError:
            pass

    def add_dated(self):
        s = simpledialog.askstring("할일", f"{self.sel} 할일", parent=self)
        if s and self.pl.add(s, self.sel):
            self.refresh()

    # ---- 할일
    def draw_todos(self):
        self.tree.delete(*self.tree.get_children())
        for t in self.pl.ordered(self.sel if self.only_sel.get() else None):
            self.tree.insert("", "end", iid=t["id"], text=("☑  " if t["done"] else "☐  ") + t["text"], values=(t.get("date") or "",),
                             tags=("done",) if t["done"] else ())

    def on_tree_click(self, e):
        row = self.tree.identify_row(e.y)
        if row and self.tree.identify_region(e.x, e.y) == "tree" and e.x < 40:     # 앞의 체크 칸을 누르면 완료 토글
            t = self.pl.find(row)
            if t:
                self.pl.update(row, done=not t["done"])
                self.refresh()

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def add_undated(self):
        text = self.entry.get()
        if self.pl.add(text):
            self.entry.delete(0, "end")
            self.refresh()

    def give_date(self):
        tid = self.selected()
        if tid:
            self.pl.update(tid, date=self.sel)
            self.refresh()

    def clear_date(self):
        tid = self.selected()
        if tid:
            self.pl.update(tid, date=None)
            self.refresh()

    def delete(self):
        tid = self.selected()
        if tid:
            self.pl.remove(tid)
            self.refresh()
