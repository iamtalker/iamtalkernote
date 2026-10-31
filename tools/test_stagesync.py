"""stagesync 의 순수 계산 시험"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import stagesync as ss
import syncpolicy as sp

ok = []
def check(desc, cond):
    ok.append(bool(cond)); print(("  ✔ " if cond else "  ✘ ") + desc)

check("받는 중이면 그대로", ss.decide(1, 5, False, 0, 0, 1000) == (1, 0, 0))
check("처음 다 받음 → 시각만 적음", ss.decide(1, 5, True, 0, 0, 1000) == (1, 1000, 0))
check("20초 안 지남 → 대기", ss.decide(1, 5, True, 1000, 0, 1010) == (1, 1000, 0))
check("20초 이어짐 → 다음 단계, 열린 시각 기록", ss.decide(1, 5, True, 1000, 0, 1025) == (2, 0, 1025))
check("방금 연 뒤 60초 안에는 다시 안 엶", ss.decide(2, 5, True, 0, 1025, 1050) == (2, 0, 1025))
check("마지막 단계면 그대로", ss.decide(5, 5, True, 0, 0, 9999) == (5, 0, 0))

pol = sp.new_policy()
plans = [{"module": "markdown", "ignore": ["/.history"]}, {"module": "ext1", "ignore": ["x"]}]
ss.extra_ignore = lambda root, policy: ["/a.md", "/b.md"]
out = ss.apply_plans(plans, "r", pol)
check("노트 폴더에만 가림 줄이 붙음", out[0]["ignore"] == ["/.history", "/a.md", "/b.md"] and out[1]["ignore"] == ["x"])
check("원본 목록은 안 바뀜", plans[0]["ignore"] == ["/.history"])
print("통과 %d / %d" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
