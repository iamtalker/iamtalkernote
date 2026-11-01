"""동기화 충돌 사본(…sync-conflict-….md) 인식 시험"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import store as st  # noqa: E402

fail = 0


def check(name, got, want):
    global fail
    if got != want:
        fail += 1
        print("FAIL", name, got, want)


c = st.conflict_of("회의록.sync-conflict-20261101-143005-ABCDEFG.md")
check("basic", c, ("회의록.md", "2026-11-01 14:30"))
check("dots", st.conflict_of("a.b.sync-conflict-20261101-143005-ABCDEFG.md"), ("a.b.md", "2026-11-01 14:30"))
check("no-id", st.conflict_of("x.sync-conflict-20261101-143005.md"), ("x.md", "2026-11-01 14:30"))
check("lower-ext", st.conflict_of("x.sync-conflict-20261101-143005-AB12CD3.MD")[0], "x.MD")
check("plain", st.conflict_of("회의록.md"), None)
check("not-md", st.conflict_of("x.sync-conflict-20261101-143005-ABCDEFG.png"), None)
check("title", st.note_title("회의록.sync-conflict-20261101-143005-ABCDEFG.md"), "회의록 (충돌 2026-11-01 14:30)")
check("title-plain", st.note_title("회의록.md"), "회의록")
print("통과" if not fail else "실패 %d" % fail)
sys.exit(1 if fail else 0)
