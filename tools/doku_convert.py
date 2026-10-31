"""도쿠위키 → 마크다운 변환(시험용 도구). 원본(pages·media)은 읽기만 하고, 변환 결과는 새 폴더에만 쓴다.

  py -3 -X utf8 tools/doku_convert.py <도쿠위키 data 폴더> <출력 폴더> <문서 이름…>        (이름은 pages 아래 .txt 를 뺀 것, 네임스페이스는 a/b)

출력 폴더가 노트 폴더(볼트)가 된다:
  <출력>/Wiki/<네임스페이스 폴더>/<제목>.md     … 위키 문서(이 앱의 최상위 노트북 'Wiki' = 위키 하나)
  <출력>/.resources/doku/<네임스페이스 폴더>/…   … 미디어(기존 UUID 그림과 분리)
변환 규칙(wikiconv 가 못 하는 것을 앞뒤에서 처리):
  {{page>문서}}        → 줄에 ![[제목]]        (포함, 이 앱의 include)
  {{tag>a b}}          → 맨 아래 '태그: #a #b' 줄
  [[ns:문서|글]]       → [[제목|글]]            (내부 링크, 제목은 id 의 마지막 이름, _ → 공백)
  {{ns:그림.png?200|설명}} → ![설명](상대경로)  + 미디어 복사
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import wikiconv  # noqa: E402

MEDIA_EXT = r"(?:png|jpe?g|gif|webp|svg|bmp)"
BAD = re.compile(r'[\\/:*?"<>|]')        # 파일 이름에 못 쓰는 글자: 도쿠위키 id 도 이런 글자는 지우므로 지운다
UNESC = re.compile(r"\\([\\_*\[\]()`#<>!|~])")      # wikiconv 가 글 속에 이스케이프한 글자를 되돌린다(자리표시자 안에서만 쓴다)


def title_of(page_id):
    """도쿠위키 id(ns:page 또는 ns/page, #절 제외) → 노트 제목(마지막 이름, _ → 공백)"""
    last = re.split(r"[:/]", page_id.strip().strip(":"))[-1]
    return re.sub(r"\s+", " ", BAD.sub("", last.replace("_", " "))).strip() or "제목 없음"


class Conv:
    def __init__(self, data, out):
        self.pages = os.path.join(data, "pages")
        self.media = os.path.join(data, "media")
        self.out = out
        self.stat = {"pages": 0, "includes": 0, "links": 0, "images": 0, "images_missing": 0, "tags": 0}
        self.missing = []

    def convert(self, name):
        src = os.path.join(self.pages, *name.split("/")) + ".txt"
        with open(src, encoding="utf-8") as fh:
            text = fh.read().replace("\r\n", "\n")
        ns = name.split("/")[:-1]
        title = title_of(name)
        depth = 1 + len(ns)                    # Wiki/ + 네임스페이스 폴더들

        tags = []

        def tag(m):
            tags.extend(m.group(1).split())
            return ""
        text = re.sub(r"\{\{tag>([^}]*)\}\}[ \t]*\n?", tag, text)

        def inc(m):
            self.stat["includes"] += 1
            target = m.group(1).split("&")[0].strip()
            pid, _, sec = target.partition("#")
            return "\n§§INC§§%s%s§§\n" % (title_of(pid), ("#" + sec.strip().replace("_", " ")) if sec.strip() else "")
        text = re.sub(r"^[ \t]*\{\{page>([^}]*)\}\}[ \t]*$", inc, text, flags=re.M)
        text = re.sub(r"\{\{page>([^}]*)\}\}", inc, text)

        def img(m):
            ref = m.group(1).strip()
            alt = (m.group(3) or "").strip()
            if re.match(r"(?i)^https?://", ref):          # 외부 그림 주소는 그대로 링크(복사할 파일이 없다)
                self.stat["images_external"] = self.stat.get("images_external", 0) + 1
                return "§§IMG§§%s§§%s§§" % (ref + (m.group(2) or ""), alt)
            mid = ref.lstrip(":") if ref.startswith(":") else ":".join(ns + [ref])
            if not ref.startswith(":") and not os.path.isfile(os.path.join(self.media, *mid.split(":"))) \
                    and os.path.isfile(os.path.join(self.media, *ref.split(":"))):
                mid = ref                                  # 상대 경로에 없으면 루트 기준(문서를 루트에서 쓰던 때의 경로)
            parts = mid.split(":")
            srcf = os.path.join(self.media, *parts)
            dst_rel = "/".join(parts)
            if os.path.isfile(srcf):
                dst = os.path.join(self.out, ".resources", "doku", *parts)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.exists(dst):
                    shutil.copy2(srcf, dst)
                self.stat["images"] += 1
            else:
                self.stat["images_missing"] += 1
                self.missing.append(mid)
            return "§§IMG§§%s§§%s§§" % ("../" * depth + ".resources/doku/" + dst_rel, alt)
        text = re.sub(r"\{\{\s*(:?[^}|?\s][^}|?]*?\." + MEDIA_EXT + r")(\?[^}|]*)?\s*(?:\|([^}]*))?\}\}", img, text, flags=re.I)

        def link(m):
            target, label = m.group(1).strip(), (m.group(2) or "").strip()
            if re.match(r"(?i)^([a-z][a-z0-9+.-]*://|mailto:|\\\\|[a-z]+>)", target) or target.startswith("#"):
                return m.group(0)
            pid, _, sec = target.partition("#")
            self.stat["links"] += 1
            t = title_of(pid) if pid else title
            return "§§LNK§§%s%s§§%s§§" % (t, ("#" + sec.strip()) if sec.strip() else "", label)
        text = re.sub(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]", link, text)

        md = wikiconv.convert(text, "dokuwiki", "markdown", title)
        md = re.sub(r"[ \t]*§§INC§§(.*?)§§[ \t]*", lambda m: "\n![[%s]]\n" % UNESC.sub(r"\1", m.group(1)), md)
        md = re.sub(r"§§IMG§§(.*?)§§(.*?)§§", lambda m: "![%s](%s)" % (UNESC.sub(r"\1", m.group(2)), UNESC.sub(r"\1", m.group(1))), md)

        def lnk(m):
            t, label = UNESC.sub(r"\1", m.group(1)), UNESC.sub(r"\1", m.group(2))
            return "[[%s|%s]]" % (t, label) if label and label != t else "[[%s]]" % t
        md = re.sub(r"§§LNK§§(.*?)§§(.*?)§§", lnk, md)
        md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
        if tags:
            self.stat["tags"] += 1
            md += "\n태그: " + " ".join("#" + t for t in tags) + "\n"
        dst = os.path.join(self.out, "Wiki", *ns, title + ".md")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
        self.stat["pages"] += 1
        return dst


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    c = Conv(sys.argv[1], sys.argv[2])
    for n in sys.argv[3:]:
        print("→", c.convert(n))
    print(c.stat)
    if c.missing:
        print("없는 미디어:", c.missing[:10])
