"""전송 엔진 어댑터: Syncthing 을 내려받아(공식 릴리스, SHA-256 확인) 숨겨서 실행하고 REST API 로 제어한다.
정책(syncpolicy)이 계산한 폴더 목록을 Syncthing 설정에 맞춰 줄 뿐이라, 엔진을 바꾸려면 이 파일만 바꾸면 된다.
표준 라이브러리만 쓴다. Syncthing 은 MPL-2.0 이며 받은 압축 파일의 LICENSE.txt 를 실행 파일 옆에 둔다."""
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import store as st
import syncpolicy as sp

VERSION = "v2.1.7"
ZIP_NAME = "syncthing-windows-amd64-%s.zip" % VERSION
URL = "https://github.com/syncthing/syncthing/releases/download/%s/%s" % (VERSION, ZIP_NAME)
SHA256 = "3ce7da770f546a8d02b65b2e7ee31f2a3b8b7c3f990ede045590cca4172ecfe1"   # 공식 sha256sum.txt.asc 의 값
CREATE_NO_WINDOW = 0x08000000
DEVICE_ID = re.compile(r"^[A-Z2-7]{7}(-[A-Z2-7]{7}){7}$")


def base_dir():
    return os.path.join(os.path.dirname(st.config_path()), "syncthing")


def exe_path():
    return os.path.join(base_dir(), "syncthing.exe")


def installed():
    return os.path.isfile(exe_path())


def install(progress=None, cancelled=None):
    """공식 릴리스에서 syncthing.exe 를 받아 base_dir() 에 둔다. progress(받은바이트, 전체바이트). 실패하면 예외"""
    os.makedirs(base_dir(), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="syncthing-", suffix=".zip")
    os.close(fd)
    try:
        h = hashlib.sha256()
        req = urllib.request.Request(URL, headers={"User-Agent": "iamtalkernote"})
        with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
            total, got = int(r.headers.get("Content-Length") or 0), 0
            while True:
                if cancelled and cancelled():
                    raise RuntimeError("취소했습니다")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress:
                    progress(got, total)
        if h.hexdigest() != SHA256:
            raise RuntimeError("받은 파일의 SHA-256 이 공식 값과 다릅니다. 설치하지 않았습니다.")
        with zipfile.ZipFile(tmp) as z:
            for name in z.namelist():
                leaf = name.rsplit("/", 1)[-1]
                if leaf in ("syncthing.exe", "LICENSE.txt", "AUTHORS.txt"):
                    dest = os.path.join(base_dir(), leaf)
                    with z.open(name) as src, open(dest + ".part", "wb") as out:
                        while True:
                            b = src.read(1024 * 1024)
                            if not b:
                                break
                            out.write(b)
                    os.replace(dest + ".part", dest)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def valid_device_id(s):
    return bool(DEVICE_ID.match(re.sub(r"[\s]", "", s or "").upper()))


def clean_device_id(s):
    return re.sub(r"[\s]", "", s or "").upper()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Engine:
    def __init__(self):
        self.proc = None

    # ---- 설정(앱 config.json 의 "sync")
    def cfg(self):
        return st.read_config().get("sync", {})

    def put(self, **patch):
        c = self.cfg()
        c.update(patch)
        st.write_config(sync=c)

    def enabled(self):
        return bool(self.cfg().get("enabled"))

    # ---- REST
    def api(self, path, method="GET", body=None, timeout=10):
        c = self.cfg()
        if not c.get("port") or not c.get("key"):
            raise RuntimeError("동기화 엔진이 설정되지 않았습니다")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (c["port"], path), method=method,
                                     headers={"X-API-Key": c["key"], "Content-Type": "application/json"},
                                     data=None if body is None else json.dumps(body).encode("utf-8"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                t = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError("Syncthing %s %s → %s %s" % (method, path, e.code, e.read().decode("utf-8", "replace")[:200]))
        return json.loads(t) if t.strip() else None

    def running(self):
        try:
            self.api("/rest/system/ping", timeout=2)
            return True
        except Exception:
            return False

    # ---- 시작·끝
    def start(self, wait=25):
        """실행 중이면 그대로 쓰고(앱이 비정상 종료돼 남은 것 포함), 아니면 숨겨서 띄운다. 성공하면 True"""
        if not installed():
            raise RuntimeError("Syncthing 이 설치되지 않았습니다")
        if self.running():
            return True
        c = self.cfg()
        port = c.get("port") or _free_port()
        key = c.get("key") or secrets.token_hex(16)
        # 저장해 둔 포트를 다른 프로그램이 쓰고 있으면 새로 고른다
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", port))
            s.close()
        except OSError:
            port = _free_port()
        self.put(port=port, key=key)
        home = os.path.join(base_dir(), "home")
        os.makedirs(home, exist_ok=True)
        env = dict(os.environ, STNODEFAULTFOLDER="1")
        # --no-restart 를 쓰지 않는다: 자체 업그레이드 뒤에 감시 프로세스가 새 버전으로 다시 띄워 준다
        self.proc = subprocess.Popen(
            [exe_path(), "serve", "--home", home, "--no-browser",
             "--gui-address=127.0.0.1:%d" % port, "--gui-apikey=" + key],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        end = time.time() + wait
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError("Syncthing 이 바로 종료됐습니다(종료 코드 %s)" % self.proc.returncode)
            if self.running():
                self.first_setup()
                return True
            time.sleep(0.4)
        raise RuntimeError("Syncthing 이 시간 안에 시작하지 않았습니다")

    def first_setup(self):
        """사용 통계 보내기·브라우저 열기를 끄고, Syncthing 자체 자동 업그레이드(공식 서명을 확인하고 교체)를 12시간마다 켠다.
        자동 업그레이드는 같은 메이저 버전 안에서만 하고, 메이저가 바뀌는 새 버전은 upgrade_info() 로 알려 주기만 한다"""
        try:
            self.api("/rest/config/options", "PATCH", {"startBrowser": False, "urAccepted": -1, "autoUpgradeIntervalH": 12, "crashReportingEnabled": False})
        except Exception:
            pass

    def upgrade_info(self):
        """{'running': 실행 중 버전, 'latest': 최신 버전, 'newer': 새 버전이 있나, 'major': 메이저가 바뀌는 새 버전인가}"""
        try:
            u = self.api("/rest/system/upgrade", timeout=15) or {}
            return {"running": u.get("running", ""), "latest": u.get("latest", ""), "newer": bool(u.get("newer")), "major": bool(u.get("majorNewer"))}
        except Exception:
            return {"running": "", "latest": "", "newer": False, "major": False}

    def stop(self):
        try:
            self.api("/rest/system/shutdown", "POST", timeout=3)
        except Exception:
            pass
        p, self.proc = self.proc, None
        if p:
            try:
                p.wait(5)
            except Exception:
                p.kill()

    # ---- 기기
    def my_id(self):
        return self.api("/rest/system/status")["myID"]

    def peers(self):
        me = self.my_id()
        return [(d["deviceID"], d.get("name", "")) for d in self.api("/rest/config")["devices"] if d["deviceID"] != me]

    def add_peer(self, dev_id, name):
        dev_id = clean_device_id(dev_id)
        if not valid_device_id(dev_id):
            raise ValueError("기기 ID 모양이 아닙니다(7글자씩 8묶음, 하이픈으로 연결)")
        try:
            chk = self.api("/rest/svc/deviceid?id=" + dev_id) or {}
        except RuntimeError:
            chk = {"error": "x"}
        if chk.get("error"):
            raise ValueError("기기 ID 가 올바르지 않습니다(글자가 틀렸을 수 있어요). 상대 기기에서 다시 복사해 보세요.")
        self.api("/rest/config/devices/" + dev_id, "PUT", {"deviceID": dev_id, "name": name or dev_id[:7], "addresses": ["dynamic"],
                                                          "autoAcceptFolders": False, "paused": False})

    def remove_peer(self, dev_id):
        self.api("/rest/config/devices/" + urllib.parse.quote(dev_id), "DELETE")

    def pending_devices(self):
        """우리 기기에 연결을 요청했지만 아직 받아들이지 않은 기기 [(id, 이름)]"""
        try:
            d = self.api("/rest/cluster/pending/devices") or {}
        except Exception:
            return []
        return [(i, v.get("name", "")) for i, v in d.items()]

    # ---- 폴더(정책 → Syncthing 설정)
    def apply(self, plans):
        """plans(syncpolicy.plan 의 결과)에 맞게 이 앱이 만든(ID 가 inn- 로 시작하는) Syncthing 폴더를 만들고 고치고 지운다.
        돌려주는 값: (만든·고친 개수, 지운 개수)"""
        cfg = self.api("/rest/config")
        me = self.my_id()
        devices = [{"deviceID": d["deviceID"], "introducedBy": "", "encryptionPassword": ""} for d in cfg["devices"]]
        if not any(d["deviceID"] == me for d in devices):
            devices.append({"deviceID": me, "introducedBy": "", "encryptionPassword": ""})
        have = {f["id"]: f for f in cfg["folders"] if f["id"].startswith(sp.ID_PREFIX)}
        template = self.api("/rest/config/defaults/folder")
        want = set()
        for p in plans:
            os.makedirs(p["path"], exist_ok=True)
            f = dict(have.get(p["id"]) or template)
            f.update({"id": p["id"], "label": p["label"], "path": p["path"], "type": p["type"], "devices": devices,
                      "fsWatcherEnabled": True, "fsWatcherDelayS": 10, "rescanIntervalS": 3600, "ignorePerms": True, "paused": False})
            self.api("/rest/config/folders/" + p["id"], "PUT", f)
            self.api("/rest/db/ignores?folder=" + urllib.parse.quote(p["id"]), "POST", {"ignore": p["ignore"]})
            want.add(p["id"])
        gone = [i for i in have if i not in want]
        for i in gone:
            self.api("/rest/config/folders/" + i, "DELETE")
        return len(want), len(gone)

    # ---- 상태
    def overview(self, folder_ids):
        """{'connected': 연결된 기기 수, 'peers': 등록된 기기 수, 'folders': {id: (상태, 남은바이트)}}"""
        conns = (self.api("/rest/system/connections") or {}).get("connections", {})
        me = self.my_id()
        peers = [d for d in self.api("/rest/config")["devices"] if d["deviceID"] != me]
        connected = sum(1 for d in peers if conns.get(d["deviceID"], {}).get("connected"))
        out = {}
        for fid in folder_ids:
            try:
                s = self.api("/rest/db/status?folder=" + urllib.parse.quote(fid), timeout=5)
                out[fid] = (s.get("state", "?"), int(s.get("needBytes", 0)))
            except Exception:
                out[fid] = ("?", 0)
        return {"connected": connected, "peers": len(peers), "folders": out}
