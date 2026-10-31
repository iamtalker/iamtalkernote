"""제3자 라이선스 고지(app/assets/THIRD_PARTY_NOTICES.md)를 만든다. 포함된 라이브러리의 라이선스 원문을 설치된 패키지에서 그대로 모은다.
  py -3 -X utf8 tools/gen_notices.py
exe 에는 app/assets 폴더가 통째로 들어가므로(도움말 → 오픈소스 라이선스) 새 라이브러리를 넣거나 버전이 바뀌면 다시 만든다."""
import importlib.metadata as md
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "assets", "THIRD_PARTY_NOTICES.md")
PYDIR = os.path.dirname(sys.executable)


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip("\n")


def dist_license(name, pattern=("licen", "copying")):
    d = md.distribution(name)
    for f in d.files or []:
        low = str(f).lower()
        if any(p in low for p in pattern) and "dist-info" in low:
            return d.version, read(str(d.locate_file(f)))
    raise SystemExit("라이선스 파일을 못 찾음: " + name)


parts = []


def add(title, meta, text, url=None):
    s = "## %s\n\n%s\n" % (title, meta)
    if url:
        s += "\n원본: %s\n" % url
    if text:
        s += "\n```text\n%s\n```\n" % text
    parts.append(s)


head = """# 제3자 소프트웨어 고지 · Third-party notices

iamtalkernote 는 아래 오픈소스 소프트웨어를 포함하거나 사용합니다. 각 소프트웨어의 저작권과 라이선스 전문을 그대로 싣습니다.
(iamtalkernote 자체는 PolyForm Noncommercial License 1.0.0 입니다. `LICENSE` 참고.)

iamtalkernote includes or uses the open-source software below. Each copyright notice and license text is reproduced as published.
(iamtalkernote itself is licensed under the PolyForm Noncommercial License 1.0.0; see `LICENSE`.)

같은 저작자(iamtalker)의 프로젝트 / Projects by the same author, included under their own licenses:
[위키나루 wiki-naru](https://github.com/iamtalker/wiki-naru) (PolyForm Noncommercial 1.0.0: `app/editor.py` · `preview.py` · `bulk.py` · `wikiconv/`),
[folder-search](https://github.com/iamtalker/folder-search) (검색 문법 · search syntax),
[Joplin Clipper Plus](https://github.com/iamtalker/joplin-clipper-plus) (MIT: `clipper/`).

"Joplin", "Evernote", "Syncthing" 은 각 소유자의 상표입니다. 이 프로젝트는 그들과 관련이 없는 비공식 프로젝트이며 이름은 호환·사용 사실을 밝히려는 목적으로만 씁니다.
"Joplin", "Evernote" and "Syncthing" are trademarks of their respective owners. This project is unofficial and unaffiliated; the names are used only to state compatibility or use.
"""
parts.append(head)

v, t = dist_license("pillow")
add("Pillow %s — MIT-CMU (HPND)" % v, "이미지 변환(WebP 등) · image conversion. Copyright (c) 1997-2011 by Secret Labs AB, Copyright (c) 1995-2011 by Fredrik Lundh and contributors, Copyright (c) 2010 by Jeffrey A. Clark and contributors.",
    t, "https://python-pillow.org")
v, t = dist_license("pypdf")
add("pypdf %s — BSD-3-Clause" % v, "PDF 글 읽기 · PDF text extraction.", t, "https://github.com/py-pdf/pypdf")
v, t = dist_license("tinytag")
add("tinytag %s — MIT" % v, "mp3 등 소리 파일 태그 읽기 · audio tag reading.", t, "https://github.com/tinytag/tinytag")
add("segno 1.6.6 — BSD-3-Clause", "QR 코드 만들기(`app/segno/` 에 포함) · QR code generation (bundled in `app/segno/`).",
    read(os.path.join(ROOT, "app", "segno", "LICENSE")), "https://github.com/heuer/segno")
add("Joplin Clipper Plus — MIT", "웹 클리퍼 확장(`clipper/`), 같은 저작자 · web clipper extension, same author.",
    read(os.path.join(ROOT, "clipper", "LICENSE")), "https://github.com/iamtalker/joplin-clipper-plus")

apache = None
for cand in ("packaging",):
    d = md.distribution(cand)
    for f in d.files or []:
        if str(f).lower().endswith("license.apache"):
            apache = read(str(d.locate_file(f)))
add("Mozilla Readability — Apache-2.0", "웹 페이지 본문 추출(`clipper/lib/Readability.js`). Copyright (c) 2010 Arc90 Inc. Licensed under the Apache License, Version 2.0.",
    apache, "https://github.com/mozilla/readability")
mit_turndown = """The MIT License (MIT)

Copyright (c) 2017+ Dom Christie

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE."""
add("Turndown and turndown-plugin-gfm — MIT", "HTML → 마크다운 변환(`clipper/lib/turndown*.js`) · HTML to Markdown.", mit_turndown, "https://github.com/mixmark-io/turndown")

v, t = dist_license("pyinstaller", ("copying",))
add("PyInstaller %s — GPL-2.0-or-later with Bootloader Exception" % v,
    "exe 를 만드는 도구와 실행 시작 코드(부트로더) · the tool that builds the exe and its bootloader. 부트로더 예외에 따라 이 프로그램은 GPL 의 제한 없이 배포됩니다 / under the Bootloader Exception, programs built with it are not subject to the GPL.",
    t, "https://pyinstaller.org")
add("Python — PSF License", "exe 에 파이썬 실행 환경이 들어 있습니다 · the exe embeds the Python runtime.", read(os.path.join(PYDIR, "LICENSE.txt")), "https://www.python.org")
add("Tcl/Tk — Tcl/Tk License", "화면(tkinter) 라이브러리 · the GUI toolkit behind tkinter.", read(os.path.join(PYDIR, "tcl", "tk8.6", "license.terms")), "https://www.tcl-lang.org")

add("Syncthing — MPL-2.0 (실행할 때 내려받음 / downloaded at run time)",
    "동기화를 켜면 공식 GitHub 릴리스에서 Syncthing 을 내려받아(코드에 박아 둔 SHA-256 과 같을 때만) 실행합니다. 이 프로그램에 포함되어 있지 않고 수정하지 않았습니다. "
    "When sync is turned on, the app downloads Syncthing from its official GitHub release (only if the SHA-256 matches) and runs it. It is not bundled and not modified. "
    "Syncthing 은 Mozilla Public License 2.0 입니다: https://www.mozilla.org/MPL/2.0/ · 소스 코드 / source code: https://github.com/syncthing/syncthing",
    "", "https://syncthing.net")

with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(parts))
print(OUT, os.path.getsize(OUT) // 1024, "KB")
