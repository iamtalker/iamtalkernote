"""태그 대량 저장 중에도 Tk 이벤트 루프가 계속 돌고 기존 태그 전용 옵션이 기본 선택인지 확인."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

tmp = tempfile.TemporaryDirectory()
base = Path(tmp.name)
vault = base / 'notes'; vault.mkdir()
config = base / 'settings' / 'iamtalkernote'; config.mkdir(parents=True)
(config / 'config.json').write_text(json.dumps({'root': str(vault), 'lang': 'ko', 'snap_auto': False}), encoding='utf-8')
os.environ['APPDATA'] = str(config.parent)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import notes
import autotags
from tagtext import edit_tags, note_tags

for i in range(100): (vault / ('note%d.md' % i)).write_text('본문 #oneoff #keep\n', encoding='utf-8')
app = notes.App()
state = {'ticks': 0, 'done': False, 'timeout': False}
old_info = notes.messagebox.showinfo
try:
    app.root.after(700, app.root.quit); app.root.mainloop()
    app.reload_notes()
    app.show_auto_tags()
    def widgets(w):
        yield w
        for child in w.winfo_children(): yield from widgets(child)
    checkbox = next(w for w in widgets(app.root) if w.winfo_class() == 'Checkbutton' and '이미 존재하는 태그' in str(w.cget('text')))
    assert checkbox.getvar(checkbox.cget('variable')) == 1
    checkbox.winfo_toplevel().destroy()
    items = []
    for n in app.all_notes:
        original = n.read(); edited, _ = edit_tags(original, ['oneoff'], None)
        items.append((n, autotags.digest(original), edited))
    original_save = app.store.save
    def slow_save(*args, **kwargs):
        time.sleep(.005)  # 느린 저장소를 재현한다.
        return original_save(*args, **kwargs)
    app.store.save = slow_save
    def info(*args, **kwargs):
        state['done'] = True; app.root.quit()
    notes.messagebox.showinfo = info
    def beat():
        state['ticks'] += 1
        if not state['done']: app.root.after(10, beat)
    def timeout(): state['timeout'] = True; app.root.quit()
    app.root.after(10, beat); app.root.after(15000, timeout)
    started = time.perf_counter(); app.tag_write(items, ['oneoff'], None)
    assert time.perf_counter() - started < .5, '일괄 저장이 UI 스레드를 막음'
    app.root.mainloop()
    assert state['done'] and not state['timeout'], state
    assert state['ticks'] > 5, state
    assert all(note_tags(n.read()) == {'keep'} for n in app.all_notes)
    print('PASS: existing-only checkbox defaults on; 100 slow saves kept UI responsive (%d heartbeats)' % state['ticks'])
finally:
    notes.messagebox.showinfo = old_info
    app.root.destroy()
