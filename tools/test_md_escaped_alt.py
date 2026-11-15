"""그림 설명(alt)에 \\[ \\] 가 들어 있는 그림(클리퍼가 제목의 대괄호를 이스케이프해서 저장한 것)이 그림으로 읽히는지 시험: py -3 -I -X utf8 tools/test_md_escaped_alt.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
from wikiconv import markdown as md  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


def blocks(src):
    return md.read(src, "t").blocks


plain = blocks("[![사진](../.resources/a.jpg)](https://x.com/a.jpg)")
check("보통 설명의 링크 달린 그림", plain == [["p", [["url", "https://x.com/a.jpg", [["img", "../.resources/a.jpg", "사진"]]]]]])

esc = blocks("[![\\[스압\\] 제목.jpg\\_1.jpg](../.resources/a.jpg)](https://x.com/a.jpg)")
check("설명에 \\[ \\] 가 있는 링크 달린 그림", esc == [["p", [["url", "https://x.com/a.jpg", [["img", "../.resources/a.jpg", "[스압] 제목.jpg_1.jpg"]]]]]])

alone = blocks("![\\[스압\\] 제목](../.resources/a.jpg)")
check("설명에 \\[ \\] 가 있는 그림", alone == [["p", [["img", "../.resources/a.jpg", "[스압] 제목"]]]])

two = blocks("![a\\]b](x.png) 그리고 ![c](y.png)")
check("한 줄의 그림 두 개가 따로 읽힌다", repr(two).count("'img'") == 2)

text = blocks("그냥 \\[대괄호\\] 글 [링크](https://x.com)")
check("그림이 아닌 이스케이프 글은 그대로", repr(text).count("'img'") == 0 and "대괄호" in repr(text))

print("FAILS:", fails)
sys.exit(1 if fails else 0)
