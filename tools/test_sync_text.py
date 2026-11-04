"""동기화 안내문: 한글 폭·변경된 문장·좁은 창 줄바꿈·복사 가능 상태."""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
from syncui import SelText

root = tk.Tk()
root.geometry('700x400')
try:
    for message in ('무엇을 어느 방향으로 맞출까', '함께 맞출 것', '미디어(그림·첨부)',
                    '끄면 그림은 폰으로 오지 않습니다', '외부 폴더(노트 폴더 밖)',
                    '파일이 아주 많습니다', '지운 노트 보관본', 'Sync notes and attachments'):
        label = SelText(root, text=message, font=('맑은 고딕', 9))
        label.pack(anchor='w')
        root.update()
        assert label.count('1.0', 'end', 'displaylines') == (1,), message
        assert label.cget('state') == 'disabled'
        label.tag_add('sel', '1.0', 'end-1c')
        assert label.get('sel.first', 'sel.last') == message
        label.destroy()
    label = SelText(root, text='짧은 글', font=('맑은 고딕', 9))
    label.pack(anchor='w'); root.update()
    label.config(text='긴 한글 설명문으로 바뀌어도 폭이 제대로 늘어나야 합니다')
    root.update()
    assert label.count('1.0', 'end', 'displaylines') == (1,)
    label.destroy()
    wrapped = SelText(root, text='컴퓨터와 폰의 동기화 규칙이 같아야 동기화됩니다. ' * 3,
                      font=('맑은 고딕', 9), wraplength=440)
    wrapped.pack(anchor='w'); root.update()
    wide = int(wrapped.cget('height'))
    root.geometry('260x400'); root.update()
    assert wrapped.winfo_width() == root.winfo_width()
    assert int(wrapped.cget('height')) > wide
    print('PASS: Korean/English text width, updated text, narrow-window wrapping, selectable read-only text')
finally:
    root.destroy()
