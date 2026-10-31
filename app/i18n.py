"""화면 글자의 언어(한국어·영어). 코드의 한국어 문장이 곧 키이고, 영어일 때만 EN 사전에서 찾아 바꾼다(없으면 한국어 그대로).
tr("새 노트")  → 한국어면 "새 노트", 영어면 "New note".   자리 채우기는 tr("제목 {n}").format(n=2).
언어는 설정(config.json 의 lang)에 저장하고, 처음 실행하면 윈도 표시 언어를 따른다(한국어 윈도 → 한국어, 그 밖 → 영어)."""
import ctypes
import sys

LANGS = {"en": "English", "ko": "한국어"}
_lang = "ko"

EN = {
    # ---- 메뉴줄
    "파일": "File", "편집": "Edit", "보기": "View", "이동": "Go", "도구": "Tools", "설정": "Settings", "도움말": "Help",
    "새 노트": "New note", "새 노트북": "New notebook", "새 하위 노트북": "New sub-notebook", "폴더 가져오기…": "Import folder…",
    "휴지통": "Trash", "종료": "Exit",
    "실행 취소": "Undo", "다시 실행": "Redo", "잘라내기": "Cut", "복사": "Copy", "붙여넣기": "Paste", "모두 선택": "Select all",
    "굵게": "Bold", "기울임꼴": "Italic", "취소선": "Strikethrough", "링크 만들기": "Insert link", "코드": "Code",
    "번호 매기기 목록": "Numbered list", "글머리 기호 목록": "Bulleted list", "인용": "Quote", "제목": "Heading", "제목 {n}": "Heading {n}",
    "본문": "Body text", "가로줄": "Horizontal rule", "표": "Table", "코드 블록": "Code block", "날짜 및 시간 삽입": "Insert date and time",
    "문서에서 찾기": "Find in note", "모든 파일에서 검색": "Search all files", "노트 속성…": "Note properties…", "노트 버전…": "Note versions…",
    "비슷한 노트 찾기…": "Find similar notes…",
    "노트북 보기": "Show notebooks", "태그 보기": "Show tags", "노트 목록 보기": "Show note list", "문법 해설 보기": "Show syntax guide",
    "마크다운만": "Markdown only", "마크다운 + 렌더링": "Markdown + preview", "렌더링만": "Preview only", "편집기 레이아웃 전환": "Cycle editor layout",
    "뒤로": "Back", "앞으로": "Forward",
    "복원 지점…": "Restore points…", "전체 변경 이력…": "Full change history…", "중복 노트 찾기…": "Find duplicate notes…",
    "스크랩 군더더기 정리…": "Clean up clipped clutter…", "안 쓰는 미디어 파일 정리…": "Clean up unused media…",
    "옵션…": "Options…", "폴더 설정… (노트·리소스 폴더)": "Folder settings… (notes · resources)", "글꼴·크기…": "Font and size…",
    "테마·색상…": "Theme and colors…", "노트 버전 설정…": "Note version settings…", "동기화 설정…": "Sync settings…", "웹 클리퍼 설정…": "Web clipper settings…",
    "사용 설명서 (GitHub)…": "User manual (GitHub)…", "검색 문법": "Search syntax", "안드로이드 앱 내려받기 (APK)…": "Download Android app (APK)…",
    "업데이트 확인…": "Check for updates…", "{app} 정보 (버전 {v})": "About {app} (version {v})",
    "위키나루 기반 마크다운 노트 앱\n노트는 .md 파일로 저장됩니다.\n\n저장 폴더: ": "A Markdown note app based on Wikinaru\nNotes are saved as .md files.\n\nNotes folder: ",
    # ---- 노트북·목록 화면
    "노트북": "Notebooks", "태그": "Tags", "바로가기": "Shortcuts", "즐겨찾기": "Favorites", "아웃라이너": "Outliner", "달력·할일": "Calendar · To-do",
    "모든 파일": "All files", "가져온 폴더": "Imported folders", "저장된 검색": "Saved searches", "🗑 휴지통": "🗑 Trash",
    "검색": "Search", "문서 안 글 포함": "Include document text", "기간": "Dates", "저장": "Save", "지우기": "Clear", "＋ 새 노트": "＋ New note",
    "예) 2021.01.01": "e.g. 2021.01.01",
    "관련도순": "Relevance", "수정순": "Modified", "생성순": "Created", "제목순": "Title",
    "누르면 고른 태그가 풀립니다": "Click to clear the selected tag",
    "지금의 검색을 왼쪽 '저장된 검색'에 이름을 붙여 저장합니다(스마트 폴더)": "Save the current search under a name in 'Saved searches' on the left (smart folder)",
    "켜면 가져온 pdf·txt 등의 본문까지 찾고, 끄면 파일 이름·경로·태그·메모만 찾습니다": "On: also search the text inside imported pdf/txt files. Off: file names, paths, tags and memos only",
    "마지막으로 고친 시각 순 (조플린 내보내기 노트는 머리말의 updated)": "Sort by last modified time (Joplin exports use 'updated' in the front matter)",
    "만든 시각 순 (조플린 내보내기 노트는 머리말의 created)": "Sort by creation time (Joplin exports use 'created' in the front matter)",
    # ---- 편집 화면
    "문법": "Syntax", "문법 해설": "Syntax guide", "마크다운": "Markdown", "렌더링": "Preview", "읽기 전용": "Read-only",
    "좌우 분할": "Side by side", "원문만": "Source only", "마크다운과 렌더링을 나란히": "Markdown and preview side by side",
    "렌더링 결과만 크게": "Large preview only", "마크다운 원문만 크게(집중 편집)": "Large Markdown source only (focus mode)",
    "문법 해설 사이드바 보이기/숨기기 (Ctrl+/)": "Show/hide the syntax guide (Ctrl+/)", "문법 해설 닫기 (Ctrl+/)": "Close the syntax guide (Ctrl+/)",
    "노트 속성": "Note properties", "노트를 선택하거나 새로 만드세요\nCtrl+N": "Select a note or create a new one\nCtrl+N",
    "Enter 다음 · Shift+Enter 이전 · Esc 닫기": "Enter next · Shift+Enter previous · Esc close",
    "누르면 커서 자리에 넣고, 글을 고르고 누르면 감쌉니다.\nCtrl+B 굵게 · Ctrl+I 기울임 · Ctrl+K 링크": "Click to insert at the cursor, or select text and click to wrap it.\nCtrl+B bold · Ctrl+I italic · Ctrl+K link",
    # ---- 우클릭 메뉴
    "노트북으로 이동": "Move to notebook", "즐겨찾기 해제": "Remove from favorites", "즐겨찾기 추가": "Add to favorites", "연결된 노트 보기…": "Show linked notes…",
    "태그 추가…": "Add tags…", "노트 링크 복사": "Copy note link", "파일 위치 열기": "Show in folder", "삭제": "Delete", "열기": "Open",
    "노트 {n}개를 노트북으로 이동": "Move {n} notes to notebook", "노트 {n}개에 태그 추가…": "Add tags to {n} notes…", "노트 {n}개 휴지통으로": "Move {n} notes to trash",
    "선택 해제": "Clear selection", "그림 삭제": "Delete image", "복원": "Restore", "완전히 삭제": "Delete permanently", "휴지통 비우기": "Empty trash",
    "기본 프로그램으로 열기": "Open with default app", "태그 추가·고치기…": "Edit tags…", "메모…": "Memo…", "메모": "Memo", "경로 복사": "Copy path",
    "노트 버전…": "Note versions…", "새 노트북 만들기": "New notebook", "하위 노트북 만들기": "New sub-notebook", "노트북 삭제(휴지통)": "Delete notebook (to trash)",
    "저장 폴더 전체 삭제(휴지통)": "Delete the whole notes folder (to trash)", "지금의 검색 저장…": "Save current search…", "다시 읽기": "Rescan",
    "모두 다시 읽기": "Rescan all", "목록에서 빼기 (원본 파일은 그대로)": "Remove from list (original files stay)", "가져오기 설정…": "Import settings…",
    "이름 바꾸기…": "Rename…", "지금의 검색으로 덮어쓰기": "Overwrite with current search",
    "태그 이름 변경": "Rename tag", "태그 삭제": "Delete tag",
    "제목": "Headings", "글자": "Text", "목록·인용": "Lists · Quotes", "넣기": "Insert", "확장": "Extras",
    "기울임": "Italic", "위 첨자": "Superscript", "아래 첨자": "Subscript", "글머리 목록": "Bullet list", "번호 목록": "Numbered list", "체크 목록": "Checklist",
    "들여쓰기": "Indent", "내어쓰기": "Outdent", "링크": "Link", "노트 링크": "Note link", "자동 링크": "Auto link", "그림": "Image", "유튜브 영상": "YouTube video",
    "언어 지정 코드": "Code with language", "수식 (줄 안)": "Math (inline)", "수식 (블록)": "Math (block)", "접기": "Collapsible", "목차": "Table of contents",
    "각주": "Footnote", "날짜·시간": "Date · time",
    "라이트 보라": "Light purple", "라이트 파랑": "Light blue", "라이트 초록": "Light green", "다크 검정": "Dark black", "다크 회색": "Dark gray", "내 테마": "My theme",
}


def _detect():
    """윈도 표시 언어가 한국어면 ko, 아니면 en"""
    try:
        if sys.platform == "win32":
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "ko" if (lid & 0x3FF) == 0x12 else "en"
    except Exception:
        pass
    return "ko"


def init(saved):
    """저장된 언어(없으면 윈도 언어)로 시작한다"""
    global _lang
    _lang = saved if saved in LANGS else _detect()
    return _lang


def lang():
    return _lang


def set_lang(code):
    global _lang
    if code in LANGS:
        _lang = code


def weekdays():
    """일요일부터 시작하는 요일 머리글(달력)"""
    return ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] if _lang == "en" else list("일월화수목금토")


_EXAMPLE = {"하위 항목": "sub-item", "한 단계 올림": "outdent", "할 일": "task", "노트 제목": "Note title", "유튜브에서 보기": "Watch on YouTube",
            "그림.png": "image.png", "제목1": "Head1", "제목2": "Head2", "제목": "Title", "항목": "item", "주소": "url", "내용": "text", "태그": "tag", "글": "text"}


def example(s):
    """문법 해설에 보이는 예시 글(영어일 때만 한글 낱말을 바꿔 보인다. 노트에 들어가는 글은 아님)"""
    if _lang != "en":
        return s
    for k in sorted(_EXAMPLE, key=len, reverse=True):
        s = s.replace(k, _EXAMPLE[k])
    return s


def group(g):
    """문법 해설의 묶음 이름(다른 곳의 '제목' 과 뜻이 달라 따로 처리)"""
    return "Headings" if (_lang == "en" and g == "제목") else tr(g)


def unit(word):
    """'N개의 파일' 처럼 개수 뒤에 붙는 말: 영어는 복수형"""
    return {"파일": "files", "노트": "notes"}.get(word, word) if _lang == "en" else word


def tr(s):
    return EN.get(s, s) if _lang == "en" else s


from lang_en1 import EN_DIALOGS  # noqa: E402   (옵션 창·대화창·동기화 탭 번역)
EN.update(EN_DIALOGS)

from lang_en2 import EN_DIALOGS_F  # noqa: E402   (값이 들어가는 문장: tr("…{0}…").format(…))
EN.update(EN_DIALOGS_F)

from lang_en3 import EN_MAIN  # noqa: E402   (메인 화면·메시지·달력·태그 번역)
EN.update(EN_MAIN)
