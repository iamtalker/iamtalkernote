"""노트북과 태그 목록의 동작. notes.py 의 App 이 이 믹스인을 상속한다.
notes.py 에서 옮겨 왔다(동작 변경 없음)."""
from notes_shared import *  # noqa: E402,F401,F403   (공용 이름: notes_shared.py)


class NotebooksMixin:
    # ------------------------------------------------------------ 노트북·태그
    def nb_label(self, key):
        """노트북 경로 → 보여 줄 이름 (하위 노트북은 '업무 › 프로젝트')"""
        if key == QUICK:
            return tr("바로가기")
        if key == TRASH:
            return tr("휴지통")
        if key == CAL:
            return tr("달력·할일")
        if key == FAVS:
            return tr("즐겨찾기")
        if key == "@docs":
            return tr("가져온 폴더")
        if key.startswith("@smart"):
            s = next((x for x in self.smart_list() if "@smart:" + x["id"] == key), None)
            return s["name"] if s else tr("저장된 검색")
        if key.startswith("@doc:"):
            fid, rel = self.doc_key_parts(key)
            if rel:
                return rel.rsplit("/", 1)[-1]
            f = next((f for f in self.docs.folders() if f["id"] == fid), None)
            return f.get("name") or f["path"] if f else tr("가져온 폴더")
        if not key or key == ALL:
            return self.store.root_name if key == "" else tr("모든 파일")
        return " › ".join(wikiconv.markdown.md_title(p + ".md") for p in key.split("/"))

    def nb_short(self, key):
        return wikiconv.markdown.md_title(key.split("/")[-1] + ".md")

    def scope_all(self):
        """'모든 파일'이나 저장된 검색을 보는 중인가(내 노트 + 가져온 파일 전체가 범위)"""
        return self.nb == ALL or self.nb.startswith("@smart:")

    def md_nb(self):
        """새 노트·하위 노트북을 만들 노트북: 노트북이 아닌 항목(모든 파일·가져온 폴더·저장된 검색)을 보고 있으면 저장 폴더 바로 아래"""
        return "" if self.nb == ALL or self.nb.startswith("@") else self.nb
