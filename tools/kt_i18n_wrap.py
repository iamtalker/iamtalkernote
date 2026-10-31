"""코틀린 파일의 한글 문자열 리터럴(값 끼움 $ 없는 것)을 tr("…") 로 감싸고, 감싼 키 목록을 json 으로 저장.
데이터로 쓰이는 줄(정규식·폴더/파일 이름·저널·비교)은 건너뛴다."""
import io, json, os, re, sys

D = r"C:\MyData\claude program\1. 개발중\iamtalkernote-android\app\src\main\java\kr\iamtalker\notes" + "\\"
SKIP_FILES = {"AppThemes.kt", "Holidays.kt", "HashTags.kt", "Meta.kt", "NoteText.kt", "Markdown.kt", "HelpText.kt", "Lang.kt", "I18nEn.kt", "EmbeddedSync.kt", "CrashLog.kt"}
SKIP_SUB = ["Regex(", '"아웃라이너"', "제목 없음", "태그: ", "journal(", "detail =", "Log.", "log(", "substringAfter", "startsWith(", "endsWith(", "const val",
            "note(ctx", "putDevice", "SimpleDateFormat(", "(충돌 ", "(복원", "\"달력\"", '"ScrapBook"', "getString(", "putString(", "edit()", "Locale."]
EQ = re.compile(r'(==|!=)\s*"[^"]*[가-힣]')
LIT = re.compile(r'"((?:[^"\\\n$]|\\.)*[가-힣](?:[^"\\\n$]|\\.)*)"')
keys = {}
for f in sorted(os.listdir(D)):
    if not f.endswith(".kt") or f in SKIP_FILES:
        continue
    src = io.open(D + f, encoding="utf-8", newline="").read()
    lines = src.split("\n")
    out = []
    in_block = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("/*"):
            in_block = "*/" not in s
        elif in_block:
            if "*/" in s:
                in_block = False
        elif s.startswith("//") or s.startswith("*") or '"""' in ln or any(x in ln for x in SKIP_SUB) or EQ.search(ln):
            pass
        elif LIT.search(ln):
            def rep(m):
                pre = ln[:m.start()]
                if pre.rstrip().endswith("tr("):
                    return m.group(0)
                keys[m.group(1)] = f
                return 'tr("' + m.group(1) + '")'
            ln = LIT.sub(rep, ln)
        out.append(ln)
    io.open(D + f, "w", encoding="utf-8", newline="").write("\n".join(out))
io.open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(keys, ensure_ascii=False, indent=0))
print(len(keys), "keys")
