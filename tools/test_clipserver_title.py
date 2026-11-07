"""웹 클리퍼 스크랩: 본문 맨 위의 제목 줄을 노트 제목과 비교해 뺀다 (clipserver.drop_leading_title)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from clipserver import drop_leading_title  # noqa: E402

FAILS = []


def check(name, got, want):
    ok = got == want
    print(("  ✔ " if ok else "  ✘ ") + name)
    if not ok:
        FAILS.append(name)
        print(f"      got={got!r}\n      want={want!r}")


T = "법원, '개인정보 무단 수집' 쿠팡 2000억원대 과징금 효력정지 인용 결정 - 자유게시판 ｜ 다모앙 종합 커뮤니티 damoang"

check("사이트 이름이 붙은 제목과 같은 헤딩은 뺀다",
      drop_leading_title("# 법원, '개인정보 무단 수집' 쿠팡 2000억원대 과징금 효력정지 인용 결정\n\n본문", T), "본문")
check("같은 제목의 ## 헤딩도 뺀다", drop_leading_title("## 아파트너가 털렸네요.\n\n본문", "아파트너가 털렸네요. - 다모앙"), "본문")
check("다른 제목의 헤딩은 그대로 둔다", drop_leading_title("# 다른 글\n본문", T), "# 다른 글\n본문")
check("본문 중간의 같은 제목은 건드리지 않는다", drop_leading_title("본문\n# 제목입니다\n", "제목입니다"), "본문\n# 제목입니다\n")
check("4글자 미만의 짧은 헤딩은 제목 안에 있어도 빼지 않는다", drop_leading_title("# 제목\n본문", "제목 - 사이트"), "# 제목\n본문")
check("제목이 없으면 그대로", drop_leading_title("# 제목\n본문", ""), "# 제목\n본문")

print("\n모두 통과" if not FAILS else f"\n실패 {len(FAILS)}개")
sys.exit(1 if FAILS else 0)
