"""서식 도구(위키나루 도구줄의 서식 적용·파일 첨부)를 붙이는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import tidytext  # noqa: E402   (글 정리: 줄 앞 공백·여러 빈 줄)

# 글 정리 설명 창의 내용: (메뉴 이름, 하는 일, 바꾸기 전, 바꾼 뒤, 조건). '·' 은 빈칸을 보이게 한 표시다.
TIDY_HELP = [
    ("줄 앞 공백 지우기", "줄 맨 앞의 빈칸을 없앱니다. 들여 쓴 하위 목록과 코드 블록은 그대로 둡니다.",
     "··안녕하세요", "안녕하세요", ""),
    ("줄 끝 공백 지우기", "줄 맨 뒤의 빈칸을 없앱니다.",
     "안녕하세요···\n만나서 반가워요·", "안녕하세요\n만나서 반가워요", ""),
    ("단어 사이 빈칸 줄이기", "단어 사이의 빈칸이 두 칸 이상이면 한 칸으로 줄입니다.",
     "나는····학생이다", "나는 학생이다", ""),
    ("여러 빈 줄을 하나로", "빈 줄이 여러 줄 이어지면 한 줄만 남깁니다.",
     "첫 문단\n\n\n\n둘째 문단", "첫 문단\n\n둘째 문단", ""),
    ("빈 줄 전부 없애기", "모든 빈 줄을 지웁니다. 문단 사이 간격도 없어집니다.",
     "첫 문단\n\n둘째 문단", "첫 문단\n둘째 문단", ""),
    ("같은 내용 삭제", "같은 줄이 다시 나오면 뒤의 것을 지웁니다. 첫 번째 줄은 남깁니다.",
     "사과\n바나나\n사과\n포도", "사과\n바나나\n포도", ""),
    ("문단 줄 잇기", "빈 줄로 나뉜 문단마다 줄을 이어 한 줄로 만듭니다. 제목·표·가로줄·목록은 그대로 둡니다.",
     "오늘은 날씨가\n좋아서 산책했다.\n\n내일은 비가 온다.", "오늘은 날씨가 좋아서 산책했다.\n\n내일은 비가 온다.", ""),
    ("문장마다 빈 줄 넣기", "문단 안에서 붙어 있는 줄 사이에 빈 줄을 넣어, 줄마다 따로 한 문단이 되게 합니다. 제목·표·목록·인용·코드 블록은 그대로 둡니다.",
     "첫 문장이다.\n둘째 문장이다.", "첫 문장이다.\n\n둘째 문장이다.", ""),
    ("고른 줄 합치기", "고른 줄들을 빈 줄 없이 공백 하나로 이어 한 줄로 만듭니다.",
     "가\n나\n다", "가 나 다", "고른 글이 있어야 합니다"),
    ("줄 가나다순 정렬 (오름차순)", "고른 줄을 가나다·abc 순으로 정렬합니다. 빈 줄은 뺍니다.",
     "다\n가\n나", "가\n나\n다", "고른 글이 있어야 합니다"),
    ("줄 가나다순 정렬 (내림차순)", "고른 줄을 거꾸로, 즉 뒤에서부터 순서대로 정렬합니다.",
     "가\n나\n다", "다\n나\n가", "고른 글이 있어야 합니다"),
    ("대문자로", "고른 영문자를 모두 대문자로 바꿉니다.",
     "hello world", "HELLO WORLD", "고른 글이 있어야 합니다"),
    ("소문자로", "고른 영문자를 모두 소문자로 바꿉니다.",
     "Hello World", "hello world", "고른 글이 있어야 합니다"),
]


class FormatToolsMixin:
    # ------------------------------------------------------------ 서식 도구 (위키나루)
    def sel_range(self, whole_lines=False):
        t = self.text
        if t.tag_ranges("sel"):
            a, b = t.index("sel.first"), t.index("sel.last")
        else:
            a = b = t.index("insert")
        if whole_lines:
            if b != a and t.index(f"{b} linestart") == b:   # 줄 맨 앞에서 끝난 선택은 그 줄을 빼기
                b = t.index(f"{b} - 1c")
            a, b = t.index(f"{a} linestart"), t.index(f"{b} lineend")
        return a, b

    def replace(self, a, b, new, s=None, e=None):
        t = self.text
        t.edit_separator()
        t.config(autoseparators=False)   # 지우기+넣기를 되돌리기 한 번으로
        t.delete(a, b)
        t.insert(a, new)
        t.config(autoseparators=True)
        t.edit_separator()
        if s is not None:
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", f"{a}+{s}c", f"{a}+{e}c")
            t.mark_set("insert", f"{a}+{e}c")
        t.focus_set()

    IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")

    def attach_files(self):
        """그림(또는 다른 파일)을 골라 노트에 넣는다: 파일은 리소스 폴더로 복사되고 노트에는 그 상대 경로 링크가 들어간다"""
        if not self.cur or self.doc_open:
            return
        if self.mode == "view":
            self.set_mode("split")
        down = os.path.join(os.path.expanduser("~"), "Downloads")
        paths = filedialog.askopenfilenames(parent=self.root, title=tr("노트에 넣을 그림·파일 고르기"), initialdir=down if os.path.isdir(down) else None,
                                            filetypes=[(tr("그림"), " ".join("*" + e for e in self.IMAGE_EXT)), (tr("모든 파일"), "*.*")])
        if not paths:
            return
        out = []
        for p in paths:
            try:
                rel = self.store.add_media(p, self.cur["nb"]).replace(" ", "%20")
            except OSError as ex:
                messagebox.showerror(APP, tr('파일을 복사하지 못했습니다.\n{0}').format(ex), parent=self.root)
                continue
            base = os.path.basename(p)
            out.append(f"![{os.path.splitext(base)[0]}]({rel})" if p.lower().endswith(self.IMAGE_EXT) else f"[{base}]({rel})")
        if not out:
            return
        a, b = self.sel_range()
        new = "\n".join(out) + "\n"
        self.replace(a, b, new, len(new), len(new))
        self.status.config(text=tr('{0}개를 리소스 폴더로 복사해 넣었습니다').format(len(out)))

    TIDY_NEED_SEL = ("join", "sort", "rsort", "upper", "lower")   # 고른 글이 있어야 하는 것(나머지는 없으면 노트 전체)

    def tidy(self, kind):
        """글 정리(편집 → 글 정리): 고른 줄들, 고른 글이 없으면 노트 전체를 고친다. 되돌리기 한 번으로 돌아온다.
        lead·trail·blank·noblank·spaces·dupes 는 고칠 곳만 지우고(tidytext.OPS), unwrap·join·sort·rsort·upper·lower 는 범위를 통째로 바꾼다."""
        if not self.cur or self.doc_open or self.is_outline_note():
            return
        if self.mode == "view":
            self.set_mode("split")
        t = self.text
        has_sel = bool(t.tag_ranges("sel"))
        if kind in self.TIDY_NEED_SEL and not has_sel:
            self.status.config(text=tr("먼저 바꿀 글을 고르세요"))
            return
        lines = t.get("1.0", "end-1c").split("\n")
        if has_sel:
            a, b = self.sel_range(True)
            lo, hi = int(a.split(".")[0]) - 1, int(b.split(".")[0]) - 1
        else:
            lo, hi = 0, len(lines) - 1
        nothing = tr("고칠 곳이 없습니다")
        if kind in ("upper", "lower"):       # 고른 글자만(코드 블록 안은 그대로)
            a, b = self.sel_range()
            la, ca = (int(x) for x in a.split("."))
            lb, cb = (int(x) for x in b.split("."))
            code = tidytext.fenced(lines)
            edits = []
            for k in range(la, lb + 1):
                ln = lines[k - 1]
                s0 = ca if k == la else 0
                s1 = cb if k == lb else len(ln)
                if code[k - 1] or s1 <= s0:
                    continue
                old = ln[s0:s1]
                new = old.upper() if kind == "upper" else old.lower()
                if new != old:
                    edits.append((k, s0, s1, new))
            if not edits:
                self.status.config(text=nothing)
                return
            t.edit_separator()
            t.config(autoseparators=False)
            try:
                for k, s0, s1, new in reversed(edits):   # 아래에서 위로: 앞쪽 칸 번호가 안 밀린다
                    t.delete(f"{k}.{s0}", f"{k}.{s1}")
                    t.insert(f"{k}.{s0}", new)
            finally:
                t.config(autoseparators=True)
                t.edit_separator()
            t.tag_remove("sel", "1.0", "end")   # 고른 글은 그대로 골라 둔다(이어서 다른 변환을 할 수 있게)
            t.tag_add("sel", a, b)
            t.focus_set()
            self.status.config(text=tr("바꿨습니다"))
            return
        if kind in ("unwrap", "split", "join", "sort", "rsort"):   # 줄들을 통째로(코드 블록 줄은 제자리에)
            part = lines[lo:hi + 1]
            if kind == "unwrap":
                out = tidytext.unwrap(lines, lo, hi)
            elif kind == "split":
                out = tidytext.space_paras(lines, lo, hi)
            elif kind == "join":
                out = tidytext.outside_code(lines, lo, hi, lambda run: [tidytext.join_lines(run)])
            else:
                out = tidytext.outside_code(lines, lo, hi, lambda run: tidytext.sort_lines(run, kind == "rsort"))
            if out == part:
                self.status.config(text=nothing)
                return
            new = "\n".join(out)
            a, b = f"{lo + 1}.0", f"{hi + 1}.end"
            if has_sel:
                self.replace(a, b, new, 0, len(new))
            else:
                self.replace(a, b, new)
                t.mark_set("insert", "1.0")
                t.see("insert")
            self.status.config(text=tr("{0}줄을 {1}줄로 바꿨습니다").format(len(part), len(out)))
            return
        kept = 0
        if kind == "lead":
            ops, kept = tidytext.leading_ops(lines, lo, hi)
        else:
            ops = tidytext.OPS[kind](lines, lo, hi)
        note = tr(" (목록·코드 블록 {0}줄은 그대로)").format(kept) if kept else ""
        if not ops:
            self.status.config(text=nothing + note)
            return
        t.edit_separator()
        t.config(autoseparators=False)   # 여러 군데를 고쳐도 되돌리기 한 번으로
        try:
            for i, c, j, d, new in sorted(ops, reverse=True):   # 아래에서 위로: 앞쪽 줄·칸 번호가 안 밀린다
                t.delete(f"{i + 1}.{c}", f"{j + 1}.{d}")
                if new:
                    t.insert(f"{i + 1}.{c}", new)
        finally:
            t.config(autoseparators=True)
            t.edit_separator()
        t.see("insert")
        t.focus_set()
        self.status.config(text=tr("{0}곳을 고쳤습니다").format(len(ops)) + note)

    def show_tidy_help(self):
        """글 정리 메뉴의 '설명 보기…': 항목마다 하는 일과 바꾸기 전·후 예시를 보여 준다(읽기 전용)"""
        top = self.tool_window(tr("글 정리 설명"), "700x640")
        box = tk.Frame(top, bg=C["bg"])
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        sb = tk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        t = tk.Text(box, wrap="word", bg=C["bg"], fg=C["text"], font=(self.ui, 10), relief="flat",
                    padx=6, pady=6, yscrollcommand=sb.set, cursor="arrow")
        t.pack(side="left", fill="both", expand=True)
        sb.config(command=t.yview)
        t.tag_configure("title", font=(self.ui, 11, "bold"), spacing1=12)
        t.tag_configure("ex", font=("Consolas", 10), lmargin1=18, lmargin2=18)
        t.tag_configure("note", font=(self.ui, 9, "italic"), foreground=C["muted"])
        t.tag_configure("lab_do", font=(self.ui, 10, "bold"), foreground=C["accent"])
        t.tag_configure("lab_before", font=(self.ui, 10, "bold"), foreground="#b91c1c")
        t.tag_configure("lab_after", font=(self.ui, 10, "bold"), foreground="#15803d")
        t.tag_configure("ex_before", font=("Consolas", 10), lmargin1=18, lmargin2=18, background="#fef2f2")
        t.tag_configure("ex_after", font=("Consolas", 10), lmargin1=18, lmargin2=18, background="#f0fdf4")
        t.insert("end", tr("메뉴 「글 정리」 항목별 설명입니다. 편집 칸에서 줄을 골라 두면 그 줄만 고치고, 고른 글이 없으면 노트 전체를 고칩니다. '·' 은 빈칸을 보이게 한 표시입니다.") + "\n")
        for name, what, before, after, cond in TIDY_HELP:
            t.insert("end", "\n" + name + "\n", "title")
            t.insert("end", tr("하는 일") + ": ", "lab_do")
            t.insert("end", what + "\n")
            if cond:
                t.insert("end", tr(cond) + "\n", "note")
            t.insert("end", tr("바꾸기 전") + ":\n", "lab_before")
            t.insert("end", before + "\n", "ex_before")
            t.insert("end", tr("바꾼 뒤") + ":\n", "lab_after")
            t.insert("end", after + "\n", "ex_after")
        t.config(state="disabled")
        Btn(top, tr("닫기"), top.destroy, padx=14, pady=3).pack(pady=(0, 12))

    def run_action(self, action):
        if not self.cur:
            return
        if self.mode == "view":
            self.set_mode("split")
        kind, *rest = action
        arg = rest[0] if rest else None
        if kind == "wrap":
            before, after, default = WRAP_X.get(arg) or (*ed.WRAP[FMT][arg], ed.WRAP_DEFAULT[arg])
            a, b = self.sel_range()
            new, s, e = ed.wrap_text(self.text.get(a, b), before, after, default)
            self.replace(a, b, new, s, e)
        elif kind == "line":
            spec = LINE_X.get(arg) or ed.LINE[FMT][arg]
            holder = PLACEHOLDER_X.get(arg) or ed.PLACEHOLDER[arg]
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if not any(ln.strip() for ln in lines):   # 빈 줄: 표시와 자리 글을 넣고 그 글을 골라 둔다
                head = spec[0].format(n=1)
                new = "\n".join([head + holder] + lines[1:])
                self.replace(a, b, new, len(head), len(head) + len(holder))
            else:
                new = "\n".join(ed.toggle_prefix(lines, *spec))
                self.replace(a, b, new, 0, len(new))
        elif kind == "heading":
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if arg > 0 and not any(ln.strip() for ln in lines):
                new = ed.set_heading("제목", arg, FMT)
                s = new.index("제목")
                self.replace(a, b, new, s, s + 2)
            else:
                new = "\n".join(ed.set_heading(ln, arg, FMT) if ln.strip() else ln for ln in lines)
                self.replace(a, b, new, 0, len(new))
        elif kind == "indent":
            a, b = self.sel_range(True)
            lines = self.text.get(a, b).split("\n")
            if arg > 0:
                new = "\n".join(("  " + ln) if ln.strip() else ln for ln in lines)
            else:
                new = "\n".join(re.sub(r"^(  |\t)", "", ln, count=1) for ln in lines)
            self.replace(a, b, new, 0, len(new))
        elif kind == "tpl":
            tpl, default = TPL[arg]
            a, b = self.sel_range()
            sel = self.text.get(a, b)
            line_empty = not self.text.get(f"{a} linestart", f"{a} lineend").strip()
            body = sel or default
            out = tpl.replace("{}", body, 1)
            at_a, at_b, pre = (a, b, "") if (sel or line_empty) else (self.text.index(f"{a} lineend"),) * 2 + ("\n\n",)
            if "{}" in tpl and body:
                s0 = len(pre) + out.index(body)
                self.replace(at_a, at_b, pre + out + ("" if sel else "\n"), s0, s0 + len(body))
            else:
                self.replace(at_a, at_b, pre + out + ("" if sel else "\n"))
        elif kind == "datetime":
            self.insert_datetime()
        elif kind == "footnote":
            t = self.text
            nums = [int(x) for x in re.findall(r"\[\^(\d+)\]", t.get("1.0", "end-1c"))]
            n = (max(nums) + 1) if nums else 1
            t.edit_separator()
            t.insert("insert", f"[^{n}]")
            whole = t.get("1.0", "end-1c")
            tail = "" if whole.endswith("\n\n") else ("\n" if whole.endswith("\n") else "\n\n")
            t.insert("end-1c", f"{tail}[^{n}]: 각주 내용")
            end = t.index("end-1c")
            t.edit_separator()
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", f"{end} - 5c", end)
            t.mark_set("insert", end)
            t.see(end)
            t.focus_set()
        elif kind == "block":
            if arg == "codeblock":
                a, b = self.sel_range()
                body = self.text.get(a, b) or "코드"
                self.replace(a, b, ed.BLOCK["codeblock"][FMT].replace("{}", body, 1))
            else:
                a, _ = self.sel_range()
                at = self.text.index(f"{a} lineend")
                empty = not self.text.get(f"{a} linestart", at).strip()
                self.replace(at, at, ("" if empty else "\n\n") + ed.BLOCK[arg][FMT] + "\n")
