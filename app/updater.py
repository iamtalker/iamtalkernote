"""업데이트 확인·내려받기: GitHub 릴리스(iamtalker/iamtalkernote)의 최신 iamtalkernote.exe 로 바꾼다.
사용자가 도움말 → 업데이트 확인을 눌렀을 때만 인터넷에 접속한다. 내려받은 파일은 릴리스 노트에 적힌 SHA-256 과 맞을 때만 쓴다
(전송 중 깨짐 방지용이며, 저장소 자체가 뚫린 경우까지 막아 주지는 않는다)."""
from i18n import tr
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit

REPO = "iamtalker/iamtalkernote"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "iamtalkernote.exe"
UA = "iamtalkernote-updater"
OK_HOSTS = ("github.com", "githubusercontent.com")   # 내려받기를 허용하는 주소(와 그 하위 도메인)


def parse_version(tag):
    """'v0.3.6' → (0, 3, 6). 읽지 못하면 (0,)"""
    nums = re.findall(r"\d+", str(tag).split("-")[0])
    return tuple(int(x) for x in nums) or (0,)


def is_newer(tag, current):
    return parse_version(tag) > parse_version(current)


def host_ok(url):
    u = urlsplit(url)
    h = (u.hostname or "").lower()
    return u.scheme == "https" and any(h == d or h.endswith("." + d) for d in OK_HOSTS)


def latest(timeout=12):
    """최신 릴리스 → {tag, url(릴리스 페이지), body, asset_url, size, sha}. 인터넷이 안 되면 예외"""
    req = urllib.request.Request(API, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    asset = next((a for a in d.get("assets", []) if a.get("name", "").lower() == ASSET), None)
    m = re.search(r"SHA-256.*?`([0-9a-fA-F]{64})`", d.get("body") or "", re.S | re.I)
    url = asset.get("browser_download_url", "") if asset else ""
    return {"tag": d.get("tag_name", ""), "url": d.get("html_url", f"https://github.com/{REPO}/releases"),
            "body": d.get("body") or "", "asset_url": url if host_ok(url) else "",
            "size": int(asset.get("size", 0)) if asset else 0, "sha": m.group(1).lower() if m else ""}


def whats_new(body, limit=700):
    """릴리스 노트에서 '바뀐 것' 부분만(없으면 앞부분)"""
    m = re.search(r"###\s*바뀐 것\s*\n(.*?)(?:\n###|\Z)", body, re.S)
    text = (m.group(1) if m else body).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def download(rel, progress=None, cancelled=lambda: False, timeout=30):
    """새 exe 를 임시 폴더에 내려받아 SHA-256 을 확인하고 경로를 돌려준다. 안 맞으면 지우고 예외"""
    if not rel.get("asset_url") or not rel.get("sha"):
        raise OSError(tr("릴리스에 exe 나 SHA-256 이 없어서 자동으로 바꿀 수 없습니다"))
    folder = os.path.join(tempfile.gettempdir(), "iamtalkernote-update")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, ASSET)
    part = dest + ".part"
    h = hashlib.sha256()
    req = urllib.request.Request(rel["asset_url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        if not host_ok(r.geturl()):
            raise OSError(tr("내려받는 주소가 GitHub 가 아니어서 중단했습니다"))
        total = int(r.headers.get("Content-Length") or rel.get("size") or 0)
        got = 0
        while True:
            if cancelled():
                break
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress:
                progress(got // 1024, total // 1024)
    if cancelled():
        _rm(part)
        return None
    if h.hexdigest() != rel["sha"]:
        _rm(part)
        raise OSError(tr("내려받은 파일의 SHA-256 이 릴리스에 적힌 값과 달라서 중단했습니다"))
    _rm(dest)
    os.replace(part, dest)
    return dest


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


# 앱이 끝날 때까지 기다렸다가(실행 중인 exe 는 덮어쓸 수 없다) 새 파일로 바꾸고 다시 시작하는 배치 파일.
# 경로는 인자(%1=새 파일, %2=바꿀 exe)로 받아서 파일 자체는 한글 경로와 상관없이 ASCII 만 쓴다.
SWAP_BAT = """@echo off
set n=0
:retry
move /y "%~1" "%~2" >nul 2>&1
if not errorlevel 1 goto done
set /a n+=1
if %n% GEQ 90 goto fail
ping -n 2 127.0.0.1 >nul
goto retry
:done
start "" "%~2"
(goto) 2>nul & del "%~f0"
:fail
exit /b 1
"""


def apply(new_path, exe_path=None):
    """새 exe 로 바꾸는 배치를 따로 띄운다. 이 뒤에 앱을 바로 끝내야 한다(그래야 파일이 풀려 바뀐다)."""
    exe_path = exe_path or sys.executable
    bat = os.path.join(tempfile.gettempdir(), "iamtalkernote-update", "swap.bat")
    with open(bat, "w", encoding="ascii", newline="\r\n") as f:
        f.write(SWAP_BAT)
    env = {k: v for k, v in os.environ.items() if not k.startswith("_MEIPASS") and not k.startswith("_PYI")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"   # 새 exe 가 이 앱의 임시 풀림 폴더를 물려받지 않고 새로 풀리게
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd", "/c", bat, new_path, exe_path], env=env, creationflags=flags, close_fds=True)
