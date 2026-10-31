"""아웃라이너 규모 측정: 항목 N개(깊이 섞음)를 불러오고 Enter·Tab·입력이 얼마나 걸리는지 잰다.
실행:  py -3 -I -X utf8 tools/perf_outliner.py [항목수]   (임시 데이터만 쓴다. 한도: 불러오기 3초, 키 한 번 0.3초)"""
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from outliner.widget import OutlineEditor

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
C = {"bg": "#ffffff", "text": "#222222", "muted": "#888888", "accent": "#2563eb", "sel": "#cfe3ff"}
root = tk.Tk()
root.geometry("700x500")
saved = []
w = OutlineEditor(root, C, ("Malgun Gothic", 11), saved.append)
w.pack(fill="both", expand=True)

lines = []
for i in range(N):
    depth = (i % 7) % 4
    lines.append("    " * depth + f"- 항목 {i} 가나다라마바사")
text = "\n".join(lines) + "\n"

t0 = time.perf_counter()
w.load(text)
root.update()
load = time.perf_counter() - t0
print(f"불러오기 {N}개: {load:.2f}초")

t = w.txt
worst = {}


def timed(name, fn):
    t1 = time.perf_counter()
    fn()
    root.update()
    dt = time.perf_counter() - t1
    worst[name] = max(worst.get(name, 0), dt)


for k in range(5):
    t.mark_set("insert", f"{N // 2 + k}.5")
    timed("Enter", lambda: w._enter(None))
    timed("Tab", lambda: w._tab(None))
    timed("Shift+Tab", lambda: w._btab(None))
    timed("글자 입력", lambda: (t.insert("insert", "가"), w.pull()))
for k, v in worst.items():
    print(f"  {k}: 최악 {v * 1000:.0f}ms")
ok = load < 3.0 and all(v < 0.3 for v in worst.values())
print("통과" if ok else "느림 — 확인 필요")
sys.exit(0 if ok else 1)
