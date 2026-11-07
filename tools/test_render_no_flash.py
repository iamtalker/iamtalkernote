"""그림 렌더링 도중 idle 재진입으로 미완성 화면을 그리지 않는지 확인한다."""
import json
import os
import sys
import tempfile
from pathlib import Path
from PIL import Image

tmp = tempfile.TemporaryDirectory()
base = Path(tmp.name); vault = base / 'notes'; vault.mkdir()
settings = base / 'config' / 'iamtalkernote'; settings.mkdir(parents=True)
(settings / 'config.json').write_text(json.dumps({'root': str(vault), 'lang': 'ko', 'snap_auto': False}), encoding='utf-8')
os.environ['APPDATA'] = str(settings.parent)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import notes

Image.new('RGB', (32, 32), 'blue').save(vault / 'picture.png')
(vault / 'images.md').write_text('# 제목\n\n' + '![](picture.png)\n\n' * 8 + 'END_MARKER\n', encoding='utf-8')
app = notes.App()
try:
    app.root.after(700, app.root.quit); app.root.mainloop(); app.reload_notes()
    app.set_mode('view'); app.root.update()
    observations = []
    original = app.show_image
    def observe_image(*args, **kw):
        app.root.after_idle(lambda: observations.append((app.view.get('1.0', 'end-1c'), app.edit_frame.winfo_ismapped())))
        return original(*args, **kw)
    app.show_image = observe_image
    app.open_note(next(n for n in app.all_notes if n['title'] == 'images'))
    # 그림 변환이 끝날 때까지 그리지 않고 기다리므로(render 보류), 그림이 그려질 때까지 이벤트를 돌린다
    import time as _t
    deadline = _t.time() + 5
    while _t.time() < deadline and not any('END_MARKER' in text for text, _ in observations):
        app.root.update(); _t.sleep(0.02)
    app.root.update()
    assert observations and all('END_MARKER' in text and not editing for text, editing in observations), observations
    app.new_note(); app.root.update()
    assert app.text.get('1.0', 'end-1c') == '', '새 노트 입력에 날짜 머리말을 노출함'
    print('PASS: image rendering paints complete text without exposing editor; new note starts blank')
finally:
    app.root.destroy()
