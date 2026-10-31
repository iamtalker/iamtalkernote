"""태그 글 처리(app/tagtext.py) 시험: py -3 -I -X utf8 tools/test_tagtext.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import tagtext as tt

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


body = "---\ntitle: x\ntags: [Work, 경제]\n---\n본문 #work 와 #workout 은 다르고\n```\n#work\n```\n주소 http://a.com/#frag 는 아님\n\n태그: #경제 #work\n"
check("해시태그 읽기(앞 글자·주소 앵커 제외)", tt.hashtags("가 #a #b_c x#no (#no) http://x/#no") == ["a", "b_c"])
check("태그 줄 읽기", tt.line_tags("태그: a, #b [링크](주소)") == ["a", "b"])
check("note_tags: 머리말·줄·본문(코드·주소 속 제외)", tt.note_tags(body) == {"Work", "경제", "work", "workout"})
check("태그 이름 정리", tt.clean_tag_name(" #내 태그 ") == "내_태그" and tt.clean_tag_name("a/b") == "")
new, n = tt.edit_tag(body, "work", "일")
check("이름 바꾸기: 본문 #work 와 태그 줄, 머리말 Work 는 별개", "#일 와" in new and "#workout" in new and "태그: #경제 #일" in new and "Work" in new)
check("이름 바꾸기: 코드 블록 속은 그대로", "```\n#work\n```" in new)
check("바꾼 개수", n["line"] == 1 and n["inline"] == 1)
gone, n2 = tt.edit_tag("a #x b\n태그: #x\n", "x", None)
check("지우기: 본문 #x 와 비게 된 태그 줄", gone == "a b\n" and n2["line"] == 1 and n2["inline"] == 1)
added, did = tt.add_tag("글\n", "새")
check("태그 더하기: 줄이 없으면 만든다", did and added.endswith("태그: #새\n"))
again, did2 = tt.add_tag(added, "새")
check("이미 있으면 그대로", not did2 and again == added)
sys.exit(1 if fails else 0)
