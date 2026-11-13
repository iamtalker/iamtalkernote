"""서식 도구(위키나루 도구줄의 서식 적용·파일 첨부)를 붙이는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import tidytext  # noqa: E402   (글 정리: 줄 앞 공백·여러 빈 줄)


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
        if kind in ("upper", "lower"):       # 고른 글자만
            a, b = self.sel_range()
            old = t.get(a, b)
            new = old.upper() if kind == "upper" else old.lower()
            if new == old:
                self.status.config(text=nothing)
                return
            self.replace(a, b, new, 0, len(new))
            self.status.config(text=tr("바꿨습니다"))
            return
        if kind in ("unwrap", "join", "sort", "rsort"):   # 줄들을 통째로
            part = lines[lo:hi + 1]
            if kind == "unwrap":
                out = tidytext.unwrap(lines, lo, hi)
            elif kind == "join":
                out = [tidytext.join_lines(part)]
            else:
                out = tidytext.sort_lines(part, kind == "rsort")
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
