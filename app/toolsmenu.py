"""도구 메뉴(중복 노트 찾기·스크랩 군더더기 정리)의 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class ToolsMenuMixin:
    # ------------------------------------------------------------ 도구: 중복 노트 · 스크랩 군더더기
    def tool_window(self, title, size="900x580", native=False):
        """native=True 면 메인 창에 딸린 창(transient)이 아니라 독립 창으로 만든다 → 제목줄 오른쪽 위에 최소화·최대화·닫기 아이콘이 생긴다"""
        top = tk.Toplevel(self.root)
        top.title(title)
        top.configure(bg=C["bg"])
        if not native:
            top.transient(self.root)
        top.geometry(f"{size}+{self.root.winfo_x() + 80}+{self.root.winfo_y() + 50}")
        top.minsize(640, 400)
        return top

    def open_path_note(self, path):
        """경로로 노트를 찾아 메인 창에서 연다"""
        n = next((x for x in self.all_notes if x["path"] == path), None)
        if n:
            self.open_note(n)
        return n

    def run_task(self, title, work, done, text=tr("노트를 읽는 중…"), cancellable=True):
        """오래 걸리는 일을 뒤에서 돌리고 진행 창을 보여 준다(work(progress, cancelled) → 결과). 끝나면 done(결과). 취소하면 done 은 부르지 않는다."""
        self.flush()
        top = self.tool_window(title, "420x150")
        msg = tk.Label(top, text=text, bg=C["bg"], fg=C["text"], font=(self.ui, 10), pady=24)
        msg.pack()
        state = {"cancel": False, "prog": (0, 0, None)}
        q = queue.Queue()

        def stop():
            state["cancel"] = True
            top.destroy()
        if cancellable:
            top.protocol("WM_DELETE_WINDOW", stop)
            Btn(top, tr("취소"), stop, padx=14, pady=3).pack()
        else:   # 중간에 멈추면 안 되는 작업(파일 옮기기·링크 고치기)
            top.protocol("WM_DELETE_WINDOW", lambda: None)
            top.grab_set()

        def job():
            try:
                q.put(("ok", work(lambda d, t, phase=None: state.update(prog=(d, t, phase)), lambda: state["cancel"])))
            except Exception as ex:  # noqa: BLE001
                q.put(("err", str(ex)))
        threading.Thread(target=job, daemon=True).start()

        def poll():
            if state["cancel"]:
                return
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                d, t, phase = state["prog"]
                msg.config(text=f"{phase or text} {d:,} / {t:,}" if t else text)
                return top.after(100, poll)
            top.destroy()
            if kind == "err":
                return messagebox.showerror(APP, val, parent=self.root)
            done(val)
        poll()

    def scan_notes(self, title, work, done):
        """모든 노트를 뒤에서 훑는다(work(notes, progress, cancelled) → 결과). 끝나면 done(결과). 취소 가능."""
        self.flush()
        notes = list(self.all_notes)
        self.run_task(title, lambda prog, cancel: work(notes, prog, cancel), done)
