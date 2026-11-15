"""스크랩 군더더기 정리 시험(숫자만 다른 사이트 공통 줄, 미디어 줄 보호, 출처 없는 노트): py -3 -I -X utf8 tools/test_cleanup_junk.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import cleanup  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


class Note(dict):
    def __init__(self, path, body):
        super().__init__(path=path, title=path)
        self.body = body

    def read(self):
        return self.body


def scrap(i, extra=""):
    return ("---\nsource: https://board.example.com/view/%d\n---\n\n# 글 제목 %d\n\n"
            "총 %d개의 사이트에서 %d 개의 댓글이 달렸습니다. (클릭시 확인)\n"
            "조회 **%d** 추천 %d\n\n"
            "이것은 %d번째 글의 고유한 본문 내용입니다. 충분히 길어서 군더더기가 아닙니다 %s.\n%s") % (i, i, i * 3, i * 7, i * 11, i, i, "x" * i, extra)


notes = [Note("n%d" % i, scrap(i)) for i in range(1, 9)]
res = cleanup.scan_junk(notes)
out = {n["path"]: (new, [l for _no, l, _w in rem]) for n, new, rem in res}
check("숫자만 다른 줄(총 N개의 사이트에서…)을 사이트 공통으로 지운다", all("댓글이 달렸습니다" not in out["n%d" % i][0] for i in range(1, 9)) and len(out) == 8)
check("강조 기호가 낀 줄(조회 **N** 추천 N)도 지운다", all("조회" not in out["n%d" % i][0] for i in range(1, 9)))
check("고유한 본문 줄은 남긴다", all("고유한 본문 내용" in out["n%d" % i][0] for i in range(1, 9)))
check("제목 줄은 남긴다", all("# 글 제목" in out["n%d" % i][0] for i in range(1, 9)))

# 미디어 줄은 사이트 공통이어도·메뉴 모양이어도 지우지 않는다
media = ["![](http://img.example.com/icon.png)", "[소리 1](https://cdn.example.com/a.mp3)", "[영상](https://cdn.example.com/b.mp4)",
         "<video src=\"https://cdn.example.com/c.mp4\"></video>", "![](../.resources/abc123.png)", "[첨부 1.jpg](https://img.example.com/download.php?no=1)",
         "https://www.youtube.com/watch?v=abcdefghijk"]
notes2 = [Note("m%d" % i, scrap(i, "\n".join(media) + "\n")) for i in range(1, 9)]
res2 = cleanup.scan_junk(notes2)
kept = {n["path"]: new for n, new, _rem in res2}
check("그림·mp3·mp4·video·리소스·유튜브 줄은 모두 남는다", all(all(m in kept["m%d" % i] for m in media) for i in range(1, 9)))
check("미디어 줄이 있어도 글자 군더더기는 지운다", all("댓글이 달렸습니다" not in kept["m%d" % i] for i in range(1, 9)))

# 출처 없는 내 글은 건드리지 않는다
mine = Note("mine", "# 할 일\n\n- 로그인\n- 광고\n- 공유\n- next\n\n본문 문장이 길게 있습니다 충분히.\n")
check("출처 없는 노트는 줄을 지우지 않는다", cleanup.scan_junk([mine]) == [])

# 한 번 정리한 뒤 다시 돌려도 더 나오지 않는다
again = [Note(n["path"], new) for n, new, _r in res]
check("정리한 뒤 다시 돌려도 더 나오지 않는다", cleanup.scan_junk(again) == [])

print("FAILS:", fails)
sys.exit(1 if fails else 0)
