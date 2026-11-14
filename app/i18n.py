"""화면 글자의 언어(한국어·영어). 코드의 한국어 문장이 곧 키이고, 영어일 때만 EN 사전에서 찾아 바꾼다(없으면 한국어 그대로).
tr("새 노트")  → 한국어면 "새 노트", 영어면 "New note".   자리 채우기는 tr("제목 {n}").format(n=2).
언어는 설정(config.json 의 lang)에 저장하고, 처음 실행하면 윈도 표시 언어를 따른다(한국어 윈도 → 한국어, 그 밖 → 영어)."""
import ctypes
import sys

LANGS = {"en": "English", "ko": "한국어"}
_lang = "ko"

EN = {
    '이미 존재하는 태그로만 추가 (부족해도 새 단어로 채우지 않음)': 'Use existing tags only (do not fill remaining slots with new words)',
    '본문이 없으면 제목을 분석합니다. 확장자 태그는 별도로 추가합니다 (txt·md 제외).': 'Use the title when the body is empty. Extension tags are added separately (except txt and md).',
    '문서마다 키워드 최대 3개와 확장자 태그를 추가합니다.\n기존 태그는 유지합니다. 본문이 없으면 제목을 분석합니다. 가져온 파일은 색인된 본문을 사용합니다.': 'Add up to three keywords and an extension tag per document.\nExisting tags are kept. Empty documents use their title; imported files use indexed text.',
    '기존 태그는 유지하고 중복은 추가하지 않습니다. 적용 전에 내용이 바뀐 문서는 건너뜁니다.': 'Keep existing tags and avoid duplicates. Skip documents changed since analysis.',
    '노트 태그 저장 중…': 'Saving note tags…',
    '가져온 문서 태그 저장 중…': 'Saving imported document tags…',
    '가져온 문서': 'Imported documents',
    '태그 목록 갱신': 'Refreshing tags',
    '변경되어 건너뜀 {0}개 · 실패 {1}개': 'Changed and skipped {0} · Failed {1}',
    '(기준일)': '(reference date)',
    "이름순": "Name", "빈도순": "Frequency",
    "이름순 (한글 → 영어)": "Name (Korean → English)",
    "태그 정렬: 빈도순 또는 이름순 (한글·영문 구분)": "Sort tags by frequency or name (Korean and English grouped)",
    '자동 태그 추가…': 'Add automatic tags…',
    '자동 태그 추가': 'Add automatic tags',
    '자동 태그 분석': 'Analyzing automatic tags',
    '자동 태그 미리보기': 'Preview automatic tags',
    '자동 태그 추가 전': 'Before adding automatic tags',
    '문서마다 자주 나온 단어를 최대 3개씩 태그로 추가합니다.\n본문에 나온 기존 태그 이름을 언어 구분 없이 우선합니다. 기존 태그는 유지하며, 가져온 파일은 색인된 본문을 분석합니다.': 'Add up to three frequent words per document as tags.\nExisting tag names in the text have priority in any language. Existing tags are kept; imported files use indexed text.',
    '전체 문서 (가져온 폴더 포함)': 'All documents (including imported folders)',
    '현재 검색 결과 전체': 'All current search results',
    '분석 후 미리보기': 'Analyze and preview',
    '분석 {0}개 · 추가할 문서 {1}개 · 읽기 실패 {2}개': 'Analyzed {0} · Documents to update {1} · Read failures {2}',
    '본문이 없거나 상위 단어가 이미 태그이면 추가하지 않습니다. 적용 전에 내용이 바뀐 문서는 건너뜁니다.': 'No additions when text is unavailable or top words are already tags. Documents changed after analysis are skipped.',
    '문서': 'Document',
    '추가할 태그': 'Tags to add',
    '이전': 'Previous',
    '다음': 'Next',
    '읽기 실패 보기': 'Show read failures',
    '이 태그들 추가': 'Add these tags',
    '추가 완료 {0}개 · 변경되어 건너뜀 {1}개 · 실패 {2}개': 'Updated {0} · Changed and skipped {1} · Failed {2}',
    '「{0}」을(를) 가져온 폴더 목록에서 뺄까요?\n(원본 파일과 태그·메모는 유지합니다. 색인은 3일 뒤 삭제하며, 그 안에 다시 넣으면 재사용합니다)': 'Remove “{0}” from imported folders?\nOriginal files, tags and memos are kept. The index is kept for three days and reused if you add the folder again during that time.)',
    # ---- 메뉴줄
    "파일": "File", "편집": "Edit", "보기": "View", "이동": "Go", "도구": "Tools", "설정": "Settings", "도움말": "Help",
    "새 노트": "New note", "새 노트북": "New notebook", "새 하위 노트북": "New sub-notebook", "폴더 가져오기…": "Import folder…",
    "휴지통": "Trash", "종료": "Exit",
    "실행 취소": "Undo", "다시 실행": "Redo", "실행 취소 (Ctrl+Z)": "Undo (Ctrl+Z)", "다시 실행 (Ctrl+Y)": "Redo (Ctrl+Y)",
    "잘라내기": "Cut", "복사": "Copy", "붙여넣기": "Paste", "모두 선택": "Select all",
    "굵게": "Bold", "기울임꼴": "Italic", "취소선": "Strikethrough", "링크 만들기": "Insert link", "코드": "Code",
    "번호 매기기 목록": "Numbered list", "글머리 기호 목록": "Bulleted list", "인용": "Quote", "제목": "Heading", "제목 {n}": "Heading {n}",
    "본문": "Body text", "가로줄": "Horizontal rule", "표": "Table", "코드 블록": "Code block", "날짜 및 시간 삽입": "Insert date and time",
    "글 정리": "Tidy text", "줄 앞 공백 지우기": "Remove leading spaces", "줄 끝 공백 지우기": "Remove trailing spaces",
    "단어 사이 빈칸 줄이기": "Shrink gaps between words", "여러 빈 줄을 하나로": "Collapse blank lines into one",
    "빈 줄 전부 없애기": "Remove all blank lines", "같은 내용 삭제": "Delete duplicate lines",
    "문단 줄 잇기": "Join lines within paragraphs", "고른 줄 합치기": "Join selected lines into one",
    "줄 가나다순 정렬 (오름차순)": "Sort lines (ascending)", "줄 가나다순 정렬 (내림차순)": "Sort lines (descending)", "대문자로": "UPPERCASE", "소문자로": "lowercase",
    "설명 보기…": "Show descriptions…", "글 정리 설명": "Tidy text help", "하는 일": "What it does", "바꾸기 전": "Before", "바꾼 뒤": "After",
    "고른 글이 있어야 합니다": "Needs selected text",
    "메뉴 「글 정리」 항목별 설명입니다. 편집 칸에서 줄을 골라 두면 그 줄만 고치고, 고른 글이 없으면 노트 전체를 고칩니다. '·' 은 빈칸을 보이게 한 표시입니다.":
        "Descriptions for each Tidy text item. If you select lines in the editor, only those are changed; without a selection, the whole note is changed. '·' marks a space.",
    "고칠 곳이 없습니다": "Nothing to change", " (목록·코드 블록 {0}줄은 그대로)": " ({0} list/code block lines left as is)",
    "먼저 바꿀 글을 고르세요": "Select the text to change first", "바꿨습니다": "Changed",
    "{0}줄을 {1}줄로 바꿨습니다": "Changed {0} lines into {1}", "{0}곳을 고쳤습니다": "Fixed {0} places",
    "찾아 바꾸기": "Find and replace", "바꿀 글": "Replace with", "바꾸기": "Replace", "모두 바꾸기": "Replace all",
    "Enter 바꾸고 다음 · 대소문자 구분 없음": "Enter: replace and next · case-insensitive", "바꿀 곳이 없습니다": "Nothing to replace",
    "{0}곳을 바꿨습니다": "Replaced {0} places", "고른 범위에서 {0}곳을 바꿨습니다": "Replaced {0} places in the selection",
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
    "본문에서 태그 추천": "Suggest tags from note text",
    "모든 파일": "All files", "가져온 폴더": "Imported folders", "저장된 검색": "Saved searches", "🗑 휴지통": "🗑 Trash",
    "검색": "Search", "최근 검색": "Recent searches", "고급 검색": "Advanced search", "검색 적용": "Apply search",
    "조건을 고르고 AND·OR·NOT으로 결합합니다. NOT은 앞 조건에 이어 제외합니다.": "Select conditions and combine them with AND, OR, and NOT. NOT excludes the condition from preceding results.",
    "시작": "From", "끝": "To", "기간을 하나 이상 입력하세요.": "Enter at least one date.",
    "날짜 형식을 확인하세요. 예: 20240131": "Check the date format. Example: 20240131",
    "태그를 선택하세요.": "Select a tag.", "가져온 폴더를 선택하세요.": "Select an imported folder.",
    "확장자를 선택하세요.": "Select an extension.",
    "문서 내부 검색": "Search inside documents", "기간": "Dates", "저장": "Save", "지우기": "Clear", "＋ 새 노트": "＋ New note",
    "태그 없음": "No tags", "전체 범위": "All tags", "현재 범위": "Current scope",
    "태그 목록 범위를 전체와 현재 범위 사이에서 바꿉니다": "Switch between all tags and the current scope",
    "예) 2021.01.01": "e.g. 2021.01.01",
    "관련도순": "Relevance", "수정순": "Modified", "생성순": "Created", "제목순": "Title",
    "누르면 고른 태그가 풀립니다": "Click to clear the selected tag",
    "지금의 검색을 왼쪽 '저장된 검색'에 이름을 붙여 저장합니다(스마트 폴더)": "Save the current search under a name in 'Saved searches' on the left (smart folder)",
    "켜면 가져온 pdf·txt 등의 본문까지 찾고, 끄면 파일 제목만 찾습니다": "On: also search the text inside imported pdf/txt files. Off: search document titles only",
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
    "오픈소스 라이선스…": "Open-source licenses…", "오픈소스 라이선스": "Open-source licenses", "라이선스 파일을 찾을 수 없습니다.": "The license file could not be found.",
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

from lang_en4 import EN_MSG  # noqa: E402   (저장소·업데이트·군더더기 이유 메시지)
EN.update(EN_MSG)

from lang_en5 import EN_MORE  # noqa: E402   (그림·중복 이미지·빈 스크랩 정리 대화창, 메뉴 새 항목, 노트 메뉴)
EN.update(EN_MORE)
