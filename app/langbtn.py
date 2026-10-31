"""창 오른쪽 위 모서리의 언어 단추: 현재 언어의 깃발 + 코드(EN / KO) + ▾ . 누르면 아래로 언어 목록이 펼쳐진다.
윈도는 국기 이모지를 글자(US)로 보여 주므로 깃발은 PhotoImage 로 직접 그린다."""
import tkinter as tk

import i18n

W, H = 20, 13
_cache = {}


def _flag(code):
    img = tk.PhotoImage(width=W, height=H)
    if code == "en":   # 미국: 빨강·흰 줄 13개 + 파란 바탕에 별(점) 무늬
        for y in range(H):
            img.put("#b22234" if y % 2 == 0 else "#ffffff", to=(0, y, W, y + 1))
        img.put("#3c3b6e", to=(0, 0, 9, 7))
        for y in range(1, 7, 2):
            for x in range(1, 9, 2):
                img.put("#ffffff", to=(x, y, x + 1, y + 1))
    else:              # 한국: 흰 바탕, 가운데 태극(위 빨강·아래 파랑), 네 모서리의 괘
        img.put("#ffffff", to=(0, 0, W, H))
        cx, cy, r = 10, 6.5, 3.6
        for y in range(H):
            for x in range(W):
                if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                    img.put("#cd2e3a" if y + 0.5 < cy else "#0047a0", to=(x, y, x + 1, y + 1))
        for x0, y0 in ((1, 1), (15, 1), (1, 9), (15, 9)):
            img.put("#000000", to=(x0, y0, x0 + 4, y0 + 1))
            img.put("#000000", to=(x0, y0 + 2, x0 + 4, y0 + 3))
    return img


def flag(code):
    if code not in _cache:
        _cache[code] = _flag(code)
    return _cache[code]


class LangButton(tk.Label):
    """parent 의 오른쪽 위에 겹쳐 놓는다. on_pick(code) 가 언어를 바꾼다."""

    def __init__(self, parent, on_pick, colors, font):
        super().__init__(parent, image=flag(i18n.lang()), text=" " + i18n.lang().upper() + " ▾", compound="left", cursor="hand2",
                         bg=colors["bg"], fg=colors["muted"], font=font, padx=4, pady=1, bd=0)
        self.on_pick, self.colors, self.font = on_pick, colors, font
        self.bind("<Button-1>", self.pop)
        self.bind("<Enter>", lambda e: self.config(bg=colors["hover"]))
        self.bind("<Leave>", lambda e: self.config(bg=colors["bg"]))
        self.place(relx=1.0, x=-4, y=1, anchor="ne")
        self.lift()

    def pop(self, e=None):
        m = tk.Menu(self, tearoff=0, font=self.font)
        for code, name in i18n.LANGS.items():
            m.add_command(label="  " + name + ("   ✓" if code == i18n.lang() else ""), image=flag(code), compound="left",
                          command=lambda c=code: self.on_pick(c))
        m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
