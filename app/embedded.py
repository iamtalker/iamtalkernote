"""도구 > 본문에 글자로 박힌 그림을 리소스 파일로 일괄 분리.
노트를 열 때 한 개씩 묻던 '그림을 리소스 폴더의 파일로 분리할까요?'(noteio.offer_split)를 전체 노트에 한 번에 적용한다.
각 노트는 저장 전 내용이 이전 버전(.history)에 남고, 수정 시각(updated)은 바꾸지 않는다."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)
import store as st  # noqa: E402


def scan_embedded(notes, progress=None, cancelled=lambda: False):
    """노트 목록 → [(노트, 그림 개수, 글자 수)] 글자 수가 큰 것부터. base64 그림이 없는 노트는 뺀다."""
    found = []
    total = len(notes)
    for i, n in enumerate(notes):
        if cancelled():
            return []
        if progress and i % 200 == 0:
            progress(i, total)
        try:
            with open(n["path"], "rb") as fh:
                text = st.decode(fh.read())
        except OSError:
            continue
        if "base64," not in text:
            continue
        count, size = st.embedded_images(text)
        if count:
            found.append((n, count, size))
    found.sort(key=lambda x: -x[2])
    return found


def convert_embedded(store, found, progress=None, cancelled=lambda: False):
    """scan_embedded 결과를 실제로 분리한다 → (바뀐 노트 수, 옮긴 그림 수, 실패 [(경로, 이유)])."""
    changed = moved_total = 0
    failed = []
    for i, (n, _count, _size) in enumerate(found):
        if cancelled():
            break
        if progress:
            progress(i, len(found))
        try:
            with open(n["path"], "rb") as fh:
                text = st.decode(fh.read())
            new, moved = store.extract_images(text, n["nb"])
            if moved and new != text:
                store.save(n["path"], new, versioned=True, force=True, touch=False, ev="image")
                changed += 1
                moved_total += moved
        except Exception as e:  # 한 노트가 실패해도 나머지는 계속한다
            failed.append((n["path"], str(e)))
    return changed, moved_total, failed


class EmbeddedMixin:
    # ------------------------------------------------------------ 도구: 글자로 박힌 그림 일괄 분리
    def show_embedded_images(self):
        """도구 > 본문의 긴 글자 그림을 리소스 파일로 일괄 분리: 먼저 찾고, 개수를 보여 준 뒤 확인을 받고 바꾼다"""
        self.scan_notes(tr("글자로 박힌 그림 찾기"), lambda notes, prog, cancel: scan_embedded(notes, prog, cancel), self.embedded_dialog)

    def embedded_dialog(self, found):
        if not found:
            return messagebox.showinfo(APP, tr("본문에 글자로 박힌 그림이 있는 노트가 없습니다."), parent=self.root)
        total_chars = sum(s for _, _, s in found)
        total_imgs = sum(c for _, c, _ in found)
        msg = tr("그림 {0}개가 글자로 박힌 노트가 {1}개 있습니다 (글자 {2:.1f}MB).\n\n그림을 리소스 폴더의 파일로 옮기고 노트를 고칩니다.\n바뀌기 전 내용은 노트 버전(.history)에 남고, 수정 시각은 그대로 둡니다.\n\n지금 바꿀까요?").format(
            total_imgs, len(found), total_chars / 1048576)
        if not messagebox.askyesno(APP, msg, parent=self.root):
            return
        self.flush()
        self.run_task(tr("그림 분리 중"), lambda prog, cancel: convert_embedded(self.store, found, prog, cancel), self.embedded_done)

    def embedded_done(self, result):
        changed, moved, failed = result
        text = tr("노트 {0}개의 그림 {1}개를 리소스 폴더로 옮겼습니다.").format(changed, moved)
        if failed:
            text += "\n\n" + tr("실패 {0}개:").format(len(failed)) + "\n" + "\n".join(f"{p}: {e}" for p, e in failed[:10])
        messagebox.showinfo(APP, text, parent=self.root)
        self.reload_notes(keep_scroll=True)
