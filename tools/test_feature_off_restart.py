"""즐겨찾기·달력·아웃라이너 폴더를 끄고 다시 시작했을 때, 닫기 전에 보던 항목이 그 기능이면 '모든 파일' 로 시작해 목록이 비지 않고 뜨는지 시험.
앱은 한 프로세스에서 두 번 띄울 수 없어서(Tk 그림) 시나리오마다 새 프로세스로 돌린다. 임시 APPDATA·임시 노트 폴더만 쓴다.
py -3 -X utf8 tools/test_feature_off_restart.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = (("즐겨찾기", "@favs", "use_favs"), ("달력·할일", "@cal", "use_cal"), ("아웃라이너 폴더", "아웃라이너", "use_outl"))


def child(saved_nb, key, on):
    """앱을 한 번 띄워 (시작 노트북, 시작 목록 수, 노트북을 누른 뒤 노트북, 목록 수) 를 JSON 한 줄로 낸다."""
    sys.path.insert(0, os.path.join(HERE, "..", "app"))
    os.environ["IAT_NO_SINGLE"] = "1"
    tmp = tempfile.mkdtemp(prefix="feat-off-")
    vault = os.path.join(tmp, "v")
    for nb in ("업무", "개인"):
        os.makedirs(os.path.join(vault, nb))
        for i in range(3):
            with open(os.path.join(vault, nb, f"{nb}{i}.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write(f"본문 {nb} {i}\n")
    os.makedirs(os.path.join(tmp, "appdata", "iamtalkernote"))
    with open(os.path.join(tmp, "appdata", "iamtalkernote", "config.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"root": vault, "window": {"nb": saved_nb}, key: on}))
    os.environ["APPDATA"] = os.path.join(tmp, "appdata")
    import notes

    a = notes.App()

    def pump(n):
        for _ in range(n):
            a.root.update()
            time.sleep(0.02)
    pump(80)
    first = (a.nb, len(a.results))
    a.nbtree.selection_set(f"nb{a.nb_keys.index('업무')}")
    a.on_nb_select()
    pump(30)
    print("RESULT " + json.dumps([first[0], first[1], a.nb, len(a.results)], ensure_ascii=False))
    a.root.destroy()


def run(saved_nb, key, on):
    p = subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "--child", saved_nb, key, str(int(on))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    print(p.stderr[-600:])
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], bool(int(sys.argv[4])))
        sys.exit(0)
    fails = 0

    def check(name, ok):
        global fails
        print(("  ✔ " if ok else "  ✘ ") + name)
        fails += 0 if ok else 1

    for label, saved, key in SCENARIOS:
        r = run(saved, key, False)
        check(f"{label}를 끄고 다시 시작하면 '모든 파일' 로 시작해 노트 6개가 뜬다", r is not None and r[0] == "*" and r[1] == 6)
        check(f"{label}를 끄고 다시 시작한 뒤 노트북을 누르면 그 노트 3개가 뜬다", r is not None and r[2] == "업무" and r[3] == 3)
    r = run("@favs", "use_favs", True)
    check("즐겨찾기를 켜 둔 채면 즐겨찾기 항목에서 시작한다", r is not None and r[0] == "@favs")
    sys.exit(1 if fails else 0)
