"""조플린 클리퍼 플러스(원본 저장소) → 이 저장소의 clipper/ 사본 동기화.

  py -3 -X utf8 tools/sync_clipper.py              무엇이 바뀌는지만 보여 준다(쓰지 않음)
  py -3 -X utf8 tools/sync_clipper.py --apply      실제로 복사한다
  py -3 -X utf8 tools/sync_clipper.py <원본 폴더>   원본 위치를 직접 지정(기본: ../2. 안정화/joplin-clipper-plus)

- 확장 본체(manifest·background·content·core·site-rules·popup·options.js·picker·toolbar·icons·lib·LICENSE)는 원본 그대로 가져온다(줄 끝 포함).
- options.html 은 앱에 맞춘 안내 문구(PATCHES)를 원본에 다시 입혀서 쓴다. 원본이 그 문구를 바꿔 입힐 수 없으면 경고하고 건드리지 않는다.
- 확장이 앱 서버(app/clipserver.py: /ping /folders /notes)에 새로 요청하는 주소나 노트 필드가 생기면 경고한다(서버를 같이 고쳐야 한다).
웹스토어 버전은 크롬이 자동 업데이트하므로 이 사본은 실행용이 아니라 소스 보관·시험용이다."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.normpath(os.path.join(HERE, "..", "clipper"))
DEFAULT_SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "2. 안정화", "joplin-clipper-plus"))

MIRROR = ["manifest.json", "background.js", "content.js", "core.js", "site-rules.js", "popup.html", "popup.js",
          "options.js", "picker.js", "toolbar.js", "LICENSE",
          "icons/icon16.png", "icons/icon48.png", "icons/icon128.png",
          "lib/Readability.js", "lib/turndown.js", "lib/turndown-plugin-gfm.js"]
# 앱에 맞춘 options.html 문구: 원본 문장 → 앱 문장
PATCHES = [
    ("<h1>Joplin Clipper Plus — 설정</h1>", "<h1>Joplin Clipper Plus (iamtalkernote 연결) — 설정</h1>"),
    ('<label for="port">조플린 Web Clipper 포트</label>', '<label for="port">웹 클리퍼 포트 (iamtalkernote 옵션 > 웹 클리퍼에 표시된 값)</label>'),
    ('<div class="hint">조플린 데스크톱 앱 → 도구 → 옵션 → Web Clipper → "Web Clipper 서비스 활성화"가 켜져 있는지 확인하세요.</div>',
     '<div class="hint">iamtalkernote 앱 → 설정 → 웹 클리퍼 설정에서 "웹 클리퍼 서비스 사용"이 켜져 있는지, 포트와 토큰이 맞는지 확인하세요. '
     '(기본 포트 41184 는 조플린과 같습니다. 조플린을 같이 켜 두면 앱은 옆 포트로 밀려 열리니 앱에 표시된 포트를 쓰세요.)</div>'),
    ('placeholder="조플린 Web Clipper 옵션 화면에 표시된 토큰을 붙여 넣으세요"', 'placeholder="iamtalkernote 옵션 > 웹 클리퍼의 토큰을 붙여 넣으세요"'),
]
SERVER_ENDPOINTS = {"ping", "folders", "notes"}     # app/clipserver.py 가 흉내 내는 조플린 API
# 안드로이드 앱의 웹 클리퍼(assets/clip)가 쓰는 라이브러리 사본: 원본 lib/ 와 같아야 한다. webclip.js 는 폰용으로 따로 만든 것이라 가져오지 않는다
PHONE = os.path.normpath(os.path.join(HERE, "..", "..", "iamtalkernote-android", "app", "src", "main", "assets", "clip"))
PHONE_LIBS = ["Readability.js", "turndown.js", "turndown-plugin-gfm.js"]


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def norm(b):
    return b.replace(b"\r\n", b"\n")


def version(path):
    try:
        m = re.search(r'"version"\s*:\s*"([^"]+)"', read(path).decode("utf-8"))
        return m.group(1) if m else "?"
    except OSError:
        return "-"


def protocol(background_js):
    """background.js 가 서버에 요청하는 주소와 노트 필드 → (주소 집합, 필드 집합)"""
    text = background_js.decode("utf-8", "ignore")
    endpoints = set(re.findall(r"joplinFetch\(\s*[`\"']/(\w+)", text))
    a, b = text.find("function buildNoteBody"), text.find("globalThis.BACKEND")
    region = text[a:b] if 0 <= a < b else text
    keys = set(re.findall(r"\b([a-z]+(?:_[a-z]+)+)\s*:", region)) | set(re.findall(r"payload\.([a-z_]+)", region))
    keys |= {k for k in re.findall(r"\b(title|body|tags)\s*:", region)}
    return endpoints, keys


def desired_options_html(src_bytes):
    """원본 options.html 에 앱 문구를 입힌다 → (바이트, 못 입힌 문구 목록)"""
    crlf = b"\r\n" in src_bytes
    text = norm(src_bytes).decode("utf-8")
    missed = []
    for a, b in PATCHES:
        if a in text:
            text = text.replace(a, b)
        else:
            missed.append(a)
    out = text.replace("\n", "\r\n") if crlf else text
    return out.encode("utf-8"), missed


def plan(src, dst):
    """무엇을 할지 계산한다 → dict(files={상대경로: 새 바이트}, new=[...], changed=[...], same=n, warnings=[...], old_ver, new_ver)"""
    files, changed, new, same, warnings = {}, [], [], 0, []
    for rel in MIRROR:
        sp, dp = os.path.join(src, *rel.split("/")), os.path.join(dst, *rel.split("/"))
        if not os.path.isfile(sp):
            warnings.append("원본에 없음(건너뜀): " + rel)
            continue
        sb = read(sp)
        if not os.path.isfile(dp):
            files[rel] = sb
            new.append(rel)
        elif norm(read(dp)) != norm(sb):
            files[rel] = sb
            changed.append(rel)
        else:
            same += 1
    sp = os.path.join(src, "options.html")
    if os.path.isfile(sp):
        want, missed = desired_options_html(read(sp))
        for a in missed:
            warnings.append("원본 options.html 이 바뀌어 앱 문구를 입힐 수 없음(수동 확인): " + a[:50])
        dp = os.path.join(dst, "options.html")
        if not missed:
            if not os.path.isfile(dp):
                files["options.html"] = want
                new.append("options.html")
            elif norm(read(dp)) != norm(want):
                files["options.html"] = want
                changed.append("options.html")
            else:
                same += 1
    # 서버와의 약속 점검: 새 주소·새 필드가 생겼는가
    sbg, dbg = os.path.join(src, "background.js"), os.path.join(dst, "background.js")
    if os.path.isfile(sbg):
        ep, keys = protocol(read(sbg))
        old_ep, old_keys = protocol(read(dbg)) if os.path.isfile(dbg) else (set(), set())
        if ep - SERVER_ENDPOINTS:
            warnings.append("확장이 앱 서버에 없는 주소를 요청함 → app/clipserver.py 를 같이 고칠 것: " + ", ".join("/" + e for e in sorted(ep - SERVER_ENDPOINTS)))
        if keys - old_keys:
            warnings.append("확장이 노트에 새 필드를 보냄 → app/clipserver.py create_note 가 처리하는지 확인: " + ", ".join(sorted(keys - old_keys)))
    return {"files": files, "new": new, "changed": changed, "same": same, "warnings": warnings,
            "old_ver": version(os.path.join(dst, "manifest.json")), "new_ver": version(os.path.join(src, "manifest.json"))}


def plan_phone(src, phone):
    """원본 lib/ 의 라이브러리를 폰 assets/clip/ 에 맞춘다 → {"files": {이름: 바이트}, "changed": [...], "warnings": [...]}.
    폰 폴더가 없으면(폰 저장소가 옆에 없을 때) 건너뛴다"""
    out = {"files": {}, "changed": [], "warnings": []}
    if not os.path.isdir(phone):
        out["warnings"].append("폰 assets/clip 폴더가 없어 건너뜀: " + phone)
        return out
    for name in PHONE_LIBS:
        sp, dp = os.path.join(src, "lib", name), os.path.join(phone, name)
        if not os.path.isfile(sp):
            out["warnings"].append("원본에 없음(건너뜀): lib/" + name)
            continue
        sb = read(sp)
        if not os.path.isfile(dp) or norm(read(dp)) != norm(sb):
            out["files"][name] = sb
            out["changed"].append(name)
    if out["changed"]:
        out["warnings"].append("폰 라이브러리가 바뀜 → 폰 assets/THIRD_PARTY_NOTICES.md 의 Readability·Turndown 버전 표기와 폰 시험(공유 → 저장) 확인")
    return out


def apply(p, dst, phone=None, ph=None):
    for rel, data in p["files"].items():
        path = os.path.join(dst, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    for name, data in (ph or {}).get("files", {}).items():
        with open(os.path.join(phone, name), "wb") as fh:
            fh.write(data)


def main(argv):
    do = "--apply" in argv
    args = [a for a in argv if not a.startswith("--")]
    src = os.path.abspath(args[0]) if args else DEFAULT_SRC
    if not os.path.isfile(os.path.join(src, "manifest.json")):
        print("원본 폴더를 찾을 수 없습니다:", src)
        return 2
    p = plan(src, DST)
    print("원본:", src)
    print("버전: %s → %s" % (p["old_ver"], p["new_ver"]))
    print("같음 %d · 새 파일 %d · 바뀜 %d" % (p["same"], len(p["new"]), len(p["changed"])))
    for r in p["new"]:
        print("  + " + r)
    for r in p["changed"]:
        print("  ~ " + r)
    for w in p["warnings"]:
        print("⚠ " + w)
    ph = plan_phone(src, PHONE)
    print("폰 assets/clip: 바뀜 %d" % len(ph["changed"]))
    for r in ph["changed"]:
        print("  ~ " + r)
    for w in ph["warnings"]:
        print("⚠ " + w)
    todo = len(p["files"]) + len(ph["files"])
    if not todo:
        print("이미 같습니다.")
    elif do:
        apply(p, DST, PHONE, ph)
        print("복사했습니다(PC 사본 %d개 · 폰 %d개). README 의 clipper 설명과 버전을 확인하세요." % (len(p["files"]), len(ph["files"])))
    else:
        print("(미리보기 — 실제로 복사하려면 --apply)")
    return 1 if (p["warnings"] or ph["warnings"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
