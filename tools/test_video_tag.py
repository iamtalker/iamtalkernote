"""영상 파일 <video src=…> 읽기(wikiconv) 시험: py -3 -I -X utf8 tools/test_video_tag.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import bulk
import wikiconv
from wikiconv import tree

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


src = '앞 글\n\n<video controls="" src="https://i.aagag.com/KuiU2.mp4"></video>\n\n뒤 글\n'
doc = wikiconv.parse(src, bulk.SYNTAX["markdown"], "t")
check("<video src> 가 영상 파일 노드로", doc.blocks[1] == ["p", [["video", "file", "https://i.aagag.com/KuiU2.mp4"]]])
out = wikiconv.render(doc, "markdown", "t")
check("마크다운으로 쓰면 재생 링크", "[▶ 동영상 재생](<https://i.aagag.com/KuiU2.mp4>)" in out)
check("그 링크를 다시 읽으면 영상 파일로 되돌아옴", wikiconv.parse(out, bulk.SYNTAX["markdown"], "t").blocks[1] == ["p", [["video", "file", "https://i.aagag.com/KuiU2.mp4"]]])
check("영상 파일 주소 판별(? 뒤 값 무시)", tree.is_video_file("https://a.b/c.MP4?x=1") and not tree.is_video_file("https://a.b/c.html"))
check("작은따옴표 없이 속성이 섞여도 읽음", wikiconv.parse('<video autoplay muted src="https://x/y.webm" loop></video>', "markdown", "t").blocks[0][1][0][:2] == ["video", "file"])
print("실패 %d" % fails if fails else "전부 통과")
sys.exit(1 if fails else 0)
