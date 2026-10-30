"""옵션의 '동기화' 탭과, 앱이 켜질 때 동기화를 이어 주는 코드. 정책 계산은 syncpolicy, Syncthing 제어는 syncengine 이 맡는다."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import syncengine as se
import syncpolicy as sp


def current_plans(app, policy=None):
    """이 컴퓨터에서 만들 Syncthing 폴더 목록. 외부 폴더의 경로는 '가져오기' 에 등록된 폴더에서 가져온다"""
    policy = policy or sp.load(app.store.root)
    ext = {f["id"]: f["path"] for f in app.docs.folders()}
    return sp.plan(policy, app.store.root, "pc", ext)


def apply_now(app, policy=None):
    """정책을 저장하고 Syncthing 설정에 맞춘다. (만든·고친 수, 지운 수)"""
    policy = policy or sp.load(app.store.root)
    sp.save(app.store.root, policy)
    return app.sync.apply(current_plans(app, policy))


def resume(app):
    """앱을 켤 때: 동기화를 켜 둔 경우 Syncthing 을 띄우고 정책을 맞춘다(화면을 막지 않게 백그라운드에서)"""
    if not (app.sync.enabled() and se.installed()):
        return

    def work():
        try:
            app.sync.start()
            if sp.exists(app.store.root):
                apply_now(app)
        except Exception as e:  # noqa: BLE001
            app.sync_error = str(e)
    threading.Thread(target=work, daemon=True).start()


def tab(app, p, kit):
    """kit: lab, title, hr, copy, Btn, C, top, ui — 옵션 창이 쓰는 도우미들"""
    lab, title, hr, copy, Btn, C, top, ui = (kit[k] for k in ("lab", "title", "hr", "copy", "Btn", "C", "top", "ui"))
    eng = app.sync
    root = app.store.root
    title(p, "동기화", "폰과 컴퓨터의 노트를 서버 없이 직접 맞춥니다(Syncthing 사용).")
    # 내용이 창보다 길어서 이 탭만 스크롤되게 한다
    canvas = tk.Canvas(p, bg=C["bg"], highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=C["bg"])
    win = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width - 4))

    def wheel(e):
        if body.winfo_height() > canvas.winfo_height():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    alive = {"on": True}
    body.bind("<Destroy>", lambda e: alive.update(on=False) if e.widget is body else None)
    state = {"policy": sp.load(root), "dirty": False}

    def bg(fn, done):
        def run():
            try:
                r, err = fn(), None
            except Exception as ex:  # noqa: BLE001
                r, err = None, ex
            if alive["on"]:
                try:
                    app.root.after(0, lambda: alive["on"] and done(r, err))
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=run, daemon=True).start()

    def clear():
        for w in body.winfo_children():
            w.destroy()

    def check(parent, text, var, cmd):
        return tk.Checkbutton(parent, text=text, variable=var, command=cmd, bg=C["bg"], activebackground=C["bg"], font=(app.ui, 10), selectcolor=C["bg"])

    # ------------------------------------------------------------ 설치 전
    def install_view():
        clear()
        lab(body, "동기화 엔진(Syncthing)이 아직 설치되지 않았습니다.", font=(app.ui, 10, "bold")).pack(anchor="w")
        lab(body, "Syncthing 은 서버 없이 기기끼리 파일을 직접 맞춰 주는 오픈소스 프로그램입니다. 공식 GitHub 릴리스에서 약 14MB 를 받아 이 앱 설정 폴더에 두고, "
                  "받은 파일이 공식 값(SHA-256)과 같은지 확인한 뒤에만 설치합니다. 새 버전은 Syncthing 이 공식 서명을 확인한 뒤 알아서 올립니다.\n\n처음 켤 때 윈도 방화벽이 네트워크 허용을 물어보면 '개인 네트워크'만 허용하세요(한 번만 묻습니다).",
            fg=C["muted"], font=(app.ui, 9), wraplength=500).pack(anchor="w", pady=(4, 12))
        msg = lab(body, "", fg=C["muted"], font=(app.ui, 9))
        msg.pack(anchor="w", pady=(0, 8))

        def go():
            if not messagebox.askyesno("Syncthing 설치", f"{se.URL}\n\n에서 약 14MB 를 받아 설치합니다. 계속할까요?", parent=top):
                return
            btn.pack_forget()

            def prog(got, total):
                if alive["on"]:
                    app.root.after(0, lambda: alive["on"] and msg.config(text=f"받는 중… {got // 1024 // 1024}MB" + (f" / {total // 1024 // 1024}MB" if total else "")))

            def done(_, err):
                if err:
                    msg.config(text=f"설치하지 못했습니다: {err}", fg=C["danger"])
                    btn.pack(anchor="w")
                else:
                    main_view()
            bg(lambda: se.install(prog), done)
        btn = Btn(body, f"Syncthing {se.VERSION} 설치…", go, kind="primary", padx=16, pady=5)
        btn.pack(anchor="w")

    # ------------------------------------------------------------ 설치 후
    def main_view():
        clear()
        on = tk.BooleanVar(value=eng.enabled())
        status = lab(body, "", fg=C["muted"], font=(app.ui, 9))
        err_lab = lab(body, "", fg=C["danger"], font=(app.ui, 9), wraplength=500)

        def toggle():
            eng.put(enabled=bool(on.get()))
            if on.get():
                status.config(text="시작하는 중…", fg=C["muted"])

                def done(_, err):
                    err_lab.config(text=f"시작하지 못했습니다: {err}" if err else "")
                    if not err:
                        refresh_id()
                    poll()
                bg(lambda: (eng.start(), sp.save(root, state["policy"]) if not sp.exists(root) else None, apply_now(app, state["policy"])), done)
            else:
                bg(eng.stop, lambda *_: poll())
        check(body, "동기화 사용 (앱을 켤 때 함께 시작하고, 끌 때 함께 멈춥니다)", on, toggle).pack(anchor="w")
        status.pack(anchor="w", pady=(2, 0))
        err_lab.pack(anchor="w")
        hr(body)

        # ---- 이 컴퓨터의 기기 ID
        lab(body, "이 컴퓨터의 기기 ID", font=(app.ui, 10, "bold")).pack(anchor="w")
        idv = tk.StringVar(value="(동기화를 켜면 나타납니다)")
        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x", pady=(4, 0))
        tk.Entry(row, textvariable=idv, state="readonly", relief="flat", bd=0, bg=C["panel"], readonlybackground=C["panel"], fg=C["text"],
                 highlightthickness=1, highlightbackground=C["line"], font=(app.ui, 9)).pack(side="left", fill="x", expand=True, ipady=4)
        Btn(row, "복사", lambda: copy(idv.get()), padx=10, pady=3).pack(side="left", padx=6)
        lab(body, "폰의 Syncthing(안드로이드는 Syncthing-Fork)에서 '기기 추가'로 이 ID 를 넣고, 아래에 폰의 ID 를 추가하세요.",
            fg=C["muted"], font=(app.ui, 9), wraplength=500).pack(anchor="w", pady=(4, 0))

        def refresh_id():
            def done(r, err):
                if r:
                    idv.set(r)
            bg(eng.my_id, done) if eng.running() else None

        # ---- 연결할 기기
        lab(body, "연결할 기기", font=(app.ui, 10, "bold")).pack(anchor="w", pady=(14, 0))
        lb = tk.Listbox(body, height=3, relief="flat", bd=0, bg=C["panel"], fg=C["text"], highlightthickness=1, highlightbackground=C["line"],
                        selectbackground=C["soft"], selectforeground=C["text"], activestyle="none", font=(app.ui, 10), exportselection=False)
        lb.pack(fill="x", pady=(4, 0))
        peer_ids = []

        def fill_peers():
            def done(r, err):
                lb.delete(0, "end")
                peer_ids.clear()
                for i, n in (r or []):
                    peer_ids.append(i)
                    lb.insert("end", f"{n or '이름 없음'}    {i[:7]}…")
            bg(eng.peers, done) if eng.running() else None

        def add_peer():
            if not eng.running():
                return messagebox.showinfo("동기화", "먼저 '동기화 사용'을 켜세요.", parent=top)
            dlg = tk.Toplevel(top)
            dlg.title("기기 추가")
            dlg.transient(top)
            dlg.configure(bg=C["bg"], padx=20, pady=16)
            lab(dlg, "상대 기기의 ID").pack(anchor="w")
            e1 = tk.Entry(dlg, width=62, font=(app.ui, 9))
            e1.pack(fill="x", pady=(2, 8), ipady=3)
            lab(dlg, "이름 (알아보기 쉽게)").pack(anchor="w")
            e2 = tk.Entry(dlg, width=30, font=(app.ui, 10))
            e2.insert(0, "내 폰")
            e2.pack(anchor="w", pady=(2, 10), ipady=3)

            def ok():
                try:
                    eng.add_peer(e1.get(), e2.get().strip())
                    apply_now(app, state["policy"])
                except (ValueError, RuntimeError) as ex:
                    return messagebox.showwarning("기기 추가", str(ex), parent=dlg)
                dlg.destroy()
                fill_peers()
            Btn(dlg, "추가", ok, kind="primary", padx=18, pady=4).pack(side="right")
            Btn(dlg, "취소", dlg.destroy, padx=14, pady=4).pack(side="right", padx=6)
            e1.focus_set()
            dlg.grab_set()

        def del_peer():
            sel = lb.curselection()
            if sel and messagebox.askyesno("기기 빼기", "이 기기와의 동기화를 끊을까요?(기기에 있는 파일은 그대로입니다)", parent=top):
                eng.remove_peer(peer_ids[sel[0]])
                fill_peers()
        row = tk.Frame(body, bg=C["bg"])
        row.pack(anchor="w", pady=(6, 0))
        Btn(row, "기기 추가…", add_peer, padx=12, pady=3).pack(side="left")
        Btn(row, "기기 빼기", del_peer, padx=12, pady=3).pack(side="left", padx=6)
        pend = tk.Frame(body, bg=C["bg"])   # 연결을 요청한 기기 목록([허용] 버튼)
        pend.pack(fill="x", pady=(4, 0))
        pend_key = {"v": None}

        def show_pending(pending):
            key = tuple(i for i, _ in pending)
            if key == pend_key["v"]:
                return
            pend_key["v"] = key
            for w in pend.winfo_children():
                w.destroy()
            for i, n in pending:
                r = tk.Frame(pend, bg=C["bg"])
                r.pack(fill="x", pady=2)
                lab(r, f"연결을 요청한 기기: {n or '이름 없음'} ({i[:7]}…)", fg=C["accent"], font=(app.ui, 9)).pack(side="left")

                def allow(i=i, n=n):
                    def work():
                        eng.add_peer(i, n or "내 폰")
                        return apply_now(app, state["policy"])

                    def done_(r_, err):
                        pend_key["v"] = None
                        if err:
                            note.config(text=f"허용하지 못했습니다: {err}", fg=C["danger"])
                        else:
                            note.config(text="허용했습니다. 폰에서 폴더를 받아 오는 중입니다(폰의 설정 → 동기화에서 진행을 볼 수 있습니다).", fg="#15803d")
                            fill_peers()
                    bg(work, done_)
                Btn(r, "허용", allow, kind="primary", padx=12, pady=2).pack(side="left", padx=8)
        hr(body)

        # ---- 모듈별 방향
        lab(body, "무엇을 어느 방향으로 맞출까", font=(app.ui, 10, "bold")).pack(anchor="w")
        mods = tk.Frame(body, bg=C["bg"])
        mods.pack(fill="x", pady=(6, 0))
        names = [sp.LABELS[d] for d in sp.DIRECTIONS]

        def draw_mods():
            for w in mods.winfo_children():
                w.destroy()
            for mid, m in state["policy"]["modules"].items():
                r = tk.Frame(mods, bg=C["bg"])
                r.pack(fill="x", pady=2)
                lab(r, m.get("label", mid), width=34).pack(side="left")
                cb = ttk.Combobox(r, values=names, state="readonly", width=14, font=(app.ui, 10))
                cb.set(sp.LABELS.get(m.get("direction"), names[0]))

                def chosen(_e, mid=mid, cb=cb):
                    sp.set_direction(state["policy"], mid, sp.DIRECTIONS[names.index(cb.get())])
                    state["dirty"] = True
                    note.config(text="바꾼 내용은 [적용]을 눌러야 반영됩니다.")
                cb.bind("<<ComboboxSelected>>", chosen)
                cb.pack(side="left")
                if m["kind"] in ("notebook", "external"):
                    def drop(mid=mid):
                        sp.remove(state["policy"], mid)
                        state["dirty"] = True
                        note.config(text="바꾼 내용은 [적용]을 눌러야 반영됩니다.")
                        draw_mods()
                    Btn(r, "×", drop, kind="icon", padx=8, pady=0).pack(side="left", padx=4)

        def add_menu(kind):
            m = tk.Menu(top, tearoff=0)
            if kind == "notebook":
                have = {x.get("path") for x in state["policy"]["modules"].values()}
                opts = [(nb, nb) for nb in app.store.notebooks() if nb not in have]
                add = lambda v: sp.add_notebook(state["policy"], v, sp.BOTH)   # noqa: E731
            else:
                have = {k.split(":", 1)[1] for k, x in state["policy"]["modules"].items() if x["kind"] == "external"}
                opts = [(f["name"] + "  (" + f["path"] + ")", f) for f in app.docs.folders() if f["id"] not in have]
                add = lambda f: sp.add_external(state["policy"], f["id"], f["name"], sp.BOTH)   # noqa: E731
            if not opts:
                m.add_command(label="추가할 항목이 없습니다" + ("" if kind == "notebook" else " (옵션 > 가져오기에서 폴더를 먼저 추가하세요)"), state="disabled")
            for text, v in opts:
                m.add_command(label=text, command=lambda v=v: (add(v), state.update(dirty=True), note.config(text="바꾼 내용은 [적용]을 눌러야 반영됩니다."), draw_mods()))
            m.tk_popup(app.root.winfo_pointerx(), app.root.winfo_pointery())
        row = tk.Frame(body, bg=C["bg"])
        row.pack(anchor="w", pady=(8, 0))
        Btn(row, "노트북 따로 설정…", lambda: add_menu("notebook"), padx=12, pady=3).pack(side="left")
        Btn(row, "외부 폴더 추가…", lambda: add_menu("external"), padx=12, pady=3).pack(side="left", padx=6)
        note = lab(body, "", fg=C["muted"], font=(app.ui, 9), wraplength=500)

        def apply_btn():
            if not eng.running():
                return messagebox.showinfo("동기화", "먼저 '동기화 사용'을 켜세요.", parent=top)

            def done(r, err):
                if err:
                    note.config(text=f"적용하지 못했습니다: {err}", fg=C["danger"])
                else:
                    state["dirty"] = False
                    note.config(text=f"적용했습니다 (폴더 {r[0]}개 맞춤, {r[1]}개 정리). 폰에서 공유 요청을 받아 주세요.", fg="#15803d")
            bg(lambda: apply_now(app, state["policy"]), done)
        Btn(body, "적용", apply_btn, kind="primary", bold=True, padx=22, pady=5).pack(anchor="w", pady=(10, 0))
        note.pack(anchor="w", pady=(6, 0))
        lab(body, "‘PC → 모바일’은 컴퓨터가 보내기만 하고, 폰에서 바꾼 내용은 컴퓨터에 반영되지 않습니다(폰의 Syncthing 에서 ‘되돌리기’를 누르면 컴퓨터 상태로 맞춰집니다). "
                  "‘모바일 → PC’는 그 반대입니다. 정책은 노트 폴더의 .sync/policy.json 에 저장돼 폰 앱도 읽을 수 있습니다.", fg=C["muted"], font=(app.ui, 9), wraplength=500).pack(anchor="w", pady=(8, 0))
        hr(body)
        ver = lab(body, "", fg=C["muted"], font=(app.ui, 9), wraplength=500)
        ver.pack(anchor="w")

        # ---- 주기적으로 상태 보기
        def poll():
            if not alive["on"]:
                return

            def status_work():
                if not eng.running():
                    return None
                ids = [x["id"] for x in current_plans(app, state["policy"])]
                return eng.overview(ids), eng.pending_devices(), eng.upgrade_info()

            def done(r, err):
                if not alive["on"]:
                    return
                if r is None:
                    status.config(text="꺼져 있음" if not eng.enabled() else "시작하지 못했거나 아직 시작 중입니다", fg=C["muted"])
                    show_pending([])
                else:
                    ov, pending, up = r
                    states = [s for s, _ in ov["folders"].values()]
                    busy = sum(1 for s in states if s not in ("idle", "?"))
                    status.config(text=f"실행 중 · 연결된 기기 {ov['connected']}/{ov['peers']}" + (f" · 맞추는 중 {busy}개" if busy else " · 모두 최신"), fg="#15803d")
                    show_pending(pending)
                    msg = f"Syncthing {up['running']}" if up["running"] else ""
                    if up["newer"] and up["major"]:
                        msg += f" — 새 메이저 버전 {up['latest']} 이 나왔습니다(설정이 바뀔 수 있어 자동으로 올리지 않습니다)"
                    elif up["newer"]:
                        msg += f" — 새 버전 {up['latest']} 이 있어 곧 자동으로 올립니다"
                    elif up["running"]:
                        msg += " (최신)"
                    ver.config(text=msg)
                    if not peer_ids and ov["peers"]:
                        fill_peers()
                try:
                    app.root.after(4000, poll)
                except Exception:  # noqa: BLE001
                    pass
            bg(status_work, done)

        draw_mods()
        if eng.running():
            refresh_id()
            fill_peers()
        poll()

    if se.installed():
        main_view()
    else:
        install_view()
