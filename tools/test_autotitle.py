"""본문 첫 줄 제목(app/autotitle.py) 시험: py -3 -I -X utf8 tools/test_autotitle.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from autotitle import title_from_body as t

fails = 0


def check(name, ok):
    global fails
    print(("  ✔ " if ok else "  ✘ ") + name)
    fails += 0 if ok else 1


check("첫 글 줄", t("오늘 할 일\n둘째 줄") == "오늘 할 일")
check("빈 줄·공백 건너뜀", t("\n\n  \n안녕") == "안녕")
check("제목 기호 # 뗌", t("## 회의 메모\n본문") == "회의 메모")
check("목록·번호·체크 칸 뗌", t("- [ ] 장보기") == "장보기" and t("1. 첫째") == "첫째" and t("* 별") == "별")
check("인용 뗌", t("> 인용문") == "인용문")
check("강조·링크 풀기", t("**굵게** [링크](http://a.b) `코드`") == "굵게 링크 코드")
check("머리말 건너뜀", t("---\ntitle: x\n---\n진짜 첫 줄") == "진짜 첫 줄")
check("가로줄·코드 울타리 건너뜀", t("---\n```\n글") == "글")
check("파일 이름에 못 쓰는 글자 제거", t("a/b:c?d") == "a b c d")
check("50자로 자름", len(t("가" * 80)) == 50)
check("본문이 비면 ''", t("") == "" and t("\n  \n") == "" and t("---\n---\n") == "")
sys.exit(1 if fails else 0)
