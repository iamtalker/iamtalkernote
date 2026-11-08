"""웹 클리퍼(브라우저에서 스크랩을 받는 로컬 서버)를 다루는 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class ClipperServerMixin:
    # ------------------------------------------------------------ 웹 클리퍼 서버
    def start_clipper(self):
        if self.srv or not st.read_config().get("clipEnabled", True):
            return
        self.srv, self.port = clipserver.start(self.store, st.clipper_token, lambda: self.clip_q.put(1))
        if self.srv and self.port != clipserver.DEFAULT_PORT:   # 확장은 보통 기본 포트(41184)에 맞춰 두므로, 밀렸으면 알려 준다(비면 자동으로 돌아간다)
            self.status.config(text=tr('웹 클리퍼가 {0}번 포트로 열렸습니다({1}번을 다른 프로그램이 쓰는 중). 비면 자동으로 {2}번으로 옮깁니다.').format(self.port, clipserver.DEFAULT_PORT, clipserver.DEFAULT_PORT))

    def retake_default_port(self):
        """기본 포트(41184)를 다른 프로그램(예: 조플린, 아직 안 닫힌 앱의 옛 창)이 쓰고 있어서 옆 포트로 밀려 열렸다면, 비는 대로 기본 포트로 옮긴다.
        확장 프로그램의 포트는 그대로인데 서버만 옮겨 가 있으면 클리퍼가 '끊긴' 것처럼 된다."""
        if not self.srv or self.port == clipserver.DEFAULT_PORT:
            return
        srv, port = clipserver.start(self.store, st.clipper_token, lambda: self.clip_q.put(1), ports=[clipserver.DEFAULT_PORT])
        if not srv:
            return
        try:
            self.srv.shutdown()
            self.srv.server_close()
        except Exception:  # noqa: BLE001
            pass
        self.srv, self.port = srv, port
        self.status.config(text=tr('웹 클리퍼가 {0}번 포트로 돌아왔습니다.').format(port))

    def stop_clipper(self):
        if self.srv:
            try:
                self.srv.shutdown()
                self.srv.server_close()
            except Exception:  # noqa: BLE001
                pass
        self.srv = self.port = None

    def poll_clip(self):
        got = False
        try:
            while True:
                self.clip_q.get_nowait()
                got = True
        except queue.Empty:
            pass
        if got:
            self.reload_notes()
            self.status.config(text=tr("웹 클리퍼에서 새 노트가 들어왔습니다 ") + time.strftime("%H:%M:%S"))
        self.clip_tick = getattr(self, "clip_tick", 0) + 1
        if self.clip_tick % 8 == 0:   # 약 5초마다
            self.retake_default_port()
        self.root.after(600, self.poll_clip)
