"""클리퍼 동기화 도구(tools/sync_clipper.py) 시험: 임시 폴더만 쓴다.  py -3 -I -X utf8 tools/test_sync_clipper.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sync_clipper as sc  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


def write(root, rel, data):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


BG = ('async function buildNoteBody(clip){ const base = { source_url: clip.url }; return { ...base, title: clip.title, body: clip.markdown }; }\n'
      'function createNote(){ payload.parent_id = 1; return joplinFetch("/notes", {}); }\n'
      'async function t(){ await joplinFetch("/folders?limit=1"); }\nglobalThis.BACKEND = {};\n')
OPT = ('<h1>Joplin Clipper Plus — 설정</h1>\n<label for="port">조플린 Web Clipper 포트</label>\n'
       '<div class="hint">조플린 데스크톱 앱 → 도구 → 옵션 → Web Clipper → "Web Clipper 서비스 활성화"가 켜져 있는지 확인하세요.</div>\n'
       '<input id="token" type="password" autocomplete="off" placeholder="조플린 Web Clipper 옵션 화면에 표시된 토큰을 붙여 넣으세요" />\n')


def make_source(root, version="1.0.0", bg=BG, lib="lib-v1"):
    for rel in sc.MIRROR:
        write(root, rel, ("// " + rel + "\n").encode("utf-8"))
    write(root, "manifest.json", '{"version": "%s"}' % version)
    write(root, "background.js", bg)
    write(root, "options.html", OPT.replace("\n", "\r\n"))
    for n in sc.PHONE_LIBS:
        write(root, "lib/" + n, lib + n)


tmp = tempfile.mkdtemp(prefix="syncclip-")
src, dst, phone = (os.path.join(tmp, d) for d in ("src", "dst", "phone"))
make_source(src)
os.makedirs(phone)

print("처음 가져오기")
p = sc.plan(src, dst)
check("모두 새 파일 + options.html", len(p["new"]) == len(sc.MIRROR) + 1 and not p["changed"])
check("버전 읽음", p["new_ver"] == "1.0.0" and p["old_ver"] == "-")
ph = sc.plan_phone(src, phone)
check("폰 라이브러리 3개 새로", sorted(ph["changed"]) == sorted(sc.PHONE_LIBS))
sc.apply(p, dst, phone, ph)
opt = open(os.path.join(dst, "options.html"), "rb").read().decode("utf-8")
check("options.html 에 앱 문구가 입혀짐", "iamtalkernote 연결" in opt and "iamtalkernote 옵션 > 웹 클리퍼" in opt and "조플린 데스크톱" not in opt)
check("options.html 줄 끝(CRLF) 유지", b"\r\n" in open(os.path.join(dst, "options.html"), "rb").read())
check("폰에 라이브러리가 복사됨", open(os.path.join(phone, "Readability.js")).read() == "lib-v1Readability.js")

print("바뀐 것이 없으면")
p = sc.plan(src, dst)
check("같음 · 바뀜 0 · 경고 없음", not p["new"] and not p["changed"] and not p["files"] and not p["warnings"] and p["same"] == len(sc.MIRROR) + 1)
check("폰도 같음", not sc.plan_phone(src, phone)["files"])
# 줄 끝만 다른 것은 같은 것으로 본다
write(dst, "core.js", b"// core.js\r\n")
write(src, "core.js", b"// core.js\n")
check("줄 끝(CRLF/LF)만 다르면 바뀐 것이 아님", "core.js" not in sc.plan(src, dst)["changed"])

print("원본이 업데이트되면")
make_source(src, version="1.1.0", lib="lib-v2")
write(src, "content.js", "// content.js changed\n")
p = sc.plan(src, dst)
check("바뀐 파일만 목록에", "content.js" in p["changed"] and "manifest.json" in p["changed"])
check("버전 변화 표시", (p["old_ver"], p["new_ver"]) == ("1.0.0", "1.1.0"))
ph = sc.plan_phone(src, phone)
check("폰 라이브러리 변화 + 안내 경고", len(ph["changed"]) == 3 and any("THIRD_PARTY" in w for w in ph["warnings"]))
sc.apply(p, dst, phone, ph)
check("복사 뒤 바로 같음", not sc.plan(src, dst)["files"] and not sc.plan_phone(src, phone)["files"])

print("서버와의 약속 점검")
bg2 = BG.replace('joplinFetch("/notes", {})', 'joplinFetch("/notes", {}); joplinFetch("/resources", {})')
write(src, "background.js", bg2)
w = sc.plan(src, dst)["warnings"]
check("앱 서버에 없는 새 주소(/resources) 경고", any("/resources" in x for x in w))
bg3 = BG.replace("{ ...base, title: clip.title,", "{ ...base, parent_name: clip.x, title: clip.title,")
write(src, "background.js", bg3)
w = sc.plan(src, dst)["warnings"]
check("노트에 새 필드(parent_name) 경고", any("parent_name" in x for x in w))
write(src, "background.js", BG)
check("원래대로면 경고 없음", not sc.plan(src, dst)["warnings"])

print("원본 options.html 이 바뀌어 문구를 못 입힐 때")
write(src, "options.html", "<h1>New title</h1>\n")
p = sc.plan(src, dst)
check("경고하고 options.html 은 건드리지 않음", any("options.html" in x for x in p["warnings"]) and "options.html" not in p["files"])

print("폰 폴더가 없으면")
check("건너뛰고 경고", "건너뜀" in sc.plan_phone(src, os.path.join(tmp, "none"))["warnings"][0])

print("\n%s" % ("모두 통과" if not fails else "실패 %d" % fails))
sys.exit(1 if fails else 0)
